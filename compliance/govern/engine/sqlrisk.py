"""Static risk assessment of SQL text.

Deliberately lexical: it strips comments and string literals, splits statements
and pattern-matches what's left. That is enough to catch the operations reviewers
care about (unbounded writes, destructive DDL, privilege changes, file export)
across MySQL, PostgreSQL and Oracle dialects without a parser per dialect. It
can miss obfuscated SQL; it is a reviewer's aid, not a gate.
"""
import re
from dataclasses import dataclass

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}

_COMMENT = re.compile(r"--[^\n]*|#[^\n]*|/\*.*?\*/", re.S)
_STRING = re.compile(r"'(?:''|\\.|[^'\\])*'|\"(?:\"\"|\\.|[^\"\\])*\"", re.S)
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    statement: str  # the offending statement, shortened

    def as_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity, "statement": self.statement}


def normalise(sql: str) -> str:
    """Comments removed, string literals replaced with '?', whitespace collapsed."""
    text = _STRING.sub("'?'", sql)
    text = _COMMENT.sub(" ", text)
    return _WS.sub(" ", text).strip()


def statements(sql: str) -> list[str]:
    return [s.strip() for s in normalise(sql).split(";") if s.strip()]


_RULES: list[tuple[str, str, re.Pattern]] = [
    ("drop_object", "critical", re.compile(r"^DROP\s+(TABLE|DATABASE|SCHEMA|VIEW|INDEX|PROCEDURE|FUNCTION|TRIGGER|USER)\b", re.I)),
    ("truncate", "critical", re.compile(r"^TRUNCATE\b", re.I)),
    ("file_export", "critical", re.compile(r"\bINTO\s+(OUTFILE|DUMPFILE)\b|\bLOAD_FILE\s*\(|\bCOPY\b.+\bTO\b\s+(PROGRAM|'\?')", re.I)),
    ("alter_drop", "high", re.compile(r"^ALTER\s+TABLE\b.*\bDROP\b", re.I)),
    ("privilege_change", "high", re.compile(r"^(GRANT|REVOKE)\b|^(CREATE|ALTER|RENAME)\s+USER\b|^SET\s+PASSWORD\b", re.I)),
    ("disable_safety", "high", re.compile(r"^SET\s+(GLOBAL\s+|SESSION\s+)?(SQL_SAFE_UPDATES|FOREIGN_KEY_CHECKS|SQL_LOG_BIN)\s*=\s*(0|OFF)\b", re.I)),
    ("rename_table", "medium", re.compile(r"^RENAME\s+TABLE\b|^ALTER\s+TABLE\b.*\bRENAME\b", re.I)),
]
_WRITE = re.compile(r"^(DELETE|UPDATE)\b", re.I)
_WHERE = re.compile(r"\bWHERE\b(?P<cond>.*)", re.I)
_TAUTOLOGY = re.compile(r"^\s*(\(?\s*1\s*=\s*1\s*\)?|TRUE|'\?'\s*=\s*'\?')\s*(LIMIT\b.*)?$", re.I)
_SELECT_STAR = re.compile(r"^SELECT\s+(DISTINCT\s+)?(\w+\.)?\*\s+FROM\b", re.I)
_TABLES = re.compile(r"\b(?:FROM|JOIN|UPDATE|INTO|TABLE)\s+([`\"\[]?[\w$]+[`\"\]]?(?:\s*\.\s*[`\"\[]?[\w$]+[`\"\]]?)?)", re.I)


def _short(stmt: str) -> str:
    return stmt if len(stmt) <= 300 else stmt[:297] + "..."


def assess(sql: str) -> list[Finding]:
    found: list[Finding] = []
    for stmt in statements(sql):
        for code, severity, pattern in _RULES:
            if pattern.search(stmt):
                found.append(Finding(code, severity, _short(stmt)))
        if _WRITE.match(stmt):
            where = _WHERE.search(stmt)
            if not where:
                found.append(Finding("write_without_where", "critical", _short(stmt)))
            elif _TAUTOLOGY.match(where.group("cond")):
                found.append(Finding("write_where_always_true", "critical", _short(stmt)))
        if _SELECT_STAR.match(stmt):
            found.append(Finding("select_star", "low", _short(stmt)))
    return found


def tables(sql: str) -> set[str]:
    """Table names referenced, lower-cased, without schema or quoting."""
    out = set()
    for m in _TABLES.finditer(normalise(sql)):
        name = re.sub(r"[`\"\[\]\s]", "", m.group(1)).split(".")[-1].lower()
        if name and name not in {"select", "dual"}:
            out.add(name)
    return out


def worst(findings: list[Finding]) -> str | None:
    return max((f.severity for f in findings), key=SEVERITY_RANK.__getitem__, default=None)
