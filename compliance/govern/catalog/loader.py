"""Framework catalogs and check-to-control mappings, loaded from the YAML beside this file."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

HERE = Path(__file__).parent
FRAMEWORK_FILES = ("iso27001.yaml", "nist_csf.yaml", "hipaa.yaml")


@dataclass(frozen=True)
class Control:
    id: str
    group: str
    title: dict[str, str]


@dataclass(frozen=True)
class Framework:
    id: str
    name: dict[str, str]
    description: dict[str, str]
    groups: dict[str, dict[str, str]]  # group id -> {en, zh}
    controls: dict[str, Control]  # in catalog order


def _framework(path: Path) -> Framework:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    groups = {g[0]: {"en": g[1], "zh": g[2]} for g in raw["groups"]}
    controls: dict[str, Control] = {}
    for cid, group, en, zh in raw["controls"]:
        cid = str(cid)
        if cid in controls:
            raise ValueError(f"{path.name}: duplicate control {cid}")
        if str(group) not in groups:
            raise ValueError(f"{path.name}: {cid} is in unknown group {group}")
        controls[cid] = Control(cid, str(group), {"en": en, "zh": zh})
    return Framework(raw["id"], raw["name"], raw["description"], groups, controls)


@lru_cache
def frameworks() -> dict[str, Framework]:
    loaded = [_framework(HERE / name) for name in FRAMEWORK_FILES]
    return {f.id: f for f in loaded}


@lru_cache
def mappings() -> dict[str, dict[str, tuple[str, ...]]]:
    """check id -> framework id -> control ids. Validated against the catalogs."""
    raw = yaml.safe_load((HERE / "mappings.yaml").read_text(encoding="utf-8"))
    fws = frameworks()
    out: dict[str, dict[str, tuple[str, ...]]] = {}
    for check_id, per_fw in raw.items():
        out[check_id] = {}
        for fw_id, control_ids in per_fw.items():
            if fw_id not in fws:
                raise ValueError(f"mappings.yaml: {check_id} maps to unknown framework {fw_id}")
            for cid in control_ids:
                if str(cid) not in fws[fw_id].controls:
                    raise ValueError(f"mappings.yaml: {check_id} maps to unknown {fw_id} control {cid}")
            out[check_id][fw_id] = tuple(str(c) for c in control_ids)
    return out


@lru_cache
def checks_by_control() -> dict[tuple[str, str], tuple[str, ...]]:
    """(framework id, control id) -> check ids that provide evidence for it."""
    index: dict[tuple[str, str], list[str]] = {}
    for check_id, per_fw in mappings().items():
        for fw_id, control_ids in per_fw.items():
            for cid in control_ids:
                index.setdefault((fw_id, cid), []).append(check_id)
    return {k: tuple(v) for k, v in index.items()}


@dataclass(frozen=True)
class PostureItem:
    code: str
    check: str | None  # an automated check, or
    rule: str | None  # an alert rule whose open alerts are the findings
    sla: bool  # check status comes from overdue findings rather than the check itself


@dataclass(frozen=True)
class PostureDomain:
    id: str
    source: str
    name: dict[str, str]
    items: tuple[PostureItem, ...]


@lru_cache
def posture() -> tuple[PostureDomain, ...]:
    """The security-check catalogue shown on the posture page, in display order."""
    raw = yaml.safe_load((HERE / "posture.yaml").read_text(encoding="utf-8"))
    domains, codes = [], set()
    for d in raw["domains"]:
        items = []
        for it in d["items"]:
            if it["code"] in codes:
                raise ValueError(f"posture.yaml: duplicate code {it['code']}")
            codes.add(it["code"])
            if bool(it.get("check")) == bool(it.get("rule")):
                raise ValueError(f"posture.yaml: {it['code']} needs exactly one of check or rule")
            items.append(PostureItem(it["code"], it.get("check"), it.get("rule"), bool(it.get("sla"))))
        domains.append(PostureDomain(d["id"], d["source"], d["name"], tuple(items)))
    return tuple(domains)


@lru_cache
def sla_graded() -> frozenset[str]:
    return frozenset(it.check for d in posture() for it in d.items if it.check and it.sla)


@lru_cache
def posture_codes() -> dict[str, str]:
    """check or rule id -> posture code"""
    return {(it.check or it.rule): it.code for d in posture() for it in d.items}
