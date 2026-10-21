"""Security-operations checks over Microsoft 365: vulnerability SLAs, endpoint protection, data loss, identity."""
from collections import Counter

from govern.checks.base import Outcome, check
from govern.timeutil import parse_time, utcnow

SEVERITY = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
PRIVILEGED_ROLE_TEMPLATES = {
    "62e90394-69f5-4237-9190-012177145e10": "Global Administrator",
    "e8611ab8-c189-46e8-94e1-60213ab1f814": "Privileged Role Administrator",
    "7be44c8a-adaf-4e2a-84d6-ab2649e08a13": "Privileged Authentication Administrator",
    "194ae4cb-b126-40b2-bd5b-6091b380977d": "Security Administrator",
    "29232cdf-9323-42fd-ade2-1d097af3e4de": "Exchange Administrator",
    "f28a1f50-f6e7-4571-818b-6a12f2af6b6c": "SharePoint Administrator",
    "fe930be7-5e62-47db-91af-98c3a49a38b1": "User Administrator",
    "b1be1c3e-b65d-4f19-8427-f6fa0d97feb9": "Conditional Access Administrator",
    "9b895d92-2cd3-44c7-9d02-a6ac2d5ea5c3": "Application Administrator",
    "158c047a-c907-4556-b7ef-446551a6b5f7": "Cloud Application Administrator",
    "3a2c62db-5318-420d-8d74-23affee5d9d5": "Intune Administrator",
}
PRIVILEGED_ROLE_NAMES = set(PRIVILEGED_ROLE_TEMPLATES.values())
# Application permissions that let an app read or change every mailbox, file or the directory itself.
HIGH_RISK_APP_PERMISSIONS = {
    "Mail.Read", "Mail.ReadWrite", "Mail.Send", "MailboxSettings.ReadWrite", "full_access_as_app",
    "Files.Read.All", "Files.ReadWrite.All", "Sites.Read.All", "Sites.ReadWrite.All", "Sites.FullControl.All",
    "Directory.ReadWrite.All", "RoleManagement.ReadWrite.Directory", "AppRoleAssignment.ReadWrite.All",
    "Application.ReadWrite.All", "User.ReadWrite.All", "Group.ReadWrite.All", "Policy.ReadWrite.ConditionalAccess",
}
DLP_TRIAGE_DAYS = {"high": 1, "medium": 3, "low": 7, "informational": 7}


# ─── Vulnerability management ─────────────────────────────────────────────────

def _vuln_items(facts, exploited_only: bool) -> list[dict]:
    kev = set(facts.get("threat.kev") or [])
    items = []
    for r in facts["defender.vulnerabilities"]:
        cve = r.get("CveId")
        in_kev = cve in kev
        exploited = bool(r.get("IsExploitAvailable")) or in_kev
        if exploited_only and not exploited:
            continue
        severity = SEVERITY.get((r.get("VulnerabilitySeverityLevel") or "").lower(), "medium")
        software = f"{r.get('SoftwareName')} {r.get('SoftwareVersion')}".strip()
        items.append({"_key": f"{r.get('DeviceId')}|{cve}", "_severity": "critical" if exploited else severity,
                      "_exploited": exploited, "_label": f"{r.get('DeviceName')} · {cve} · {software}",
                      "device": r.get("DeviceName"), "cve": cve, "software": software, "severity": severity,
                      "cvss": r.get("CvssScore"), "exploit": bool(r.get("IsExploitAvailable")), "kev": in_kev,
                      "fix": r.get("RecommendedSecurityUpdate"), "published": r.get("PublishedDate")})
    return items


def _vuln_outcome(items: list[dict]) -> Outcome:
    # The status shown is recomputed from finding ages (posture.yaml marks these SLA-graded).
    by = Counter(i["_severity"] for i in items)
    return Outcome("partial" if items else "pass",
                   {"open": len(items), "critical": by["critical"], "high": by["high"], "medium": by["medium"],
                    "low": by["low"], "devices": len({i["device"] for i in items})}, items)


