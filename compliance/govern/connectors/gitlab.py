"""Self-managed GitLab instance, read with an administrator token.

Reads instance settings, every user with their SSO identities, personal access
tokens, SSH keys, group and project memberships, push mirrors, CI/CD variable
*names* (never values), branch protection, deploy keys and audit events.
Everything is read-only. If the instance has Admin Mode on, the token needs the
`admin_mode` scope as well as `read_api`.

Git clone and archive downloads aren't in GitLab Premium's audit events; they
arrive through log ingestion instead (see govern/api/ingest.py).
"""
import base64
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import quote, urlparse

import httpx

from govern.connectors.base import Collected, ConfigField, Connector, EventRecord, SourceUnavailable
from govern.connectors.http import ApiClient, paginate_link, raise_for_source
from govern.timeutil import iso, parse_time, utcnow

AUDIT_LOOKBACK_DAYS = 7
OWNER, MAINTAINER, DEVELOPER = 50, 40, 30
PARALLEL = 8
UPSTREAM_TAGS = "https://gitlab.com/api/v4/projects/gitlab-org%2Fgitlab/repository/tags"

SETTINGS_KEYS = (
    "signup_enabled", "require_admin_approval_after_user_signup", "domain_allowlist", "email_restrictions_enabled",
    "password_authentication_enabled_for_web", "password_authentication_enabled_for_git",
    "require_two_factor_authentication", "two_factor_grace_period", "max_personal_access_token_lifetime",
    "deactivate_dormant_users", "deactivate_dormant_users_period", "default_project_visibility",
    "restricted_visibility_levels", "admin_mode", "user_default_external", "mirror_available",
)


