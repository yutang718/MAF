"""Security checks over a self-managed GitLab instance, several cross-checked against Entra ID."""
import re
from datetime import timedelta
from urllib.parse import urlparse

from govern.checks.base import Outcome, check, ratio_outcome
from govern.checks.codehost import register_shared
from govern.checks.identity import classify_all, company_domains
from govern.connectors.gitlab import DEVELOPER, MAINTAINER, OWNER, parse_version
from govern.timeutil import parse_time, utcnow

register_shared("gitlab", "GitLab")

ENTRA = {"m365": ("entra.users", "entra.domains")}
LEVEL = {10: "Guest", 15: "Planner", 20: "Reporter", 30: "Developer", 40: "Maintainer", 50: "Owner"}


def _humans(facts) -> list[dict]:
    return [u for u in facts["gitlab.users"] if u["state"] == "active" and not u["bot"]]


def _last_seen(u: dict):
    stamps = [parse_time(u.get(k)) for k in ("last_activity_on", "current_sign_in_at", "last_sign_in_at")]
    stamps = [s for s in stamps if s]
    return max(stamps) if stamps else None


def _leavers(facts, params) -> list[tuple[dict, str]]:
    matches = classify_all(facts, params)
    return [(u, matches[u["username"]].status) for u in _humans(facts)
            if matches[u["username"]].status in ("disabled", "missing")]


REASON = {"disabled": "Entra account disabled", "missing": "no Entra account (deleted?)"}


# ─── Accounts and identity ────────────────────────────────────────────────────

@check("gitlab.leavers", "gitlab", severity="critical", requires=["gitlab.users"], cross=ENTRA,
       title={"en": "No GitLab accounts left active for leavers", "zh": "离职人员的 GitLab 账号已全部停用"},
       summary={"en": "{count} active GitLab accounts belong to people whose Entra account is disabled or gone",
                "zh": "{count} 个仍有效的 GitLab 账号，其 Entra 账号已禁用或不存在"},
       remediation={"en": "Block these accounts now, then revoke their tokens and SSH keys. Add GitLab to the leaver "
                          "process, or let SCIM/LDAP sync block users automatically.",
                    "zh": "立即封禁这些账号，并吊销其令牌和 SSH 密钥；把 GitLab 纳入离职流程，或用 SCIM/LDAP 同步自动封禁。"})
def leavers(facts, p):
    items = [{"_key": u["username"], "_label": f"{u['username']} · {u['email']} · {REASON[why]}",
              "username": u["username"], "name": u["name"], "email": u["email"], "reason": why,
              "is_admin": u["is_admin"], "last_activity": u.get("last_activity_on")}
             for u, why in _leavers(facts, p)]
    return Outcome("fail" if items else "pass", {"count": len(items)}, items)


@check("gitlab.leaver_credentials", "gitlab", severity="critical",
       requires=["gitlab.users", "gitlab.tokens", "gitlab.ssh_keys"], cross=ENTRA,
       title={"en": "Leavers hold no live tokens or SSH keys", "zh": "离职人员没有仍有效的令牌或 SSH 密钥"},
       summary={"en": "{tokens} access tokens and {keys} SSH keys still work for {people} leavers",
                "zh": "{people} 名离职人员仍有 {tokens} 个有效令牌和 {keys} 个 SSH 密钥"},
       remediation={"en": "Revoke them. Blocking a user stops tokens, but these accounts are not blocked.",
                    "zh": "立即吊销。封禁用户会使令牌失效，但这些账号尚未封禁。"})
def leaver_credentials(facts, p):
    gone = {u["username"] for u, _ in _leavers(facts, p)}
    items = [{"_key": f"token:{t['id']}", "_label": f"{t['username']} · token {t['name']}", "username": t["username"],
              "credential": "token", "name": t["name"], "scopes": t["scopes"], "last_used_at": t.get("last_used_at")}
             for t in facts["gitlab.tokens"] if t["username"] in gone]
    tokens = len(items)
    items += [{"_key": f"ssh:{k['username']}:{k['title']}", "_label": f"{k['username']} · SSH {k['title']}",
               "username": k["username"], "credential": "ssh_key", "name": k["title"],
               "last_used_at": k.get("last_used_at")}
              for k in facts["gitlab.ssh_keys"] if k["username"] in gone]
    people = len({i["username"] for i in items})
    return Outcome("fail" if items else "pass", {"tokens": tokens, "keys": len(items) - tokens, "people": people}, items)


