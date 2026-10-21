"""Risky-operation and bulk-download rules over GitHub and GitLab audit events."""
from datetime import timedelta

from govern.rules.base import AlertDraft, day_bounds, rule

# ─── GitHub: exact audit-log action names ─────────────────────────────────────

GITHUB_ACTIONS: dict[str, tuple[str, str, str]] = {
    # action: (severity, English title, Chinese title)
    "repo.destroy": ("high", "Repository deleted", "仓库被删除"),
    "repo.transfer_outgoing": ("high", "Repository transferred out of the organisation", "仓库被转出组织"),
    "repo.transfer": ("high", "Repository transferred", "仓库被转移"),
    "protected_branch.destroy": ("high", "Branch protection removed", "分支保护被移除"),
    "repository_ruleset.destroy": ("high", "Repository ruleset deleted", "仓库规则集被删除"),
    "protected_branch.policy_override": ("medium", "Admin pushed past branch protection", "管理员绕过分支保护推送"),
    "secret_scanning_push_protection.bypass": ("high", "Secret pushed past push protection", "密钥绕过推送保护被提交"),
    "org.disable_two_factor_requirement": ("critical", "Organisation 2FA requirement turned off", "组织 2FA 强制要求被关闭"),
    "org.disable_saml": ("critical", "SAML single sign-on turned off", "SAML 单点登录被关闭"),
    "secret_scanning.disable": ("high", "Secret scanning turned off", "密钥扫描被关闭"),
    "secret_scanning_push_protection.disable": ("high", "Push protection turned off", "推送保护被关闭"),
    "repository_secret_scanning.disable": ("high", "Secret scanning turned off for a repository", "仓库密钥扫描被关闭"),
    "repository_secret_scanning_push_protection.disable": ("high", "Push protection turned off for a repository",
                                                           "仓库推送保护被关闭"),
    "dependabot_alerts.disable": ("medium", "Dependabot alerts turned off", "Dependabot 告警被关闭"),
    "integration_installation.create": ("low", "GitHub App installed", "安装了 GitHub App"),
    "org.oauth_app_access_approved": ("low", "OAuth app granted organisation access", "OAuth 应用获得组织访问权限"),
    "hook.create": ("low", "Webhook created", "创建了 Webhook"),
    "personal_access_token.access_granted": ("low", "Fine-grained token granted organisation access",
                                             "细粒度令牌获得组织访问权限"),
}
GITHUB_DOWNLOAD_ACTIONS = ("git.clone", "git.fetch", "repo.download_zip")
ADMIN_WORDS = {"admin", "owner"}


@rule("github.risky_operation", "github",
      title={"en": "Risky GitHub operation", "zh": "GitHub 风险操作"},
      description={"en": "Deleting or transferring repositories, removing branch protection, bypassing push protection, "
                         "turning off 2FA/SSO or security features, and installing integrations.",
                   "zh": "删除或转移仓库、移除分支保护、绕过推送保护、关闭 2FA/SSO 或安全功能、安装集成等操作。"})
def github_risky(ctx, events):
    for e in events:
        if e.action in GITHUB_ACTIONS:
            sev, en, zh = GITHUB_ACTIONS[e.action]
        elif e.action in ("repo.access", "repo.create") and e.data.get("visibility") == "public":
            sev, en, zh = "critical", "Repository made public", "仓库被设为公开"
        elif e.action in ("org.add_member", "org.update_member", "repo.add_member", "repo.update_member") and (
                {str(e.data.get(k, "")).lower() for k in ("permission", "role")} & ADMIN_WORDS):
            sev, en, zh = "medium", "Admin access granted", "授予了管理员权限"
        else:
            continue
        yield AlertDraft("github.risky_operation", sev, f"{en}: {e.target or e.action}",
                         f"{zh}：{e.target or e.action}", e.occurred_at, f"github.risky:{e.connector_id}:{e.external_id}",
                         e.actor, {"action": e.action, "target": e.target, **e.data})


# ─── GitLab: event names vary by version, so match on what the details say ───

GITLAB_PATTERNS: list[tuple[tuple[str, ...], str, str, str]] = [
    (("project_destroyed", "project_deleted", "project removed", "delete project"), "high",
     "Project deleted", "项目被删除"),
    (("protected_branch_removed", "protected_branch_deleted", "unprotected branch"), "high",
     "Branch protection removed", "分支保护被移除"),
    (("project_transferred", "transferred project", "group_transferred"), "high",
     "Project or group transferred", "项目或群组被转移"),
    (("project_export", "export file download", "export started"), "medium",
     "Project exported", "项目被导出"),
    (("personal_access_token_created", "group_access_token_created", "project_access_token_created"), "low",
     "Access token created", "创建了访问令牌"),
]
GITLAB_DOWNLOAD_HINTS = ("repository_download", "repository_git_operation", "git_clone", "repository download",
                         "download started")