@check("m365.vuln_sla", "m365", severity="high", requires=["defender.vulnerabilities"],
       title={"en": "Vulnerabilities are fixed within SLA", "zh": "漏洞在修复时限内完成修复"},
       summary={"en": "{open} open vulnerabilities on {devices} devices (critical {critical}, high {high}, "
                      "medium {medium}, low {low})",
                "zh": "{devices} 台设备上有 {open} 个未修复漏洞（严重 {critical}、高 {high}、中 {medium}、低 {low}）"},
       remediation={"en": "Patch by due date: exploited/KEV 7 days, critical 15, high 30, medium 90, low 180. Use "
                          "Defender's security recommendations and Intune update rings; record exceptions for "
                          "systems that can't be patched.",
                    "zh": "按到期日修复：已被利用/KEV 7 天、严重 15 天、高危 30 天、中危 90 天、低危 180 天。"
                          "借助 Defender 安全建议和 Intune 更新通道；无法修补的系统登记例外。"})
def vuln_sla(facts, p):
    return _vuln_outcome(_vuln_items(facts, exploited_only=False))


@check("m365.exploited_vulns", "m365", severity="critical", requires=["defender.vulnerabilities"],
       title={"en": "No exploitable or KEV-listed vulnerabilities left open", "zh": "没有未修复的可利用或 KEV 漏洞"},
       summary={"en": "{open} vulnerabilities with a public exploit or on the CISA KEV list, on {devices} devices",
                "zh": "{devices} 台设备上有 {open} 个存在公开利用或列入 CISA KEV 的漏洞"},
       remediation={"en": "Patch within 7 days or isolate the device; these are being used in real attacks.",
                    "zh": "7 天内修补或隔离设备；这些漏洞正被用于真实攻击。"})
def exploited_vulns(facts, p):
    return _vuln_outcome(_vuln_items(facts, exploited_only=True))


@check("m365.end_of_support", "m365", severity="high", requires=["defender.eos_software"],
       title={"en": "No end-of-support software in use", "zh": "没有在用的停止支持软件"},
       summary={"en": "{eos} installs of software past end of support, {upcoming} reaching it soon, on {devices} devices",
                "zh": "{devices} 台设备上有 {eos} 个已停止支持、{upcoming} 个即将停止支持的软件安装"},
       remediation={"en": "Upgrade or remove; end-of-support software gets no security fixes.",
                    "zh": "升级或卸载；停止支持的软件不再获得安全修复。"})
def end_of_support(facts, p):
    items = []
    for r in facts["defender.eos_software"]:
        status = r.get("EndOfSupportStatus") or ""
        upcoming = "upcoming" in status.lower()
        items.append({"_key": f"{r.get('DeviceId')}|{r.get('SoftwareName')}|{r.get('SoftwareVersion')}",
                      "_severity": "medium" if upcoming else "high", "device": r.get("DeviceName"),
                      "software": f"{r.get('SoftwareName')} {r.get('SoftwareVersion')}", "status": status,
                      "date": r.get("EndOfSupportDate")})
    upcoming = sum(1 for i in items if i["_severity"] == "medium")
    return Outcome("fail" if len(items) > upcoming else ("partial" if items else "pass"),
                   {"eos": len(items) - upcoming, "upcoming": upcoming, "devices": len({i["device"] for i in items})},
                   items)


# ─── Endpoint protection ──────────────────────────────────────────────────────

def _norm_name(name: str | None) -> str:
    return (name or "").lower().split(".")[0]


@check("m365.mde_onboarding_gap", "m365", severity="high", requires=["intune.devices", "defender.machines"],
       title={"en": "Every managed device is protected by Defender for Endpoint", "zh": "所有受管设备都已接入 Defender"},
       summary={"en": "{count} of {total} Intune-managed Windows and macOS devices aren't onboarded to Defender",
                "zh": "{total} 台 Intune 受管 Windows/macOS 设备中有 {count} 台未接入 Defender"},
       remediation={"en": "Deploy the Defender onboarding policy (Intune → Endpoint security → EDR) to every device.",
                    "zh": "向所有设备下发 Defender 接入策略（Intune → 终端安全 → EDR）。"})