@check("gitlab.leaver_activity", "gitlab", severity="critical", requires=["gitlab.users"], cross=ENTRA,
       defaults={"days": 30},
       title={"en": "No recent activity from leavers' accounts", "zh": "离职人员账号近期没有活动"},
       summary={"en": "{count} leavers' accounts were active in the last {days} days",
                "zh": "{count} 个离职人员账号在近 {days} 天内仍有活动"},
       remediation={"en": "Treat as a possible incident: block the account, review what it cloned or changed "
                          "(audit events and ingested git logs), and preserve the logs.",
                    "zh": "按疑似安全事件处理：封禁账号，核查其克隆或修改了什么（审计事件和 git 日志），并保全日志。"})
def leaver_activity(facts, p):
    cutoff = utcnow() - timedelta(days=p["days"])
    items = []
    for u, why in _leavers(facts, p):
        seen = _last_seen(u)
        if seen and seen >= cutoff:
            items.append({"_key": u["username"], "_label": f"{u['username']} · last active {seen.date()}",
                          "username": u["username"], "email": u["email"], "reason": why,
                          "last_active": seen.date().isoformat()})
    return Outcome("fail" if items else "pass", {"count": len(items), "days": p["days"]}, items)


@check("gitlab.dormant_users", "gitlab", severity="high", requires=["gitlab.users"], defaults={"days": 90},
       title={"en": "No dormant GitLab accounts", "zh": "没有长期闲置的 GitLab 账号"},
       summary={"en": "{failing} of {total} active accounts have had no activity for {days} days",
                "zh": "{total} 个有效账号中有 {failing} 个超过 {days} 天无任何活动"},
       remediation={"en": "Deactivate them, and turn on 'Deactivate dormant users' in Admin → Settings → General.",
                    "zh": "停用这些账号，并在「管理 → 设置 → 通用」中开启「停用闲置用户」。"})
def dormant_users(facts, p):
    cutoff = utcnow() - timedelta(days=p["days"])
    service = {s.lower() for s in p.get("service_accounts") or []}
    pool = [u for u in _humans(facts) if u["username"].lower() not in service]
    failing = []
    for u in pool:
        seen = _last_seen(u) or parse_time(u.get("created_at"))
        if seen is None or seen < cutoff:
            failing.append({"_key": u["username"], "username": u["username"], "email": u["email"],
                            "last_active": seen.date().isoformat() if seen else None, "is_admin": u["is_admin"]})
    return ratio_outcome(failing, len(pool), pass_at=1.0, partial_at=0.95, days=p["days"])


@check("gitlab.non_corporate_users", "gitlab", severity="high", requires=["gitlab.users"], cross=ENTRA,
       title={"en": "Every account belongs to a corporate identity", "zh": "所有账号都对应公司身份"},
       summary={"en": "{count} active accounts have neither SSO nor a company email address",
                "zh": "{count} 个有效账号既没有 SSO 身份，也没有公司邮箱"},
       remediation={"en": "Move contractors to Entra guest accounts with SSO, or mark them External with an expiry; "
                          "block personal accounts.",
                    "zh": "将外包人员迁移为带 SSO 的 Entra 来宾账号，或标记为 External 并设置到期日；封禁个人账号。"})
def non_corporate_users(facts, p):
    matches = classify_all(facts, p)
    items = [{"_key": u["username"], "username": u["username"], "email": u["email"], "external": u["external"],
              "is_admin": u["is_admin"], "created_at": u.get("created_at")}
             for u in _humans(facts) if matches[u["username"]].status == "non_corporate"]
    return Outcome("fail" if items else "pass", {"count": len(items)}, items)


