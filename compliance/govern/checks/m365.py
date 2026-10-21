"""Checks over Microsoft 365 facts (Entra ID, Defender, Intune, Purview)."""
from datetime import timedelta

from govern.checks.base import MAX_ITEMS, Outcome, check, ratio_outcome
from govern.timeutil import parse_time, utcnow

GLOBAL_ADMIN_TEMPLATE = "62e90394-69f5-4237-9190-012177145e10"
HIGH_RISK_SERVICE_SOURCES = {"dataLossPrevention", "microsoftInsiderRiskManagement"}


def _user_ref(u: dict) -> dict:
    return {"name": u.get("displayName") or u.get("userDisplayName"), "upn": u.get("userPrincipalName")}


# ─── Identity ──────────────────────────────────────────────────────────────────

@check("m365.mfa_registered", "m365", severity="high",
       requires=["entra.mfa_registration"], defaults={"pass_at": 1.0, "partial_at": 0.95},
       title={"en": "All member users have MFA registered", "zh": "所有成员用户已注册 MFA"},
       summary={"en": "{failing} of {total} member users have no MFA method registered ({percent}% covered)",
                "zh": "{total} 个成员用户中有 {failing} 个未注册 MFA（覆盖率 {percent}%）"},
       remediation={"en": "Run an MFA registration campaign and enforce registration with Conditional Access.",
                    "zh": "发起 MFA 注册活动，并用条件访问策略强制注册。"})
def mfa_registered(facts, p):
    members = [u for u in facts["entra.mfa_registration"] if u.get("userType") != "guest"]
    failing = [_user_ref(u) for u in members if not u.get("isMfaRegistered")]
    return ratio_outcome(failing, len(members), pass_at=p["pass_at"], partial_at=p["partial_at"])


@check("m365.admin_mfa", "m365", severity="critical", requires=["entra.mfa_registration"],
       title={"en": "Every administrator has MFA registered", "zh": "所有管理员已注册 MFA"},
       summary={"en": "{failing} of {total} administrators have no MFA method registered",
                "zh": "{total} 个管理员中有 {failing} 个未注册 MFA"},
       remediation={"en": "Register phishing-resistant MFA for these admins before anything else.",
                    "zh": "优先为这些管理员注册抗钓鱼的 MFA。"})
def admin_mfa(facts, p):
    admins = [u for u in facts["entra.mfa_registration"] if u.get("isAdmin")]
    failing = [_user_ref(u) for u in admins if not u.get("isMfaRegistered")]
    return ratio_outcome(failing, len(admins), pass_at=1.0, partial_at=1.0)


def _targets_everyone(policy: dict) -> bool:
    cond = policy.get("conditions") or {}
    users = cond.get("users") or {}
    apps = cond.get("applications") or {}
    return "All" in (users.get("includeUsers") or []) and "All" in (apps.get("includeApplications") or [])


def _policy_ref(policy: dict) -> dict:
    users = (policy.get("conditions") or {}).get("users") or {}
    return {"name": policy.get("displayName"), "state": policy.get("state"),
            "excludedUsers": len(users.get("excludeUsers") or []),
            "excludedGroups": len(users.get("excludeGroups") or [])}


@check("m365.ca_require_mfa", "m365", severity="critical",
       requires=["entra.conditional_access", "entra.security_defaults"],
       title={"en": "MFA is enforced for all users and apps", "zh": "已对所有用户和应用强制 MFA"},
       summary={"en": "{result}", "zh": "{result_zh}"},
       remediation={"en": "Create an enabled Conditional Access policy for All users / All cloud apps that requires "
                          "MFA, excluding only break-glass accounts.",
                    "zh": "创建已启用的条件访问策略：所有用户 / 所有云应用，要求 MFA，仅排除紧急访问账号。"})
def ca_require_mfa(facts, p):
    if facts["entra.security_defaults"]:
        return Outcome("pass", {"result": "Security defaults are on, which require MFA registration and use",
                                "result_zh": "已开启安全默认值，会要求注册并使用 MFA"})
    matching = [pol for pol in facts["entra.conditional_access"] if _targets_everyone(pol) and _grants_mfa(pol)]
    enforced = [pol for pol in matching if pol.get("state") == "enabled"]
    if enforced:
        return Outcome("pass", {"result": f"Enforced by {len(enforced)} Conditional Access policy(ies)",
                                "result_zh": f"由 {len(enforced)} 条条件访问策略强制执行"},
                       [_policy_ref(x) for x in enforced])
    if matching:
        return Outcome("partial", {"result": "A matching policy exists but is in report-only mode",
                                   "result_zh": "存在匹配的策略，但处于仅报告模式"},
                       [_policy_ref(x) for x in matching])
    return Outcome("fail", {"result": "No policy requires MFA for all users and apps, and security defaults are off",
                            "result_zh": "没有对所有用户和应用要求 MFA 的策略，且安全默认值未开启"})


