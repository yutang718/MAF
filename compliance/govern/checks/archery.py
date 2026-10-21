"""Checks over Archery facts: masking, privileges, change review."""
from datetime import date, timedelta

from govern.checks.base import Outcome, check, ratio_outcome
from govern.timeutil import parse_time, utcnow


def _on(config: dict, key: str) -> bool | None:
    value = config.get(key)
    if value is None:
        return None
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def _config_check(key: str, facts, on_text: tuple[str, str], off_text: tuple[str, str]) -> Outcome:
    value = _on(facts["archery.config"], key)
    if value is None:
        return Outcome("fail", {"result": f"'{key}' is not configured", "result_zh": f"未配置「{key}」"})
    en, zh = on_text if value else off_text
    return Outcome("pass" if value else "fail", {"result": en, "result_zh": zh})


@check("archery.masking_enabled", "archery", severity="high", requires=["archery.config"],
       title={"en": "Query results are masked", "zh": "已开启查询结果脱敏"},
       summary={"en": "{result}", "zh": "{result_zh}"},
       remediation={"en": "System settings → enable data masking (data_masking).",
                    "zh": "系统配置 → 开启数据脱敏（data_masking）。"})
def masking_enabled(facts, p):
    return _config_check("data_masking", facts, ("Data masking is on", "数据脱敏已开启"),
                         ("Data masking is off: queries return raw values", "数据脱敏未开启：查询返回原始数据"))


@check("archery.masking_enforced", "archery", severity="high", requires=["archery.config"],
       title={"en": "Queries are refused when masking can't be applied", "zh": "脱敏失败时拒绝查询"},
       summary={"en": "{result}", "zh": "{result_zh}"},
       remediation={"en": "System settings → enable query_check so a masking failure blocks the result.",
                    "zh": "系统配置 → 开启 query_check，脱敏失败时阻止返回结果。"})
def masking_enforced(facts, p):
    return _config_check("query_check", facts, ("Masking failures block the query", "脱敏失败会阻止查询"),
                         ("A query whose masking fails still returns data", "脱敏失败的查询仍会返回数据"))


@check("archery.select_star_disabled", "archery", severity="low", requires=["archery.config"],
       title={"en": "SELECT * is disabled in queries", "zh": "查询中禁止 SELECT *"},
       summary={"en": "{result}", "zh": "{result_zh}"},
       remediation={"en": "System settings → enable disable_star.", "zh": "系统配置 → 开启 disable_star。"})
def select_star_disabled(facts, p):
    return _config_check("disable_star", facts, ("SELECT * is refused", "已禁止 SELECT *"),
                         ("SELECT * is allowed", "允许 SELECT *"))


def _masked_index(masking: list[dict]) -> set[tuple]:
    return {(m["instance"], (m["schema"] or "").lower(), (m["table"] or "").lower(), (m["column"] or "").lower())
            for m in masking if m.get("active")}


@check("archery.unmasked_sensitive_columns", "archery", severity="high",
       requires=["archery.sensitive_columns", "archery.masking_columns"],
       title={"en": "Every sensitive column has a masking rule", "zh": "所有敏感字段都配置了脱敏规则"},
       summary={"en": "{failing} of {total} sensitive columns found have no active masking rule in Archery",
                "zh": "发现的 {total} 个敏感字段中有 {failing} 个未在 Archery 配置有效的脱敏规则"},
       remediation={"en": "Add these columns under Data masking → Masking fields, with a rule matching their type.",
                    "zh": "在「数据脱敏 → 脱敏字段」中添加这些字段，并选择与其类型匹配的规则。"})
