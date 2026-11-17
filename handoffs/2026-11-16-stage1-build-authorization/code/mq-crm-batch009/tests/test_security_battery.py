"""Adversarial battery for the Message Center — builder-side, NOT a
substitute for independent verification. Each test attempts a bypass the
way an operator (or a bug) actually could: through the service rules and
through the API's role gates. Expected: every bypass refused, and every
refused send leaves an audit record."""
import os
import tempfile

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "battery.db"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main as main_mod  # noqa: E402
from app.services import ai_assist, customers, messages  # noqa: E402
from tests.conftest import auth_headers  # noqa: E402

client = TestClient(main_mod.app)


def _cust(conn, phone, consent=True):
    c, _ = customers.create_customer(conn, "Target", phone=phone, language="en",
                                     consent_marketing=consent,
                                     consent_source="battery")
    return c


def test_duplicate_send_refused(conn):
    cust = _cust(conn, "3215550601")
    msg = messages.compose_template(conn, cust["id"], "comeback")
    messages.approve(conn, msg["id"])
    messages.send(conn, msg["id"])
    with pytest.raises(PermissionError):
        messages.send(conn, msg["id"])  # second send must refuse


def test_send_inbound_message_refused(conn):
    cust = _cust(conn, "3215550602")
    inbound = messages.record_inbound(conn, cust["id"], "hello?", "en")
    with pytest.raises(PermissionError):
        messages.send(conn, inbound["id"])


def test_double_approve_refused(conn):
    cust = _cust(conn, "3215550603")
    msg = messages.compose_template(conn, cust["id"], "comeback")
    messages.approve(conn, msg["id"])
    with pytest.raises(ValueError):
        messages.approve(conn, msg["id"])


def test_tampered_approval_with_pending_translation_refused(conn):
    """Alter the status directly in the DB (bypassing approve()) on a
    message whose translation is still pending: send must STILL refuse —
    the send gate re-checks the precondition, it does not trust the flag."""
    cust = _cust(conn, "3215550604")
    cust_es, _ = customers.create_customer(conn, "ES Target", phone="3215550605",
                                           language="es")
    msg = messages.compose_free_text(conn, cust_es["id"], "Your part arrived.", "en")
    assert msg["translation_pending"] == 1
    conn.execute("UPDATE messages SET status = 'approved' WHERE id = ?", (msg["id"],))
    conn.commit()
    with pytest.raises(PermissionError):
        messages.send(conn, msg["id"])


def test_ai_draft_respects_consent_gate(conn):
    cust = _cust(conn, "3215550606", consent=False)
    with pytest.raises(PermissionError):
        ai_assist.draft_comeback(conn, cust["id"])


def test_failed_send_leaves_audit_record():
    r = client.post("/api/customers", json={
        "name": "Audit Ana", "phone": "3215550607", "language": "en",
        "consent_marketing": True, "consent_source": "battery"})
    cid = r.json()["customer"]["id"]
    r = client.post("/api/messages/template", json={
        "customer_id": cid, "template_key": "comeback", "context": {}})
    mid = r.json()["id"]
    before = main_mod.conn.execute(
        "SELECT COUNT(*) AS n FROM audit_log WHERE action = 'send_message_denied'"
    ).fetchone()["n"]
    r = client.post(f"/api/messages/{mid}/send")  # draft, never approved
    assert r.status_code == 403
    after = main_mod.conn.execute(
        "SELECT COUNT(*) AS n FROM audit_log WHERE action = 'send_message_denied'"
    ).fetchone()["n"]
    assert after == before + 1


def test_viewer_role_cannot_approve_or_send():
    r = client.post("/api/customers", json={
        "name": "Viewer Vic", "phone": "3215550608", "language": "en",
        "consent_marketing": True, "consent_source": "battery"})
    cid = r.json()["customer"]["id"]
    r = client.post("/api/messages/template", json={
        "customer_id": cid, "template_key": "comeback", "context": {}})
    mid = r.json()["id"]
    assert client.post(f"/api/messages/{mid}/approve",
                       headers=auth_headers("viewer")).status_code == 403
    assert client.post(f"/api/messages/{mid}/send",
                       headers=auth_headers("viewer")).status_code == 403
