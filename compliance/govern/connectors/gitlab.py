"""GitLab group (gitlab.com or self-managed): members, project settings, tokens and audit events.

Read-only, with a token that has the read_api scope from a group Owner. Audit
events need GitLab Premium or Ultimate; per-user 2FA status needs an instance
administrator, so on gitlab.com only the group's 2FA policy is checked.
"""
import time
from datetime import timedelta
from urllib.parse import quote

import httpx

from govern.connectors.base import Collected, ConfigField, Connector, EventRecord, SourceUnavailable
from govern.connectors.http import ApiClient, paginate_link
from govern.timeutil import iso, parse_time, utcnow

AUDIT_LOOKBACK_DAYS = 7
OWNER, MAINTAINER, DEVELOPER = 50, 40, 30


class GitLabConnector(Connector):
    kind = "gitlab"
    title = {"en": "GitLab", "zh": "GitLab"}
    fields = (
        ConfigField("group", {"en": "Group path or ID", "zh": "群组路径或 ID"}, required=True),
        ConfigField("token", {"en": "Access token", "zh": "访问令牌"}, type="secret", required=True),
        ConfigField("base_url", {"en": "GitLab URL", "zh": "GitLab 地址"}, default="https://gitlab.com"),
        ConfigField("max_projects", {"en": "Max projects inspected", "zh": "最多检查的项目数"}, type="int", default=500),
        ConfigField("instance_admin", {"en": "Token belongs to an instance admin", "zh": "令牌属于实例管理员"},
                    type="bool", default=False,
                    help={"en": "Self-managed only: enables per-user 2FA status and instance audit events",
                          "zh": "仅自建实例：可获取每个用户的 2FA 状态和实例级审计事件"}),
        ConfigField("public_project_allowlist", {"en": "Projects allowed to be public", "zh": "允许公开的项目"},
                    type="list", default=[]),
    )
    permissions_help = {
        "en": "Personal, group or service-account token with the read_api scope, from a group Owner.",
        "zh": "具有 read_api 权限的个人、群组或服务账号令牌，需来自群组所有者。",
    }

    def __init__(self, config, secrets, cursor=None, *, transport: httpx.BaseTransport | None = None,
                 sleep=time.sleep):
        super().__init__(config, secrets, cursor)
        token = secrets.get("token", "")
        base = (self.config["base_url"] or "https://gitlab.com").rstrip("/")
        self.api = ApiClient(f"{base}/api/v4", lambda: {"PRIVATE-TOKEN": token}, transport=transport, sleep=sleep)
        self.group = quote(str(self.config["group"]), safe="")

    def close(self) -> None:
        self.api.close()

    def test(self) -> str:
        g = self.api.get_json(f"/groups/{self.group}", params={"with_projects": "false"})
        return f"Connected to group {g.get('full_path')}"

    def _list(self, path: str, params: dict | None = None, limit: int | None = None) -> list[dict]:
        return list(paginate_link(self.api, path, {"per_page": 100, **(params or {})}, limit))

    def collect(self) -> Collected:
        c = Collected(cursor=dict(self.cursor))
        g = self.group
        c.gather("gitlab.group", lambda: _group(self.api.get_json(f"/groups/{g}", params={"with_projects": "false"})))
        members = c.gather("gitlab.members", lambda: [
            {"username": m.get("username"), "name": m.get("name"), "access_level": m.get("access_level"),
             "expires_at": m.get("expires_at"), "state": m.get("state")}
            for m in self._list(f"/groups/{g}/members/all")])
        if self.config["instance_admin"] and members is not None:
            names = {m["username"] for m in members}
            c.gather("gitlab.members_2fa_disabled", lambda: [
                u["username"] for u in self._list("/users", {"two_factor": "disabled", "active": "true"})
                if u.get("username") in names])
        else:
            c.unavailable["gitlab.members_2fa_disabled"] = "Per-user 2FA status needs an instance administrator token"
        projects = c.gather("gitlab.projects", lambda: [
            {"id": p["id"], "path": p.get("path_with_namespace"), "visibility": p.get("visibility"),
             "default_branch": p.get("default_branch"), "last_activity_at": p.get("last_activity_at")}
            for p in self._list(f"/groups/{g}/projects", {"include_subgroups": "true", "archived": "false"},
                                limit=self.config["max_projects"])])
        if projects is not None:
            c.gather("gitlab.branch_protection", lambda: [self._protection(p) for p in projects])
            c.gather("gitlab.deploy_keys", lambda: self._deploy_keys(projects))
        c.gather("gitlab.group_tokens", lambda: [
            {"name": t.get("name"), "scopes": t.get("scopes"), "expires_at": t.get("expires_at"),
             "active": t.get("active"), "last_used_at": t.get("last_used_at"), "access_level": t.get("access_level")}
            for t in self._list(f"/groups/{g}/access_tokens") if t.get("active", True) and not t.get("revoked")])
        self._audit_events(c)
        return c

    def _protection(self, project: dict) -> dict:
        out = {"repo": project["path"], "visibility": project["visibility"], "requires_pr": False,
               "approvals": 0, "blocks_force_push": False, "blocks_deletion": False}
        branch = project.get("default_branch")
        if not branch:
            return out  # empty repository
        try:
            pb = self.api.get_json(f"/projects/{project['id']}/protected_branches/{quote(branch, safe='')}")
        except SourceUnavailable:
            return out
        # Protected branches can't be deleted through the UI or API, and refuse force pushes unless allowed.
        out["blocks_deletion"] = True
        out["blocks_force_push"] = not pb.get("allow_force_push", False)
        push_levels = [lvl.get("access_level") for lvl in pb.get("push_access_levels", [])]
        # "No one" may push (level 0) means every change goes through a merge request.
        out["requires_pr"] = bool(push_levels) and all(lvl == 0 for lvl in push_levels)
        try:
            rules = self._list(f"/projects/{project['id']}/approval_rules")
            out["approvals"] = max((r.get("approvals_required", 0) for r in rules), default=0)
        except SourceUnavailable:
            pass  # approval rules are a Premium feature
        return out

    def _deploy_keys(self, projects: list[dict]) -> list[dict]:
        keys = []
        for p in projects:
            try:
                for k in self._list(f"/projects/{p['id']}/deploy_keys"):
                    keys.append({"repo": p["path"], "title": k.get("title"), "read_only": not k.get("can_push"),
                                 "created_at": k.get("created_at"), "expires_at": k.get("expires_at")})
            except SourceUnavailable:
                continue
        return keys

    def _audit_events(self, c: Collected) -> None:
        since = parse_time(self.cursor.get("audit_since")) or (utcnow() - timedelta(days=AUDIT_LOOKBACK_DAYS))
        path = "/audit_events" if self.config["instance_admin"] else f"/groups/{self.group}/audit_events"
        latest, count = since, 0
        try:
            for e in paginate_link(self.api, path, {"created_after": iso(since), "per_page": 100}):
                when = parse_time(e.get("created_at")) or utcnow()
                latest = max(latest, when)
                count += 1
                details = e.get("details") or {}
                c.events.append(EventRecord(
                    kind="gitlab.audit", external_id=str(e.get("id")), occurred_at=when,
                    actor=details.get("author_name") or str(e.get("author_id") or ""),
                    action=e.get("event_name") or details.get("event_name") or details.get("custom_message")
                    or _change_action(details),
                    target=details.get("entity_path") or details.get("target_details") or "",
                    data={"entity_type": e.get("entity_type"), **{k: details.get(k) for k in (
                        "change", "from", "to", "custom_message", "target_type", "target_details",
                        "ip_address", "entity_path", "add", "remove", "as") if k in details}}))
        except SourceUnavailable as err:
            c.unavailable["audit.events"] = f"audit events not available (needs Premium/Ultimate): {err}"
            return
        except Exception as err:
            c.errors["audit.events"] = f"{type(err).__name__}: {err}"
            return
        c.cursor["audit_since"] = iso(latest)
        c.facts["audit.events"] = {"count": count, "since": iso(since), "latest": iso(latest)}


def _change_action(details: dict) -> str:
    if "change" in details:
        return f"change:{details['change']}"
    for verb in ("add", "remove"):
        if verb in details:
            return f"{verb}:{details[verb]}"
    return ""


def _group(g: dict) -> dict:
    keys = ("full_path", "visibility", "require_two_factor_authentication", "two_factor_grace_period",
            "project_creation_level", "subgroup_creation_level", "prevent_forking_outside_group",
            "membership_lock", "share_with_group_lock", "default_branch_protection")
    return {k: g.get(k) for k in keys}
