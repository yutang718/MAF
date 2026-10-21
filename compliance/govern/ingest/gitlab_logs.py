"""Turn GitLab's own JSON logs into download events.

GitLab Premium's audit events don't record clones or archive downloads; the
Rails and gitlab-shell logs do. Ship these files from the GitLab host
(Fluent Bit, Vector, Filebeat) as JSON lines:

  /var/log/gitlab/gitlab-rails/production_json.log   git over HTTPS, web archive and export downloads
  /var/log/gitlab/gitlab-rails/api_json.log          archive and export downloads through the API
  /var/log/gitlab/gitlab-shell/gitlab-shell.log      git over SSH

Lines that aren't a download are ignored, so shipping whole files is fine.
"""
import hashlib
import json
from typing import Any

from govern.connectors.base import EventRecord
from govern.timeutil import parse_time

KIND = "gitlab.git"


def parse(raw: Any) -> EventRecord | None:
    entry = _unwrap(raw)
    if not isinstance(entry, dict):
        return None
    action, project = _classify(entry)
    actor = entry.get("username") or entry.get("meta.user") or ""
    if not action or not actor:
        return None
    when = parse_time(entry.get("time"))
    if when is None:
        return None
    digest = hashlib.sha1(json.dumps(entry, sort_keys=True, default=str).encode()).hexdigest()
    return EventRecord(
        kind=KIND, external_id=f"log:{digest}", occurred_at=when, actor=str(actor)[:200], action=action,
        target=(project or "")[:300],
        data={"ip": entry.get("remote_ip"), "ua": (entry.get("ua") or "")[:200], "status": entry.get("status"),
              "source": _source(entry), "protocol": entry.get("git_protocol")})


def _unwrap(raw: Any) -> Any:
    """Shippers often wrap the original line, e.g. {"log": "<json>"} or {"message": "<json>"}."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    if isinstance(raw, dict):
        for key in ("log", "message"):
            inner = raw.get(key)
            if isinstance(inner, str) and inner.lstrip().startswith("{"):
                return _unwrap(inner)
    return raw


def _ok(entry: dict) -> bool:
    status = entry.get("status")
    return status is None or (isinstance(status, int) and 200 <= status < 300)


def _project_from_git_path(path: str) -> str | None:
    marker = ".git/"
    if marker in path:
        return path.split(marker)[0].lstrip("/")
    return None


def _classify(e: dict) -> tuple[str | None, str | None]:
    if not _ok(e):
        return None, None
    project = e.get("meta.project") or e.get("gl_project_path")
    controller, action = e.get("controller"), e.get("action")
    if controller == "Repositories::GitHttpController" and action == "git_upload_pack":
        return "git.pull", project or _project_from_git_path(e.get("path") or "")
    if controller == "Projects::RepositoryController" and action == "archive":
        return "archive.download", project
    if controller == "ProjectsController" and action == "download_export":
        return "export.download", project
    route = e.get("route") or ""
    if route.endswith("/repository/archive") or route.endswith("/repository/archive.:format"):
        return "archive.download", project
    if route.endswith("/export/download"):
        return "export.download", project
    if e.get("command") == "git-upload-pack" and (e.get("msg") or "").startswith("executing git command"):
        return "git.pull", project
    return None, None


def _source(e: dict) -> str:
    if "controller" in e:
        return "rails"
    if "route" in e:
        return "api"
    return "shell" if "command" in e else "unknown"
