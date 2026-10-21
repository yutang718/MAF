"""Microsoft 365: Entra ID, Defender, Intune and Purview through Microsoft Graph.

Uses an Entra app registration with application (not delegated) permissions,
all read-only. What the tenant's licences don't cover comes back 403 and is
recorded as unavailable, not as a failed control.
"""
import time
from datetime import datetime, timedelta, timezone

import httpx

from govern.connectors.base import (
    Collected, ConfigField, Connector, EventRecord, SourceUnavailable,
)
from govern.connectors.http import ApiClient, raise_for_source
from govern.connectors.m365_security import M365SecurityMixin
from govern.timeutil import parse_time, utcnow

CLOUDS = {
    "global": ("https://login.microsoftonline.com", "https://graph.microsoft.com",
               "https://api.securitycenter.microsoft.com"),
    "usgov": ("https://login.microsoftonline.us", "https://graph.microsoft.us",
              "https://api-gov.securitycenter.microsoft.us"),
}
PAGE_CAP = 50_000  # objects per collection; far above any tenant this is meant for
ALERT_LOOKBACK_DAYS = 7


class M365Connector(M365SecurityMixin, Connector):
    kind = "m365"
    title = {"en": "Microsoft 365", "zh": "Microsoft 365"}
    fields = (
        ConfigField("tenant_id", {"en": "Tenant ID", "zh": "租户 ID"}, required=True),
        ConfigField("client_id", {"en": "Application (client) ID", "zh": "应用程序（客户端）ID"}, required=True),
        ConfigField("client_secret", {"en": "Client secret", "zh": "客户端密码"}, type="secret", required=True),
        ConfigField("cloud", {"en": "Cloud", "zh": "云环境"}, default="global",
                    help={"en": "global or usgov", "zh": "global（全球）或 usgov（美国政府云）"}),
        ConfigField("defender_endpoint", {"en": "Collect Defender for Endpoint devices", "zh": "采集 Defender for Endpoint 设备"},
                    type="bool", default=True,
                    help={"en": "Needs the WindowsDefenderATP Machine.Read.All permission",
                          "zh": "需要 WindowsDefenderATP 的 Machine.Read.All 权限"}),
        ConfigField("fetch_kev", {"en": "Use the CISA Known Exploited Vulnerabilities list",
                                  "zh": "使用 CISA 已知被利用漏洞（KEV）清单"}, type="bool", default=True,
                    help={"en": "Needs outbound HTTPS to cisa.gov. KEV CVEs get the 7-day remediation clock.",
                          "zh": "需要能访问 cisa.gov。KEV 中的漏洞按 7 天时限计算。"}),
        ConfigField("collect_file_downloads", {"en": "Track SharePoint/OneDrive downloads (audit log)",
                                               "zh": "跟踪 SharePoint/OneDrive 下载（审计日志）"}, type="bool",
                    default=True, help={"en": "Needs AuditLogsQuery.Read.All and unified audit logging turned on.",
                                        "zh": "需要 AuditLogsQuery.Read.All，且已开启统一审计日志。"}),
        ConfigField("break_glass_accounts", {"en": "Break-glass accounts (UPNs)", "zh": "紧急访问账号（UPN）"},
                    type="list", default=[],
                    help={"en": "Allowed to hold permanent Global Administrator.",
                          "zh": "允许永久持有全局管理员角色。"}),
    )
    permissions_help = {
        "en": "Microsoft Graph application permissions: User.Read.All, AuditLog.Read.All, Policy.Read.All, "
              "RoleManagement.Read.Directory, RoleAssignmentSchedule.Read.Directory, Application.Read.All, "
              "IdentityRiskyUser.Read.All, SecurityEvents.Read.All, SecurityAlert.Read.All, "
              "SecurityIncident.Read.All, ThreatHunting.Read.All, AuditLogsQuery.Read.All, "
              "SharePointTenantSettings.Read.All, DeviceManagementManagedDevices.Read.All, "
              "DeviceManagementConfiguration.Read.All, InformationProtectionPolicy.Read.All, "
              "RecordsManagement.Read.All; WindowsDefenderATP: Machine.Read.All. Grant admin consent.",
        "zh": "Microsoft Graph 应用程序权限：User.Read.All、AuditLog.Read.All、Policy.Read.All、"
              "RoleManagement.Read.Directory、RoleAssignmentSchedule.Read.Directory、Application.Read.All、"
              "IdentityRiskyUser.Read.All、SecurityEvents.Read.All、SecurityAlert.Read.All、"
              "SecurityIncident.Read.All、ThreatHunting.Read.All、AuditLogsQuery.Read.All、"
              "SharePointTenantSettings.Read.All、DeviceManagementManagedDevices.Read.All、"
              "DeviceManagementConfiguration.Read.All、InformationProtectionPolicy.Read.All、"
              "RecordsManagement.Read.All；WindowsDefenderATP：Machine.Read.All。需要管理员同意。",
    }

    def __init__(self, config, secrets, cursor=None, *, transport: httpx.BaseTransport | None = None,
                 sleep=time.sleep):
        super().__init__(config, secrets, cursor)
        login, graph, mde = CLOUDS.get(self.config["cloud"] or "global", CLOUDS["global"])
        self._login = login
        self._tokens: dict[str, tuple[str, float]] = {}
        self._token_http = httpx.Client(timeout=30, transport=transport)
        self.graph = ApiClient(graph, lambda: self._auth(f"{graph}/.default"), transport=transport, sleep=sleep)
        self.mde = ApiClient(f"{mde}/api", lambda: self._auth(f"{mde}/.default"), transport=transport, sleep=sleep)
        self.public = ApiClient("", lambda: {}, transport=transport, sleep=sleep, timeout=30)
        self._sleep = sleep

    def close(self) -> None:
        self.graph.close()
        self.mde.close()
        self.public.close()
        self._token_http.close()

    # ─── auth ──────────────────────────────────────────────────────────────

    def _auth(self, scope: str) -> dict[str, str]:
        token, expires = self._tokens.get(scope, ("", 0.0))
        if time.time() > expires - 120:
            resp = self._token_http.post(
                f"{self._login}/{self.config['tenant_id']}/oauth2/v2.0/token",
                data={"grant_type": "client_credentials", "client_id": self.config["client_id"],
                      "client_secret": self.secrets.get("client_secret", ""), "scope": scope},
            )
            if resp.status_code != 200:
                detail = resp.json().get("error_description", resp.text) if resp.content else resp.status_code
                raise PermissionError(f"token request for {scope} failed: {str(detail)[:300]}")
            body = resp.json()
            token, expires = body["access_token"], time.time() + int(body.get("expires_in", 3600))
            self._tokens[scope] = (token, expires)
        return {"Authorization": f"Bearer {token}"}

    def _pages(self, client: ApiClient, path: str, params: dict | None = None,
               headers: dict | None = None) -> list[dict]:
        out: list[dict] = []
        url: str | None = path
        first = True
        while url and len(out) < PAGE_CAP:
            resp = client.request("GET", url, params=params if first else None, headers=dict(headers or {}))
            first = False
            raise_for_source(resp)
            body = resp.json()
            out.extend(body.get("value", []))
            url = body.get("@odata.nextLink")
        return out

    def test(self) -> str:
        orgs = self._pages(self.graph, "/v1.0/organization", {"$select": "id,displayName"})
        name = orgs[0]["displayName"] if orgs else self.config["tenant_id"]
        return f"Connected to tenant {name}"

    # ─── collection ────────────────────────────────────────────────────────

    def collect(self) -> Collected:
        c = Collected(cursor=dict(self.cursor))
        g = self.graph

        c.gather("entra.users", self._users(c))
        c.gather("entra.domains", lambda: sorted({
            d["name"].lower() for org in self._pages(g, "/v1.0/organization", {"$select": "verifiedDomains"})
            for d in org.get("verifiedDomains", []) if d.get("name")}))
        c.gather("entra.mfa_registration", lambda: [
            _pick(u, "id", "userPrincipalName", "userDisplayName", "userType", "isAdmin",
                  "isMfaRegistered", "isMfaCapable", "methodsRegistered")
            for u in self._pages(g, "/v1.0/reports/authenticationMethods/userRegistrationDetails")])
        c.gather("entra.conditional_access", lambda: self._pages(g, "/v1.0/identity/conditionalAccess/policies"))
        c.gather("entra.security_defaults", lambda: g.get_json(
            "/v1.0/policies/identitySecurityDefaultsEnforcementPolicy").get("isEnabled", False))
        c.gather("entra.directory_roles", lambda: [
            {"displayName": r.get("displayName"), "roleTemplateId": r.get("roleTemplateId"),
             "members": [_pick(m, "id", "displayName", "userPrincipalName", "@odata.type")
                         for m in r.get("members", [])]}
            for r in self._pages(g, "/v1.0/directoryRoles", {"$expand": "members"})])
        c.gather("entra.risky_users", lambda: [
            _pick(u, "id", "userPrincipalName", "userDisplayName", "riskLevel", "riskState",
                  "riskLastUpdatedDateTime")
            for u in self._pages(g, "/v1.0/identityProtection/riskyUsers", {"$filter": "riskState eq 'atRisk'"})])
        c.gather("defender.secure_score", self._secure_score)
        c.gather("defender.incidents_open", lambda: [
            _pick(i, "id", "displayName", "severity", "status", "createdDateTime", "lastUpdateDateTime",
                  "assignedTo", "incidentWebUrl")
            for i in self._pages(g, "/v1.0/security/incidents", {"$filter": "status ne 'resolved'"})])
        c.gather("defender.alerts_open", lambda: [
            _alert(a) for a in self._pages(g, "/v1.0/security/alerts_v2", {"$filter": "status ne 'resolved'"},
                                           headers={"Prefer": "include-unknown-enum-members"})])
        if self.config["defender_endpoint"]:
            c.gather("defender.machines", lambda: [
                _pick(m, "id", "computerDnsName", "osPlatform", "healthStatus", "onboardingStatus",
                      "riskScore", "exposureLevel", "lastSeen", "aadDeviceId")
                for m in self._pages(self.mde, "/machines")])
        else:
            c.unavailable["defender.machines"] = "Defender for Endpoint collection is turned off for this connector"
        c.gather("intune.devices", lambda: self._pages(g, "/v1.0/deviceManagement/managedDevices", {
            "$select": "id,deviceName,operatingSystem,osVersion,complianceState,isEncrypted,jailBroken,"
                       "lastSyncDateTime,userPrincipalName,managedDeviceOwnerType,azureADDeviceId"}))
        c.gather("intune.compliance_policies", lambda: [
            {"id": p.get("id"), "displayName": p.get("displayName"), "type": p.get("@odata.type", ""),
             "assigned": bool(p.get("assignments"))}
            for p in self._pages(g, "/v1.0/deviceManagement/deviceCompliancePolicies", {"$expand": "assignments"})])
        c.gather("purview.sensitivity_labels", lambda: [
            _pick(lbl, "id", "name", "isActive", "sensitivity")
            for lbl in self._pages(g, "/beta/security/informationProtection/sensitivityLabels")])
        c.gather("purview.retention_labels", lambda: [
            _pick(lbl, "id", "displayName", "retentionDuration", "actionAfterRetentionPeriod")
            for lbl in self._pages(g, "/v1.0/security/labels/retentionLabels")])

        self._security(c)
        self._new_alerts(c)
        return c

    def _users(self, c: Collected):
        def fetch():
            select = "id,displayName,userPrincipalName,mail,accountEnabled,userType,createdDateTime"
            try:
                users = self._pages(self.graph, "/v1.0/users", {"$select": select + ",signInActivity", "$top": "999"})
                c.facts["entra.sign_in_activity"] = True
            except SourceUnavailable as e:
                # signInActivity needs Entra ID P1 and AuditLog.Read.All; the user list itself doesn't.
                c.unavailable["entra.sign_in_activity"] = str(e)
                users = self._pages(self.graph, "/v1.0/users", {"$select": select, "$top": "999"})
            return [{**_pick(u, *select.split(",")),
                     "lastSignIn": _last_sign_in(u.get("signInActivity"))} for u in users]
        return fetch

    def _secure_score(self) -> dict:
        scores = self.graph.get_json("/v1.0/security/secureScores", params={"$top": "1"}).get("value", [])
        if not scores:
            raise SourceUnavailable("no Secure Score has been computed for this tenant yet")
        s = scores[0]
        return {"currentScore": s.get("currentScore"), "maxScore": s.get("maxScore"),
                "createdDateTime": s.get("createdDateTime")}

    def _new_alerts(self, c: Collected) -> None:
        """Alerts created since the last run become events, so alert rules see each one once."""
        since = self.cursor.get("alerts_since") or (
            datetime.now(timezone.utc) - timedelta(days=ALERT_LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            alerts = self._pages(self.graph, "/v1.0/security/alerts_v2",
                                 {"$filter": f"createdDateTime gt {since}"},
                                 headers={"Prefer": "include-unknown-enum-members"})
        except SourceUnavailable as e:
            c.unavailable["events.alerts"] = str(e)
            return
        except Exception as e:
            c.errors["events.alerts"] = f"{type(e).__name__}: {e}"
            return
        latest = since
        for a in alerts:
            created = a.get("createdDateTime") or ""
            latest = max(latest, created)
            c.events.append(EventRecord(
                kind="m365.alert", external_id=a["id"], occurred_at=parse_time(created) or utcnow(),
                actor=_alert_user(a), action=a.get("serviceSource", ""), target=a.get("title", ""),
                data=_alert(a)))
        c.cursor["alerts_since"] = latest


def _pick(obj: dict, *keys: str) -> dict:
    return {k: obj.get(k) for k in keys}


def _alert(a: dict) -> dict:
    return _pick(a, "id", "title", "severity", "status", "serviceSource", "detectionSource", "category",
                 "createdDateTime", "incidentId", "alertWebUrl")


def _alert_user(a: dict) -> str:
    for ev in a.get("evidence", []) or []:
        account = (ev.get("userAccount") or {})
        if account.get("userPrincipalName"):
            return account["userPrincipalName"]
    return ""


def _last_sign_in(activity: dict | None) -> str | None:
    if not activity:
        return None
    stamps = [activity.get(k) for k in ("lastSignInDateTime", "lastNonInteractiveSignInDateTime",
                                         "lastSuccessfulSignInDateTime")]
    stamps = [s for s in stamps if s]
    return max(stamps) if stamps else None
