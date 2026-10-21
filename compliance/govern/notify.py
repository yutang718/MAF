"""Teams: the weekly security-check report and, optionally, each new critical alert as it's raised.

Posts an Adaptive Card to a Teams Workflows webhook ("Post to a channel when a
webhook request is received"). Office 365 connector webhooks are retired.
"""
from datetime import datetime, time, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from govern.engine.metrics import posture_summary, sla_metrics
from govern.log import get_logger
from govern.models import Alert, Connector
from govern.settings_store import get as get_setting, get_secret, put as put_setting
from govern.timeutil import iso, utcnow

logger = get_logger(__name__)
SECRET_KEY = "notify"
SEVERITY_ZH = {"critical": "严重", "high": "高", "medium": "中", "low": "低"}
SLA_LABEL = {"exploited": "已被利用/KEV", "critical": "严重", "high": "高危", "medium": "中危", "low": "低危"}


class NotifyError(RuntimeError):
    pass


def webhook(db: Session) -> str:
    return get_secret(db, SECRET_KEY).get("teams_webhook", "")


def validate_webhook(url: str) -> None:
    u = urlparse(url)
    if u.scheme != "https" or not u.hostname:
        raise ValueError("The Teams webhook must be an https:// URL")


def post(url: str, card: dict, transport: httpx.BaseTransport | None = None) -> None:
    payload = {"type": "message", "attachments": [
        {"contentType": "application/vnd.microsoft.card.adaptive", "contentUrl": None, "content": card}]}
    with httpx.Client(timeout=20, transport=transport) as client:
        resp = client.post(url, json=payload)
    if resp.status_code >= 300:
        raise NotifyError(f"Teams webhook answered HTTP {resp.status_code}: {resp.text[:200]}")


def _text(text: str, **kw) -> dict:
    return {"type": "TextBlock", "text": text, "wrap": True, **kw}


def _facts(pairs: list[tuple[str, str]]) -> dict:
    return {"type": "FactSet", "facts": [{"title": k, "value": v} for k, v in pairs]}


def weekly_card(db: Session, base_url: str = "") -> dict:
    s = posture_summary(db, days=7)
    t = s["totals"]
    body: list[dict] = [
        _text("安全检查周报 · Weekly security check", size="Large", weight="Bolder"),
        _text(f"{(utcnow() - timedelta(days=7)).date()} – {utcnow().date()}", isSubtle=True, spacing="None"),
        _facts([("未通过检查项 / Failing checks", str(t.get("fail", 0))),
                ("未关闭问题 / Open findings", str(t.get("open", 0))),
                ("已超时 / Past SLA", str(t.get("overdue", 0))),
                ("本周新增 / New this week", str(t.get("new", 0))),
                ("本周修复 / Fixed this week", str(t.get("resolved", 0)))]),
        _text("各领域 / By area", weight="Bolder", spacing="Medium"),
        _facts([(d["name"]["zh"], f"未通过 {d['failing']} · 未关闭 {d['open']} · 超时 {d['overdue']}")
                for d in s["domains"]]),
    ]
    failing = [i for d in s["domains"] for i in d["items"] if i["status"] == "fail"]
    failing.sort(key=lambda i: (-i["overdue"], ["critical", "high", "medium", "low"].index(i["severity"])))
    if failing:
        body.append(_text("需优先处理 / Fix first", weight="Bolder", spacing="Medium"))
        body.append(_facts([(i["code"], f"{i['title']['zh']}（未关闭 {i['open']}，超时 {i['overdue']}）")
                            for i in failing[:10]]))
    vm = sla_metrics(db)["by_severity"]
    rows = [(SLA_LABEL[k], f"{v['sla_days']} 天 · 未修复 {v['open']} · 超时 {v['open_overdue']}"
             + (f" · 达标率 {v['within_sla_pct']}% · MTTR {v['mttr_days']} 天" if v["resolved"] else ""))
            for k, v in vm.items() if v["open"] or v["resolved"]]
    if rows:
        body.append(_text("漏洞修复时限 / Vulnerability SLA", weight="Bolder", spacing="Medium"))
        body.append(_facts(rows))
    card = {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4", "body": body}
    if base_url:
        card["actions"] = [{"type": "Action.OpenUrl", "title": "打开安全检查 / Open",
                            "url": base_url.rstrip("/") + "/governance"}]
    return card


def alert_card(a: Alert, conn: Connector | None, base_url: str = "") -> dict:
    title_zh = (a.detail or {}).get("title_zh", a.title)
    card = {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4", "body": [
                _text(f"🔴 {SEVERITY_ZH.get(a.severity, a.severity)}风险告警 · {a.severity.upper()} alert",
                      weight="Bolder", color="Attention"),
                _text(title_zh, size="Medium", weight="Bolder"),
                _text(a.title, isSubtle=True, spacing="None"),
                _facts([("账号 / Account", a.actor or "—"), ("数据源 / Source", conn.name if conn else "—"),
                        ("时间 / When", a.occurred_at.strftime("%Y-%m-%d %H:%M UTC"))])]}
    if base_url:
        card["actions"] = [{"type": "Action.OpenUrl", "title": "处理告警 / Triage",
                            "url": f"{base_url.rstrip('/')}/governance/alerts?id={a.id}"}]
    return card


def last_slot(report: dict, now: datetime) -> datetime:
    """The most recent scheduled send time at or before now."""
    tz = ZoneInfo(report.get("timezone") or "UTC")
    local = now.astimezone(tz)
    days_back = (local.isoweekday() - int(report.get("weekday", 1))) % 7
    slot = datetime.combine(local.date() - timedelta(days=days_back), time(int(report.get("hour", 9))), tzinfo=tz)
    if slot > local:
        slot -= timedelta(days=7)
    return slot.astimezone(ZoneInfo("UTC"))


def send_weekly_if_due(db: Session, now: datetime | None = None, transport=None) -> bool:
    report = get_setting(db, "report")
    url = webhook(db)
    if not report.get("enabled") or not url:
        return False
    now = now or utcnow()
    slot = last_slot(report, now)
    state = get_setting(db, "report_state")
    sent = state.get("last_sent_at")
    if sent and sent >= iso(slot):
        return False
    try:
        post(url, weekly_card(db, report.get("base_url", "")), transport)
        put_setting(db, "report_state", {"last_sent_at": iso(now), "last_error": ""})
        return True
    except Exception as e:
        logger.warning(f"weekly report failed: {e}")
        put_setting(db, "report_state", {"last_error": f"{iso(now)}: {e}"[:500]})
        return False
    finally:
        db.commit()


def push_new_critical(db: Session, alert_ids: list[int], transport=None) -> int:
    if not alert_ids:
        return 0
    report = get_setting(db, "report")
    url = webhook(db)
    if not report.get("realtime_critical") or not url:
        return 0
    sent = 0
    for a in db.scalars(select(Alert).where(Alert.id.in_(alert_ids), Alert.severity == "critical")):
        try:
            post(url, alert_card(a, db.get(Connector, a.connector_id), report.get("base_url", "")), transport)
            sent += 1
        except Exception as e:  # a notification failure must never break collection
            logger.warning(f"posting alert {a.id} to Teams failed: {e}")
    return sent
