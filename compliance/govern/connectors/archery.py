"""Archery (hhyo/Archery) SQL audit platform, read straight from its MySQL database.

Needs a read-only MySQL account on Archery's own database. Table and column names
follow Archery 1.9–1.11; Archery stores business-database passwords encrypted
with its own key, and this connector never reads them. Sensitive-data discovery
connects to business databases only through DSNs given here explicitly.
"""
import json
from datetime import timedelta
from typing import Any

from govern.config import get_settings
from govern.connectors.base import Collected, ConfigField, Connector, EventRecord, SourceUnavailable
from govern.engine import discovery, sqlrisk
from govern.timeutil import iso, parse_time, utcnow

SQL_KEEP = 4000  # characters of SQL text kept per event
QUERY_BATCH = 20_000
REVIEW_WINDOW_DAYS = 30
FINISHED = ("workflow_finish", "workflow_exception")
# Archery WorkflowLog.operation_type: 1 = approved
APPROVED = 1
# Archery WorkflowAudit.workflow_type: 2 = SQL change request
SQL_CHANGE = 2


class ArcheryConnector(Connector):
    kind = "archery"
    title = {"en": "Archery", "zh": "Archery"}
    fields = (
        ConfigField("host", {"en": "Archery database host", "zh": "Archery 数据库主机"}, required=True),
        ConfigField("port", {"en": "Port", "zh": "端口"}, type="int", default=3306),
        ConfigField("database", {"en": "Database name", "zh": "数据库名"}, default="archery"),
        ConfigField("user", {"en": "Read-only user", "zh": "只读账号"}, required=True),
        ConfigField("password", {"en": "Password", "zh": "密码"}, type="secret", required=True),
        ConfigField("timezone", {"en": "Archery's local time zone", "zh": "Archery 所在时区"}, default="Asia/Brunei",
                    help={"en": "Archery stores local times; used to read them and to judge working hours",
                          "zh": "Archery 以本地时间存储，用于换算时间并判断工作时间"}),
        ConfigField("work_hours", {"en": "Working hours", "zh": "工作时间"}, default="08:00-19:00"),
        ConfigField("work_days", {"en": "Working days (1=Mon)", "zh": "工作日（1=周一）"}, type="list",
                    default=[1, 2, 3, 4, 5]),
        ConfigField("discovery_dsns", {"en": "Databases to scan for sensitive data", "zh": "需扫描敏感数据的数据库"},
                    type="secret",
                    help={"en": 'JSON list: [{"instance": "<Archery instance name>", "dsn": "mysql://ro:pw@host:3306/db"}]. '
                                "Use read-only accounts.",
                          "zh": 'JSON 列表：[{"instance": "<Archery 实例名>", "dsn": "mysql://ro:pw@host:3306/db"}]。'
                                "请使用只读账号。"}),
        ConfigField("discovery_sample", {"en": "Confirm with MAF PII detection on sampled values",
                                         "zh": "抽样数据并用 MAF PII 检测确认"}, type="bool", default=True),
        ConfigField("discovery_every_hours", {"en": "Re-scan interval (hours)", "zh": "重新扫描间隔（小时）"},
                    type="int", default=24),
    )
    permissions_help = {
        "en": "CREATE USER 'govern_ro'@'%' IDENTIFIED BY '…'; GRANT SELECT ON archery.* TO 'govern_ro'@'%';",
        "zh": "CREATE USER 'govern_ro'@'%' IDENTIFIED BY '…'; GRANT SELECT ON archery.* TO 'govern_ro'@'%';",
    }

    def __init__(self, config, secrets, cursor=None, *, connect=None, scan=None, sampler=None):
        super().__init__(config, secrets, cursor)
        self._connect = connect or self._mysql
        self._scan = scan or discovery.scan_database
        self._sampler = sampler
        self._conn = None
        self._instances: dict = {}
        from zoneinfo import ZoneInfo
        self.tz = ZoneInfo(self.config["timezone"] or "UTC")

    def _mysql(self):
        import pymysql
        return pymysql.connect(host=self.config["host"], port=int(self.config["port"] or 3306),
                               user=self.config["user"], password=self.secrets.get("password", ""),
                               database=self.config["database"], charset="utf8mb4", connect_timeout=15,
                               read_timeout=300, cursorclass=pymysql.cursors.DictCursor)

    @property
    def conn(self):
        if self._conn is None:
            self._conn = self._connect()
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        if self._sampler is not None:
            self._sampler.close()

    def _rows(self, sql: str, args: tuple = ()) -> list[dict]:
        cur = self.conn.cursor()
        try:
            cur.execute(sql, args)
            return list(cur.fetchall())
        except Exception as e:
            # 1146 = table doesn't exist (older/newer Archery schema), 1142 = SELECT denied
            code = getattr(e, "args", [None])[0]
            if code in (1146, 1142, 1054):
                raise SourceUnavailable(f"Archery schema mismatch or no access: {e}") from e
            raise
        finally:
            cur.close()

    def _local(self, value) -> str | None:
        """Archery DATETIMEs are naive local time; return ISO UTC."""
        if value is None:
            return None
        dt = value if hasattr(value, "year") else parse_time(str(value))
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.tz)
        return iso(dt)

    def _to_local_naive(self, dt):
        return dt.astimezone(self.tz).replace(tzinfo=None)

    def test(self) -> str:
        rows = self._rows("SELECT COUNT(*) AS n FROM sql_users")
        return f"Connected to Archery database ({rows[0]['n']} users)"

    # ─── collection ────────────────────────────────────────────────────────

    def collect(self) -> Collected:
        c = Collected(cursor=dict(self.cursor))
        c.gather("archery.config", lambda: {r["item"]: r["value"] for r in self._rows(
            "SELECT item, value FROM sql_config")})
        c.gather("archery.users", lambda: [
            {"username": r["username"], "display": r.get("display"), "is_superuser": bool(r["is_superuser"]),
             "is_active": bool(r["is_active"]), "last_login": self._local(r.get("last_login")),
             "date_joined": self._local(r.get("date_joined"))}
            for r in self._rows("SELECT username, display, is_superuser, is_active, last_login, date_joined "
                                "FROM sql_users")])
        instances = c.gather("archery.instances", lambda: {
            r["id"]: {"name": r["instance_name"], "type": r.get("type"), "db_type": r.get("db_type")}
            for r in self._rows("SELECT id, instance_name, type, db_type FROM sql_instance")}) or {}
        self._instances = instances
        c.gather("archery.query_privileges", lambda: [
            {"user": r["user_name"], "instance": instances.get(r["instance_id"], {}).get("name", r["instance_id"]),
             "db": r.get("db_name"), "table": r.get("table_name"), "valid_date": str(r.get("valid_date")),
             "limit_num": r.get("limit_num"), "level": "database" if r.get("priv_type") == 1 else "table",
             "granted": self._local(r.get("create_time"))}
            for r in self._rows("SELECT user_name, instance_id, db_name, table_name, valid_date, limit_num, priv_type, "
                                "create_time FROM query_privileges WHERE is_deleted = 0 AND valid_date >= CURDATE()")])
        c.gather("archery.masking_columns", lambda: [
            {"instance": instances.get(r["instance_id"], {}).get("name", r["instance_id"]),
             "schema": r["table_schema"], "table": r["table_name"], "column": r["column_name"],
             "rule_type": r.get("rule_type"), "active": bool(r.get("active"))}
            for r in self._rows("SELECT instance_id, table_schema, table_name, column_name, rule_type, active "
                                "FROM data_masking_columns")])
        c.gather("archery.change_review", self._change_review)
        c.gather("archery.query_activity", self._query_activity)
        self._discover(c)
        self._query_events(c)
        self._workflow_events(c)
        return c

    def _instance_name(self, instance_id) -> str:
        return self._instances.get(instance_id, {}).get("name", str(instance_id))

    def _query_activity(self) -> dict:
        row = self._rows("SELECT COUNT(*) AS queries, MAX(create_time) AS latest FROM query_log WHERE create_time >= %s",
                         (self._to_local_naive(utcnow() - timedelta(days=7)),))[0]
        return {"queries": int(row.get("queries") or 0), "latest": self._local(row.get("latest"))}

    def _change_review(self) -> list[dict]:
        """SQL changes executed in the review window, with who approved them."""
        since = self._to_local_naive(utcnow() - timedelta(days=REVIEW_WINDOW_DAYS))
        rows = self._workflows("w.finish_time >= %s", (since,))
        return [{k: r[k] for k in ("id", "title", "engineer", "approvers", "self_approved", "unapproved", "manual",
                                   "instance", "db", "syntax", "finished", "risk", "worst")} for r in rows]

    def _workflows(self, where: str, args: tuple, limit: int = 5000) -> list[dict]:
        rows = self._rows(
            "SELECT w.id, w.workflow_name, w.engineer, w.engineer_display, w.instance_id, w.db_name, w.syntax_type, "
            "w.status, w.is_manual, w.create_time, w.finish_time, c.sql_content "
            "FROM sql_workflow w LEFT JOIN sql_workflow_content c ON c.workflow_id = w.id "
            f"WHERE w.status IN ('workflow_finish','workflow_exception') AND {where} ORDER BY w.finish_time LIMIT {int(limit)}",
            args)
        if not rows:
            return []
        ids = [r["id"] for r in rows]
        marks = ",".join(["%s"] * len(ids))
        approvals: dict[int, list[str]] = {}
        for a in self._rows(
                f"SELECT a.workflow_id, l.operator FROM workflow_audit a JOIN workflow_log l ON l.audit_id = a.audit_id "
                f"WHERE a.workflow_type = %s AND l.operation_type = %s AND a.workflow_id IN ({marks})",
                (SQL_CHANGE, APPROVED, *ids)):
            approvals.setdefault(a["workflow_id"], []).append(a["operator"])
        out = []
        for r in rows:
            sql = r.get("sql_content") or ""
            findings = sqlrisk.assess(sql)
            approvers = sorted(set(approvals.get(r["id"], [])))
            out.append({
                "id": r["id"], "title": r.get("workflow_name"), "engineer": r.get("engineer"),
                "approvers": approvers, "self_approved": r.get("engineer") in approvers,
                "unapproved": not approvers, "manual": bool(r.get("is_manual")),
                "instance": self._instance_name(r["instance_id"]), "db": r.get("db_name"),
                "syntax": {1: "DDL", 2: "DML", 3: "export"}.get(r.get("syntax_type"), "unknown"),
                "status": r.get("status"), "created": self._local(r.get("create_time")),
                "finished": self._local(r.get("finish_time")), "sql": sql[:SQL_KEEP],
                "risk": [f.as_dict() for f in findings], "worst": sqlrisk.worst(findings),
            })
        return out

    def _query_events(self, c: Collected) -> None:
        last_id = int(self.cursor.get("query_log_id") or 0)
        if not last_id:
            # First run: start a week back rather than replaying years of history.
            start = self._to_local_naive(utcnow() - timedelta(days=7))
            where, args = "create_time >= %s", (start,)
        else:
            where, args = "id > %s", (last_id,)
        try:
            rows = self._rows(
                "SELECT id, instance_name, db_name, sqllog, effect_row, cost_time, username, user_display, "
                f"priv_check, hit_rule, masking, create_time FROM query_log WHERE {where} ORDER BY id LIMIT {QUERY_BATCH}",
                args)
        except SourceUnavailable as e:
            c.unavailable["events.queries"] = str(e)
            return
        for r in rows:
            sql = r.get("sqllog") or ""
            c.events.append(EventRecord(
                kind="archery.query", external_id=f"q{r['id']}",
                occurred_at=parse_time(self._local(r["create_time"])) or utcnow(),
                actor=r.get("username") or "", action="query", target=f"{r.get('instance_name')}/{r.get('db_name')}",
                data={"instance": r.get("instance_name"), "db": r.get("db_name"), "sql": sql[:SQL_KEEP],
                      "rows": int(r.get("effect_row") or 0), "cost": r.get("cost_time"),
                      "hit_rule": bool(r.get("hit_rule")), "masked": bool(r.get("masking")),
                      "priv_check": bool(r.get("priv_check")), "tables": sorted(sqlrisk.tables(sql)),
                      "risk": [f.as_dict() for f in sqlrisk.assess(sql)]}))
            last_id = max(last_id, int(r["id"]))
        c.cursor["query_log_id"] = last_id

    def _workflow_events(self, c: Collected) -> None:
        since = parse_time(self.cursor.get("workflow_since")) or (utcnow() - timedelta(days=7))
        try:
            rows = self._workflows("w.finish_time > %s", (self._to_local_naive(since),))
        except SourceUnavailable as e:
            c.unavailable["events.workflows"] = str(e)
            return
        latest = since
        for w in rows:
            finished = parse_time(w["finished"]) or utcnow()
            latest = max(latest, finished)
            c.events.append(EventRecord(
                kind="archery.workflow", external_id=f"w{w['id']}", occurred_at=finished,
                actor=w.get("engineer") or "", action=w["syntax"], target=f"{w['instance']}/{w.get('db')}", data=w))
        c.cursor["workflow_since"] = iso(latest)

    def _discover(self, c: Collected) -> None:
        raw = self.secrets.get("discovery_dsns", "")
        if not raw:
            c.unavailable["archery.sensitive_columns"] = "No databases configured for sensitive-data discovery"
            return
        last = parse_time(self.cursor.get("discovered_at"))
        every = timedelta(hours=int(self.config["discovery_every_hours"] or 24))
        if last and utcnow() - last < every:
            c.carry_forward.add("archery.sensitive_columns")
            return

        def scan() -> list[dict[str, Any]]:
            targets = json.loads(raw)
            sampler = self._sampler
            if sampler is None and self.config["discovery_sample"]:
                sampler = self._sampler = discovery.PIISampler(get_settings().MAF_URL)
            found: list[dict[str, Any]] = []
            failures = []
            for t in targets:
                try:
                    conn, dialect = discovery.connect(t["dsn"])
                except Exception as e:
                    failures.append(f"{t.get('instance')}: {type(e).__name__}")
                    continue
                try:
                    found += [f.as_dict() for f in self._scan(conn, dialect, t["instance"], sampler=sampler)]
                finally:
                    conn.close()
            if failures and not found:
                raise RuntimeError("could not connect to any discovery database: " + "; ".join(failures))
            return found

        if c.gather("archery.sensitive_columns", scan) is not None:
            c.cursor["discovered_at"] = iso(utcnow())