def _sso_only(settings: dict) -> bool:
    return not settings.get("password_authentication_enabled_for_web") and \
        not settings.get("password_authentication_enabled_for_git")


@check("gitlab.user_2fa", "gitlab", severity="high", requires=["gitlab.users", "gitlab.settings"],
       title={"en": "Password logins are protected by a second factor", "zh": "密码登录有第二因素保护"},
       summary={"en": "{result}", "zh": "{result_zh}"},
       remediation={"en": "Best: turn off password sign-in so everyone goes through Entra MFA. Otherwise require 2FA "
                          "for all users in Admin → Settings → General → Sign-in restrictions.",
                    "zh": "最佳做法：关闭密码登录，让所有人通过 Entra MFA 登录；否则在「管理 → 设置 → 通用 → 登录限制」"
                          "中要求所有用户启用 2FA。"})
def user_2fa(facts, p):
    s = facts["gitlab.settings"]
    if _sso_only(s):
        return Outcome("pass", {"result": "Password sign-in is off; MFA is enforced by Entra SSO",
                                "result_zh": "已关闭密码登录，MFA 由 Entra SSO 强制"})
    if s.get("require_two_factor_authentication"):
        return Outcome("pass", {"result": "2FA is required for every user", "result_zh": "已要求所有用户启用 2FA"})
    humans = _humans(facts)
    failing = [{"_key": u["username"], "username": u["username"], "email": u["email"], "is_admin": u["is_admin"]}
               for u in humans if not u["two_factor"]]
    out = ratio_outcome(failing, len(humans), pass_at=1.0, partial_at=0.95)
    out.params.update(result=f"{len(failing)} of {len(humans)} users can sign in with a password and have no 2FA",
                      result_zh=f"{len(humans)} 个用户中有 {len(failing)} 个可用密码登录且未启用 2FA")
    return out


@check("gitlab.password_login", "gitlab", severity="medium", requires=["gitlab.settings"],
       title={"en": "Sign-in goes through Entra SSO only", "zh": "仅允许通过 Entra SSO 登录"},
       summary={"en": "{result}", "zh": "{result_zh}"},
       remediation={"en": "Turn off password authentication for web and Git (Admin → Settings → General → "
                          "Sign-in restrictions); Git over HTTPS then uses personal access tokens.",
                    "zh": "关闭 Web 和 Git 的密码认证（管理 → 设置 → 通用 → 登录限制）；HTTPS 方式的 Git 改用个人访问令牌。"})
def password_login(facts, p):
    s = facts["gitlab.settings"]
    web, git = s.get("password_authentication_enabled_for_web"), s.get("password_authentication_enabled_for_git")
    if not web and not git:
        return Outcome("pass", {"result": "Password sign-in is off for web and Git",
                                "result_zh": "Web 和 Git 均已关闭密码登录"})
    where_en = " and ".join(w for w, on in (("web", web), ("Git over HTTPS", git)) if on)
    where_zh = "、".join(w for w, on in (("Web", web), ("HTTPS Git", git)) if on)
    return Outcome("fail", {"result": f"Password sign-in is allowed for {where_en}",
                            "result_zh": f"仍允许密码登录：{where_zh}"})


@check("gitlab.signup", "gitlab", severity="high", requires=["gitlab.settings"],
       title={"en": "Nobody can register an account without approval", "zh": "未经审批无法自行注册账号"},
       summary={"en": "{result}", "zh": "{result_zh}"},
       remediation={"en": "Turn off sign-up (accounts come from SSO), or require admin approval and restrict domains.",
                    "zh": "关闭自助注册（账号由 SSO 创建），或要求管理员审批并限制域名。"})
def signup(facts, p):
    s = facts["gitlab.settings"]
    if not s.get("signup_enabled"):
        return Outcome("pass", {"result": "Sign-up is off", "result_zh": "已关闭自助注册"})
    if s.get("require_admin_approval_after_user_signup") and s.get("domain_allowlist"):
        return Outcome("partial", {"result": "Sign-up is on, with admin approval and a domain allow list",
                                   "result_zh": "已开启注册，但需管理员审批并限制了域名"})
    return Outcome("fail", {"result": "Anyone who can reach GitLab can register an account",
                            "result_zh": "任何能访问 GitLab 的人都可以注册账号"})


