"""Find columns that hold personal or health data, so masking gaps can be shown.

Two signals: the column's name and comment (English, Chinese, Malay), and,
optionally, a small sample of values run through MAF's own PII detector. Sampled
values are never stored — only the entity types found and how often.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import httpx

from govern.log import get_logger

logger = get_logger(__name__)

CATEGORIES: dict[str, re.Pattern] = {
    "national_id": re.compile(r"id_?card|idcard|identity_?(no|num)|nric|(^|_)ic_?(no|num)|mykad|ssn|身份证|证件号|kad_pengenalan", re.I),
    "phone": re.compile(r"phone|mobile|(^|_)tel(_|$)|cellphone|contact_?no|手机|电话|no_?tel|telefon", re.I),
    "email": re.compile(r"(^|_)e?mail(_|$)|email|邮箱", re.I),
    "person_name": re.compile(r"(^|_)(full_?|real_?|first_?|last_?)?name$|姓名|真实姓名|(^|_)nama(_|$)", re.I),
    "address": re.compile(r"address|(^|_)addr(_|$)|住址|地址|alamat", re.I),
    "birth_date": re.compile(r"birth|(^|_)dob(_|$)|生日|出生|tarikh_?lahir", re.I),
    "financial": re.compile(r"bank_?(card|account|acct|no)|card_?(no|num)|iban|account_?(no|num)|银行卡|卡号|akaun", re.I),
    "passport": re.compile(r"passport|护照|pasport", re.I),
    "health": re.compile(r"diagnos|(^|_)icd|medical|patient|(^|_)mrn(_|$)|病历|诊断|病史|allerg|prescri|medication|"
                         r"blood_?type|lab_?result|symptom|treatment|处方|过敏|pesakit|rawatan", re.I),
    "credential": re.compile(r"password|passwd|(^|_)pwd(_|$)|secret|api_?key|(^|_)token(_|$)|密码", re.I),
}
TEXT_TYPES = {"char", "varchar", "text", "tinytext", "mediumtext", "longtext", "nvarchar", "nchar",
              "character varying", "character", "json", "jsonb"}
# MAF entity types that confirm a column holds personal data.
PII_ENTITY_TYPES = {"EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON", "CREDIT_CARD", "IBAN_CODE", "US_SSN",
                    "LOCATION", "DATE_TIME", "IP_ADDRESS", "MEDICAL_LICENSE", "US_PASSPORT"}


@dataclass
class ColumnFinding:
    instance: str
    schema: str
    table: str
    column: str
    categories: list[str]
    by: list[str] = field(default_factory=list)  # name | comment | sample
    sample_entities: dict[str, float] = field(default_factory=dict)  # entity type -> share of sampled values

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def classify_name(column: str, comment: str = "") -> tuple[list[str], list[str]]:
    cats, by = [], []
    for cat, pattern in CATEGORIES.items():
        hit_name = bool(pattern.search(column))
        hit_comment = bool(comment and pattern.search(comment))
        if hit_name or hit_comment:
            cats.append(cat)
            if hit_name and "name" not in by:
                by.append("name")
            if hit_comment and "comment" not in by:
                by.append("comment")
    return cats, by


class PIISampler:
    """Calls MAF's POST /api/v1/pii/detect/batch."""

    def __init__(self, maf_url: str, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(base_url=maf_url.rstrip("/"), timeout=60, transport=transport)

    def close(self) -> None:
        self._client.close()

    def entity_shares(self, values: list[str]) -> dict[str, float]:
        values = [v[:500] for v in values if v and v.strip()]
        if not values:
            return {}
        resp = self._client.post("/api/v1/pii/detect/batch", json={"texts": values, "language": "en"})
        resp.raise_for_status()
        counts: Counter[str] = Counter()
        for result in resp.json().get("results", []):
            for t in {e.get("type") for e in result.get("entities", []) if e.get("score", 1) >= 0.6}:
                counts[t] += 1
        return {t: round(n / len(values), 2) for t, n in counts.items()}


def scan_database(conn, dialect: str, instance: str, *, sampler: PIISampler | None = None,
                  sample_size: int = 20, max_columns: int = 2000) -> list[ColumnFinding]:
    """Scan one database connection. `conn` is a DB-API connection; reads only."""
    cur = conn.cursor()
    if dialect == "mysql":
        cur.execute("SELECT table_schema, table_name, column_name, data_type, column_comment "
                    "FROM information_schema.columns WHERE table_schema NOT IN "
                    "('mysql','information_schema','performance_schema','sys') LIMIT %s", (max_columns,))
    else:
        cur.execute("SELECT c.table_schema, c.table_name, c.column_name, c.data_type, "
                    "coalesce(col_description((quote_ident(c.table_schema)||'.'||quote_ident(c.table_name))::regclass, "
                    "c.ordinal_position), '') FROM information_schema.columns c "
                    "WHERE c.table_schema NOT IN ('pg_catalog','information_schema') LIMIT %s", (max_columns,))
    findings = []
    for schema, table, column, data_type, comment in cur.fetchall():
        cats, by = classify_name(column, comment or "")
        sample: dict[str, float] = {}
        if sampler and (cats or (data_type or "").lower() in TEXT_TYPES):
            try:
                sample = sampler.entity_shares(_sample(conn, dialect, schema, table, column, sample_size))
            except Exception as e:  # sampling is a bonus; name matches still count
                logger.warning(f"sampling {schema}.{table}.{column} failed: {e}")
            confirmed = {t: s for t, s in sample.items() if t in PII_ENTITY_TYPES and s >= 0.3}
            if confirmed:
                by.append("sample")
                if not cats:
                    cats = ["detected_pii"]
            sample = confirmed
        if cats:
            findings.append(ColumnFinding(instance, schema, table, column, cats, by, sample))
    cur.close()
    return findings


def _quote(dialect: str, ident: str) -> str:
    if dialect == "mysql":
        return "`" + ident.replace("`", "``") + "`"
    return '"' + ident.replace('"', '""') + '"'


def _sample(conn, dialect: str, schema: str, table: str, column: str, n: int) -> list[str]:
    q = _quote
    col = q(dialect, column)
    sql = (f"SELECT {col} FROM {q(dialect, schema)}.{q(dialect, table)} "
           f"WHERE {col} IS NOT NULL LIMIT {int(n)}")
    cur = conn.cursor()
    try:
        cur.execute(sql)
        return [str(r[0]) for r in cur.fetchall()]
    finally:
        cur.close()


def connect(dsn: str):
    """Open a read-only connection from mysql://user:pass@host:port/db or postgresql://..."""
    from urllib.parse import unquote, urlparse
    u = urlparse(dsn)
    if u.scheme.startswith("mysql"):
        import pymysql
        conn = pymysql.connect(host=u.hostname, port=u.port or 3306, user=unquote(u.username or ""),
                               password=unquote(u.password or ""), database=(u.path or "/").lstrip("/") or None,
                               connect_timeout=15, read_timeout=120, charset="utf8mb4")
        with conn.cursor() as cur:
            cur.execute("SET SESSION TRANSACTION READ ONLY")
        return conn, "mysql"
    if u.scheme.startswith("postgres"):
        import psycopg
        conn = psycopg.connect(dsn.replace("postgresql+psycopg", "postgresql"), connect_timeout=15)
        conn.read_only = True
        return conn, "postgresql"
    raise ValueError(f"unsupported database scheme {u.scheme!r}")
