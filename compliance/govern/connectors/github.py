"""GitHub organisation: members, repository settings, security alerts and the audit log.

Read-only. A fine-grained or classic token from an organisation owner sees
everything here; with less, the parts it can't see are recorded as unavailable.
The audit log API needs GitHub Enterprise Cloud; git clone/fetch events in it are
kept by GitHub for only 7 days, so schedule this connector at least daily.
"""
import time
from datetime import timedelta
from urllib.parse import quote

import httpx

from govern.connectors.base import Collected, ConfigField, Connector, EventRecord, SourceUnavailable
from govern.connectors.http import ApiClient, paginate_link, raise_for_source
from govern.timeutil import iso, parse_time, utcnow

AUDIT_LOOKBACK_DAYS = 7


class GitHubConnector(Connector):
    kind = "github"
    title = {"en": "GitHub", "zh": "GitHub"}
    fields = (
        ConfigField("org", {"en": "Organisation", "zh": "组织"}, required=True),
        ConfigField("token", {"en": "Access token", "zh": "访问令牌"}, type="secret", required=True),
        ConfigField("api_url", {"en": "API URL", "zh": "API 地址"}, default="https://api.github.com",
                    help={"en": "For GitHub Enterprise Server use https://HOST/api/v3",
                          "zh": "GitHub Enterprise Server 请填 https://主机/api/v3"}),
        ConfigField("max_repos", {"en": "Max repositories inspected", "zh": "最多检查的仓库数"}, type="int",
                    default=500),
        ConfigField("public_repo_allowlist", {"en": "Repositories allowed to be public", "zh": "允许公开的仓库"},
                    type="list", default=[]),
        ConfigField("collaborator_allowlist", {"en": "Approved outside collaborators", "zh": "已批准的外部协作者"},
                    type="list", default=[]),
    )
    permissions_help = {
        "en": "Classic token scopes: read:org, repo, admin:org (read audit log), security_events, "
              "admin:org_hook (read webhooks). Use an owner's token or a GitHub App with equivalent read access.",
        "zh": "经典令牌权限：read:org、repo、admin:org（读取审计日志）、security_events、"
              "admin:org_hook（读取 Webhook）。请使用组织所有者的令牌，或具备同等只读权限的 GitHub App。",
    }

    def __init__(self, config, secrets, cursor=None, *, transport: httpx.BaseTransport | None = None,
                 sleep=time.sleep):
        super().__init__(config, secrets, cursor)
        token = secrets.get("token", "")
        self.api = ApiClient(self.config["api_url"] or "https://api.github.com", lambda: {
            "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}, transport=transport, sleep=sleep)
        self.org = quote(self.config["org"], safe="")

    def close(self) -> None:
        self.api.close()

    def test(self) -> str:
        org = self.api.get_json(f"/orgs/{self.org}")
        return f"Connected to {org.get('login')} ({org.get('plan', {}).get('name', 'plan hidden')})"

    def _list(self, path: str, params: dict | None = None, item_key: str | None = None,
              limit: int | None = None) -> list[dict]:
        return list(paginate_link(self.api, path, {"per_page": 100, **(params or {})}, limit, item_key))

    def collect(self) -> Collected:
        c = Collected(cursor=dict(self.cursor))
        o = self.org
        org = c.gather("github.org", lambda: _org_settings(self.api.get_json(f"/orgs/{o}")))
        if org is not None and org.get("two_factor_requirement_enabled") is None:
            c.unavailable["github.org.2fa"] = "The token isn't an organisation owner's, so 2FA policy is hidden"
        c.gather("github.members", lambda: [
            {"login": m["login"], "role": "admin"} for m in self._list(f"/orgs/{o}/members", {"role": "admin"})
        ] + [{"login": m["login"], "role": "member"} for m in self._list(f"/orgs/{o}/members", {"role": "member"})])
        c.gather("github.members_2fa_disabled", lambda: [
            m["login"] for m in self._list(f"/orgs/{o}/members", {"filter": "2fa_disabled"})])
        c.gather("github.outside_collaborators", lambda: [
            m["login"] for m in self._list(f"/orgs/{o}/outside_collaborators")])
        repos = c.gather("github.repos", lambda: [
            _repo(r) for r in self._list(f"/orgs/{o}/repos", {"type": "all"}, limit=self.config["max_repos"])])
        if repos is not None:
            active = [r for r in repos if not r["archived"]]
            c.gather("github.branch_protection", lambda: [self._protection(r) for r in active])
            c.gather("github.deploy_keys", lambda: self._deploy_keys(active))
        c.gather("github.secret_alerts", lambda: [
            {"repo": a.get("repository", {}).get("full_name"), "type": a.get("secret_type_display_name"),
             "created_at": a.get("created_at"), "url": a.get("html_url"),
             "push_protection_bypassed": a.get("push_protection_bypassed")}
            for a in self._list(f"/orgs/{o}/secret-scanning/alerts", {"state": "open"})])
        c.gather("github.dependabot_alerts", lambda: [
            {"repo": a.get("repository", {}).get("full_name"),
             "severity": (a.get("security_advisory") or {}).get("severity"),
             "package": ((a.get("dependency") or {}).get("package") or {}).get("name"),
             "ghsa": (a.get("security_advisory") or {}).get("ghsa_id"),
             "created_at": a.get("created_at"), "url": a.get("html_url")}
            for a in self._list(f"/orgs/{o}/dependabot/alerts", {"state": "open", "severity": "critical,high"})])
        c.gather("github.code_scanning_alerts", lambda: [
            {"repo": a.get("repository", {}).get("full_name"),
             "severity": (a.get("rule") or {}).get("security_severity_level"),
             "rule": (a.get("rule") or {}).get("description"),
             "created_at": a.get("created_at"), "url": a.get("html_url")}
            for a in self._list(f"/orgs/{o}/code-scanning/alerts", {"state": "open", "severity": "critical,high"})])
        c.gather("github.installations", lambda: [
            {"app": i.get("app_slug"), "permissions": i.get("permissions"),
             "repository_selection": i.get("repository_selection"), "created_at": i.get("created_at")}
            for i in self._list(f"/orgs/{o}/installations", item_key="installations")])
        c.gather("github.hooks", lambda: [
            {"id": h.get("id"), "url": (h.get("config") or {}).get("url"),
             "insecure_ssl": str((h.get("config") or {}).get("insecure_ssl", "0")),
             "has_secret": bool((h.get("config") or {}).get("secret")), "active": h.get("active"),
             "events": h.get("events")}
            for h in self._list(f"/orgs/{o}/hooks")])
        # Only exists for organisations with SAML single sign-on.
        c.gather("github.credential_authorizations", lambda: [
            {"login": a.get("login"), "type": a.get("credential_type"),
             "authorized_at": a.get("credential_authorized_at"), "accessed_at": a.get("credential_accessed_at"),
             "expires_at": a.get("authorized_credential_expires_at"), "scopes": a.get("scopes")}
            for a in self._list(f"/orgs/{o}/credential-authorizations")])
        self._audit_log(c)
        return c

    def _protection(self, repo: dict) -> dict:
        """Effective default-branch protection from rulesets and classic branch protection combined."""
        name, branch = quote(repo["name"], safe=""), quote(repo["default_branch"] or "main", safe="")
        out = {"repo": repo["name"], "visibility": repo["visibility"], "requires_pr": False, "approvals": 0,
               "blocks_force_push": False, "blocks_deletion": False, "source": []}
        try:
            for rule in self._list(f"/repos/{self.org}/{name}/rules/branches/{branch}"):
                kind = rule.get("type")
                if kind == "pull_request":
                    out["requires_pr"] = True
                    count = (rule.get("parameters") or {}).get("required_approving_review_count", 0)
                    out["approvals"] = max(out["approvals"], count)
                elif kind == "non_fast_forward":
                    out["blocks_force_push"] = True
                elif kind == "deletion":
                    out["blocks_deletion"] = True
                out["source"].append("ruleset")
        except SourceUnavailable:
            pass
        resp = self.api.request("GET", f"/repos/{self.org}/{name}/branches/{branch}/protection")
        if resp.status_code == 200:
            p = resp.json()
            reviews = p.get("required_pull_request_reviews")
            if reviews:
                out["requires_pr"] = True
                out["approvals"] = max(out["approvals"], reviews.get("required_approving_review_count", 0))
            if not (p.get("allow_force_pushes") or {}).get("enabled", False):
                out["blocks_force_push"] = True
            if not (p.get("allow_deletions") or {}).get("enabled", False):
                out["blocks_deletion"] = True
            out["enforce_admins"] = (p.get("enforce_admins") or {}).get("enabled", False)
            out["source"].append("branch_protection")
        elif resp.status_code not in (403, 404):
            raise_for_source(resp)
        out["source"] = sorted(set(out["source"]))
        return out

    def _deploy_keys(self, repos: list[dict]) -> list[dict]:
        keys = []
        for r in repos:
            try:
                for k in self._list(f"/repos/{self.org}/{quote(r['name'], safe='')}/keys"):
                    keys.append({"repo": r["name"], "title": k.get("title"), "read_only": k.get("read_only"),
                                 "created_at": k.get("created_at"), "last_used": k.get("last_used")})
            except SourceUnavailable:
                continue  # no admin on this repo
        return keys

    def _audit_log(self, c: Collected) -> None:
        since = parse_time(self.cursor.get("audit_since")) or (utcnow() - timedelta(days=AUDIT_LOOKBACK_DAYS))
        # GitHub's search is inclusive and second-granular; the unique document id drops repeats.
        phrase = f"created:>={since.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        latest = since
        count = 0
        try:
            for entry in paginate_link(self.api, f"/orgs/{self.org}/audit-log",
                                       {"phrase": phrase, "include": "all", "order": "asc", "per_page": 100}):
                when = parse_time(entry.get("@timestamp")) or parse_time(entry.get("created_at")) or utcnow()
                latest = max(latest, when)
                count += 1
                c.events.append(EventRecord(
                    kind="github.audit", external_id=str(entry.get("_document_id") or f"{when.timestamp()}-{count}"),
                    occurred_at=when, actor=entry.get("actor") or "", action=entry.get("action") or "",
                    target=entry.get("repo") or entry.get("user") or entry.get("name") or "",
                    data=_audit_data(entry)))
        except SourceUnavailable as e:
            c.unavailable["audit.events"] = f"audit log API not available (needs GitHub Enterprise Cloud): {e}"
            return
        except Exception as e:
            c.errors["audit.events"] = f"{type(e).__name__}: {e}"
            return
        c.cursor["audit_since"] = iso(latest)
        c.facts["audit.events"] = {"count": count, "since": iso(since), "latest": iso(latest)}


def _org_settings(org: dict) -> dict:
    keys = ("login", "two_factor_requirement_enabled", "default_repository_permission",
            "members_can_create_public_repositories", "members_can_fork_private_repositories",
            "web_commit_signoff_required", "advanced_security_enabled_for_new_repositories",
            "secret_scanning_enabled_for_new_repositories",
            "secret_scanning_push_protection_enabled_for_new_repositories")
    return {**{k: org.get(k) for k in keys}, "plan": (org.get("plan") or {}).get("name")}


def _repo(r: dict) -> dict:
    sa = r.get("security_and_analysis") or {}
    return {"name": r["name"], "visibility": r.get("visibility") or ("private" if r.get("private") else "public"),
            "archived": r.get("archived", False), "fork": r.get("fork", False),
            "default_branch": r.get("default_branch"), "pushed_at": r.get("pushed_at"),
            "secret_scanning": (sa.get("secret_scanning") or {}).get("status"),
            "push_protection": (sa.get("secret_scanning_push_protection") or {}).get("status"),
            "dependabot_updates": (sa.get("dependabot_security_updates") or {}).get("status")}


_AUDIT_KEEP = ("action", "actor", "actor_ip", "actor_location", "repo", "repository", "user", "org", "visibility",
               "previous_visibility", "permission", "old_permission", "role", "name", "transport_protocol_name",
               "repository_public", "business", "operation_type", "hashed_token", "programmatic_access_type",
               "user_agent", "branch", "ruleset_name")


def _audit_data(entry: dict) -> dict:
    return {k: entry[k] for k in _AUDIT_KEEP if k in entry}
