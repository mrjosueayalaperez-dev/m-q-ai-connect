"""Batch 004 tests — real compose context, audit-chain recovery, and
region/data-residency metadata. Builder-side, as always; the independent
layer confirms."""
import os
import tempfile

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b4.db"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as dbmod  # noqa: E402
from app import main as main_mod  # noqa: E402
from app.services import billing, bookings, customers, data_rights, messages  # noqa: E402
from tests.conftest import auth_headers  # noqa: E402

client = TestClient(main_mod.app)


# ---- 1. Real compose context (Batch 002 placeholder fix) ----

def _cust(conn, phone, lang="en"):
    c, _ = customers.create_customer(conn, "Ctx", phone=phone, language=lang,
                                     consent_marketing=True, consent_source="b4")
    return c


def test_reminder_composes_real_booking_context(conn):
    cust = _cust(conn, "3215550901")
    bookings.create_booking(conn, cust["id"], "Haircut", "2026-12-01 09:00",
                            "America/New_York")
    msg = messages.compose_template(conn, cust["id"], "reminder")
    assert "Haircut" in msg["original_text"]
    assert "2026-12-01 09:00 EST" in msg["original_text"]
    assert "—" not in msg["original_text"] and "{when}" not in msg["original_text"]


def test_reminder_real_context_in_ht(conn):
    cust = _cust(conn, "3215550902", lang="ht")
    bookings.create_booking(conn, cust["id"], "Koupe cheve", "2026-12-01 09:00",
                            "America/New_York")
    msg = messages.compose_template(conn, cust["id"], "reminder")
    assert msg["original_text"].startswith("Bonjou")
    assert "Koupe cheve" in msg["original_text"]


def test_reminder_explicit_context_wins(conn):
    cust = _cust(conn, "3215550903")
    bookings.create_booking(conn, cust["id"], "Real", "2026-12-01 09:00",
                            "America/New_York")
    msg = messages.compose_template(conn, cust["id"], "reminder",
                                    when="CUSTOM WHEN", title="CUSTOM TITLE")
    assert "CUSTOM WHEN" in msg["original_text"] and "CUSTOM TITLE" in msg["original_text"]


def test_reminder_without_booking_refused(conn):
    cust = _cust(conn, "3215550904")
    with pytest.raises(ValueError):
        messages.compose_template(conn, cust["id"], "reminder")


def test_quote_ready_real_total_and_summary(conn):
    cust = _cust(conn, "3215550905")
    q = billing.create_quote(conn, cust["id"], "USD")
    billing.add_quote_item(conn, q["id"], "Work", 2, 2500)
    msg = messages.compose_template(conn, cust["id"], "quote_ready")
    assert "USD 50.00" in msg["original_text"]
    assert "2 × Work" in msg["original_text"]


def test_quote_ready_without_quote_refused(conn):
    cust = _cust(conn, "3215550906")
    with pytest.raises(ValueError):
        messages.compose_template(conn, cust["id"], "quote_ready")


def test_invoice_ready_real_total(conn):
    cust = _cust(conn, "3215550907")
    q = billing.create_quote(conn, cust["id"], "USD")
    billing.add_quote_item(conn, q["id"], "Work", 1, 123456)
    billing.set_quote_status(conn, q["id"], "accepted")
    billing.convert_to_invoice(conn, q["id"])
    msg = messages.compose_template(conn, cust["id"], "invoice_ready")
    assert "USD 1,234.56" in msg["original_text"]


def test_api_compose_empty_context_uses_real_records():
    r = client.post("/api/customers", json={
        "name": "API Ctx", "phone": "3215550908", "language": "es",
        "consent_marketing": True, "consent_source": "b4"})
    cid = r.json()["customer"]["id"]
    r = client.post("/api/bookings", json={
        "customer_id": cid, "title": "Cita real", "local_start": "2026-12-02 10:30",
        "tz": "America/New_York"})
    assert r.status_code == 200
    r = client.post("/api/messages/template", json={
        "customer_id": cid, "template_key": "reminder", "context": {}})
    assert r.status_code == 200
    text = r.json()["original_text"]
    assert "Cita real" in text and "2026-12-02 10:30 EST" in text


def test_api_compose_unresolvable_context_is_400():
    r = client.post("/api/customers", json={
        "name": "API NoCtx", "phone": "3215550909", "language": "en"})
    cid = r.json()["customer"]["id"]
    r = client.post("/api/messages/template", json={
        "customer_id": cid, "template_key": "reminder", "context": {}})
    assert r.status_code == 400


# ---- 2. Audit-chain recovery ----

