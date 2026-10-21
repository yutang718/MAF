"""Surface new Defender / Purview alerts on the platform's own alert board."""
from govern.rules.base import AlertDraft, rule

DATA_SOURCES = {"dataLossPrevention", "microsoftInsiderRiskManagement"}


@rule("m365.security_alert", "m365", defaults={"min_severity": "high"},
      title={"en": "Microsoft 365 security alert", "zh": "Microsoft 365 安全告警"},
      description={"en": "New high-severity Defender alerts, and medium-or-higher data loss and insider-risk alerts.",
                   "zh": "新的 Defender 高危告警，以及中危及以上的数据泄露和内部风险告警。"})
def security_alert(ctx, events):
    for e in events:
        sev = e.data.get("severity")
        source = e.data.get("serviceSource") or ""
        if sev == "high" or (sev == "medium" and source in DATA_SOURCES):
            title = e.data.get("title") or "Alert"
            yield AlertDraft("m365.security_alert", sev, f"{source}: {title}", f"{source}：{title}", e.occurred_at,
                             f"m365.alert:{e.connector_id}:{e.external_id}", e.actor, e.data)