# ─── Privileges ───────────────────────────────────────────────────────────────

@check("gitlab.instance_admins", "gitlab", severity="critical", requires=["gitlab.users"], cross=ENTRA,
       defaults={"max": 3},
       title={"en": "Few instance administrators, all with valid corporate identities",
              "zh": "实例管理员数量受控，且身份均有效"},
       summary={"en": "{count} administrators (at most {max} expected); {invalid} without a valid Entra account",
                "zh": "共 {count} 个管理员（建议不超过 {max} 个）；其中 {invalid} 个没有有效的 Entra 账号"},
       remediation={"en": "Remove admin rights from anyone who doesn't administer the instance daily; use a "
                          "separate admin account per person, and turn on Admin Mode.",
                    "zh": "移除非日常运维人员的管理员权限；每人使用单独的管理员账号，并开启 Admin Mode。"})
def instance_admins(facts, p):
    matches = classify_all(facts, p)
    service = {s.lower() for s in p.get("service_accounts") or []}
    admins = [u for u in facts["gitlab.users"] if u["is_admin"] and u["state"] == "active"]
    invalid = {u["username"] for u in admins
               if matches[u["username"]].status in ("disabled", "missing", "non_corporate")
               and u["username"].lower() not in service}
    too_many = len(admins) > p["max"]
    items = [{"_key": u["username"], "username": u["username"], "email": u["email"],
              "identity": matches[u["username"]].status,
              "last_active": (_last_seen(u).date().isoformat() if _last_seen(u) else None),
              "_severity": "critical" if u["username"] in invalid else "high"}
             for u in admins if u["username"] in invalid or too_many]
    return Outcome("fail" if invalid or too_many else "pass",
                   {"count": len(admins), "max": p["max"], "invalid": len(invalid)}, items)


@check("gitlab.maintainer_sprawl", "gitlab", severity="high", requires=["gitlab.group_members", "gitlab.groups"],
       defaults={"max_share": 0.2, "min_members": 5, "max_top_owners": 3},
       title={"en": "Maintainer and Owner roles are the exception", "zh": "Maintainer 和 Owner 角色只授予少数人"},
       summary={"en": "{count} groups give Maintainer or Owner to too many members",
                "zh": "{count} 个群组中拥有 Maintainer 或 Owner 的成员过多"},
       remediation={"en": "Lower most members to Developer; keep Owner on top-level groups to a named few.",
                    "zh": "将大部分成员降为 Developer；顶级群组的 Owner 仅保留少数指定人员。"})
def maintainer_sprawl(facts, p):
    top = {g["path"] for g in facts["gitlab.groups"] if not g.get("parent_id")}
    by_group: dict[str, list[dict]] = {}
    for m in facts["gitlab.group_members"]:
        if m.get("state", "active") == "active":
            by_group.setdefault(m["group"], []).append(m)
    items = []
    for group, members in sorted(by_group.items()):
        high = [m for m in members if (m["access_level"] or 0) >= MAINTAINER]
        owners = [m for m in members if (m["access_level"] or 0) >= OWNER]
        reasons = []
        if len(members) >= p["min_members"] and len(high) / len(members) > p["max_share"]:
            reasons.append(f"{len(high)}/{len(members)} Maintainer+")
        if group in top and len(owners) > p["max_top_owners"]:
            reasons.append(f"{len(owners)} Owners on a top-level group")
        if reasons:
            items.append({"_key": group, "group": group, "members": len(members), "maintainers": len(high),
                          "owners": len(owners), "reason": "; ".join(reasons)})
    return Outcome("fail" if items else "pass", {"count": len(items)}, items)