def _grants_mfa(policy: dict) -> bool:
    grant = policy.get("grantControls") or {}
    return "mfa" in (grant.get("builtInControls") or []) or bool(grant.get("authenticationStrength"))


@check("m365.legacy_auth_blocked", "m365", severity="high",
       requires=["entra.conditional_access", "entra.security_defaults"],
       title={"en": "Legacy authentication is blocked", "zh": "已阻止旧式身份验证"},
       summary={"en": "{result}", "zh": "{result_zh}"},
       remediation={"en": "Block the 'Exchange ActiveSync' and 'Other clients' client app types for all users.",
                    "zh": "对所有用户阻止「Exchange ActiveSync」和「其他客户端」两类客户端应用。"})
def legacy_auth_blocked(facts, p):
    if facts["entra.security_defaults"]:
        return Outcome("pass", {"result": "Security defaults block legacy authentication",
                                "result_zh": "安全默认值已阻止旧式身份验证"})
    blocking = []
    for pol in facts["entra.conditional_access"]:
        cond = pol.get("conditions") or {}
        apps = set(cond.get("clientAppTypes") or [])
        users = (cond.get("users") or {}).get("includeUsers") or []
        grant = (pol.get("grantControls") or {}).get("builtInControls") or []
        if {"exchangeActiveSync", "other"} <= apps and "All" in users and "block" in grant:
            blocking.append(pol)
    enforced = [x for x in blocking if x.get("state") == "enabled"]
    if enforced:
        return Outcome("pass", {"result": f"Blocked by {len(enforced)} policy(ies)",
                                "result_zh": f"由 {len(enforced)} 条策略阻止"}, [_policy_ref(x) for x in enforced])
    if blocking:
        return Outcome("partial", {"result": "A blocking policy exists but is report-only",
                                   "result_zh": "存在阻止策略，但处于仅报告模式"}, [_policy_ref(x) for x in blocking])
    return Outcome("fail", {"result": "Nothing blocks legacy authentication protocols",
                            "result_zh": "没有任何策略阻止旧式身份验证协议"})


@check("m365.global_admin_count", "m365", severity="high", requires=["entra.directory_roles"],
       defaults={"min": 2, "max": 4},
       title={"en": "Global Administrators are few but not one", "zh": "全局管理员数量适当（不止一个、不宜过多）"},
       summary={"en": "{count} Global Administrators (expected {min}–{max})",
                "zh": "共 {count} 个全局管理员（建议 {min}–{max} 个）"},
       remediation={"en": "Move day-to-day admins to least-privileged roles; keep two break-glass accounts.",
                    "zh": "将日常管理员改为最小权限角色，保留两个紧急访问账号。"})
def global_admin_count(facts, p):
    members = []
    for role in facts["entra.directory_roles"]:
        if role.get("roleTemplateId") == GLOBAL_ADMIN_TEMPLATE:
            members = [m for m in role.get("members", []) if "user" in (m.get("@odata.type") or "user")]
    n = len(members)
    status = "pass" if p["min"] <= n <= p["max"] else ("partial" if n < p["min"] else "fail")
    return Outcome(status, {"count": n, "min": p["min"], "max": p["max"]}, [_user_ref(m) for m in members])


@check("m365.stale_accounts", "m365", severity="medium",
       requires=["entra.users", "entra.sign_in_activity"], defaults={"days": 90},
       title={"en": "No enabled member accounts are dormant", "zh": "没有长期未登录的已启用成员账号"},
       summary={"en": "{failing} of {total} enabled member accounts haven't signed in for {days} days",
                "zh": "{total} 个已启用成员账号中有 {failing} 个超过 {days} 天未登录"},
       remediation={"en": "Disable accounts of leavers and review the rest with their managers.",
                    "zh": "禁用离职人员账号，其余账号与直属主管确认。"})
def stale_accounts(facts, p):
    return _dormant(facts["entra.users"], "Member", p["days"])


@check("m365.stale_guests", "m365", severity="medium",
       requires=["entra.users", "entra.sign_in_activity"], defaults={"days": 90},
       title={"en": "No dormant guest accounts", "zh": "没有长期未登录的来宾账号"},
       summary={"en": "{failing} of {total} enabled guests haven't signed in for {days} days",
                "zh": "{total} 个已启用来宾中有 {failing} 个超过 {days} 天未登录"},
       remediation={"en": "Set up an access review for guests, or remove them.",
                    "zh": "为来宾配置访问评审，或直接移除。"})
