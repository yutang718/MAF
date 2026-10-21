"""Risk rules over Archery query logs and executed SQL changes."""
from govern.engine.sqlrisk import SEVERITY_RANK
from govern.rules.base import AlertDraft, WorkHours, day_bounds, rule

QUERY = "archery.query"


def _sensitive_tables(ctx) -> set[str]:
    cols = ctx.latest_fact("archery.sensitive_columns") or []
    return {c["table"].lower() for c in cols if "credential" not in c.get("categories", [])}


def _work_hours(ctx) -> WorkHours:
    cfg = ctx.connector.config
    return WorkHours(cfg.get("timezone") or "UTC", cfg.get("work_hours") or "00:00-24:00",
                     cfg.get("work_days") or [1, 2, 3, 4, 5, 6, 7])


def _query_detail(e) -> dict:
    return {k: e.data.get(k) for k in ("instance", "db", "rows", "tables", "masked", "hit_rule", "sql")}


@rule("archery.query_risk", "archery", defaults={"rows": 10_000},
      title={"en": "Risky database query", "zh": "高风险数据库查询"},
      description={"en": "A single query returning many rows, a masking rule that matched but didn't mask, unmasked "
                         "reads of tables holding sensitive data, and file export through SQL.",
                   "zh": "单次查询返回大量数据、命中脱敏规则但未脱敏、未脱敏读取含敏感数据的表、通过 SQL 导出文件。"})
def query_risk(ctx, events):
    sensitive = _sensitive_tables(ctx)
    for e in events:
        if e.kind != QUERY:
            continue
        d = e.data
        hits = []
        if d.get("rows", 0) >= ctx.params["rows"]:
            hits.append(("high", "mass_export", f"{d['rows']} rows returned", f"返回 {d['rows']} 行数据"))
        if d.get("hit_rule") and not d.get("masked"):
            hits.append(("high", "masking_failed", "masking rule matched but result was not masked",
                         "命中脱敏规则但结果未脱敏"))
        elif not d.get("masked") and sensitive & set(d.get("tables") or []):
            hits.append(("medium", "unmasked_sensitive", "unmasked read of a table with sensitive columns",
                         "未脱敏读取含敏感字段的表"))
        for f in d.get("risk") or []:
            if SEVERITY_RANK[f["severity"]] >= SEVERITY_RANK["high"]:
                hits.append((f["severity"], f["code"], f"SQL pattern {f['code']}", f"SQL 风险模式 {f['code']}"))
        if not hits:
            continue
        sev = max((h[0] for h in hits), key=SEVERITY_RANK.__getitem__)
        yield AlertDraft(
            "archery.query_risk", sev, f"{e.actor} on {e.target}: " + "; ".join(h[2] for h in hits),
            f"{e.actor} 于 {e.target}：" + "；".join(h[3] for h in hits), e.occurred_at,
            f"archery.query:{e.connector_id}:{e.external_id}", e.actor,
            {**_query_detail(e), "reasons": [h[1] for h in hits]})


@rule("archery.daily_volume", "archery", defaults={"rows": 100_000, "baseline_factor": 5.0, "min_queries": 50},
      title={"en": "Unusual query volume", "zh": "异常的查询量"},
      description={"en": "One account pulling far more rows or running far more queries in a day than a fixed limit "
                         "or its own 30-day norm.",
                   "zh": "同一账号一天内查询的行数或次数远超固定阈值或其近 30 天的日常水平。"})
