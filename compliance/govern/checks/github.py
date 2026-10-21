"""Checks over GitHub organisation facts."""
from urllib.parse import urlparse

from govern.checks.base import MAX_ITEMS, Outcome, check, ratio_outcome
from govern.checks.codehost import overdue, register_shared

register_shared("github", "GitHub")

ADMIN_APP_PERMISSIONS = {"administration", "organization_administration", "members",
                         "organization_secrets", "secrets", "workflows"}


@check("github.org_2fa_required", "github", severity="critical", requires=["github.org"],
       title={"en": "The organisation requires two-factor authentication", "zh": "组织要求双因素认证"},
       summary={"en": "{result}", "zh": "{result_zh}"},
       remediation={"en": "Organisation settings → Authentication security → Require two-factor authentication.",
                    "zh": "组织设置 → 身份验证安全 → 要求双因素认证。"})
def org_2fa_required(facts, p):
    required = facts["github.org"].get("two_factor_requirement_enabled")
    if required is None:
        return Outcome("not_available", {"result": "Only visible to an organisation owner's token",
                                         "result_zh": "仅组织所有者的令牌可见"})
    if required:
        return Outcome("pass", {"result": "2FA is required for all members", "result_zh": "已要求所有成员启用 2FA"})
    return Outcome("fail", {"result": "2FA is not required", "result_zh": "未要求启用 2FA"})


@check("github.members_without_2fa", "github", severity="high",
       requires=["github.members", "github.members_2fa_disabled"],
       title={"en": "Every member has 2FA enabled", "zh": "所有成员已启用 2FA"},
       summary={"en": "{failing} of {total} members have 2FA disabled",
                "zh": "{total} 个成员中有 {failing} 个未启用 2FA"},
       remediation={"en": "Ask these members to enable 2FA, then turn on the organisation requirement.",
                    "zh": "要求这些成员启用 2FA，再开启组织级强制要求。"})
def members_without_2fa(facts, p):
    failing = [{"login": login} for login in facts["github.members_2fa_disabled"]]
    return ratio_outcome(failing, len(facts["github.members"]), pass_at=1.0, partial_at=0.95)


@check("github.owner_count", "github", severity="medium", requires=["github.members"],
       defaults={"min": 2, "max": 5},
       title={"en": "Organisation owners are few but not one", "zh": "组织所有者数量适当"},
       summary={"en": "{count} organisation owners (expected {min}–{max})",
                "zh": "共 {count} 个组织所有者（建议 {min}–{max} 个）"},
       remediation={"en": "Demote owners who don't need it to member and grant repository admin where required.",
                    "zh": "将无需所有者权限的人降为成员，按需授予仓库管理员。"})
def owner_count(facts, p):
    owners = [m for m in facts["github.members"] if m["role"] == "admin"]
    n = len(owners)
    status = "pass" if p["min"] <= n <= p["max"] else ("partial" if n < p["min"] else "fail")
    return Outcome(status, {"count": n, "min": p["min"], "max": p["max"]}, [{"login": m["login"]} for m in owners])


@check("github.default_permission", "github", severity="medium", requires=["github.org"],
       title={"en": "Members get no more than read access by default", "zh": "成员默认权限不高于只读"},
       summary={"en": "Base repository permission is '{permission}'", "zh": "仓库基础权限为「{permission}」"},
       remediation={"en": "Set the base permission to 'Read' or 'No permission' and grant write through teams.",
                    "zh": "将基础权限设为「Read」或「No permission」，通过团队授予写权限。"})
def default_permission(facts, p):
    perm = facts["github.org"].get("default_repository_permission")
    if perm is None:
        return Outcome("not_available", {"permission": "hidden"})
    return Outcome("pass" if perm in ("none", "read") else "fail", {"permission": perm})


@check("github.outside_collaborators", "github", severity="medium", requires=["github.outside_collaborators"],
       title={"en": "Outside collaborators are approved", "zh": "外部协作者均已批准"},
       summary={"en": "{failing} outside collaborators are not on the approved list ({total} in total)",
                "zh": "{failing} 个外部协作者不在批准名单中（共 {total} 个）"},
       remediation={"en": "Remove collaborators whose engagement has ended; add the rest to the approved list.",
                    "zh": "移除合作已结束的协作者；其余加入批准名单。"})