class GitLabConnector(Connector):
    kind = "gitlab"
    title = {"en": "GitLab (self-managed)", "zh": "GitLab（自建）"}
    fields = (
        ConfigField("base_url", {"en": "GitLab URL", "zh": "GitLab 地址"}, required=True,
                    help={"en": "e.g. https://gitlab.example.internal", "zh": "例如 https://gitlab.example.internal"}),
        ConfigField("token", {"en": "Administrator access token", "zh": "管理员访问令牌"}, type="secret", required=True,
                    help={"en": "Scopes: read_api, plus admin_mode if Admin Mode is on. Use a dedicated admin account.",
                          "zh": "权限：read_api；如开启了 Admin Mode 还需 admin_mode。建议使用专用管理员账号。"}),
        ConfigField("verify_tls", {"en": "Verify TLS certificate", "zh": "校验 TLS 证书"}, type="bool", default=True,
                    help={"en": "Turn off only for an internal CA not trusted by this container.",
                          "zh": "仅在容器不信任内部 CA 时关闭。"}),
        ConfigField("company_domains", {"en": "Company email domains", "zh": "公司邮箱域名"}, type="list", default=[],
                    help={"en": "Empty: use the verified domains of the connected Microsoft 365 tenant.",
                          "zh": "留空则使用已接入的 Microsoft 365 租户的已验证域名。"}),
        ConfigField("service_accounts", {"en": "Service accounts (usernames)", "zh": "服务账号（用户名）"}, type="list",
                    default=[], help={"en": "Excluded from leaver and dormancy checks; still checked for tokens.",
                                      "zh": "不参与离职和闲置检查，但仍检查其令牌。"}),
        ConfigField("allowed_mirror_hosts", {"en": "Allowed push-mirror hosts", "zh": "允许的推送镜像主机"}, type="list",
                    default=[]),
        ConfigField("public_project_allowlist", {"en": "Projects allowed to be public or internal",
                                                 "zh": "允许公开或内部可见的项目"}, type="list", default=[]),
        ConfigField("max_projects", {"en": "Max projects inspected", "zh": "最多检查的项目数"}, type="int", default=3000),
        ConfigField("check_upstream_version", {"en": "Compare version with gitlab.com releases",
                                               "zh": "与 gitlab.com 发布版本比对"}, type="bool", default=True,
                    help={"en": "Needs outbound HTTPS to gitlab.com.", "zh": "需要能访问 gitlab.com。"}),
        ConfigField("log_ingest_token", {"en": "Log ingestion token", "zh": "日志接入令牌"}, type="secret",
                    help={"en": "A long random string your log shipper sends to POST /api/v1/governance/ingest/gitlab/<id>.",
                          "zh": "日志采集器调用 POST /api/v1/governance/ingest/gitlab/<id> 时使用的长随机字符串。"}),
    )
    permissions_help = {
        "en": "Create a dedicated GitLab administrator account and give it a personal access token with read_api "
              "(and admin_mode if Admin Mode is enabled). The platform only reads.",
        "zh": "创建专用的 GitLab 管理员账号，为其生成具有 read_api 权限的个人访问令牌（如启用了 Admin Mode，"
              "还需 admin_mode）。平台只读取，不做任何修改。",
    }

    def __init__(self, config, secrets, cursor=None, *, transport: httpx.BaseTransport | None = None,
                 sleep=time.sleep, upstream_transport: httpx.BaseTransport | None = None):
        super().__init__(config, secrets, cursor)
        token = secrets.get("token", "")
        base = (self.config["base_url"] or "").rstrip("/")
        self.host = urlparse(base).hostname or ""
        self.api = ApiClient(f"{base}/api/v4", lambda: {"PRIVATE-TOKEN": token}, transport=transport, sleep=sleep,
                             verify=bool(self.config["verify_tls"]))
        self.upstream = ApiClient(UPSTREAM_TAGS, lambda: {}, transport=upstream_transport or transport, sleep=sleep,
                                  timeout=15)

    def close(self) -> None:
        self.api.close()
        self.upstream.close()

    def test(self) -> str:
        v = self.api.get_json("/version")
        try:
            self.api.get_json("/application/settings")
        except SourceUnavailable:
            return f"Connected to GitLab {v.get('version')}, but the token is not an administrator's (or lacks admin_mode)"
        return f"Connected to GitLab {v.get('version')} with administrator access"

    def _list(self, path: str, params: dict | None = None, limit: int | None = None) -> list[dict]:
        return list(paginate_link(self.api, path, {"per_page": 100, **(params or {})}, limit))

    def _each(self, items: list, fn) -> list:
        """Run a per-item fetch in parallel, skipping items this token can't see."""
        def safe(item):
            try:
                return fn(item)
            except SourceUnavailable:
                return []
        with ThreadPoolExecutor(PARALLEL) as pool:
            return [row for rows in pool.map(safe, items) for row in rows]

    # ─── collection ────────────────────────────────────────────────────────

    def collect(self) -> Collected:
        c = Collected(cursor=dict(self.cursor))
        version = c.gather("gitlab.version", lambda: self.api.get_json("/version"))
        c.gather("gitlab.settings", lambda: {k: v for k, v in self.api.get_json("/application/settings").items()
                                             if k in SETTINGS_KEYS})
        users = c.gather("gitlab.users", lambda: [_user(u) for u in self._list("/users", {"exclude_internal": "true"})])
        names = {u["id"]: u["username"] for u in users or []}
        c.gather("gitlab.tokens", lambda: [_token(t, names) for t in self._list(
            "/personal_access_tokens", {"state": "active"}) if t.get("active", True) and not t.get("revoked")])
        if users is not None:
            humans = [u for u in users if u["state"] == "active" and not u["bot"]]
            c.gather("gitlab.ssh_keys", lambda: self._each(humans, self._keys))
        groups = c.gather("gitlab.groups", lambda: [
            {"id": g["id"], "path": g.get("full_path"), "parent_id": g.get("parent_id"), "visibility": g.get("visibility")}
            for g in self._list("/groups", {"all_available": "true"})])
        if groups is not None:
            c.gather("gitlab.group_members", lambda: self._each(groups, lambda g: [
                _member(m, group=g["path"]) for m in self._list(f"/groups/{g['id']}/members")]))
        projects = c.gather("gitlab.projects", lambda: [_project(p) for p in self._list(
            "/projects", {"archived": "false", "order_by": "id", "sort": "asc"}, limit=self.config["max_projects"])])
        if projects is not None:
            c.gather("gitlab.project_members", lambda: self._each(projects, lambda p: [
                _member(m, project=p["path"]) for m in self._list(f"/projects/{p['id']}/members")]))
            c.gather("gitlab.mirrors", lambda: self._each(projects, self._mirrors))
            c.gather("gitlab.branch_protection", lambda: self._each(projects, lambda p: [self._protection(p)]))
            c.gather("gitlab.ci_variables", lambda: self._ci_variables(projects, groups or []))
        c.gather("gitlab.deploy_keys", self._deploy_keys)
        if self.config["check_upstream_version"] and version:
            c.gather("gitlab.upstream", lambda: self._upstream(version.get("version", "")))
        else:
            c.unavailable["gitlab.upstream"] = "Comparison with gitlab.com releases is turned off"
        self._audit_events(c)
        return c

    def _keys(self, u: dict) -> list[dict]:
        out = []
        for k in self._list(f"/users/{u['id']}/keys"):
            kind, bits = ssh_key_strength(k.get("key", ""))
            out.append({"username": u["username"], "title": k.get("title"), "type": kind, "bits": bits,
                        "created_at": k.get("created_at"), "expires_at": k.get("expires_at"),
                        "last_used_at": k.get("last_used_at")})
        return out

    def _mirrors(self, p: dict) -> list[dict]:
        out = []
        for m in self._list(f"/projects/{p['id']}/remote_mirrors"):
            u = urlparse(m.get("url") or "")
            # GitLab masks credentials in the URL; keep only host and path regardless.
            out.append({"project": p["path"], "host": (u.hostname or "").lower(), "path": u.path,
                        "enabled": m.get("enabled"), "last_success": m.get("last_successful_update_at")})
        return out

    def _ci_variables(self, projects: list[dict], groups: list[dict]) -> list[dict]:
        def strip(v: dict, scope: str, owner: str) -> dict:
            # The value is deliberately not kept.
            return {"scope": scope, "owner": owner, "key": v.get("key"), "protected": v.get("protected"),
                    "masked": v.get("masked"), "type": v.get("variable_type"),
                    "environment": v.get("environment_scope")}
        rows = self._each(projects, lambda p: [strip(v, "project", p["path"])
                                               for v in self._list(f"/projects/{p['id']}/variables")])
        rows += self._each(groups, lambda g: [strip(v, "group", g["path"])
                                              for v in self._list(f"/groups/{g['id']}/variables")])
        try:
            rows += [strip(v, "instance", "instance") for v in self._list("/admin/ci/variables")]
        except SourceUnavailable:
            pass
        return rows

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
        # Protected branches can't be deleted, and refuse force pushes unless allowed.
        out["blocks_deletion"] = True
        out["blocks_force_push"] = not pb.get("allow_force_push", False)
        push_levels = [lvl.get("access_level") for lvl in pb.get("push_access_levels", [])]
        # "No one" may push (level 0) means every change goes through a merge request.
        out["requires_pr"] = bool(push_levels) and all(lvl == 0 for lvl in push_levels)
        try:
            rules = self._list(f"/projects/{project['id']}/approval_rules")
            out["approvals"] = max((r.get("approvals_required", 0) for r in rules), default=0)
        except SourceUnavailable:
            pass
        return out

    def _deploy_keys(self) -> list[dict]:
        keys = []
        for k in self._list("/deploy_keys"):
            writable = [p.get("path_with_namespace") for p in k.get("projects_with_write_access") or []]
            readable = [p.get("path_with_namespace") for p in k.get("projects_with_readonly_access") or []]
            for repo in writable:
                keys.append({"repo": repo, "title": k.get("title"), "read_only": False,
                             "created_at": k.get("created_at"), "expires_at": k.get("expires_at")})
            for repo in readable:
                keys.append({"repo": repo, "title": k.get("title"), "read_only": True,
                             "created_at": k.get("created_at"), "expires_at": k.get("expires_at")})
        return keys

    def _upstream(self, installed: str) -> dict:
        """Latest EE releases from gitlab.com, to judge patch currency. Release date = tag commit date."""
        resp = self.upstream.request("GET", "", params={"order_by": "version", "sort": "desc", "search": "-ee",
                                                        "per_page": 100})
        raise_for_source(resp)
        releases = []
        for t in resp.json():
            v = parse_version(t.get("name", ""))
            if v:
                releases.append({"version": ".".join(map(str, v)),
                                 "released": (t.get("commit") or {}).get("created_at")})
        return {"installed": installed, "releases": releases}

    def _audit_events(self, c: Collected) -> None:
        since = parse_time(self.cursor.get("audit_since")) or (utcnow() - timedelta(days=AUDIT_LOOKBACK_DAYS))
        latest, count = since, 0
        try:
            for e in paginate_link(self.api, "/audit_events", {"created_after": iso(since), "per_page": 100}):
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
                    data={"entity_type": e.get("entity_type"), "event_name": e.get("event_name"),
                          **{k: details.get(k) for k in (
                              "change", "from", "to", "custom_message", "target_type", "target_details",
                              "ip_address", "entity_path", "add", "remove", "as") if k in details}}))
        except SourceUnavailable as err:
            c.unavailable["audit.events"] = f"audit events not available (needs Premium and an admin token): {err}"
            return
        except Exception as err:
            c.errors["audit.events"] = f"{type(err).__name__}: {err}"
            return
        c.cursor["audit_since"] = iso(latest)
        c.facts["audit.events"] = {"count": count, "since": iso(since), "latest": iso(latest)}


