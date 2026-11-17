"""Batch 006 tests — the processing register becomes operable (owner-only,
audited) and the Message Center becomes genuinely two-way (inbound
endpoint + honest direction). Builder-side, as always."""
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b6.db"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main as main_mod  # noqa: E402
from app.services import customers, delivery, messages, register  # noqa: E402

client = TestClient(main_mod.app)


# ---- Processing register service ----

def test_register_entry_starts_unreviewed(conn):
    entry = register.add_entry(conn, "messages", "webhook", "delivery")
    assert entry["terms_reviewed"] == 0
    assert register.list_entries(conn)[0]["provider"] == "webhook"


def test_register_terms_toggle(conn):
    entry = register.add_entry(conn, "messages", "webhook")
    updated = register.set_terms_reviewed(conn, entry["id"], True)
    assert updated["terms_reviewed"] == 1
    updated = register.set_terms_reviewed(conn, entry["id"], False)
    assert updated["terms_reviewed"] == 0
    with pytest.raises(ValueError):
        register.set_terms_reviewed(conn, 99999, True)


# ---- Register drives the Batch 005 gate, end to end ----

class _Stub:
    def __init__(self):
        self.payloads = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.payloads.append(json.loads(body))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"id": "stub-6"}).encode())

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/hook"

    def stop(self):
        self.server.shutdown()


def test_gate_opens_and_closes_via_register(conn, monkeypatch):
    stub = _Stub()
    monkeypatch.setenv("MQ_CRM_WEBHOOK_URL", stub.url)
    try:
        cust, _ = customers.create_customer(
            conn, "Gate", phone="3215551201", consent_marketing=True,
            consent_source="b6")
        msg = messages.compose_template(conn, cust["id"], "comeback")
        messages.approve(conn, msg["id"])
        messages.send(conn, msg["id"])
        with pytest.raises(PermissionError):
            delivery.dispatch(conn, msg["id"], transport="webhook")
        entry = register.add_entry(conn, "messages", "webhook", "delivery")
        register.set_terms_reviewed(conn, entry["id"], True)
        rec = delivery.dispatch(conn, msg["id"], transport="webhook")
        assert rec["status"] == "delivered" and len(stub.payloads) == 1
        # Closing the gate again blocks the NEXT message.
        register.set_terms_reviewed(conn, entry["id"], False)
        msg2 = messages.compose_template(conn, cust["id"], "comeback")
        messages.approve(conn, msg2["id"])
        messages.send(conn, msg2["id"])
        with pytest.raises(PermissionError):
            delivery.dispatch(conn, msg2["id"], transport="webhook")
        assert len(stub.payloads) == 1
    finally:
        stub.stop()


# ---- Register API: owner-only + audited ----

def test_api_register_owner_only_and_audited():
    r = client.post("/api/processing-register", json={
        "data_kind": "messages", "provider": "webhook",
        "purpose": "delivery"}, headers={"X-Role": "staff"})
    assert r.status_code == 403
    r = client.post("/api/processing-register", json={
        "data_kind": "messages", "provider": "webhook",
        "purpose": "delivery"}, headers={"X-Role": "owner"})
    assert r.status_code == 200
    entry = r.json()
    assert entry["terms_reviewed"] == 0
    r = client.post(f"/api/processing-register/{entry['id']}/terms",
                    json={"reviewed": True}, headers={"X-Role": "staff"})
    assert r.status_code == 403
    r = client.post(f"/api/processing-register/{entry['id']}/terms",
                    json={"reviewed": True}, headers={"X-Role": "owner"})
    assert r.status_code == 200 and r.json()["terms_reviewed"] == 1
    actions = [row["action"] for row in main_mod.conn.execute(
        "SELECT action FROM audit_log WHERE entity = 'processing_register'")]
    assert "register_provider" in actions
    assert "provider_terms_reviewed" in actions
    r = client.get("/api/processing-register")
    assert any(e["id"] == entry["id"] for e in r.json())


# ---- Inbound: two-way messaging ----

def test_inbound_recorded_with_direction(conn):
    cust, _ = customers.create_customer(conn, "Ines", phone="3215551202",
                                        language="es")
    msg = messages.record_inbound(conn, cust["id"], "¿Pueden el viernes?",
                                  "es")
    assert msg["status"] == "received" and msg["direction"] == "in"
    assert msg["created_by"] == "customer"
    listed = messages.list_messages(conn, cust["id"])
    assert any(m["id"] == msg["id"] for m in listed)
    with pytest.raises(ValueError):
        messages.record_inbound(conn, 99999, "hola", "es")


def test_api_inbound_flow():
    r = client.post("/api/customers", json={
        "name": "API Inbound", "phone": "3215551203", "language": "ht"})
    cid = r.json()["customer"]["id"]
    r = client.post("/api/messages/inbound", json={
        "customer_id": cid, "text": "Wi, mwen dakò", "lang": "ht"},
        headers={"X-Role": "viewer"})
    assert r.status_code == 403
    r = client.post("/api/messages/inbound", json={
        "customer_id": cid, "text": "Wi, mwen dakò", "lang": "ht"})
    assert r.status_code == 200
    body = r.json()
    assert body["direction"] == "in" and body["status"] == "received"
    actions = [row["action"] for row in main_mod.conn.execute(
        "SELECT action FROM audit_log WHERE action = 'record_inbound'")]
    assert len(actions) >= 1