def outside_collaborators(facts, p):
    allowed = {x.lower() for x in p.get("collaborator_allowlist", [])}
    people = facts["github.outside_collaborators"]
    failing = [{"login": x} for x in people if x.lower() not in allowed]
    return Outcome("pass" if not failing else "partial", {"failing": len(failing), "total": len(people)},
                   failing[:MAX_ITEMS])


@check("github.public_repos", "github", severity="high", requires=["github.repos"],
       title={"en": "No unexpected public repositories", "zh": "没有意外公开的仓库"},
       summary={"en": "{failing} public repositories are not on the allow list",
                "zh": "{failing} 个公开仓库不在允许名单中"},
       remediation={"en": "Make these private, or add them to the allow list if publishing was intended.",
                    "zh": "将其设为私有；如确需公开，请加入允许名单。"})
def public_repos(facts, p):
    allowed = {x.lower() for x in p.get("public_repo_allowlist", [])}
    failing = [{"repo": r["name"]} for r in facts["github.repos"]
               if r["visibility"] == "public" and r["name"].lower() not in allowed]
    return Outcome("fail" if failing else "pass", {"failing": len(failing)}, failing[:MAX_ITEMS])


@check("github.secret_scanning", "github", severity="high", requires=["github.repos"],
       title={"en": "Secret scanning and push protection are on", "zh": "已开启密钥扫描和推送保护"},
       summary={"en": "{failing} of {total} active repositories lack secret scanning or push protection",
                "zh": "{total} 个活跃仓库中有 {failing} 个未开启密钥扫描或推送保护"},
       remediation={"en": "Enable secret scanning and push protection for all repositories via a security configuration.",
                    "zh": "通过安全配置为所有仓库开启密钥扫描和推送保护。"})
def secret_scanning(facts, p):
    repos = [r for r in facts["github.repos"] if not r["archived"]]
    if repos and all(r.get("secret_scanning") is None for r in repos):
        return Outcome("not_available", {"failing": 0, "total": len(repos)})
    failing = [{"repo": r["name"], "secret_scanning": r.get("secret_scanning"),
                "push_protection": r.get("push_protection")}
               for r in repos if r.get("secret_scanning") != "enabled" or r.get("push_protection") != "enabled"]
    return ratio_outcome(failing, len(repos), pass_at=1.0, partial_at=0.8)


@check("github.open_secret_alerts", "github", severity="critical", requires=["github.secret_alerts"],
       title={"en": "No leaked secrets left open", "zh": "没有未处理的泄露密钥"},
       summary={"en": "{count} open secret-scanning alerts ({bypassed} pushed past push protection)",
                "zh": "{count} 个未处理的密钥扫描告警（其中 {bypassed} 个绕过了推送保护）"},
       remediation={"en": "Revoke and rotate each exposed credential, then close the alert.",
                    "zh": "吊销并轮换每个泄露的凭据，再关闭告警。"})
def open_secret_alerts(facts, p):
    alerts = facts["github.secret_alerts"]
    bypassed = sum(1 for a in alerts if a.get("push_protection_bypassed"))
    return Outcome("fail" if alerts else "pass", {"count": len(alerts), "bypassed": bypassed}, alerts[:MAX_ITEMS])


@check("github.dependabot_sla", "github", severity="high", requires=["github.dependabot_alerts"],
       defaults={"sla_days": 30},
       title={"en": "Critical and high dependency vulnerabilities are fixed within SLA",
              "zh": "严重和高危依赖漏洞在时限内修复"},
       summary={"en": "{overdue} of {open} open critical/high Dependabot alerts are older than {sla_days} days",
                "zh": "{open} 个未处理的严重/高危 Dependabot 告警中有 {overdue} 个超过 {sla_days} 天"},
       remediation={"en": "Merge the Dependabot security updates or document why the vulnerable path isn't reachable.",
                    "zh": "合并 Dependabot 安全更新，或记录漏洞路径不可达的理由。"})
def dependabot_sla(facts, p):
    return _sla(facts["github.dependabot_alerts"], p["sla_days"])


