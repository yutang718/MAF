"""Checks over GitLab group facts."""
from datetime import timedelta

from govern.checks.base import MAX_ITEMS, Outcome, check, ratio_outcome
from govern.checks.codehost import register_shared
from govern.connectors.gitlab import OWNER
from govern.timeutil import parse_time, utcnow

register_shared("gitlab", "GitLab")


@check("gitlab.group_2fa_required", "gitlab", severity="critical", requires=["gitlab.group"],
       title={"en": "The group requires two-factor authentication", "zh": "群组要求双因素认证"},
       summary={"en": "{result}", "zh": "{result_zh}"},
       remediation={"en": "Group → Settings → General → Permissions → Require all users in this group to set up 2FA.",
                    "zh": "群组 → 设置 → 通用 → 权限 → 要求群组所有用户设置 2FA。"})
def group_2fa_required(facts, p):
    g = facts["gitlab.group"]
    if g.get("require_two_factor_authentication"):
        return Outcome("pass", {"result": f"Required, {g.get('two_factor_grace_period')} h grace period",
                                "result_zh": f"已要求，宽限期 {g.get('two_factor_grace_period')} 小时"})
    return Outcome("fail", {"result": "2FA is not required", "result_zh": "未要求启用 2FA"})


@check("gitlab.members_without_2fa", "gitlab", severity="high",
       requires=["gitlab.members", "gitlab.members_2fa_disabled"],
       title={"en": "Every member has 2FA enabled", "zh": "所有成员已启用 2FA"},
       summary={"en": "{failing} of {total} members have 2FA disabled", "zh": "{total} 个成员中有 {failing} 个未启用 2FA"},
       remediation={"en": "Require 2FA for the group; follow up with these members.",
                    "zh": "为群组强制 2FA，并跟进这些成员。"})
def members_without_2fa(facts, p):
    failing = [{"username": u} for u in facts["gitlab.members_2fa_disabled"]]
    return ratio_outcome(failing, len(facts["gitlab.members"]), pass_at=1.0, partial_at=0.95)


@check("gitlab.owner_count", "gitlab", severity="medium", requires=["gitlab.members"],
       defaults={"min": 2, "max": 5},
       title={"en": "Group owners are few but not one", "zh": "群组所有者数量适当"},
       summary={"en": "{count} group owners (expected {min}–{max})", "zh": "共 {count} 个群组所有者（建议 {min}–{max} 个）"},
       remediation={"en": "Lower owners who don't need it to Maintainer.", "zh": "将无需所有者权限的人降为 Maintainer。"})
def owner_count(facts, p):
    owners = [m for m in facts["gitlab.members"] if m.get("access_level") == OWNER and m.get("state") != "blocked"]
    n = len(owners)
    status = "pass" if p["min"] <= n <= p["max"] else ("partial" if n < p["min"] else "fail")
    return Outcome(status, {"count": n, "min": p["min"], "max": p["max"]}, [{"username": m["username"]} for m in owners])


@check("gitlab.public_projects", "gitlab", severity="high", requires=["gitlab.projects"],
       title={"en": "No unexpected public or internal projects", "zh": "没有意外公开或内部可见的项目"},
       summary={"en": "{failing} projects are public or internal and not on the allow list",
                "zh": "{failing} 个项目为公开或内部可见且不在允许名单中"},
       remediation={"en": "Set these projects to Private, or add intentional ones to the allow list.",
                    "zh": "将这些项目设为私有；确需公开的加入允许名单。"})
def public_projects(facts, p):
    allowed = {x.lower() for x in p.get("public_project_allowlist", [])}
    failing = [{"repo": pr["path"], "visibility": pr["visibility"]} for pr in facts["gitlab.projects"]
               if pr["visibility"] in ("public", "internal") and (pr["path"] or "").lower() not in allowed]
    return Outcome("fail" if failing else "pass", {"failing": len(failing)}, failing[:MAX_ITEMS])


@check("gitlab.token_expiry", "gitlab", severity="medium", requires=["gitlab.group_tokens"],
       defaults={"max_days": 365},
       title={"en": "Group access tokens expire within a year", "zh": "群组访问令牌在一年内过期"},
       summary={"en": "{failing} of {total} active group tokens have no expiry or expire after {max_days} days",
                "zh": "{total} 个有效群组令牌中有 {failing} 个无过期时间或有效期超过 {max_days} 天"},
       remediation={"en": "Rotate long-lived tokens and give new ones the narrowest scope and shortest life that works.",
                    "zh": "轮换长期令牌，新令牌使用最小权限和最短可用有效期。"})
def token_expiry(facts, p):
    limit = utcnow() + timedelta(days=p["max_days"])
    tokens = facts["gitlab.group_tokens"]
    failing = [{"name": t["name"], "scopes": t.get("scopes"), "expires_at": t.get("expires_at")} for t in tokens
               if not t.get("expires_at") or (parse_time(t["expires_at"]) or limit) > limit]
    return ratio_outcome(failing, len(tokens), pass_at=1.0, partial_at=0.8, max_days=p["max_days"])


@check("gitlab.forking_outside_group", "gitlab", severity="low", requires=["gitlab.group"],
       title={"en": "Projects can't be forked outside the group", "zh": "禁止将项目派生到群组之外"},
       summary={"en": "{result}", "zh": "{result_zh}"},
       remediation={"en": "Enable 'Prevent forking outside the group' (Premium).", "zh": "开启「禁止在群组外派生」（Premium）。"})
def forking_outside_group(facts, p):
    value = facts["gitlab.group"].get("prevent_forking_outside_group")
    if value is None:
        return Outcome("not_available", {"result": "Setting not exposed on this tier",
                                         "result_zh": "当前版本不提供此设置"})
    return Outcome("pass" if value else "fail",
                   {"result": "Forking outside the group is " + ("blocked" if value else "allowed"),
                    "result_zh": "群组外派生已" + ("禁止" if value else "允许")})