def unmasked_sensitive_columns(facts, p):
    masked = _masked_index(facts["archery.masking_columns"])
    cols = facts["archery.sensitive_columns"]
    failing = [{"instance": c["instance"], "column": f"{c['schema']}.{c['table']}.{c['column']}",
                "categories": c["categories"], "by": c.get("by"), "sample": c.get("sample_entities")}
               for c in cols
               if (c["instance"], c["schema"].lower(), c["table"].lower(), c["column"].lower()) not in masked
               and "credential" not in c["categories"]]
    # Credentials shouldn't be masked for display — they shouldn't be queryable at all.
    total = sum(1 for c in cols if "credential" not in c["categories"])
    return ratio_outcome(failing, total, pass_at=1.0, partial_at=0.9)


@check("archery.queryable_credentials", "archery", severity="medium", requires=["archery.sensitive_columns"],
       title={"en": "No password or secret columns found in queryable databases",
              "zh": "可查询的数据库中没有密码或密钥字段"},
       summary={"en": "{count} columns look like they hold passwords, tokens or keys",
                "zh": "{count} 个字段疑似存放密码、令牌或密钥"},
       remediation={"en": "Confirm these hold only salted hashes, and exclude the tables from query privileges.",
                    "zh": "确认这些字段只保存加盐哈希，并将相关表排除在查询权限之外。"})
def queryable_credentials(facts, p):
    hits = [{"instance": c["instance"], "column": f"{c['schema']}.{c['table']}.{c['column']}"}
            for c in facts["archery.sensitive_columns"] if "credential" in c["categories"]]
    return Outcome("partial" if hits else "pass", {"count": len(hits)}, hits)


@check("archery.superusers", "archery", severity="medium", requires=["archery.users"], defaults={"max": 3},
       title={"en": "Few Archery superusers", "zh": "Archery 超级管理员数量受控"},
       summary={"en": "{count} active superusers (at most {max} expected)",
                "zh": "共 {count} 个有效超级管理员（建议不超过 {max} 个）"},
       remediation={"en": "Give operators a role-based permission group instead of superuser.",
                    "zh": "为运维人员分配基于角色的权限组，而非超级管理员。"})
def superusers(facts, p):
    supers = [u for u in facts["archery.users"] if u["is_superuser"] and u["is_active"]]
    return Outcome("pass" if len(supers) <= p["max"] else "fail", {"count": len(supers), "max": p["max"]},
                   [{"username": u["username"], "last_login": u["last_login"]} for u in supers])


@check("archery.dormant_users", "archery", severity="medium", requires=["archery.users"], defaults={"days": 90},
       title={"en": "No dormant Archery accounts", "zh": "没有长期未登录的 Archery 账号"},
       summary={"en": "{failing} of {total} active accounts haven't logged in for {days} days",
                "zh": "{total} 个有效账号中有 {failing} 个超过 {days} 天未登录"},
       remediation={"en": "Deactivate these accounts; they keep their query privileges until you do.",
                    "zh": "停用这些账号；在停用前它们仍保有查询权限。"})
def dormant_users(facts, p):
    cutoff = utcnow() - timedelta(days=p["days"])
    active = [u for u in facts["archery.users"] if u["is_active"]]
    failing = []
    for u in active:
        last = parse_time(u["last_login"]) or parse_time(u["date_joined"])
        if last is None or last < cutoff:
            failing.append({"username": u["username"], "last_login": u["last_login"]})
    return ratio_outcome(failing, len(active), pass_at=1.0, partial_at=0.9, days=p["days"])


@check("archery.long_privileges", "archery", severity="medium", requires=["archery.query_privileges"],
       defaults={"max_days": 90},
       title={"en": "Query privileges are time-limited", "zh": "查询权限设置了有限期限"},
       summary={"en": "{failing} of {total} active query privileges run more than {max_days} days ahead",
                "zh": "{total} 个有效查询权限中有 {failing} 个有效期超过 {max_days} 天"},
       remediation={"en": "Shorten these privileges; grant long-term access only through reviewed roles.",
                    "zh": "缩短这些权限的期限；长期访问仅通过经评审的角色授予。"})