def _user(u: dict) -> dict:
    return {
        "id": u["id"], "username": u.get("username"), "name": u.get("name"), "email": (u.get("email") or "").lower(),
        "state": u.get("state"), "is_admin": bool(u.get("is_admin")), "bot": bool(u.get("bot")),
        "external": bool(u.get("external")), "two_factor": bool(u.get("two_factor_enabled")),
        "created_at": u.get("created_at"), "last_sign_in_at": u.get("last_sign_in_at"),
        "current_sign_in_at": u.get("current_sign_in_at"), "last_activity_on": u.get("last_activity_on"),
        "identities": [{"provider": i.get("provider"), "extern_uid": (i.get("extern_uid") or "").lower()}
                       for i in u.get("identities") or []],
    }


def _token(t: dict, names: dict) -> dict:
    return {"id": t.get("id"), "name": t.get("name"), "username": names.get(t.get("user_id"), str(t.get("user_id"))),
            "user_id": t.get("user_id"), "scopes": t.get("scopes") or [], "created_at": t.get("created_at"),
            "expires_at": t.get("expires_at"), "last_used_at": t.get("last_used_at")}


def _member(m: dict, group: str | None = None, project: str | None = None) -> dict:
    return {"group": group, "project": project, "username": m.get("username"), "access_level": m.get("access_level"),
            "expires_at": m.get("expires_at"), "state": m.get("state")}