def _seed_audit(conn):
    dbmod.audit(conn, "op", "owner", "record_payment", "invoices", 1,
                {"amount_minor": 100})
    dbmod.audit(conn, "op", "owner", "send_message", "messages", 2)
    dbmod.audit(conn, "op", "staff", "import_backlog", "customers", None,
                {"imported": 3})


def test_audit_recovery_after_tamper(conn):
    _seed_audit(conn)
    assert dbmod.verify_audit_chain(conn)
    conn.execute("UPDATE audit_log SET detail = '{\"amount_minor\": 999}'"
                 " WHERE id = 1")
    conn.commit()
    assert not dbmod.verify_audit_chain(conn)
    status = dbmod.audit_chain_status(conn)
    assert status["ok"] is False and status["first_bad_id"] == 1
    out = dbmod.recover_audit_chain(conn, "op", "owner", "tamper drill")
    assert out["chain_ok"] is True and out["rows_preserved"] == 3
    assert dbmod.verify_audit_chain(conn)
    dbmod.audit(conn, "op", "owner", "record_payment", "invoices", 2)
    assert dbmod.verify_audit_chain(conn)


def test_audit_recovery_refuses_intact_chain(conn):
    _seed_audit(conn)
    with pytest.raises(ValueError):
        dbmod.recover_audit_chain(conn, "op", "owner", "not needed")


def test_audit_recovery_detects_later_tamper(conn):
    _seed_audit(conn)
    conn.execute("UPDATE audit_log SET actor = 'mallory' WHERE id = 2")
    conn.commit()
    dbmod.recover_audit_chain(conn, "op", "owner", "drill")
    assert dbmod.verify_audit_chain(conn)
    dbmod.audit(conn, "op", "owner", "send_message", "messages", 5)
    last = conn.execute("SELECT MAX(id) AS m FROM audit_log").fetchone()["m"]
    conn.execute("UPDATE audit_log SET detail = '{\"forged\": true}'"
                 " WHERE id = ?", (last,))
    conn.commit()
    assert not dbmod.verify_audit_chain(conn)


def test_audit_recovery_detects_deleted_prefix_row(conn):
    _seed_audit(conn)
    conn.execute("UPDATE audit_log SET actor = 'mallory' WHERE id = 1")
    conn.commit()
    dbmod.recover_audit_chain(conn, "op", "owner", "drill")
    assert dbmod.verify_audit_chain(conn)
    conn.execute("DELETE FROM audit_log WHERE id = 1")
    conn.commit()
    assert not dbmod.verify_audit_chain(conn)


def test_audit_recovery_detects_snapshot_tamper(conn):
    _seed_audit(conn)
    conn.execute("UPDATE audit_log SET actor = 'mallory' WHERE id = 1")
    conn.commit()
    dbmod.recover_audit_chain(conn, "op", "owner", "drill")
    assert dbmod.verify_audit_chain(conn)
    conn.execute("UPDATE audit_snapshots SET rows_json = '[]'")
    conn.commit()
    assert not dbmod.verify_audit_chain(conn)


def test_api_audit_status_and_recover_roles():
    r = client.get("/api/audit/status")
    assert r.status_code == 200 and r.json()["ok"] is True
    r = client.post("/api/audit/recover", json={"reason": "x"},
                    headers=auth_headers("staff"))
    assert r.status_code == 403
    r = client.post("/api/audit/recover", json={"reason": "x"},
                    headers=auth_headers("owner"))
    assert r.status_code == 400  # healthy chain: recovery refuses


# ---- 3. Region / data-residency metadata ----

def test_region_metadata_on_record_and_export(conn):
    cust, _ = customers.create_customer(
        conn, "Region Rosa", phone="3215550910", language="es",
        region="US-FL", data_residency="US")
    assert cust["region"] == "US-FL" and cust["data_residency"] == "US"
    exported = data_rights.export_customer(conn, cust["id"])
    assert exported["customer"]["region"] == "US-FL"
    assert exported["customer"]["data_residency"] == "US"


def test_region_metadata_defaults(conn):
    cust, _ = customers.create_customer(conn, "Default Dan", phone="3215550911")
    assert cust["data_residency"] == "US" and cust["region"] is None


def test_region_filled_on_duplicate_merge(conn):
    first, _ = customers.create_customer(conn, "Merge Mia", phone="3215550912")
    assert first["region"] is None
    merged, was_merged = customers.create_customer(
        conn, "Merge Mia", phone="3215550912", region="US-FL")
    assert was_merged and merged["region"] == "US-FL"