def stale_guests(facts, p):
    return _dormant(facts["entra.users"], "Guest", p["days"])


def _dormant(users: list[dict], user_type: str, days: int) -> Outcome:
    cutoff = utcnow() - timedelta(days=days)
    pool = [u for u in users if u.get("accountEnabled") and u.get("userType") == user_type]
    failing = []
    for u in pool:
        last = parse_time(u.get("lastSignIn"))
        created = parse_time(u.get("createdDateTime"))
        if (last and last < cutoff) or (not last and created and created < cutoff):
            failing.append({**_user_ref(u), "lastSignIn": u.get("lastSignIn")})
    return ratio_outcome(failing, len(pool), pass_at=1.0, partial_at=0.95, days=days)


@check("m365.risky_users", "m365", severity="high", requires=["entra.risky_users"],
       title={"en": "No users flagged at risk by Identity Protection", "zh": "没有被身份保护标记为有风险的用户"},
       summary={"en": "{high} high-risk and {other} other at-risk users awaiting remediation",
                "zh": "{high} 个高风险用户、{other} 个其他风险用户待处理"},
       remediation={"en": "Investigate, reset credentials and confirm or dismiss the risk.",
                    "zh": "调查后重置凭据，并确认或消除风险。"})
def risky_users(facts, p):
    users = facts["entra.risky_users"]
    high = [u for u in users if u.get("riskLevel") == "high"]
    status = "fail" if high else ("partial" if users else "pass")
    return Outcome(status, {"high": len(high), "other": len(users) - len(high)},
                   [{**_user_ref(u), "riskLevel": u.get("riskLevel")} for u in users][:MAX_ITEMS])


# ─── Defender ──────────────────────────────────────────────────────────────────

@check("m365.secure_score", "m365", severity="medium", requires=["defender.secure_score"],
       defaults={"pass_at": 70, "partial_at": 50},
       title={"en": "Microsoft Secure Score is healthy", "zh": "Microsoft 安全分数良好"},
       summary={"en": "Secure Score {current} / {max} ({percent}%)", "zh": "安全分数 {current} / {max}（{percent}%）"},
       remediation={"en": "Work through the highest-impact improvement actions in the Defender portal.",
                    "zh": "在 Defender 门户中按影响度处理改进操作。"})
def secure_score(facts, p):
    s = facts["defender.secure_score"]
    current, maximum = s.get("currentScore") or 0, s.get("maxScore") or 0
    pct = round(current / maximum * 100, 1) if maximum else 0.0
    status = "pass" if pct >= p["pass_at"] else ("partial" if pct >= p["partial_at"] else "fail")
    return Outcome(status, {"current": round(current, 1), "max": round(maximum, 1), "percent": pct})


@check("m365.open_high_incidents", "m365", severity="high", requires=["defender.incidents_open"],
       defaults={"sla_days": 3},
       title={"en": "High-severity incidents are handled within SLA", "zh": "高危安全事件在时限内处理"},
       summary={"en": "{overdue} high-severity incidents open longer than {sla_days} days ({open} open in total)",
                "zh": "{overdue} 个高危事件超过 {sla_days} 天未关闭（共 {open} 个未关闭）"},
       remediation={"en": "Assign an owner to each overdue incident and record the outcome.",
                    "zh": "为每个超时事件指定负责人并记录处理结果。"})
def open_high_incidents(facts, p):
    cutoff = utcnow() - timedelta(days=p["sla_days"])
    high = [i for i in facts["defender.incidents_open"] if i.get("severity") == "high"]
    overdue = [i for i in high if (parse_time(i.get("createdDateTime")) or utcnow()) < cutoff]
    status = "fail" if overdue else ("partial" if high else "pass")
    return Outcome(status, {"overdue": len(overdue), "open": len(high), "sla_days": p["sla_days"]},
                   [{"name": i.get("displayName"), "created": i.get("createdDateTime"),
                     "assignedTo": i.get("assignedTo"), "url": i.get("incidentWebUrl")} for i in overdue][:MAX_ITEMS])


@check("m365.data_loss_alerts", "m365", severity="high", requires=["defender.alerts_open"],
       title={"en": "No unresolved data loss or insider-risk alerts", "zh": "没有未处理的数据泄露或内部风险告警"},
       summary={"en": "{high} high and {other} other open DLP / insider-risk alerts",
                "zh": "未处理的 DLP / 内部风险告警：高危 {high} 个，其他 {other} 个"},
       remediation={"en": "Triage these in Purview; tune policies that produce false positives.",
                    "zh": "在 Purview 中分诊处理；调整产生误报的策略。"})