def long_privileges(facts, p):
    limit = date.today() + timedelta(days=p["max_days"])
    privs = facts["archery.query_privileges"]
    failing = []
    for x in privs:
        try:
            valid = date.fromisoformat(str(x["valid_date"])[:10])
        except ValueError:
            continue
        if valid > limit:
            failing.append({k: x[k] for k in ("user", "instance", "db", "table", "valid_date", "level")})
    return ratio_outcome(failing, len(privs), pass_at=1.0, partial_at=0.9, max_days=p["max_days"])


@check("archery.database_wide_privileges", "archery", severity="low", requires=["archery.query_privileges"],
       title={"en": "Query access is granted per table, not per database", "zh": "查询权限按表授予，而非整库授予"},
       summary={"en": "{failing} of {total} active query privileges cover a whole database",
                "zh": "{total} 个有效查询权限中有 {failing} 个覆盖整个数据库"},
       remediation={"en": "Replace database-level grants with the specific tables people need.",
                    "zh": "将整库授权替换为具体所需的表。"})
def database_wide_privileges(facts, p):
    privs = facts["archery.query_privileges"]
    failing = [{k: x[k] for k in ("user", "instance", "db", "valid_date")} for x in privs if x["level"] == "database"]
    return ratio_outcome(failing, len(privs), pass_at=1.0, partial_at=0.8)


@check("archery.change_segregation", "archery", severity="high", requires=["archery.change_review"],
       title={"en": "SQL changes are approved by someone other than the submitter",
              "zh": "SQL 变更由提交人以外的人审批"},
       summary={"en": "{failing} of {total} changes executed in 30 days were self-approved or had no approval",
                "zh": "近 30 天执行的 {total} 个变更中有 {failing} 个为自审自批或无审批记录"},
       remediation={"en": "Configure approval flows so the submitter's group can't approve its own tickets.",
                    "zh": "配置审批流程，使提交人所在组无法审批自己的工单。"})
def change_segregation(facts, p):
    rows = facts["archery.change_review"]
    failing = [{"id": r["id"], "title": r["title"], "engineer": r["engineer"], "approvers": r["approvers"],
                "issue": "self_approved" if r["self_approved"] else "no_approval"}
               for r in rows if r["self_approved"] or r.get("unapproved")]
    return ratio_outcome(failing, len(rows), pass_at=1.0, partial_at=0.95)


@check("archery.high_risk_changes", "archery", severity="high", requires=["archery.change_review"],
       title={"en": "No unbounded or destructive SQL executed", "zh": "未执行无条件或破坏性的 SQL"},
       summary={"en": "{failing} of {total} changes executed in 30 days contained critical-risk SQL",
                "zh": "近 30 天执行的 {total} 个变更中有 {failing} 个包含严重风险 SQL"},
       remediation={"en": "Review each change: confirm it was intended and a backup existed; tighten review rules.",
                    "zh": "逐一复核：确认是有意为之且有备份；收紧审核规则。"})
def high_risk_changes(facts, p):
    rows = facts["archery.change_review"]
    failing = [{"id": r["id"], "title": r["title"], "engineer": r["engineer"],
                "risk": [x["code"] for x in r["risk"] if x["severity"] == "critical"]}
               for r in rows if r.get("worst") == "critical"]
    return ratio_outcome(failing, len(rows), pass_at=1.0, partial_at=0.98)


@check("archery.query_audit", "archery", severity="medium", requires=["archery.query_activity"],
       title={"en": "Database queries are logged", "zh": "数据库查询有审计日志"},
       summary={"en": "{queries} queries logged in the last 7 days", "zh": "近 7 天记录了 {queries} 次查询"},
       remediation={"en": "Make sure queries go through Archery and that query logging hasn't been disabled.",
                    "zh": "确认查询都经由 Archery，且查询日志未被关闭。"})
def query_audit(facts, p):
    q = facts["archery.query_activity"]
    return Outcome("pass" if q["queries"] else "partial", {"queries": q["queries"]})