def gitlab_classify(e) -> tuple[str, str, str] | None:
    text = f"{e.action} {e.data.get('custom_message') or ''}".lower()
    change = str(e.data.get("change") or "").lower()
    to = str(e.data.get("to") or "").lower()
    if "visibility" in change and to in ("public", "internal"):
        zh = "公开" if to == "public" else "内部"
        return "critical" if to == "public" else "high", f"Visibility changed to {to}", f"可见性被改为{zh}"
    if "two_factor" in change and to in ("false", "0", "disabled"):
        return "critical", "Group 2FA requirement turned off", "群组 2FA 强制要求被关闭"
    if e.data.get("add") == "user_access" and str(e.data.get("as") or "").lower() == "owner":
        return "medium", "Owner access granted", "授予了所有者权限"
    for needles, sev, en, zh in GITLAB_PATTERNS:
        if any(n in text for n in needles):
            return sev, en, zh
    return None


@rule("gitlab.risky_operation", "gitlab",
      title={"en": "Risky GitLab operation", "zh": "GitLab 风险操作"},
      description={"en": "Visibility made public/internal, projects deleted, transferred or exported, branch protection "
                         "removed, 2FA requirement turned off, owners added. Matched on event details; verify against "
                         "your GitLab version's audit event names.",
                   "zh": "可见性改为公开/内部、项目删除/转移/导出、分支保护移除、关闭 2FA 要求、新增所有者。"
                         "按事件详情匹配，请对照所用 GitLab 版本的审计事件名称确认。"})
def gitlab_risky(ctx, events):
    for e in events:
        hit = gitlab_classify(e)
        if hit is None:
            continue
        sev, en, zh = hit
        yield AlertDraft("gitlab.risky_operation", sev, f"{en}: {e.target or e.action}", f"{zh}：{e.target or e.action}",
                         e.occurred_at, f"gitlab.risky:{e.connector_id}:{e.external_id}", e.actor,
                         {"action": e.action, "target": e.target, **e.data})


# ─── Bulk download, for both ───────────────────────────────────────────────────

BULK_DEFAULTS = {"distinct_repos": 20, "min_events": 200, "baseline_factor": 5.0, "actor_allowlist": []}


def _bulk(ctx, events, kind: str, rule_id: str, is_download, actions: tuple[str, ...] | None = None):
    p = ctx.params
    allow = {a.lower() for a in p.get("actor_allowlist", [])}
    touched: dict[tuple[str, object], None] = {}
    for e in events:
        if e.actor and e.actor.lower() not in allow and is_download(e):
            touched[(e.actor, day_bounds(e.occurred_at)[0])] = None
    for actor, day in touched:
        start, end = day_bounds(day)
        # Look at the whole day from the database, not only this run's slice of it.
        day_events = [e for e in ctx.events(kind=kind, actor=actor, start=start, end=end, actions=actions)
                      if is_download(e)]
        repos = {e.target for e in day_events if e.target}
        if actions is not None:
            baseline = ctx.baseline_daily(kind=kind, actor=actor, before=start, actions=actions)
        else:
            baseline = sum(1 for e in ctx.events(kind=kind, actor=actor, start=start - timedelta(days=30), end=start)
                           if is_download(e)) / 30
        threshold = max(p["min_events"], p["baseline_factor"] * baseline)
        reasons = []
        if len(repos) >= p["distinct_repos"]:
            reasons.append("distinct_repos")
        if len(day_events) >= threshold:
            reasons.append("volume")
        if not reasons:
            continue
        severity = "critical" if len(reasons) == 2 else "high"
        yield AlertDraft(
            rule_id, severity, f"Bulk download by {actor}: {len(day_events)} operations across {len(repos)} repositories",
            f"{actor} 批量下载：{len(repos)} 个仓库共 {len(day_events)} 次操作",
            max(e.occurred_at for e in day_events), f"{rule_id}:{ctx.connector.id}:{actor}:{start.date()}", actor,
            {"day": str(start.date()), "operations": len(day_events), "repositories": len(repos),
             "sample_repositories": sorted(repos)[:50], "baseline_per_day": round(baseline, 1),
             "threshold": round(threshold, 1), "reasons": reasons})


@rule("github.bulk_download", "github", defaults=BULK_DEFAULTS,
      title={"en": "Bulk repository download", "zh": "大量下载代码仓库"},
      description={"en": "One account cloning, fetching or downloading archives of many repositories in a day, or far "
                         "more than its own 30-day norm. Needs GitHub Enterprise Cloud git events.",
                   "zh": "同一账号一天内克隆、拉取或下载大量仓库，或远超其近 30 天的日常水平。需要 GitHub Enterprise Cloud 的 git 事件。"})
def github_bulk(ctx, events):
    yield from _bulk(ctx, events, "github.audit", "github.bulk_download",
                     lambda e: e.action in GITHUB_DOWNLOAD_ACTIONS, GITHUB_DOWNLOAD_ACTIONS)


@rule("gitlab.bulk_download", "gitlab", defaults=BULK_DEFAULTS,
      title={"en": "Bulk repository download", "zh": "大量下载代码仓库"},
      description={"en": "One account downloading or exporting many projects in a day. GitLab records git clone events "
                         "only in some tiers and versions.",
                   "zh": "同一账号一天内下载或导出大量项目。GitLab 仅在部分版本中记录 git 克隆事件。"})
def gitlab_bulk(ctx, events):
    def is_download(e):
        text = f"{e.action} {e.data.get('custom_message') or ''}".lower()
        return any(h in text for h in GITLAB_DOWNLOAD_HINTS)
    yield from _bulk(ctx, events, "gitlab.audit", "gitlab.bulk_download", is_download)