def mde_onboarding_gap(facts, p):
    aad = {m.get("aadDeviceId") for m in facts["defender.machines"] if m.get("aadDeviceId")}
    names = {_norm_name(m.get("computerDnsName")) for m in facts["defender.machines"]}
    pool = [d for d in facts["intune.devices"] if (d.get("operatingSystem") or "").lower() in ("windows", "macos")]
    items = [{"_key": d.get("id"), "device": d.get("deviceName"), "os": d.get("operatingSystem"),
              "user": d.get("userPrincipalName"), "last_sync": d.get("lastSyncDateTime")}
             for d in pool if d.get("azureADDeviceId") not in aad and _norm_name(d.get("deviceName")) not in names]
    return Outcome("fail" if items else "pass", {"count": len(items), "total": len(pool)}, items)


def _config_items(facts, category: str) -> list[dict]:
    by_device: dict[str, dict] = {}
    for r in facts["defender.secure_config"]:
        if r.get("category") != category:
            continue
        d = by_device.setdefault(r.get("DeviceId"), {"_key": r.get("DeviceId"), "device": r.get("DeviceName"),
                                                     "settings": []})
        d["settings"].append(r.get("ConfigurationName"))
    for d in by_device.values():
        d["settings"] = sorted(set(d["settings"]))
    return list(by_device.values())


@check("m365.av_health", "m365", severity="high", requires=["defender.secure_config"],
       title={"en": "Antivirus is on, real-time and up to date", "zh": "防病毒已开启实时保护且特征库最新"},
       summary={"en": "{count} devices have antivirus settings out of compliance",
                "zh": "{count} 台设备的防病毒设置不合规"},
       remediation={"en": "Fix through Intune Antivirus policy: real-time and cloud protection on, signatures updated "
                          "daily, not in passive mode.",
                    "zh": "通过 Intune 防病毒策略修复：开启实时和云保护，特征库每日更新，不处于被动模式。"})
def av_health(facts, p):
    items = _config_items(facts, "av")
    return Outcome("fail" if items else "pass", {"count": len(items)}, items)


@check("m365.tamper_protection", "m365", severity="high", requires=["defender.secure_config"],
       title={"en": "Tamper protection is on everywhere", "zh": "所有设备都开启了防篡改保护"},
       summary={"en": "{count} devices don't have tamper protection on", "zh": "{count} 台设备未开启防篡改保护"},
       remediation={"en": "Turn it on tenant-wide in Defender → Settings → Endpoints → Advanced features.",
                    "zh": "在 Defender → 设置 → 终端 → 高级功能中为整个租户开启。"})
def tamper_protection(facts, p):
    items = _config_items(facts, "tamper")
    return Outcome("fail" if items else "pass", {"count": len(items)}, items)


@check("m365.asr_rules", "m365", severity="medium", requires=["defender.secure_config"],
       title={"en": "Attack surface reduction rules block", "zh": "攻击面减少（ASR）规则处于阻止模式"},
       summary={"en": "{count} devices have ASR rules off or in audit only", "zh": "{count} 台设备的 ASR 规则关闭或仅审计"},
       remediation={"en": "Move the standard ASR rules from Audit to Block after checking their audit hits.",
                    "zh": "查看审计命中情况后，将标准 ASR 规则从审计切换到阻止。"})
def asr_rules(facts, p):
    items = _config_items(facts, "asr")
    return Outcome("partial" if items else "pass", {"count": len(items)}, items)


@check("m365.high_risk_devices", "m365", severity="high", requires=["defender.machines"],
       title={"en": "No devices at high risk", "zh": "没有高风险设备"},
       summary={"en": "{count} devices are rated high risk by Defender", "zh": "{count} 台设备被 Defender 评为高风险"},
       remediation={"en": "Investigate the alerts behind each device's risk; isolate if compromise is suspected.",
                    "zh": "调查每台设备风险背后的告警；如怀疑失陷，立即隔离。"})