@check("gitlab.direct_project_members", "gitlab", severity="medium", requires=["gitlab.project_members"],
       title={"en": "Project access is granted through groups", "zh": "项目权限通过群组授予"},
       summary={"en": "{count} memberships give Developer or higher directly on individual projects",
                "zh": "{count} 条成员关系直接在项目上授予了 Developer 及以上权限"},
       remediation={"en": "Move these people into the right group so access is reviewed and removed in one place.",
                    "zh": "将这些人加入相应群组，便于集中评审和回收权限。"})
def direct_project_members(facts, p):
    items = [{"_key": f"{m['project']}:{m['username']}", "project": m["project"], "username": m["username"],
              "role": LEVEL.get(m["access_level"], m["access_level"]), "expires_at": m.get("expires_at")}
             for m in facts["gitlab.project_members"] if (m["access_level"] or 0) >= DEVELOPER]
    return Outcome("partial" if items else "pass", {"count": len(items)}, items)


@check("gitlab.external_member_expiry", "gitlab", severity="medium",
       requires=["gitlab.users", "gitlab.group_members", "gitlab.project_members"], cross=ENTRA,
       title={"en": "Contractor access has an end date", "zh": "外部人员的权限设置了到期日"},
       summary={"en": "{count} memberships of external or non-corporate accounts have no expiry",
                "zh": "{count} 条外部或非公司账号的成员关系没有到期日"},
       remediation={"en": "Set an expiry matching the contract end on every membership of these accounts.",
                    "zh": "为这些账号的每条成员关系设置与合同结束日一致的到期日。"})
def external_member_expiry(facts, p):
    matches = classify_all(facts, p)
    outsiders = {u["username"] for u in _humans(facts)
                 if u["external"] or matches[u["username"]].status == "non_corporate"}
    items = [{"_key": f"{m['group'] or m['project']}:{m['username']}", "username": m["username"],
              "where": m["group"] or m["project"], "role": LEVEL.get(m["access_level"], m["access_level"])}
             for m in facts["gitlab.group_members"] + facts["gitlab.project_members"]
             if m["username"] in outsiders and not m.get("expires_at")]
    return Outcome("fail" if items else "pass", {"count": len(items)}, items)


@check("gitlab.blast_radius", "gitlab", severity="medium",
       requires=["gitlab.users", "gitlab.group_members", "gitlab.project_members", "gitlab.projects"],
       defaults={"max_projects": 100},
       title={"en": "No personal account can write to a large share of the code base",
              "zh": "没有个人账号能写入大量代码仓库"},
       summary={"en": "{count} accounts have Developer or higher on more than {max_projects} projects",
                "zh": "{count} 个账号对超过 {max_projects} 个项目拥有 Developer 及以上权限"},
       remediation={"en": "Split broad group memberships; a stolen account with this reach exposes most repositories.",
                    "zh": "拆分范围过大的群组成员关系；此类账号一旦被盗，大部分仓库都会暴露。"})
def blast_radius(facts, p):
    projects = [pr["path"] for pr in facts["gitlab.projects"]]
    reach: dict[str, set[str]] = {}
    for m in facts["gitlab.group_members"]:
        if (m["access_level"] or 0) >= DEVELOPER:
            prefix = m["group"] + "/"
            reach.setdefault(m["username"], set()).update(x for x in projects if x.startswith(prefix))
    for m in facts["gitlab.project_members"]:
        if (m["access_level"] or 0) >= DEVELOPER:
            reach.setdefault(m["username"], set()).add(m["project"])
    bots = {u["username"] for u in facts["gitlab.users"] if u["bot"]}
    items = [{"_key": user, "username": user, "projects": len(ps)}
             for user, ps in sorted(reach.items(), key=lambda kv: -len(kv[1]))
             if len(ps) > p["max_projects"] and user not in bots]
    return Outcome("partial" if items else "pass", {"count": len(items), "max_projects": p["max_projects"]}, items)


# ─── Tokens, keys and secrets ─────────────────────────────────────────────────

ADMIN_SCOPES = {"sudo", "admin_mode"}
BROAD_SCOPES = {"api", "write_repository"}


