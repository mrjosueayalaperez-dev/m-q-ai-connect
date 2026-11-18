"""The backlog-import safeguard test (acceptance checklist, Stage 1):
validation, duplicate handling, and an outcome report — proven on
synthetic records, never displayed-only."""
from app.services import comeback, customers

CSV = """name,phone,email,language,last_service_date
Old Customer,321-555-0200,old@example.com,en,2025-01-15
Never Served,321-555-0201,,es,
Old Customer Duplicate,(321) 555-0200,old@example.com,en,2025-01-15
,321-555-0202,ghost@example.com,en,2025-03-01
No Contact,,,en,2025-02-01
Bad Date,321-555-0203,bad@example.com,en,15/01/2025
"""


def test_import_outcome_report(conn):
    report = comeback.import_backlog(conn, CSV)
    assert report["received"] == 6
    assert report["imported"] == 2
    assert report["merged"] == 1
    assert len(report["rejected"]) == 3
    reasons = " ".join(r["reason"] for r in report["rejected"])
    assert "missing name" in reasons
    assert "missing both phone and email" in reasons
    assert "YYYY-MM-DD" in reasons


def test_imported_customers_are_found_by_comeback(conn):
    comeback.import_backlog(conn, CSV)
    lapsed = comeback.lapsed_customers(conn, inactive_days=90, now="2026-11-17T00:00:00Z")
    names = {c["name"] for c in lapsed}
    assert "Old Customer" in names       # served long ago
    assert "Never Served" in names       # imported, never served
    assert len(customers.list_customers(conn)) == 2  # duplicate resolved to one


def test_bad_header_rejected(conn):
    import pytest
    with pytest.raises(ValueError):
        comeback.import_backlog(conn, "foo,bar\n1,2\n")
