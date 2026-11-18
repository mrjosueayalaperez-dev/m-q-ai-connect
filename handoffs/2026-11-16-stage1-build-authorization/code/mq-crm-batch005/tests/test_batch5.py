"""Batch 005 tests — the delivery layer: outbox transport, the
processing-register privacy gate on the webhook transport, retry and
idempotency, and the dispatch API. Builder-side, as always."""
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b5.db"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main as main_mod  # noqa: E402
from app.services import customers, delivery, messages  # noqa: E402

client = TestClient(main_mod.app)


def _sent_message(conn, phone, lang="en"):
    cust, _ = customers.create_customer(
        conn, "Del", phone=phone, language=lang, consent_marketing=True,
        consent_source="b5")
    msg = messages.compose_template(conn, cust["id"], "comeback")
    messages.approve(conn, msg["id"])
    messages.send(conn, msg["id"])
    return cust, messages.get_message(conn, msg["id"])


# ---- Outbox transport ----

def test_outbox_dispatch_records_honest_delivery(conn):
    _, msg = _sent_message(conn, "3215551001")
    rec = delivery.dispatch(conn, msg["id"])
    assert rec["status"] == "delivered" and rec["transport"] == "outbox"
    assert rec["attempts"] == 1
    assert rec["text_snapshot"] == msg["original_text"]
    # The record must not overclaim: outbox is not the customer's device.
    assert "NOT received" in rec["detail"]


def test_dispatch_refuses_unsent_message(conn):
    cust, _ = customers.create_customer(
        conn, "Draft", phone="3215551002", consent_marketing=True,
        consent_source="b5")
    msg = messages.compose_template(conn, cust["id"], "comeback")
    with pytest.raises(PermissionError):
        delivery.dispatch(conn, msg["id"])
    messages.approve(conn, msg["id"])
    with pytest.raises(PermissionError):
        delivery.dispatch(conn, msg["id"])


def test_dispatch_is_idempotent_after_delivery(conn):
    _, msg = _sent_message(conn, "3215551003")
    first = delivery.dispatch(conn, msg["id"])
    second = delivery.dispatch(conn, msg["id"])
    assert second["id"] == first["id"] and second["attempts"] == 1


def test_unknown_transport_fails_recorded(conn):
    _, msg = _sent_message(conn, "3215551004")
    rec = delivery.dispatch(conn, msg["id"], transport="pigeon")
    assert rec["status"] == "failed" and "unknown transport" in rec["detail"]


# ---- Webhook transport + privacy gate ----

class _Stub:
    def __init__(self):
        self.status = 200
        self.payloads = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.payloads.append(json.loads(body))
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"id": "stub-42"}).encode())

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/hook"

    def stop(self):
        self.server.shutdown()


@pytest.fixture()
def stub(monkeypatch):
    s = _Stub()
    monkeypatch.setenv("MQ_CRM_WEBHOOK_URL", s.url)
    yield s
    s.stop()


def _register_terms(conn, reviewed=1):
    conn.execute(
        "INSERT INTO processing_register (data_kind, provider, purpose,"
        " terms_reviewed) VALUES ('messages', 'webhook', 'delivery', ?)",
        (reviewed,))
    conn.commit()


def test_webhook_refused_without_terms_review(conn, stub):
    _, msg = _sent_message(conn, "3215551005", lang="pt")
    with pytest.raises(PermissionError):
        delivery.dispatch(conn, msg["id"], transport="webhook")
    rec = delivery.get_delivery(conn, msg["id"])
    assert rec["status"] == "failed" and "privacy gate" in rec["detail"]
    assert stub.payloads == []  # nothing left the building


def test_webhook_refused_when_terms_not_reviewed(conn, stub):
    _register_terms(conn, reviewed=0)
    _, msg = _sent_message(conn, "3215551006")
    with pytest.raises(PermissionError):
        delivery.dispatch(conn, msg["id"], transport="webhook")
    assert stub.payloads == []


def test_webhook_delivery_after_terms_review(conn, stub):
    _register_terms(conn, reviewed=1)
    _, msg = _sent_message(conn, "3215551007", lang="pt")
    rec = delivery.dispatch(conn, msg["id"], transport="webhook")
    assert rec["status"] == "delivered" and rec["provider_ref"] == "stub-42"
    assert len(stub.payloads) == 1
    payload = stub.payloads[0]
    assert payload["text"] == msg["original_text"]
    assert payload["lang"] == "pt" and payload["channel"] == "sms"


def test_webhook_failure_then_retry_succeeds(conn, stub):
    _register_terms(conn, reviewed=1)
    _, msg = _sent_message(conn, "3215551008")
    stub.status = 500
    rec = delivery.dispatch(conn, msg["id"], transport="webhook")
    assert rec["status"] == "failed" and rec["attempts"] == 1
    stub.status = 200
    rec2 = delivery.dispatch(conn, msg["id"], transport="webhook")
    assert rec2["status"] == "delivered"
    assert rec2["id"] == rec["id"] and rec2["attempts"] == 2


# ---- API ----

def test_api_dispatch_flow_and_roles():
    r = client.post("/api/customers", json={
        "name": "API Del", "phone": "3215551009", "language": "en",
        "consent_marketing": True, "consent_source": "b5"})
    cid = r.json()["customer"]["id"]
    r = client.post("/api/messages/template", json={
        "customer_id": cid, "template_key": "comeback", "context": {}})
    mid = r.json()["id"]
    client.post(f"/api/messages/{mid}/approve")
    client.post(f"/api/messages/{mid}/send")
    r = client.post(f"/api/messages/{mid}/dispatch",
                    headers={"X-Role": "viewer"})
    assert r.status_code == 403
    r = client.post(f"/api/messages/{mid}/dispatch")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "delivered" and body["transport"] == "outbox"
    r = client.get(f"/api/messages/{mid}/delivery")
    assert r.json()["delivery"]["id"] == body["id"]
    r = client.get("/api/deliveries")
    assert any(d["id"] == body["id"] for d in r.json())