@check("gitlab.risky_tokens", "gitlab", severity="high", requires=["gitlab.tokens"], defaults={"max_days": 365},
       title={"en": "Access tokens are short-lived and narrowly scoped", "zh": "访问令牌有效期短、权限窄"},
       summary={"en": "{count} active tokens carry admin scopes, never expire, or have broad scopes and live "
                      "longer than {max_days} days",
                "zh": "{count} 个有效令牌带有管理员权限、永不过期，或权限宽泛且有效期超过 {max_days} 天"},
       remediation={"en": "Set 'Maximum allowable lifetime for access tokens' (Premium) and rotate these tokens with "
                          "the narrowest scope that works; sudo/admin_mode only for named automation.",
                    "zh": "设置「访问令牌最长有效期」（Premium），并以最小可用权限轮换这些令牌；sudo/admin_mode 仅限指定的自动化用途。"})
def risky_tokens(facts, p):
    items = []
    for t in facts["gitlab.tokens"]:
        created, expires = parse_time(t.get("created_at")), parse_time(t.get("expires_at"))
        scopes = set(t.get("scopes") or [])
        reasons = []
        if scopes & ADMIN_SCOPES:
            reasons.append("admin scope")
        if expires is None:
            reasons.append("no expiry")
        elif created and (expires - created).days > p["max_days"] and scopes & BROAD_SCOPES:
            reasons.append(f"broad scope, {(expires - created).days}-day lifetime")
        if not reasons:
            continue
        items.append({"_key": f"token:{t['id']}", "_label": f"{t['username']} · {t['name']} · {', '.join(reasons)}",
                      "_severity": "critical" if scopes & ADMIN_SCOPES else "high",
                      "username": t["username"], "name": t["name"], "scopes": sorted(scopes),
                      "expires_at": t.get("expires_at"), "reason": ", ".join(reasons)})
    return Outcome("fail" if items else "pass", {"count": len(items), "max_days": p["max_days"]}, items)


@check("gitlab.idle_tokens", "gitlab", severity="medium", requires=["gitlab.tokens"], defaults={"days": 90},
       title={"en": "No unused tokens left valid", "zh": "没有闲置但仍有效的令牌"},
       summary={"en": "{count} active tokens haven't been used for {days} days",
                "zh": "{count} 个有效令牌已超过 {days} 天未使用"},
       remediation={"en": "Revoke them; whoever needs one can create a new, short-lived token.",
                    "zh": "吊销这些令牌；确有需要时可重新创建短期令牌。"})
def idle_tokens(facts, p):
    cutoff = utcnow() - timedelta(days=p["days"])
    items = []
    for t in facts["gitlab.tokens"]:
        used, created = parse_time(t.get("last_used_at")), parse_time(t.get("created_at"))
        if (used and used < cutoff) or (not used and created and created < cutoff):
            items.append({"_key": f"token:{t['id']}", "username": t["username"], "name": t["name"],
                          "last_used_at": t.get("last_used_at"), "created_at": t.get("created_at")})
    return Outcome("partial" if items else "pass", {"count": len(items), "days": p["days"]}, items)


@check("gitlab.weak_ssh_keys", "gitlab", severity="medium", requires=["gitlab.ssh_keys"],
       defaults={"min_rsa_bits": 2048},
       title={"en": "SSH keys use strong algorithms", "zh": "SSH 密钥使用强算法"},
       summary={"en": "{count} SSH keys are DSA or RSA shorter than {min_rsa_bits} bits",
                "zh": "{count} 个 SSH 密钥为 DSA 或长度不足 {min_rsa_bits} 位的 RSA"},
       remediation={"en": "Replace with Ed25519 keys, and restrict allowed key types in Admin → Settings → General.",
                    "zh": "替换为 Ed25519 密钥，并在「管理 → 设置 → 通用」中限制允许的密钥类型。"})
def weak_ssh_keys(facts, p):
    items = [{"_key": f"{k['username']}:{k['title']}", "username": k["username"], "title": k["title"],
              "type": k["type"], "bits": k["bits"]}
             for k in facts["gitlab.ssh_keys"]
             if k["type"] == "ssh-dss" or (k["type"] == "ssh-rsa" and k["bits"] and k["bits"] < p["min_rsa_bits"])]
    return Outcome("fail" if items else "pass", {"count": len(items), "min_rsa_bits": p["min_rsa_bits"]}, items)