def high_risk_devices(facts, p):
    items = [{"_key": m.get("id"), "device": m.get("computerDnsName"), "risk": m.get("riskScore"),
              "exposure": m.get("exposureLevel"), "last_seen": m.get("lastSeen")}
             for m in facts["defender.machines"] if m.get("riskScore") == "High"]
    return Outcome("fail" if items else "pass", {"count": len(items)}, items)


# ─── Data loss ────────────────────────────────────────────────────────────────

@check("m365.dlp_alert_sla", "m365", severity="high", requires=["defender.alerts_open"],
       title={"en": "DLP and insider-risk alerts are triaged on time", "zh": "DLP 和内部风险告警按时分诊"},
       summary={"en": "{open} open data-loss alerts ({high} high)", "zh": "{open} 条未处理的数据泄露告警（高危 {high} 条）"},
       remediation={"en": "Triage in Purview within the SLA (high 1 day, medium 3, low 7); tune policies that "
                          "produce noise.",
                    "zh": "在 Purview 中按时分诊（高危 1 天、中危 3 天、低危 7 天）；调整噪声大的策略。"})
def dlp_alert_sla(facts, p):
    items = [{"_key": a.get("id"), "_severity": a.get("severity") if a.get("severity") in SEVERITY else "medium",
              "_due_days": DLP_TRIAGE_DAYS.get(a.get("severity"), 3), "_label": a.get("title"),
              "_since": a.get("createdDateTime"),
              "title": a.get("title"), "source": a.get("serviceSource"), "created": a.get("createdDateTime"),
              "url": a.get("alertWebUrl")}
             for a in facts["defender.alerts_open"]
             if a.get("serviceSource") in ("dataLossPrevention", "microsoftInsiderRiskManagement")]
    high = sum(1 for i in items if i["_severity"] == "high")
    return Outcome("partial" if items else "pass", {"open": len(items), "high": high}, items)


@check("m365.dlp_repeat_offenders", "m365", severity="high", requires=["purview.dlp_alerts_30d"],
       defaults={"threshold": 5},
       title={"en": "No repeat DLP offenders", "zh": "没有反复触发 DLP 的人员"},
       summary={"en": "{count} people triggered {threshold} or more DLP alerts in 30 days",
                "zh": "{count} 人在 30 天内触发了 {threshold} 次及以上 DLP 告警"},
       remediation={"en": "Talk to each person and their manager; repeated hits are rarely accidental. Consider an "
                          "Insider Risk policy for them.",
                    "zh": "与当事人及其主管沟通；反复命中很少是无意的。可考虑为其启用内部风险策略。"})
def dlp_repeat_offenders(facts, p):
    counts = Counter(a["user"] for a in facts["purview.dlp_alerts_30d"]
                     if a.get("user") and a.get("serviceSource") == "dataLossPrevention")
    items = [{"_key": u, "upn": u, "alerts_30d": n} for u, n in counts.most_common() if n >= p["threshold"]]
    return Outcome("fail" if items else "pass", {"count": len(items), "threshold": p["threshold"]}, items)


@check("m365.insider_risk_alerts", "m365", severity="high", requires=["defender.alerts_open"],
       title={"en": "No open insider-risk alerts", "zh": "没有未处理的内部风险告警"},
       summary={"en": "{count} insider-risk alerts are open", "zh": "{count} 条内部风险告警未处理"},
       remediation={"en": "Review in Purview Insider Risk Management with HR and legal as your process requires.",
                    "zh": "按公司流程，会同人事和法务在 Purview 内部风险管理中审查。"})
def insider_risk_alerts(facts, p):
    items = [{"_key": a.get("id"), "title": a.get("title"), "severity": a.get("severity"),
              "created": a.get("createdDateTime")}
             for a in facts["defender.alerts_open"] if a.get("serviceSource") == "microsoftInsiderRiskManagement"]
    return Outcome("fail" if items else "pass", {"count": len(items)}, items)


@check("m365.leaver_downloads", "m365", severity="critical", requires=["m365.download_history", "entra.users"],
       defaults={"files": 100},
       title={"en": "No bulk downloads by people who have since left", "zh": "离职人员离职前没有大量下载"},
       summary={"en": "{count} disabled accounts downloaded {files} or more files in their last 30 days",
                "zh": "{count} 个已禁用账号在最近 30 天内下载了 {files} 个及以上文件"},
       remediation={"en": "Review what was taken (audit log FileDownloaded records) with HR and legal; ask for return "
                          "or deletion and preserve the evidence.",
                    "zh": "会同人事和法务核查下载内容（审计日志 FileDownloaded 记录）；要求归还或删除，并保全证据。"})
