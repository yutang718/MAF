"""Check registry.

A check reads facts a connector collected and returns a verdict. It knows nothing
about frameworks: which controls a check provides evidence for is declared in
catalog/mappings.yaml, so one check can serve ISO 27001, NIST CSF and HIPAA at once.
"""
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

STATUSES = ("pass", "partial", "fail", "not_available", "error")
SEVERITIES = ("low", "medium", "high", "critical")
MAX_ITEMS = 200  # failing items kept per result; the count is always exact


@dataclass
class Outcome:
    status: str
    # Values substituted into the check's summary template, e.g. {"failing": 3, "total": 40}.
    params: dict[str, Any] = field(default_factory=dict)
    # The specific users/devices/repos behind a non-pass result.
    items: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        assert self.status in STATUSES, self.status


@dataclass(frozen=True)
class Check:
    id: str
    kind: str  # connector kind the facts come from
    title: Mapping[str, str]
    summary: Mapping[str, str]  # template with {param} placeholders
    remediation: Mapping[str, str]
    severity: str
    requires: tuple[str, ...]  # fact keys; missing any -> not_available
    defaults: Mapping[str, Any]  # thresholds an operator can override per connector
    fn: Callable[[Mapping[str, Any], Mapping[str, Any]], Outcome]

    def render_summary(self, lang: str, params: Mapping[str, Any]) -> str:
        template = self.summary.get(lang) or self.summary["en"]
        try:
            return template.format(**params)
        except (KeyError, IndexError, ValueError):
            return template


REGISTRY: dict[str, Check] = {}


def check(id: str, kind: str, *, title: dict, summary: dict, remediation: dict,
          severity: str, requires: tuple[str, ...] | list[str], defaults: dict | None = None):
    assert severity in SEVERITIES, severity

    def register(fn):
        assert id not in REGISTRY, f"duplicate check {id}"
        REGISTRY[id] = Check(id=id, kind=kind, title=title, summary=summary, remediation=remediation,
                             severity=severity, requires=tuple(requires), defaults=defaults or {}, fn=fn)
        return fn
    return register


def ratio_outcome(failing: list[dict], total: int, *, pass_at: float = 1.0, partial_at: float = 0.9,
                  **extra) -> Outcome:
    """Grade by the share of items that are fine. Nothing to judge counts as a pass."""
    ok = total - len(failing)
    share = ok / total if total else 1.0
    if share >= pass_at:
        status = "pass"
    elif share >= partial_at:
        status = "partial"
    else:
        status = "fail"
    return Outcome(status, {"failing": len(failing), "total": total, "percent": round(share * 100, 1), **extra},
                   failing[:MAX_ITEMS])


def load_all() -> dict[str, Check]:
    """Import every check module so their decorators register."""
    from govern.checks import archery, github, gitlab, m365  # noqa: F401
    return REGISTRY
