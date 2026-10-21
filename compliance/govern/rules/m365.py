"""Surface new Defender / Purview alerts on the platform's own alert board."""
from datetime import timedelta

from govern.rules.base import AlertDraft, day_bounds, rule
from govern.timeutil import parse_time

DATA_SOURCES = {"dataLossPrevention", "microsoftInsiderRiskManagement"}


@rule("m365.security_alert", "m365", defaults={"min_severity": "high"},
      title={"en": "Microsoft 365 security alert", "zh": "Microsoft 365 安全告警"},
      description={"en": "New high-severity Defender alerts, and medium-or-higher data loss and insider-risk alerts.",
                   "zh": "新的 Defender 高危告警，以及中危及以上的数据泄露和内部风险告警。"})
def security_alert(ctx, events):
    for e in events:
        if e.kind != "m365.alert":
            continue
        sev = e.data.get("severity")
        source = e.data.get("serviceSource") or ""
        if sev == "high" or (sev == "medium" and source in DATA_SOURCES):
            title = e.data.get("title") or "Alert"
            yield AlertDraft("m365.security_alert", sev, f"{source}: {title}", f"{source}：{title}", e.occurred_at,
                             f"m365.alert:{e.connector_id}:{e.external_id}", e.actor, e.data)


@rule("m365.bulk_file_download", "m365", defaults={"min_files": 500, "baseline_factor": 5.0, "disabled_factor": 0.2},
      title={"en": "Bulk SharePoint/OneDrive download", "zh": "从 SharePoint/OneDrive 大量下载"},
      description={"en": "One account downloading or syncing far more files in a day than a fixed limit or its own "
                         "30-day norm. The limit drops sharply for accounts that are already disabled.",
                   "zh": "同一账号一天内下载或同步的文件数远超固定阈值或其近 30 天的日常水平。账号已被禁用时阈值大幅降低。"})
def bulk_file_download(ctx, events):
    p = ctx.params
    users = ctx.latest_fact("entra.users") or []
    disabled = {(u.get("userPrincipalName") or "").lower() for u in users if not u.get("accountEnabled")}
    for actor, day in {(e.actor, e.data.get("day")) for e in events if e.kind == "m365.download_summary"}:
        start, end = day_bounds(parse_time(f"{day}T12:00:00Z"))
        today = ctx.events(kind="m365.download_summary", actor=actor, start=start, end=end)
        files = sum(e.data.get("files", 0) for e in today)
        history = ctx.events(kind="m365.download_summary", actor=actor, start=start - timedelta(days=30), end=start)
        baseline = sum(e.data.get("files", 0) for e in history) / 30
        threshold = max(p["min_files"], p["baseline_factor"] * baseline)
        leaver = actor in disabled
        if leaver:
            threshold *= p["disabled_factor"]
        if files < threshold:
            continue
        sites = sorted({s for e in today for s in e.data.get("sites", [])})
        yield AlertDraft(
            "m365.bulk_file_download", "critical" if leaver else "high",
            f"{actor} downloaded {files} files on {day}" + (" (account disabled)" if leaver else ""),
            f"{actor} 于 {day} 下载了 {files} 个文件" + ("（账号已禁用）" if leaver else ""),
            max(e.occurred_at for e in today), f"m365.download:{ctx.connector.id}:{actor}:{day}", actor,
            {"day": day, "files": files, "baseline_per_day": round(baseline, 1), "threshold": round(threshold, 1),
             "sites": sites[:50], "account_disabled": leaver})