def leaver_downloads(facts, p):
    disabled = {(u.get("userPrincipalName") or "").lower() for u in facts["entra.users"] if not u.get("accountEnabled")}
    items = []
    for user, days in facts["m365.download_history"].items():
        total = sum(days.values())
        if user in disabled and total >= p["files"]:
            peak_day, peak = max(days.items(), key=lambda kv: kv[1])
            items.append({"_key": user, "upn": user, "files_30d": total, "peak_day": peak_day, "peak_files": peak})
    return Outcome("fail" if items else "pass", {"count": len(items), "files": p["files"]}, items)


@check("m365.external_sharing", "m365", severity="high", requires=["sharepoint.settings"],
       title={"en": "SharePoint and OneDrive don't allow anonymous links", "zh": "SharePoint 和 OneDrive 不允许匿名链接"},
       summary={"en": "{result}", "zh": "{result_zh}"},
       remediation={"en": "Set external sharing to 'New and existing guests' at most, restrict to partner domains, and "
                          "stop guests from re-sharing.",
                    "zh": "外部共享最多设为「新的和现有的来宾」，限定合作方域名，并禁止来宾再次共享。"})
def external_sharing(facts, p):
    s = facts["sharepoint.settings"]
    cap = s.get("sharingCapability")
    if cap == "externalUserAndGuestSharing":
        return Outcome("fail", {"result": "Anyone links are allowed: files can be shared with no sign-in",
                                "result_zh": "允许「任何人」链接：文件可在无需登录的情况下被共享"},
                       [{"_key": "sharingCapability", "setting": "sharingCapability", "value": cap}])
    issues = []
    if cap in ("externalUserSharingOnly", "existingExternalUserSharingOnly") and \
            s.get("sharingDomainRestrictionMode") in (None, "none"):
        issues.append({"_key": "domains", "setting": "sharingDomainRestrictionMode", "value": "none"})
    if s.get("isResharingByExternalUsersEnabled"):
        issues.append({"_key": "reshare", "setting": "isResharingByExternalUsersEnabled", "value": True})
    if issues:
        return Outcome("partial", {"result": "Guest sharing has no domain limit or guests can re-share",
                                   "result_zh": "来宾共享未限制域名，或来宾可再次共享"}, issues)
    return Outcome("pass", {"result": f"Sharing level: {cap}", "result_zh": f"共享级别：{cap}"})


@check("m365.forwarding_alerts", "m365", severity="high", requires=["defender.alerts_open"],
       title={"en": "No open alerts about mail forwarding", "zh": "没有未处理的邮件转发告警"},
       summary={"en": "{count} open alerts about suspicious forwarding or redirect rules",
                "zh": "{count} 条关于可疑转发或重定向规则的告警未处理"},
       remediation={"en": "Remove the rule, check the mailbox for compromise, and block automatic external forwarding "
                          "in the outbound spam policy.",
                    "zh": "删除该规则，检查邮箱是否失陷，并在出站垃圾邮件策略中阻止自动外部转发。"})
def forwarding_alerts(facts, p):
    items = [{"_key": a.get("id"), "title": a.get("title"), "severity": a.get("severity"),
              "created": a.get("createdDateTime"), "url": a.get("alertWebUrl")}
             for a in facts["defender.alerts_open"]
             if any(w in (a.get("title") or "").lower() for w in ("forward", "redirect"))]
    return Outcome("fail" if items else "pass", {"count": len(items)}, items)


# ─── Identity ─────────────────────────────────────────────────────────────────

