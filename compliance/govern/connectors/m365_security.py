"""Security-operations data from Microsoft 365: Defender vulnerability and configuration state through
Advanced Hunting, Purview DLP history, SharePoint sharing, file-download volume from the audit log,
PIM role assignments and app registrations.

Mixed into M365Connector, which provides the authenticated Graph client and paging.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse

from govern.connectors.base import Collected, EventRecord, SourceUnavailable
from govern.connectors.http import raise_for_source
from govern.timeutil import iso, parse_time, utcnow

HUNT_ROWS = 100_000  # Advanced Hunting returns at most this many rows per query
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"
EXCHANGE_APP_ID = "00000002-0000-0ff1-ce00-000000000000"
DOWNLOAD_OPS = ["FileDownloaded", "FileSyncDownloadedFull"]
AUDIT_POLL_SECONDS = 90
HISTORY_DAYS = 30

VULN_QUERY = f"""
DeviceTvmSoftwareVulnerabilities
| join kind=leftouter (DeviceTvmSoftwareVulnerabilitiesKB
    | project CveId, IsExploitAvailable, CvssScore, PublishedDate) on CveId
| project DeviceId, DeviceName, OSPlatform, SoftwareVendor, SoftwareName, SoftwareVersion, CveId,
          VulnerabilitySeverityLevel, RecommendedSecurityUpdate, IsExploitAvailable, CvssScore, PublishedDate
| take {HUNT_ROWS}
"""

CONFIG_QUERY = f"""
DeviceTvmSecureConfigurationAssessment
| where IsApplicable == true and IsCompliant == false
| join kind=inner (DeviceTvmSecureConfigurationAssessmentKB
    | project ConfigurationId, ConfigurationName, ConfigurationSubcategory) on ConfigurationId
| where ConfigurationSubcategory has_any ("Antivirus", "Attack Surface Reduction", "Tamper")
     or ConfigurationName has_any ("Tamper", "real-time", "security intelligence", "Antivirus", "Attack Surface Reduction")
