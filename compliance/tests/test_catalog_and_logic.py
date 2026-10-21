from datetime import datetime, timezone

from govern.catalog.loader import frameworks, mappings
from govern.checks.base import load_all as load_checks
from govern.engine import discovery, sqlrisk
from govern.rules.base import WorkHours, load_all as load_rules
from govern.timeutil import parse_time


def test_catalog_sizes_match_the_published_standards():
    fws = frameworks()
    assert len(fws["iso27001"].controls) == 93
    assert len(fws["nist_csf"].controls) == 106
    assert len(fws["hipaa"].controls) == 48
    for fw in fws.values():
        for c in fw.controls.values():
            assert c.title["en"] and c.title["zh"], c.id


def test_every_check_maps_to_real_controls_and_every_mapping_to_a_check():
    checks = load_checks()
    m = mappings()  # raises on unknown control ids
    assert set(checks) == set(m)
    for check_id, per_fw in m.items():
        assert per_fw.get("iso27001"), f"{check_id} has no ISO 27001 mapping"


def test_check_metadata_is_bilingual():
    for ch in load_checks().values():
        for d in (ch.title, ch.summary, ch.remediation):
            assert d.get("en") and d.get("zh"), ch.id


def test_rules_load():
    rules = load_rules()
    assert {"github.risky_operation", "github.bulk_download", "archery.query_risk", "m365.security_alert"} <= set(rules)


# ─── SQL risk ──────────────────────────────────────────────────────────────────

def codes(sql):
    return {f.code for f in sqlrisk.assess(sql)}


def test_unbounded_writes_are_critical():
    assert "write_without_where" in codes("DELETE FROM patients")
    assert "write_without_where" in codes("update users set role='admin'")
    assert "write_where_always_true" in codes("DELETE FROM t WHERE 1=1")
    assert not codes("DELETE FROM t WHERE id = 5")


def test_where_inside_a_string_or_comment_doesnt_count():
    assert "write_without_where" in codes("UPDATE t SET note = 'where am I'")
    assert "write_without_where" in codes("DELETE FROM t -- WHERE id = 1")


def test_destructive_ddl_and_privileges():
    assert "drop_object" in codes("DROP TABLE orders")
    assert "truncate" in codes("truncate table logs")
    assert "alter_drop" in codes("ALTER TABLE t DROP COLUMN ssn")
    assert "privilege_change" in codes("GRANT ALL ON *.* TO 'x'@'%'")
    assert "file_export" in codes("SELECT * FROM users INTO OUTFILE '/tmp/u.csv'")


def test_multiple_statements_are_each_assessed():
    found = codes("SELECT 1; DELETE FROM a; UPDATE b SET x=1 WHERE id=2")
    assert found == {"write_without_where"}


def test_select_star_and_tables():
    assert "select_star" in codes("select * from patient_record where id = 1")
    assert sqlrisk.tables("SELECT a.x FROM hr.employees a JOIN `salary` s ON s.id=a.id") == {"employees", "salary"}


# ─── discovery ─────────────────────────────────────────────────────────────────

def test_column_names_in_three_languages():
    assert "national_id" in discovery.classify_name("ic_no")[0]
    assert "national_id" in discovery.classify_name("id_card")[0]
    assert "phone" in discovery.classify_name("no_tel")[0]
    assert "health" in discovery.classify_name("diagnosis_code")[0]
    assert "health" in discovery.classify_name("remark", "病历摘要")[0]
    assert discovery.classify_name("remark", "病历摘要")[1] == ["comment"]
    assert discovery.classify_name("created_at")[0] == []


# ─── time ──────────────────────────────────────────────────────────────────────

def test_time_parsing():
    assert parse_time("2026-10-01T10:00:00.1234567Z") == datetime(2026, 10, 1, 10, 0, 0, 123456, timezone.utc)
    assert parse_time(1_790_000_000_000).year == 2026  # epoch ms
    assert parse_time("") is None and parse_time("garbage") is None


def test_work_hours_use_local_time():
    hours = WorkHours("Asia/Brunei", "08:00-19:00", [1, 2, 3, 4, 5])
    # Wednesday 2026-10-21 02:00 UTC = 10:00 in Brunei
    assert hours.contains(datetime(2026, 10, 21, 2, 0, tzinfo=timezone.utc))
    # 12:00 UTC = 20:00 local
    assert not hours.contains(datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc))
    # Saturday
    assert not hours.contains(datetime(2026, 10, 24, 2, 0, tzinfo=timezone.utc))