@check("github.code_scanning_sla", "github", severity="high", requires=["github.code_scanning_alerts"],
       defaults={"sla_days": 30},
       title={"en": "Critical and high code-scanning findings are fixed within SLA",
              "zh": "严重和高危代码扫描问题在时限内修复"},
       summary={"en": "{overdue} of {open} open critical/high code-scanning alerts are older than {sla_days} days",
                "zh": "{open} 个未处理的严重/高危代码扫描告警中有 {overdue} 个超过 {sla_days} 天"},
       remediation={"en": "Fix or triage each finding; dismissals need a recorded reason.",
                    "zh": "修复或分诊每个问题；忽略需要记录理由。"})
def code_scanning_sla(facts, p):
    return _sla(facts["github.code_scanning_alerts"], p["sla_days"])


def _sla(alerts: list[dict], days: int) -> Outcome:
    late = overdue(alerts, days)
    status = "fail" if late else ("partial" if alerts else "pass")
    return Outcome(status, {"overdue": len(late), "open": len(alerts), "sla_days": days}, late[:MAX_ITEMS])


@check("github.webhooks_secure", "github", severity="medium", requires=["github.hooks"],
       title={"en": "Organisation webhooks use verified HTTPS and a secret", "zh": "组织 Webhook 使用经验证的 HTTPS 和签名密钥"},
       summary={"en": "{failing} of {total} webhooks send over plain HTTP, skip TLS verification or are unsigned",
                "zh": "{total} 个 Webhook 中有 {failing} 个使用明文 HTTP、跳过 TLS 校验或未签名"},
       remediation={"en": "Use https:// endpoints, keep SSL verification on and set a webhook secret.",
                    "zh": "使用 https:// 地址，保持 SSL 校验开启，并设置 Webhook 密钥。"})
def webhooks_secure(facts, p):
    hooks = facts["github.hooks"]
    failing = []
    for h in hooks:
        issues = []
        if urlparse(h.get("url") or "").scheme != "https":
            issues.append("not_https")
        if h.get("insecure_ssl") == "1":
            issues.append("tls_verification_off")
        if not h.get("has_secret"):
            issues.append("no_secret")
        if issues:
            failing.append({"url": h.get("url"), "issues": issues})
    # Plaintext or unverified TLS exposes payloads; a missing secret only weakens origin checks.
    exposed = any({"not_https", "tls_verification_off"} & set(f["issues"]) for f in failing)
    status = "fail" if exposed else ("partial" if failing else "pass")
    return Outcome(status, {"failing": len(failing), "total": len(hooks)}, failing[:MAX_ITEMS])


@check("github.token_expiry", "github", severity="medium", requires=["github.credential_authorizations"],
       title={"en": "Authorised personal access tokens expire", "zh": "已授权的个人访问令牌设置了过期时间"},
       summary={"en": "{failing} of {total} SSO-authorised tokens never expire",
                "zh": "{total} 个已 SSO 授权的令牌中有 {failing} 个永不过期"},
       remediation={"en": "Require token expiry in the organisation's personal access token policy.",
                    "zh": "在组织的个人访问令牌策略中要求设置过期时间。"})
def token_expiry(facts, p):
    tokens = [a for a in facts["github.credential_authorizations"] if a.get("type") == "personal access token"]
    failing = [{"login": a["login"], "scopes": a.get("scopes"), "accessed_at": a.get("accessed_at")}
               for a in tokens if not a.get("expires_at")]
    return ratio_outcome(failing, len(tokens), pass_at=1.0, partial_at=0.8)


@check("github.app_permissions", "github", severity="low", requires=["github.installations"],
       title={"en": "Installed apps with admin-level access are reviewed", "zh": "已审查具有管理级权限的已安装应用"},
       summary={"en": "{failing} of {total} installed apps hold administration, members, secrets or workflow write access",
                "zh": "{total} 个已安装应用中有 {failing} 个拥有管理、成员、密钥或工作流写权限"},
       remediation={"en": "Confirm each app still needs this access; uninstall the ones nobody owns.",
                    "zh": "确认每个应用仍需此权限；卸载无人负责的应用。"})
def app_permissions(facts, p):
    apps = facts["github.installations"]
    failing = []
    for a in apps:
        powerful = sorted(k for k, v in (a.get("permissions") or {}).items()
                          if k in ADMIN_APP_PERMISSIONS and v in ("write", "admin"))
        if powerful:
            failing.append({"app": a["app"], "permissions": powerful})
    return Outcome("partial" if failing else "pass", {"failing": len(failing), "total": len(apps)}, failing)