def daily_volume(ctx, events):
    p = ctx.params
    for actor, day in {(e.actor, day_bounds(e.occurred_at)[0]) for e in events if e.kind == QUERY and e.actor}:
        start, end = day_bounds(day)
        day_events = ctx.events(kind=QUERY, actor=actor, start=start, end=end)
        rows = sum(e.data.get("rows", 0) for e in day_events)
        baseline = ctx.baseline_daily(kind=QUERY, actor=actor, before=start)
        reasons = []
        if rows >= p["rows"]:
            reasons.append("rows")
        if len(day_events) >= max(p["min_queries"], p["baseline_factor"] * baseline):
            reasons.append("queries")
        if not reasons:
            continue
        yield AlertDraft(
            "archery.daily_volume", "high", f"{actor} ran {len(day_events)} queries returning {rows} rows on {start.date()}",
            f"{actor} 于 {start.date()} 执行 {len(day_events)} 次查询，返回 {rows} 行", max(e.occurred_at for e in day_events),
            f"archery.volume:{ctx.connector.id}:{actor}:{start.date()}", actor,
            {"day": str(start.date()), "queries": len(day_events), "rows": rows,
             "baseline_queries_per_day": round(baseline, 1), "reasons": reasons})


@rule("archery.off_hours", "archery", defaults={"escalate_rows": 10_000},
      title={"en": "Database access outside working hours", "zh": "非工作时间访问数据库"},
      description={"en": "Queries and changes outside the configured working hours, one alert per person per day.",
                   "zh": "在设定工作时间之外的查询和变更，每人每天合并为一条告警。"})
def off_hours(ctx, events):
    hours = _work_hours(ctx)
    groups: dict[tuple, list] = {}
    for e in events:
        if e.actor and not hours.contains(e.occurred_at):
            groups.setdefault((e.actor, day_bounds(e.occurred_at)[0]), []).append(e)
    for (actor, day), evs in groups.items():
        start, end = day_bounds(day)
        all_off = [e for kind in (QUERY, "archery.workflow")
                   for e in ctx.events(kind=kind, actor=actor, start=start, end=end) if not hours.contains(e.occurred_at)]
        rows = sum(e.data.get("rows", 0) for e in all_off if e.kind == QUERY)
        changes = sum(1 for e in all_off if e.kind == "archery.workflow")
        sev = "medium" if rows >= ctx.params["escalate_rows"] or changes else "low"
        yield AlertDraft(
            "archery.off_hours", sev, f"{actor}: {len(all_off)} database operations outside working hours",
            f"{actor}：{len(all_off)} 次非工作时间数据库操作", max(e.occurred_at for e in all_off),
            f"archery.offhours:{ctx.connector.id}:{actor}:{start.date()}", actor,
            {"day": str(start.date()), "operations": len(all_off), "rows": rows, "changes": changes})


@rule("archery.change_risk", "archery",
      title={"en": "Risky SQL change executed", "zh": "执行了高风险 SQL 变更"},
      description={"en": "Executed tickets that were self-approved, had no approval record, ran manually, or contained "
                         "unbounded or destructive SQL.",
                   "zh": "已执行的工单存在自审自批、无审批记录、手动执行，或包含无条件/破坏性 SQL。"})
def change_risk(ctx, events):
    for e in events:
        if e.kind != "archery.workflow":
            continue
        w = e.data
        hits = []
        if w.get("self_approved"):
            hits.append(("high", "self_approved", "approved by its own submitter", "由提交人自行审批"))
        elif w.get("unapproved"):
            hits.append(("medium", "no_approval", "no approval on record", "没有审批记录"))
        if w.get("manual"):
            hits.append(("medium", "manual_execution", "executed manually outside Archery", "在 Archery 之外手动执行"))
        for f in w.get("risk") or []:
            if SEVERITY_RANK[f["severity"]] >= SEVERITY_RANK["high"]:
                hits.append((f["severity"], f["code"], f"SQL pattern {f['code']}", f"SQL 风险模式 {f['code']}"))
        if not hits:
            continue
        sev = max((h[0] for h in hits), key=SEVERITY_RANK.__getitem__)
        yield AlertDraft(
            "archery.change_risk", sev, f"Ticket #{w.get('id')} {w.get('title')}: " + "; ".join(h[2] for h in hits),
            f"工单 #{w.get('id')} {w.get('title')}：" + "；".join(h[3] for h in hits), e.occurred_at,
            f"archery.change:{e.connector_id}:{e.external_id}", e.actor,
            {k: w.get(k) for k in ("id", "title", "engineer", "approvers", "instance", "db", "syntax", "sql")}
            | {"reasons": [h[1] for h in hits]})
