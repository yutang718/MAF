"""Checks that read the same normalised facts from GitHub and GitLab."""
from datetime import timedelta

from govern.checks.base import Outcome, check, ratio_outcome
from govern.timeutil import parse_time, utcnow


def register_shared(kind: str, label: str) -> None:
    @check(f"{kind}.branch_protection", kind, severity="high",
           requires=[f"{kind}.branch_protection"], defaults={"min_approvals": 1},
           title={"en": f"{label} default branches require reviewed changes",
                  "zh": f"{label} 默认分支要求经评审的变更"},
           summary={"en": "{failing} of {total} repositories let changes reach the default branch without review "
                          "or allow force pushes",
                    "zh": "{total} 个仓库中有 {failing} 个允许未经评审的变更进入默认分支，或允许强制推送"},
           remediation={"en": "Protect the default branch: require a merge/pull request with at least one approval, "
                              "and block force pushes and deletion.",
                        "zh": "保护默认分支：要求合并请求且至少一人批准，并禁止强制推送和删除。"})
    def branch_protection(facts, p):
        rows = facts[f"{kind}.branch_protection"]
        failing = []
        for r in rows:
            gaps = []
            if not r.get("requires_pr"):
                gaps.append("no_review_required")
            elif r.get("approvals", 0) < p["min_approvals"]:
                gaps.append("too_few_approvals")
            if not r.get("blocks_force_push"):
                gaps.append("force_push_allowed")
            if not r.get("blocks_deletion"):
                gaps.append("deletion_allowed")
            if gaps:
                failing.append({"repo": r["repo"], "gaps": gaps})
        return ratio_outcome(failing, len(rows), pass_at=1.0, partial_at=0.8)

    @check(f"{kind}.writable_deploy_keys", kind, severity="medium", requires=[f"{kind}.deploy_keys"],
           title={"en": f"{label} deploy keys are read-only", "zh": f"{label} 部署密钥均为只读"},
           summary={"en": "{failing} of {total} deploy keys can push", "zh": "{total} 个部署密钥中有 {failing} 个可推送"},
           remediation={"en": "Replace write deploy keys with read-only keys, or with a scoped app/bot identity.",
                        "zh": "将可写部署密钥换成只读密钥，或改用权限受限的应用/机器人身份。"})
    def writable_deploy_keys(facts, p):
        keys = facts[f"{kind}.deploy_keys"]
        failing = [{"repo": k["repo"], "title": k.get("title"), "created_at": k.get("created_at")}
                   for k in keys if not k.get("read_only")]
        return ratio_outcome(failing, len(keys), pass_at=1.0, partial_at=0.0)

    @check(f"{kind}.audit_log", kind, severity="medium", requires=["audit.events"],
           title={"en": f"{label} audit log is being collected", "zh": f"{label} 审计日志正在采集"},
           summary={"en": "{count} audit events collected since {since}", "zh": "自 {since} 起采集到 {count} 条审计事件"},
           remediation={"en": "Upgrade to a plan with audit log API access, or stream the audit log to this platform.",
                        "zh": "升级到支持审计日志 API 的版本，或将审计日志流式推送到本平台。"})
    def audit_log(facts, p):
        a = facts["audit.events"]
        return Outcome("pass", {"count": a.get("count", 0), "since": a.get("since")})


def overdue(alerts: list[dict], days: int) -> list[dict]:
    cutoff = utcnow() - timedelta(days=days)
    return [a for a in alerts if (parse_time(a.get("created_at")) or utcnow()) < cutoff]