SECRET_NAME = re.compile(r"TOKEN|SECRET|PASSW|PRIVATE|CREDENTIAL|API_?KEY|ACCESS_?KEY|_KEY$|^KEY", re.I)


@check("gitlab.ci_secret_variables", "gitlab", severity="high", requires=["gitlab.ci_variables"],
       title={"en": "CI/CD secrets are masked and protected", "zh": "CI/CD 密钥变量已遮蔽并受保护"},
       summary={"en": "{count} variables that look like secrets are not masked or not protected",
                "zh": "{count} 个疑似密钥的变量未遮蔽或未受保护"},
       remediation={"en": "Mark them Masked and Protected so they don't print in job logs or reach unprotected "
                          "branches; better, move them to an external secrets manager.",
                    "zh": "设为 Masked 和 Protected，避免出现在作业日志或被未受保护分支读取；更好的做法是迁移到外部密钥管理。"})
def ci_secret_variables(facts, p):
    items = []
    for v in facts["gitlab.ci_variables"]:
        if not SECRET_NAME.search(v.get("key") or ""):
            continue
        gaps = [g for g, ok in (("not masked", v.get("masked") or v.get("type") == "file"),
                                ("not protected", v.get("protected"))) if not ok]
        if gaps:
            items.append({"_key": f"{v['scope']}:{v['owner']}:{v['key']}:{v.get('environment')}", "scope": v["scope"],
                          "owner": v["owner"], "key": v["key"], "gaps": ", ".join(gaps)})
    return Outcome("fail" if items else "pass", {"count": len(items)}, items)


# ─── Data exfiltration and exposure ───────────────────────────────────────────

@check("gitlab.external_mirrors", "gitlab", severity="critical", requires=["gitlab.mirrors"], cross=ENTRA,
       title={"en": "No code is mirrored to outside hosts", "zh": "没有代码被镜像到外部主机"},
       summary={"en": "{count} push mirrors send code to hosts outside the company",
                "zh": "{count} 个推送镜像把代码同步到公司外部的主机"},
       remediation={"en": "Remove unapproved mirrors and find out who set them up; add approved hosts to the allow list.",
                    "zh": "删除未经批准的镜像并查清设置人；已批准的主机加入允许列表。"})
def external_mirrors(facts, p):
    domains = company_domains(facts, p)
    allowed = {h.lower() for h in p.get("allowed_mirror_hosts") or []}
    base_host = (urlparse(p.get("base_url") or "").hostname or "").lower()

    def internal(host: str) -> bool:
        return host == base_host or host in allowed or any(host == d or host.endswith("." + d) for d in domains)
    items = [{"_key": f"{m['project']}:{m['host']}{m['path']}", "project": m["project"], "host": m["host"],
              "path": m["path"], "enabled": m.get("enabled"), "last_success": m.get("last_success")}
             for m in facts["gitlab.mirrors"] if m.get("host") and not internal(m["host"])]
    return Outcome("fail" if items else "pass", {"count": len(items)}, items)


@check("gitlab.personal_forks", "gitlab", severity="medium", requires=["gitlab.projects"],
       title={"en": "Company code isn't forked into personal namespaces", "zh": "公司代码未被派生到个人命名空间"},
       summary={"en": "{count} forks of group projects live in personal namespaces",
                "zh": "{count} 个群组项目的派生位于个人命名空间"},
       remediation={"en": "Delete them or move them into a group; consider blocking forks outside groups.",
                    "zh": "删除或迁移到群组下；考虑禁止向群组外派生。"})
def personal_forks(facts, p):
    group_projects = {pr["path"] for pr in facts["gitlab.projects"] if pr.get("namespace_kind") == "group"}
    items = [{"_key": pr["path"], "project": pr["path"], "forked_from": pr["forked_from"],
              "last_activity_at": pr.get("last_activity_at")}
             for pr in facts["gitlab.projects"]
             if pr.get("namespace_kind") == "user" and pr.get("forked_from") in group_projects]
    return Outcome("partial" if items else "pass", {"count": len(items)}, items)