| project DeviceId, DeviceName, ConfigurationId, ConfigurationName, ConfigurationSubcategory
| take {HUNT_ROWS}
"""

EOS_QUERY = f"""
DeviceTvmSoftwareInventory
| where isnotempty(EndOfSupportStatus)
| project DeviceId, DeviceName, SoftwareVendor, SoftwareName, SoftwareVersion, EndOfSupportStatus, EndOfSupportDate
| take {HUNT_ROWS}
"""


class M365SecurityMixin:
    def _security(self, c: Collected) -> None:
        g = self.graph
        c.gather("defender.vulnerabilities", lambda: self._hunt(VULN_QUERY, c, "defender.vulnerabilities"))
        c.gather("defender.secure_config", lambda: [
            {**r, "category": _config_category(r)} for r in self._hunt(CONFIG_QUERY, c, "defender.secure_config")])
        c.gather("defender.eos_software", lambda: self._hunt(EOS_QUERY, c, "defender.eos_software"))
        if self.config.get("fetch_kev"):
            c.gather("threat.kev", self._kev)
        else:
            c.unavailable["threat.kev"] = "KEV lookups are turned off for this connector"
        c.gather("purview.dlp_alerts_30d", lambda: [
            {**_dlp(a), "user": _alert_user(a)} for a in self._pages(
                g, "/v1.0/security/alerts_v2",
                {"$filter": f"createdDateTime ge {iso(utcnow() - timedelta(days=30))}"},
                headers={"Prefer": "include-unknown-enum-members"})
            if a.get("serviceSource") in ("dataLossPrevention", "microsoftInsiderRiskManagement")])
        c.gather("sharepoint.settings", lambda: {
            k: v for k, v in g.get_json("/v1.0/admin/sharepoint/settings").items()
            if k in ("sharingCapability", "sharingDomainRestrictionMode", "sharingAllowedDomainList",
                     "isResharingByExternalUsersEnabled", "isRequireAcceptingUserToMatchInvitedUserEnabled")})
        c.gather("entra.pim_active", self._pim_active)
        c.gather("entra.app_registrations", self._app_registrations)
        if self.config.get("collect_file_downloads"):
            self._file_downloads(c)
        else:
            c.unavailable["m365.download_history"] = "Download tracking is turned off for this connector"

    # ─── Advanced Hunting ─────────────────────────────────────────────────

    def _hunt(self, query: str, c: Collected, key: str) -> list[dict]:
        resp = self.graph.request("POST", "/v1.0/security/runHuntingQuery", json={"Query": query})
        raise_for_source(resp)
        rows = resp.json().get("results", [])
        if len(rows) >= HUNT_ROWS:
            c.errors[f"{key}.truncated"] = f"Advanced Hunting returned the {HUNT_ROWS}-row maximum; some rows are missing"
        return rows

    def _kev(self) -> list[str]:
        resp = self.public.request("GET", KEV_URL)
        raise_for_source(resp)
        return sorted({v["cveID"] for v in resp.json().get("vulnerabilities", []) if v.get("cveID")})

    # ─── Identity ─────────────────────────────────────────────────────────

    def _pim_active(self) -> list[dict]:
        roles = {r["id"]: r for r in self._pages(self.graph, "/v1.0/roleManagement/directory/roleDefinitions",
                                                 {"$select": "id,displayName,templateId"})}
        rows = []
        for a in self._pages(self.graph, "/v1.0/roleManagement/directory/roleAssignmentScheduleInstances",
                             {"$expand": "principal"}):
            role = roles.get(a.get("roleDefinitionId"), {})
            principal = a.get("principal") or {}
            rows.append({"role": role.get("displayName"), "roleTemplateId": role.get("templateId"),
                         "principal": principal.get("userPrincipalName") or principal.get("displayName"),
                         "principalType": (principal.get("@odata.type") or "").rsplit(".", 1)[-1],
                         "assignmentType": a.get("assignmentType"), "memberType": a.get("memberType"),
                         "start": a.get("startDateTime"), "end": a.get("endDateTime")})
        return rows

    def _app_registrations(self) -> dict:
        def role_names(app_id: str) -> dict[str, str]:
            sps = self._pages(self.graph, "/v1.0/servicePrincipals",
                              {"$filter": f"appId eq '{app_id}'", "$select": "appRoles"})
            return {r["id"]: r["value"] for sp in sps for r in sp.get("appRoles", [])}
        names = {GRAPH_APP_ID: role_names(GRAPH_APP_ID), EXCHANGE_APP_ID: role_names(EXCHANGE_APP_ID)}
        apps = []
        for a in self._pages(self.graph, "/v1.0/applications", {
                "$select": "id,appId,displayName,createdDateTime,passwordCredentials,keyCredentials,requiredResourceAccess"}):
            requested = []
            for res in a.get("requiredResourceAccess") or []:
                table = names.get(res.get("resourceAppId"), {})
                for acc in res.get("resourceAccess") or []:
                    if acc.get("type") == "Role":  # application permission, not delegated
                        requested.append(table.get(acc.get("id"), acc.get("id")))
            creds = [{"type": kind, "start": cr.get("startDateTime"), "end": cr.get("endDateTime")}
                     for kind, lst in (("secret", a.get("passwordCredentials")), ("certificate", a.get("keyCredentials")))
                     for cr in lst or []]
            apps.append({"appId": a.get("appId"), "name": a.get("displayName"), "created": a.get("createdDateTime"),
                         "application_permissions": sorted(requested), "credentials": creds})
        return {"apps": apps}

    # ─── File downloads from the unified audit log ────────────────────────

    def _file_downloads(self, c: Collected) -> None:
        """Daily per-user download counts from the asynchronous audit-log query API.

        A query can take minutes. It is started in one run and, if not finished
        within a short wait, collected by the next run; the cursor remembers it.
        """
        history: dict[str, dict[str, int]] = dict(self.cursor.get("download_history") or {})
        pending = self.cursor.get("download_query")
        try:
            if pending:
                finished = self._poll_audit_query(pending["id"])
                if finished is None:
                    c.cursor["download_query"] = pending
                    c.facts["m365.download_history"] = _trim(history)
                    return
                self._ingest_downloads(c, pending, finished, history)
                c.cursor.pop("download_query", None)
                c.cursor["downloads_until"] = pending["end"]
            start = parse_time(c.cursor.get("downloads_until") or self.cursor.get("downloads_until")) \
                or utcnow() - timedelta(days=1)
            end = utcnow() - timedelta(minutes=15)  # the audit log lags behind real time
            if end - start > timedelta(minutes=30):
                query = self._start_audit_query(start, end)
                finished = self._wait_audit_query(query["id"])
                if finished is None:
                    c.cursor["download_query"] = query
                else:
                    self._ingest_downloads(c, query, finished, history)
                    c.cursor["downloads_until"] = query["end"]
        except SourceUnavailable as e:
            c.unavailable["m365.download_history"] = f"audit log query API not available: {e}"
            return
        except Exception as e:
            c.errors["m365.download_history"] = f"{type(e).__name__}: {e}"
            return
        c.cursor["download_history"] = _trim(history)
        c.facts["m365.download_history"] = c.cursor["download_history"]

    def _start_audit_query(self, start: datetime, end: datetime) -> dict:
        resp = self.graph.request("POST", "/beta/security/auditLog/queries", json={
            "displayName": f"govern downloads {iso(start)}", "filterStartDateTime": iso(start),
            "filterEndDateTime": iso(end), "operationFilters": DOWNLOAD_OPS})
        raise_for_source(resp)
        return {"id": resp.json()["id"], "start": iso(start), "end": iso(end)}

    def _poll_audit_query(self, query_id: str) -> list[dict] | None:
        status = self.graph.get_json(f"/beta/security/auditLog/queries/{query_id}").get("status")
        if status == "succeeded":
            return self._pages(self.graph, f"/beta/security/auditLog/queries/{query_id}/records")
        if status == "failed":
            raise RuntimeError(f"audit log query {query_id} failed")
        return None

    def _wait_audit_query(self, query_id: str) -> list[dict] | None:
        waited = 0
        while waited < AUDIT_POLL_SECONDS:
            records = self._poll_audit_query(query_id)
            if records is not None:
                return records
            self._sleep(10)
            waited += 10
        return None

    def _ingest_downloads(self, c: Collected, query: dict, records: list[dict], history: dict) -> None:
        per: dict[tuple[str, str], dict] = defaultdict(lambda: {"files": 0, "sites": set()})
        for r in records:
            user = (r.get("userPrincipalName") or "").lower()
            when = parse_time(r.get("createdDateTime"))
            if not user or not when:
                continue
            day = when.date().isoformat()
            agg = per[(user, day)]
            agg["files"] += 1
            agg["sites"].add(_site(r.get("objectId") or ""))
        for (user, day), agg in per.items():
            history.setdefault(user, {})
            history[user][day] = history[user].get(day, 0) + agg["files"]
            c.events.append(EventRecord(
                kind="m365.download_summary", external_id=f"dl:{user}:{day}:{query['start']}",
                occurred_at=parse_time(f"{day}T12:00:00Z"), actor=user, action="files.download", target="",
                data={"day": day, "files": agg["files"], "sites": sorted(s for s in agg["sites"] if s)[:50],
                      "window": [query["start"], query["end"]]}))


def _trim(history: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    cutoff = (utcnow() - timedelta(days=HISTORY_DAYS)).date().isoformat()
    out = {}
    for user, days in history.items():
        kept = {d: n for d, n in days.items() if d >= cutoff}
        if kept:
            out[user] = kept
    return out


def _site(url: str) -> str:
    u = urlparse(url)
    parts = [p for p in u.path.split("/") if p]
    return f"{u.hostname}/{'/'.join(parts[:2])}" if u.hostname else ""


def _config_category(row: dict) -> str:
    text = f"{row.get('ConfigurationName', '')} {row.get('ConfigurationSubcategory', '')}".lower()
    if "tamper" in text:
        return "tamper"
    if "attack surface reduction" in text:
        return "asr"
    return "av"


def _dlp(a: dict) -> dict:
    return {k: a.get(k) for k in ("id", "title", "severity", "status", "serviceSource", "createdDateTime",
                                  "alertWebUrl")}


def _alert_user(a: dict) -> str:
    for ev in a.get("evidence", []) or []:
        account = ev.get("userAccount") or {}
        if account.get("userPrincipalName"):
            return account["userPrincipalName"].lower()
    return ""