@check("m365.permanent_privileged_roles", "m365", severity="high", requires=["entra.directory_roles"],
       title={"en": "Privileged roles are activated just in time", "zh": "特权角色按需激活（PIM）"},
       summary={"en": "{count} permanent assignments to privileged roles{pim_note}",
                "zh": "{count} 个特权角色为永久分配{pim_note_zh}"},
       remediation={"en": "Convert these to PIM eligible assignments with approval and MFA on activation; keep only "
                          "two break-glass Global Administrators permanent.",
                    "zh": "改为 PIM 合格分配，激活时需审批和 MFA；仅保留两个紧急访问全局管理员为永久分配。"})
def permanent_privileged_roles(facts, p):
    glass = {x.lower() for x in p.get("break_glass_accounts") or []}
    rows = []
    if facts.get("entra.pim_active") is not None:
        for a in facts["entra.pim_active"]:
            if a.get("assignmentType") == "Assigned" and not a.get("end") and \
                    (a.get("role") in PRIVILEGED_ROLE_NAMES or a.get("roleTemplateId") in PRIVILEGED_ROLE_TEMPLATES):
                rows.append((a.get("role"), a.get("principal")))
        note = ("", "")
    else:
        # Without PIM (Entra ID P2) every directory-role member is permanent.
        for r in facts["entra.directory_roles"]:
            if r.get("roleTemplateId") in PRIVILEGED_ROLE_TEMPLATES:
                rows += [(r.get("displayName"), m.get("userPrincipalName") or m.get("displayName"))
                         for m in r.get("members", [])]
        note = (" (PIM not available, so all are permanent)", "（未启用 PIM，全部为永久分配）")
    items = [{"_key": f"{role}|{who}", "role": role, "principal": who}
             for role, who in rows if (who or "").lower() not in glass]
    return Outcome("fail" if items else "pass", {"count": len(items), "pim_note": note[0], "pim_note_zh": note[1]},
                   items)


@check("m365.risky_app_registrations", "m365", severity="high", requires=["entra.app_registrations"],
       defaults={"max_secret_days": 365},
       title={"en": "App registrations with powerful permissions are controlled", "zh": "高权限应用注册受控"},
       summary={"en": "{powerful} apps request mailbox, file or directory-wide application permissions; "
                      "{long_lived} have secrets valid for more than {max_secret_days} days; {expired} carry expired secrets",
                "zh": "{powerful} 个应用申请了邮箱、文件或目录级应用权限；{long_lived} 个应用的密钥有效期超过 "
                      "{max_secret_days} 天；{expired} 个应用带有已过期密钥"},
       remediation={"en": "Confirm an owner and business need for each; scope mailbox access with application access "
                          "policies / RBAC for Applications; use certificates or managed identities, rotate secrets "
                          "yearly and delete expired ones.",
                    "zh": "为每个应用确认负责人和业务需要；用应用访问策略或 RBAC 限定邮箱范围；改用证书或托管身份，"
                          "密钥每年轮换并删除过期密钥。"})
def risky_app_registrations(facts, p):
    now = utcnow()
    items, powerful, long_lived, expired = [], 0, 0, 0
    for a in facts["entra.app_registrations"]["apps"]:
        risky = sorted(set(a["application_permissions"]) & HIGH_RISK_APP_PERMISSIONS)
        reasons = []
        if risky:
            powerful += 1
            reasons.append("high-risk permissions: " + ", ".join(risky))
        lifetimes, stale = [], False
        for cr in a["credentials"]:
            start, end = parse_time(cr.get("start")), parse_time(cr.get("end"))
            if start and end and cr["type"] == "secret":
                lifetimes.append((end - start).days)
            if end and end < now:
                stale = True
        if any(d > p["max_secret_days"] for d in lifetimes):
            long_lived += 1
            reasons.append(f"secret valid {max(lifetimes)} days")
        if stale:
            expired += 1
            reasons.append("expired credential still present")
        if reasons:
            items.append({"_key": a["appId"], "_severity": "high" if risky else "medium", "app": a["name"],
                          "app_id": a["appId"], "reason": "; ".join(reasons)})
    status = "fail" if powerful else ("partial" if items else "pass")
    return Outcome(status, {"powerful": powerful, "long_lived": long_lived, "expired": expired,
                            "max_secret_days": p["max_secret_days"]}, items)