def _project(p: dict) -> dict:
    ns = p.get("namespace") or {}
    return {"id": p["id"], "path": p.get("path_with_namespace"), "visibility": p.get("visibility"),
            "default_branch": p.get("default_branch"), "namespace_kind": ns.get("kind"),
            "namespace": ns.get("full_path"), "last_activity_at": p.get("last_activity_at"),
            "forked_from": (p.get("forked_from_project") or {}).get("path_with_namespace")}


def _change_action(details: dict) -> str:
    if "change" in details:
        return f"change:{details['change']}"
    for verb in ("add", "remove"):
        if verb in details:
            return f"{verb}:{details[verb]}"
    return ""


def parse_version(text: str) -> tuple[int, int, int] | None:
    core = text.lstrip("v").split("-")[0]
    parts = core.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    return int(parts[0]), int(parts[1]), int(parts[2])


def ssh_key_strength(key: str) -> tuple[str, int | None]:
    """(type, bits) of an OpenSSH public key line. Bits only for RSA, where length is the risk."""
    parts = key.split()
    if len(parts) < 2:
        return "unknown", None
    kind = parts[0]
    if kind != "ssh-rsa":
        return kind, None
    try:
        blob = base64.b64decode(parts[1])
        fields, pos = [], 0
        for _ in range(3):  # key type, exponent, modulus
            (n,) = struct.unpack(">I", blob[pos:pos + 4])
            fields.append(blob[pos + 4:pos + 4 + n])
            pos += 4 + n
        modulus = fields[2].lstrip(b"\x00")
        return kind, len(modulus) * 8 - (8 - modulus[0].bit_length())
    except (ValueError, struct.error, IndexError):
        return kind, None