@check("gitlab.project_visibility", "gitlab", severity="high", requires=["gitlab.projects"],
       title={"en": "Projects are private unless meant to be shared", "zh": "项目默认私有，确需共享的除外"},
       summary={"en": "{count} projects are public or internal (internal = every signed-in user)",
                "zh": "{count} 个项目为公开或内部可见（内部 = 所有登录用户可见）"},
       remediation={"en": "Make them private; add deliberate exceptions to the allow list. Restrict the Public level "
                          "in Admin → Settings → General → Visibility.",
                    "zh": "设为私有；确需共享的加入允许列表。在「管理 → 设置 → 通用 → 可见性」中限制 Public 级别。"})
def project_visibility(facts, p):
    allowed = {x.lower() for x in p.get("public_project_allowlist") or []}
    items = [{"_key": pr["path"], "project": pr["path"], "visibility": pr["visibility"],
              "_severity": "critical" if pr["visibility"] == "public" else "high"}
             for pr in facts["gitlab.projects"]
             if pr["visibility"] in ("public", "internal") and (pr["path"] or "").lower() not in allowed]
    return Outcome("fail" if items else "pass", {"count": len(items)}, items)


# ─── Platform ─────────────────────────────────────────────────────────────────

@check("gitlab.version_patch", "gitlab", severity="critical", requires=["gitlab.version", "gitlab.upstream"],
       defaults={"patch_grace_days": 30, "supported_minors": 3},
       title={"en": "GitLab is on a supported, patched release", "zh": "GitLab 处于受支持且已打补丁的版本"},
       summary={"en": "{result}", "zh": "{result_zh}"},
       remediation={"en": "Upgrade to the latest patch of a supported minor release. GitLab backports security fixes "
                          "to the current and two previous minor versions only.",
                    "zh": "升级到受支持次版本的最新补丁。GitLab 只为当前及前两个次版本提供安全修复。"})
def version_patch(facts, p):
    installed = parse_version(facts["gitlab.upstream"].get("installed") or facts["gitlab.version"].get("version", ""))
    releases = [(parse_version(r["version"]), parse_time(r.get("released"))) for r in facts["gitlab.upstream"]["releases"]]
    releases = [(v, d) for v, d in releases if v]
    if not installed or not releases:
        return Outcome("not_available", {"result": "Version comparison unavailable", "result_zh": "无法比对版本"})
    minors = sorted({v[:2] for v, _ in releases}, reverse=True)[:p["supported_minors"]]
    label = ".".join(map(str, installed))
    supported = ", ".join(".".join(map(str, m)) for m in minors)
    if installed[:2] not in minors:
        return Outcome("fail", {"result": f"{label} no longer gets security fixes (supported: {supported})",
                                "result_zh": f"{label} 已不再获得安全修复（受支持版本：{supported}）"},
                       [{"_key": "version", "installed": label, "supported": supported, "_severity": "critical"}])
    newer = [(v, d) for v, d in releases if v[:2] == installed[:2] and v > installed]
    if not newer:
        return Outcome("pass", {"result": f"{label} is the latest patch of a supported release",
                                "result_zh": f"{label} 是受支持版本的最新补丁"})
    latest = max(v for v, _ in newer)
    dates = [d for _, d in newer if d]
    age = (utcnow() - min(dates)).days if dates else 0
    latest_label = ".".join(map(str, latest))
    return Outcome("fail" if age > p["patch_grace_days"] else "partial",
                   {"result": f"{label} is {len(newer)} patch release(s) behind {latest_label}; "
                              f"the oldest missing patch is {age} days old",
                    "result_zh": f"{label} 落后 {latest_label} 共 {len(newer)} 个补丁版本，最早缺失的补丁已发布 {age} 天"},
                   [{"_key": "version", "installed": label, "latest": latest_label, "days_behind": age}])