def data_loss_alerts(facts, p):
    alerts = [a for a in facts["defender.alerts_open"] if a.get("serviceSource") in HIGH_RISK_SERVICE_SOURCES]
    high = [a for a in alerts if a.get("severity") == "high"]
    status = "fail" if high else ("partial" if alerts else "pass")
    return Outcome(status, {"high": len(high), "other": len(alerts) - len(high)},
                   [{"name": a.get("title"), "severity": a.get("severity"), "created": a.get("createdDateTime"),
                     "url": a.get("alertWebUrl")} for a in alerts][:MAX_ITEMS])


@check("m365.defender_sensor_health", "m365", severity="high", requires=["defender.machines"],
       title={"en": "Defender for Endpoint sensors are reporting", "zh": "Defender for Endpoint 传感器正常上报"},
       summary={"en": "{failing} of {total} onboarded devices are not reporting as active ({percent}% healthy)",
                "zh": "{total} 台已接入设备中有 {failing} 台未正常上报（健康率 {percent}%）"},
       remediation={"en": "Fix sensors on impaired devices; offboard devices that were retired.",
                    "zh": "修复传感器异常的设备；对已报废设备执行下线。"})
def defender_sensor_health(facts, p):
    machines = [m for m in facts["defender.machines"] if m.get("onboardingStatus", "Onboarded") == "Onboarded"]
    failing = [{"name": m.get("computerDnsName"), "health": m.get("healthStatus"), "lastSeen": m.get("lastSeen")}
               for m in machines if m.get("healthStatus") != "Active"]
    return ratio_outcome(failing, len(machines), pass_at=0.98, partial_at=0.9)


@check("m365.defender_exposure", "m365", severity="high", requires=["defender.machines"],
       title={"en": "No devices at high exposure", "zh": "没有高暴露等级的设备"},
       summary={"en": "{failing} of {total} devices have a high exposure level",
                "zh": "{total} 台设备中有 {failing} 台暴露等级为高"},
       remediation={"en": "Apply the security recommendations for these devices in Defender Vulnerability Management.",
                    "zh": "在 Defender 漏洞管理中为这些设备落实安全建议。"})
def defender_exposure(facts, p):
    machines = facts["defender.machines"]
    failing = [{"name": m.get("computerDnsName"), "exposure": m.get("exposureLevel"), "risk": m.get("riskScore")}
               for m in machines if m.get("exposureLevel") == "High"]
    return ratio_outcome(failing, len(machines), pass_at=1.0, partial_at=0.95)


# ─── Intune ────────────────────────────────────────────────────────────────────

def _device_ref(d: dict) -> dict:
    return {"name": d.get("deviceName"), "os": d.get("operatingSystem"), "user": d.get("userPrincipalName")}


@check("m365.device_compliance", "m365", severity="high", requires=["intune.devices"],
       defaults={"pass_at": 0.95, "partial_at": 0.85},
       title={"en": "Managed devices meet compliance policy", "zh": "受管设备满足合规策略"},
       summary={"en": "{failing} of {total} managed devices are not compliant ({percent}% compliant)",
                "zh": "{total} 台受管设备中有 {failing} 台不合规（合规率 {percent}%）"},
       remediation={"en": "Use Conditional Access to require a compliant device, and chase the non-compliant ones.",
                    "zh": "用条件访问要求合规设备，并跟进不合规设备。"})
def device_compliance(facts, p):
    devices = facts["intune.devices"]
    failing = [{**_device_ref(d), "state": d.get("complianceState")}
               for d in devices if d.get("complianceState") != "compliant"]
    return ratio_outcome(failing, len(devices), pass_at=p["pass_at"], partial_at=p["partial_at"])


@check("m365.device_encryption", "m365", severity="high", requires=["intune.devices"],
       title={"en": "Managed devices are encrypted", "zh": "受管设备已加密"},
       summary={"en": "{failing} of {total} managed devices report no disk encryption",
                "zh": "{total} 台受管设备中有 {failing} 台未启用磁盘加密"},
       remediation={"en": "Deploy BitLocker / FileVault policies and require encryption in compliance policy.",
                    "zh": "下发 BitLocker / FileVault 策略，并在合规策略中要求加密。"})
def device_encryption(facts, p):
    devices = facts["intune.devices"]
    failing = [_device_ref(d) for d in devices if not d.get("isEncrypted")]
    return ratio_outcome(failing, len(devices), pass_at=1.0, partial_at=0.95)


