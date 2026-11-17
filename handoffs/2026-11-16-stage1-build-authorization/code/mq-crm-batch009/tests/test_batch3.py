"""Batch 003 tightening tests — each maps to an inspection target from the
readiness map. Builder-side, as always; the independent layer confirms."""
import os
import tempfile
import threading

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b3.db"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as dbmod  # noqa: E402
from app import main as main_mod  # noqa: E402
from app.services import customers, messages  # noqa: E402
from tests.conftest import auth_headers  # noqa: E402

client = TestClient(main_mod.app)


def _consented(conn, phone, lang="en"):
    c, _ = customers.create_customer(conn, "Tight", phone=phone, language=lang,
                                     consent_marketing=True, consent_source="b3")
    return c


def test_consent_withdrawn_after_approval_blocks_send(conn):
    cust = _consented(conn, "3215550801")
    msg = messages.compose_template(conn, cust["id"], "comeback")
    messages.approve(conn, msg["id"])
    customers.set_consent(conn, cust["id"], False, "customer asked to stop")
    with pytest.raises(PermissionError):
        messages.send(conn, msg["id"])


def test_content_change_after_approval_invalidates(conn):
    cust, _ = customers.create_customer(conn, "ES B3", phone="3215550802",
                                        language="es")
    # Batch 008b: free text carries an operator-declared purpose (unset => held).
    msg = messages.compose_free_text(conn, cust["id"], "Your part arrived.", "en",
                                     purpose="transactional")
    msg = messages.supply_translation(conn, msg["id"], "Su pieza llegó.")
    messages.approve(conn, msg["id"])
    changed = messages.supply_translation(conn, msg["id"], "Su pieza llegó ayer.")
    assert changed["status"] == "draft" and changed["approved_hash"] is None
    with pytest.raises(PermissionError):
        messages.send(conn, msg["id"])


def test_tampered_text_after_approval_blocks_send(conn):
    cust = _consented(conn, "3215550803")
    msg = messages.compose_template(conn, cust["id"], "comeback")
    messages.approve(conn, msg["id"])
    conn.execute("UPDATE messages SET original_text = 'SEND MONEY NOW'"
                 " WHERE id = ?", (msg["id"],))
    conn.commit()
    with pytest.raises(PermissionError):
        messages.send(conn, msg["id"])


def test_flag_only_tamper_blocks_send(conn):
    """Setting status='approved' directly in the DB, without approve(),
    leaves approved_hash empty — the send gate refuses."""
    cust = _consented(conn, "3215550804")
    msg = messages.compose_template(conn, cust["id"], "comeback")
    conn.execute("UPDATE messages SET status = 'approved' WHERE id = ?",
                 (msg["id"],))
    conn.commit()
    with pytest.raises(PermissionError):
        messages.send(conn, msg["id"])


def test_concurrent_duplicate_send_exactly_one_wins(tmp_path):
    path = str(tmp_path / "race.db")
    setup = dbmod.connect(path)
    cust = _consented(setup, "3215550805")
    msg = messages.compose_template(setup, cust["id"], "comeback")
    messages.approve(setup, msg["id"])
    setup.close()
    barrier = threading.Barrier(2)
    results = []

    def attempt():
        c = dbmod.connect(path)
        barrier.wait()
        try:
            messages.send(c, msg["id"])
            results.append("sent")
        except PermissionError:
            results.append("refused")
        finally:
            c.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["refused", "sent"]


def test_audit_chain_detects_tampering(conn):
    dbmod.audit(conn, "op", "owner", "record_payment", "invoices", 1, {"a": 1})
    dbmod.audit(conn, "op", "owner", "send_message", "messages", 2, {})
    assert dbmod.verify_audit_chain(conn) is True
    conn.execute("UPDATE audit_log SET detail = '{\"a\": 999}' WHERE id = 1")
    conn.commit()
    assert dbmod.verify_audit_chain(conn) is False


def test_withdraw_is_terminal(conn):
    cust = _consented(conn, "3215550806")
    msg = messages.compose_template(conn, cust["id"], "comeback")
    messages.approve(conn, msg["id"])
    gone = messages.withdraw(conn, msg["id"])
    assert gone["status"] == "withdrawn"
    with pytest.raises(PermissionError):
        messages.send(conn, msg["id"])
    with pytest.raises(ValueError):
        messages.approve(conn, msg["id"])
    with pytest.raises(ValueError):
        messages.withdraw(conn, msg["id"])


def test_export_role_gates():
    r = client.post("/api/customers", json={
        "name": "Gate Gail", "phone": "3215550807", "language": "pt",
        "consent_marketing": True, "consent_source": "b3"})
    cid = r.json()["customer"]["id"]
    assert client.get("/api/export", headers=auth_headers("staff")).status_code == 403
    assert client.get("/api/export", headers=auth_headers("viewer")).status_code == 403
    assert client.get(f"/api/customers/{cid}/export",
                      headers=auth_headers("staff")).status_code == 403
    ok = client.get(f"/api/customers/{cid}/export", headers=auth_headers("owner"))
    assert ok.status_code == 200
    assert ok.json()["customer"]["language"] == "pt"