@check("m365.jailbroken_devices", "m365", severity="high", requires=["intune.devices"],
       title={"en": "No jailbroken or rooted devices", "zh": "没有越狱或 Root 的设备"},
       summary={"en": "{failing} jailbroken or rooted devices among {total}",
                "zh": "{total} 台设备中有 {failing} 台已越狱或 Root"},
       remediation={"en": "Block these devices and wipe corporate data from them.",
                    "zh": "阻止这些设备访问，并清除其中的企业数据。"})
def jailbroken_devices(facts, p):
    devices = facts["intune.devices"]
    failing = [_device_ref(d) for d in devices if str(d.get("jailBroken")).lower() == "true"]
    return ratio_outcome(failing, len(devices), pass_at=1.0, partial_at=1.0)


@check("m365.stale_devices", "m365", severity="low", requires=["intune.devices"], defaults={"days": 30},
       title={"en": "Device inventory is current", "zh": "设备清单保持最新"},
       summary={"en": "{failing} of {total} devices haven't checked in for {days} days",
                "zh": "{total} 台设备中有 {failing} 台超过 {days} 天未同步"},
       remediation={"en": "Retire devices that are gone; set up automatic clean-up rules.",
                    "zh": "停用已不存在的设备，并配置自动清理规则。"})
def stale_devices(facts, p):
    cutoff = utcnow() - timedelta(days=p["days"])
    devices = facts["intune.devices"]
    failing = [{**_device_ref(d), "lastSync": d.get("lastSyncDateTime")} for d in devices
               if (parse_time(d.get("lastSyncDateTime")) or cutoff) < cutoff]
    return ratio_outcome(failing, len(devices), pass_at=0.98, partial_at=0.9, days=p["days"])


_PLATFORM_KEYS = {"windows": "Windows", "ios": "iOS", "macos": "macOS", "android": "Android"}


def _platform(name: str) -> str | None:
    name = (name or "").lower()
    if name == "ipados":
        return "iOS"
    for key, label in _PLATFORM_KEYS.items():
        if key in name:
            return label
    return None


@check("m365.compliance_policy_coverage", "m365", severity="medium",
       requires=["intune.devices", "intune.compliance_policies"],
       title={"en": "Every device platform in use has an assigned compliance policy",
              "zh": "每个在用的设备平台都有已分配的合规策略"},
       summary={"en": "{failing} of {total} platforms in use have no assigned compliance policy",
                "zh": "{total} 个在用平台中有 {failing} 个没有已分配的合规策略"},
       remediation={"en": "Create and assign a compliance policy for each listed platform.",
                    "zh": "为列出的每个平台创建并分配合规策略。"})
def compliance_policy_coverage(facts, p):
    in_use = {_platform(d.get("operatingSystem")) for d in facts["intune.devices"]} - {None}
    covered = {_platform(pol["type"].removeprefix("#microsoft.graph."))
               for pol in facts["intune.compliance_policies"] if pol.get("assigned")} - {None}
    failing = [{"platform": plat} for plat in sorted(in_use - covered)]
    return ratio_outcome(failing, len(in_use), pass_at=1.0, partial_at=1.0)


# ─── Purview ───────────────────────────────────────────────────────────────────

@check("m365.sensitivity_labels", "m365", severity="medium", requires=["purview.sensitivity_labels"],
       title={"en": "Sensitivity labels are defined", "zh": "已定义敏感度标签"},
       summary={"en": "{count} active sensitivity labels", "zh": "共 {count} 个启用的敏感度标签"},
       remediation={"en": "Define a classification scheme in Purview and publish labels to users.",
                    "zh": "在 Purview 中定义分级方案并向用户发布标签。"})
def sensitivity_labels(facts, p):
    active = [lbl for lbl in facts["purview.sensitivity_labels"] if lbl.get("isActive", True)]
    return Outcome("pass" if active else "fail", {"count": len(active)}, [{"name": x.get("name")} for x in active])


@check("m365.retention_labels", "m365", severity="medium", requires=["purview.retention_labels"],
       title={"en": "Retention labels are defined", "zh": "已定义保留标签"},
       summary={"en": "{count} retention labels", "zh": "共 {count} 个保留标签"},
       remediation={"en": "Create retention labels matching your records schedule (HIPAA documentation: 6 years).",
                    "zh": "按记录保留计划创建保留标签（HIPAA 文档要求保留 6 年）。"})
def retention_labels(facts, p):
    labels = facts["purview.retention_labels"]
    return Outcome("pass" if labels else "fail", {"count": len(labels)},
                   [{"name": x.get("displayName"), "duration": x.get("retentionDuration")} for x in labels])
