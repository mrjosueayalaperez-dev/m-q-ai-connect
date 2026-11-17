"""Batch 008 — corrective batch (founder-authorized, Nov 17): regression
tests for the eight defects found by the Nov 17 read-only audit
(/workspace/crm-audit-2026-11-17/REPORT.md). One section per item; every
test uses synthetic data, a temp SQLite file or :memory:, and a stub HTTP
server on 127.0.0.1 only."""
import json
import os
import sqlite3
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b8.db"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as dbmod  # noqa: E402
from app import main as main_mod  # noqa: E402
from app.services import (customers, data_rights, delivery, messages,  # noqa: E402
                          register)
from tests.conftest import anonymous_client, auth_headers  # noqa: E402

client = TestClient(main_mod.app)          # harness: explicit owner + actor
anon = anonymous_client(main_mod.app)       # no role, no actor
OWNER = {"X-Role": "owner", "X-Actor": "b8-owner"}


class _Stub:
    def __init__(self, delay=0.0):
        self.payloads, self.headers, self.delay = [], [], delay
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.payloads.append(json.loads(body))
                outer.headers.append(dict(self.headers))
                time.sleep(outer.delay)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"id": "stub-8"}')

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/hook"

    def stop(self):
        self.server.shutdown()


@pytest.fixture()
def stub(monkeypatch):
    s = _Stub()
    monkeypatch.setenv("MQ_CRM_WEBHOOK_URL", s.url)
    yield s
    s.stop()


def _cust(c, phone, consent=True, lang="en", name="Synthetic B8"):
    cust, _ = customers.create_customer(c, name, phone=phone, language=lang,
                                        consent_marketing=consent,
                                        consent_source="b8")
    return cust


def _sent(c, cust, template="comeback"):
    m = messages.compose_template(c, cust["id"], template)
    messages.approve(c, m["id"])
    messages.send(c, m["id"])
    return m


def _bind(c, url, provider="webhook", ref="synthetic-terms-v1"):
    e = register.add_entry(c, "messages", provider, "delivery", endpoint=url)
    return register.set_terms_reviewed(c, e["id"], True, terms_reference=ref,
                                       reviewed_by="b8-owner")


def _api_customer(phone, consent=True, name="API B8", lang="en"):
    r = client.post("/api/customers", json={
        "name": name, "phone": phone, "language": lang,
        "consent_marketing": consent, "consent_source": "b8"})
    assert r.status_code == 200, r.text
    return r.json()["customer"]["id"]


def _api_sent_comeback(cid):
    mid = client.post("/api/messages/template", json={
        "customer_id": cid, "template_key": "comeback", "context": {}}).json()["id"]
    assert client.post(f"/api/messages/{mid}/approve").status_code == 200
    assert client.post(f"/api/messages/{mid}/send").status_code == 200
    return mid


# ---------------------------------------------------------------- item 1
# Customer deletion: atomic (one transaction, rollback on error), FK-ordered
# (deliveries first), audited, and deliveries included in export.

def test_b8_1_delete_after_dispatch_succeeds_and_removes_deliveries(conn):
    cust = _cust(conn, "3215558101", name="Synthetic Delete Me")
    m = _sent(conn, cust)
    assert delivery.dispatch(conn, m["id"])["status"] == "delivered"
    exp = data_rights.export_customer(conn, cust["id"])
    assert len(exp["deliveries"]) == 1          # export now includes them
    counts = data_rights.delete_customer(conn, cust["id"], "b8-owner", "owner")
    assert counts["deliveries"] == 1 and counts["customers"] == 1
    for table in ("customers", "messages", "deliveries", "bookings"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    rows = conn.execute("SELECT * FROM audit_log WHERE action ="
                        " 'delete_customer'").fetchall()
    assert len(rows) == 1 and rows[0]["actor"] == "b8-owner"
    assert "Synthetic Delete Me" not in rows[0]["detail"]   # counts only
    assert dbmod.verify_audit_chain(conn)


def test_b8_1_delete_rolls_back_completely_on_error(monkeypatch):
    path = os.path.join(tempfile.mkdtemp(), "rb.db")
    c = dbmod.connect(path)
    cust = _cust(c, "3215558102")
    from app.services import bookings
    bookings.create_booking(c, cust["id"], "Visit", "2027-02-01 10:00")
    m = _sent(c, cust)
    delivery.dispatch(c, m["id"])

    def boom(*a, **k):
        raise RuntimeError("injected failure inside the deletion")
    monkeypatch.setattr(data_rights, "audit", boom)
    with pytest.raises(RuntimeError):
        data_rights.delete_customer(c, cust["id"])
    assert not c.in_transaction                      # nothing left pending
    # An unrelated later write must NOT commit a half-deletion.
    customers.create_customer(c, "Synthetic Other", phone="3215558199")
    other = sqlite3.connect(path)
    for table, n in (("customers", 2), ("bookings", 1), ("messages", 1),
                     ("deliveries", 1)):
        assert other.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == n
    assert other.execute("SELECT COUNT(*) FROM audit_log WHERE action ="
                         " 'delete_customer'").fetchone()[0] == 0
    other.close()
    c.close()


def test_b8_1_api_delete_after_dispatch_200_and_unknown_404():
    cid = _api_customer("3215558103")
    mid = _api_sent_comeback(cid)
    assert client.post(f"/api/messages/{mid}/dispatch").json()["status"] == "delivered"
    exp = client.get(f"/api/customers/{cid}/export").json()
    assert "deliveries" in exp and len(exp["deliveries"]) == 1
    r = client.delete(f"/api/customers/{cid}")
    assert r.status_code == 200 and r.json()["deliveries"] == 1
    assert client.delete(f"/api/customers/{cid}").status_code == 404
    rows = main_mod.conn.execute(
        "SELECT actor, role FROM audit_log WHERE action = 'delete_customer'"
        " AND entity_id = ?", (cid,)).fetchall()
    assert [tuple(r) for r in rows] == [("test-operator", "owner")]


def test_b8_1_delete_refused_while_delivery_in_flight(conn):
    cust = _cust(conn, "3215558104")
    m = _sent(conn, cust)
    conn.execute("INSERT INTO deliveries (message_id, channel, transport, status,"
                 " text_snapshot, attempts, created_at, updated_at) VALUES"
                 " (?, 'sms', 'webhook', 'sending', 't', 1, ?, ?)",
                 (m["id"], dbmod.now_utc(), dbmod.now_utc()))
    conn.commit()
    with pytest.raises(data_rights.DeletionBlocked):
        data_rights.delete_customer(conn, cust["id"])
    assert customers.get_customer(conn, cust["id"]) is not None
    assert not conn.in_transaction


# ---------------------------------------------------------------- item 2
# Deny by default: no role header (or an unknown role) is never 'owner'.

def _concrete(path):
    import re
    return re.sub(r"\{[^}]+\}", "1", path)


def test_b8_2_every_api_route_denies_missing_role():
    checked = 0
    for route in main_mod.app.routes:
        path = getattr(route, "path", "")
        # Batch 009: /api/auth/login is the one other open path (it is how
        # a session is obtained); it is covered in test_batch9.py.
        if not path.startswith("/api") or path in ("/api/health",
                                                   "/api/auth/login"):
            continue
        for method in sorted(getattr(route, "methods", []) or []):
            if method == "HEAD":
                continue
            r = anon.request(method, _concrete(path), json={})
            assert r.status_code == 401, (method, path, r.status_code)
            r = anon.request(method, _concrete(path), json={},
                             headers={"X-Role": "nobody", "X-Actor": "x"})
            assert r.status_code == 401, (method, path, "nobody")
            checked += 1
    assert checked >= 40          # every route, GETs and export included
    assert anon.get("/api/health").status_code == 200   # liveness only


def test_b8_2_export_and_reads_need_explicit_role():
    _api_customer("3215558105")
    r = anon.get("/api/export")
    assert r.status_code == 401 and "customers" not in r.text
    assert anon.get("/api/customers").status_code == 401
    assert anon.get("/api/customers",
                    headers=auth_headers("viewer")).status_code == 200
    assert anon.get("/api/export",
                    headers=auth_headers("viewer")).status_code == 403
    assert anon.get("/api/export",
                    headers=auth_headers("owner")).status_code == 200


def test_b8_2_writes_require_named_actor():
    # Batch 009: self-asserted role + actor headers no longer authenticate;
    # the named actor is the logged-in user.
    r = anon.post("/api/customers", json={"name": "No Actor"},
                  headers={"X-Role": "owner"})
    assert r.status_code == 401
    r = anon.post("/api/customers", json={"name": "Named", "phone": "3215558106"},
                  headers={"X-Role": "owner", "X-Actor": "b8-owner"})
    assert r.status_code == 401
    r = anon.post("/api/customers", json={"name": "Named", "phone": "3215558106"},
                  headers=auth_headers("owner", "b8-owner"))
    assert r.status_code == 200


# ---------------------------------------------------------------- item 3
# Stored XSS: all dynamic HTML goes through the escaping html`` tag.

WEB = os.path.join(os.path.dirname(__file__), "..", "web")


def _read(name):
    with open(os.path.join(WEB, name), encoding="utf-8") as f:
        return f.read()


def test_b8_3_no_raw_innerhtml_in_app_js():
    js = _read("app.js")
    assert "innerHTML" not in js and "insertAdjacentHTML" not in js \
        and "outerHTML" not in js and "document.write" not in js
    assert js.count("setHTML(") >= 9          # every list renderer
    safe = _read("safe_html.js")
    assert safe.count(".innerHTML =") == 1   # the one guarded sink
    html_page = _read("index.html")
    assert html_page.index("safe_html.js") < html_page.index("app.js")


NODE_HARNESS = r"""
const vm = require("vm"), fs = require("fs"), path = require("path");
const web = process.argv[2];
const PAY = '<img src=x onerror="globalThis.PWNED=1">';
const els = {};
function el(sel) {
  if (!els[sel]) els[sel] = {sel, innerHTML: "", textContent: "", value: sel === "#op-role" ? "owner" : "op",
    hidden: false, dataset: {}, files: [], onclick: null, onchange: null, onsubmit: null,
    classList: {toggle() {}, add() {}, remove() {}}, getAttribute() { return null; }};
  return els[sel];
}
const data = {
  "/api/customers": [{id: 1, name: PAY, phone: PAY, email: PAY, language: "en"}],
  "/api/bookings": [{id: 2, customer_name: PAY, title: PAY, starts_at_utc: PAY, status: "booked"}],
  "/api/reminders": [{id: 2, customer_name: PAY, title: PAY, starts_at_utc: PAY}],
  "/api/quotes": [{id: 3, customer_name: PAY, status: "draft", total_minor: 100, currency: "USD",
                   items: [{description: PAY, qty: 1, unit_amount_minor: 100}]}],
  "/api/invoices": [{id: 4, status: "open", total_minor: 1, paid_minor: 0, currency: "USD"}],
  "/api/messages": [{id: 5, customer_id: 1, status: "received", created_by: "customer", direction: "in",
                     original_text: PAY, translated_text: PAY, translation_pending: 0}],
  "/api/deliveries": [{message_id: 5, transport: PAY, status: PAY}],
  "/api/comeback/lapsed": [{name: PAY, last_service_at: PAY, language: "en"}],
  "/api/reports/summary": {customers: PAY, lapsed_customers: 0, upcoming_bookings: 0, average_rating: PAY},
};
const seen = [];
const ctx = {
  console, sessionStorage: {getItem() { return null; }, setItem() {}},
  document: {querySelector: el, querySelectorAll: (s) => s === ".customer-select" ? [el("sel1")] : []},
  fetch: async (p, o) => { seen.push(o && o.headers); const k = p.split("?")[0];
    return {ok: true, json: async () => data[k]}; },
  alert() {},
};
ctx.window = ctx; ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(web, "safe_html.js"), "utf8"), ctx);
vm.runInContext(fs.readFileSync(path.join(web, "app.js"), "utf8"), ctx);
(async () => {
  await vm.runInContext("(async () => { await refreshSelects(); await loadBookings(); await loadReminders();"
    + " await loadQuotes(); await loadInvoices(); await loadMessages(); await loadLapsed(); await loadSummary(); })()", ctx);
  const out = {};
  for (const [k, v] of Object.entries(els)) if (v.innerHTML) out[k] = v.innerHTML;
  const sh = vm.runInContext("({esc, html, setHTML})", ctx);
  let rejected = false; try { sh.setHTML(el("#x"), "<b>raw</b>"); } catch (e) { rejected = true; }
  console.log(JSON.stringify({out, rejected, headers: seen[0] || null, all_headers: seen,
    nested: String(sh.html`<b>${sh.html`<i>${PAY}</i>`}</b>`)}));
})().catch(e => { console.error(e); process.exit(1); });
"""


def _node():
    import shutil
    return shutil.which("node")


@pytest.mark.skipif(_node() is None, reason="node not installed")
def test_b8_3_rendered_ui_escapes_attacker_text(tmp_path):
    import subprocess
    h = tmp_path / "h.js"
    h.write_text(NODE_HARNESS)
    res = subprocess.run([_node(), str(h), os.path.abspath(WEB)],
                         capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, res.stderr
    r = json.loads(res.stdout)
    rendered = r["out"]
    for target in ("#customer-list", "sel1", "#booking-list", "#reminder-list",
                   "#quote-list", "#message-list", "#lapsed-list",
                   "#summary-box"):
        assert target in rendered, target
        assert "<img" not in rendered[target], target
        assert "&lt;img src=x onerror=&quot;" in rendered[target], target
    assert "<button" in rendered["#booking-list"]     # real markup survives
    assert r["rejected"] is True                       # raw strings refused
    assert r["nested"] == "<b><i>&lt;img src=x onerror=&quot;globalThis.PWNED=1&quot;&gt;</i></b>"
    # Batch 009: the UI never sends a self-asserted role or actor; it relies
    # on the HttpOnly session cookie and sends the CSRF token on writes.
    assert r["headers"] is not None
    assert all("X-Role" not in (h or {}) and "X-Actor" not in (h or {})
               for h in r["all_headers"])


# ---------------------------------------------------------------- item 4
# Per-request / per-thread connections + idempotent dispatch.

def test_b8_4_requests_use_their_own_closed_connections(monkeypatch):
    opened, used = [], []
    real_open = dbmod.open_connection

    def tracking_open(path):
        c = real_open(path)
        opened.append(c)
        return c
    monkeypatch.setattr(dbmod, "open_connection", tracking_open)
    real_list = main_mod.customers.list_customers

    def spy(c):
        used.append(main_mod._current_conn())
        return real_list(c)
    monkeypatch.setattr(main_mod.customers, "list_customers", spy)
    assert client.get("/api/customers").status_code == 200
    assert client.get("/api/customers").status_code == 200
    assert len(used) == 2 and used[0] is not used[1]
    assert all(u in opened for u in used)
    for u in used:                       # closed when the request ended
        with pytest.raises(sqlite3.ProgrammingError):
            u.execute("SELECT 1")


def test_b8_4_threads_get_distinct_connections():
    got = []
    ts = [threading.Thread(target=lambda: got.append(main_mod._current_conn()))
          for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len({id(c) for c in got}) == 3


def test_b8_4_concurrent_dispatch_delivers_exactly_once(monkeypatch):
    s = _Stub(delay=0.4)
    monkeypatch.setenv("MQ_CRM_WEBHOOK_URL", s.url)
    try:
        c = main_mod.conn
        _bind(c, s.url)
        for round_no in range(5):
            cust = _cust(c, f"32155582{round_no:02d}")
            m = _sent(c, cust)
            s.payloads.clear()
            out, barrier = [], threading.Barrier(6)

            def go():
                barrier.wait()
                try:
                    out.append(delivery.dispatch(main_mod.conn, m["id"],
                                                 transport="webhook")["status"])
                except delivery.DispatchInProgress:
                    out.append("in_progress")
                except Exception as e:          # pragma: no cover - must not happen
                    out.append(f"{type(e).__name__}: {e}")
            ts = [threading.Thread(target=go) for _ in range(6)]
            [t.start() for t in ts]
            [t.join() for t in ts]
            assert len(s.payloads) == 1, (round_no, out)
            assert out.count("delivered") >= 1
            assert set(out) <= {"delivered", "in_progress"}, out
            rec = delivery.get_delivery(main_mod.conn, m["id"])
            assert rec["status"] == "delivered" and rec["attempts"] == 1
        assert s.headers[0]["Idempotency-Key"].startswith("mq-crm-message-")
    finally:
        s.stop()


def test_b8_4_concurrent_api_dispatch_200_or_409_single_payload(monkeypatch):
    s = _Stub(delay=0.4)
    monkeypatch.setenv("MQ_CRM_WEBHOOK_URL", s.url)
    monkeypatch.setenv("MQ_CRM_TRANSPORT", "webhook")
    try:
        _bind(main_mod.conn, s.url, provider="api-race")
        mid = _api_sent_comeback(_api_customer("3215558301"))
        codes = []

        def go():
            codes.append(TestClient(main_mod.app).post(
                f"/api/messages/{mid}/dispatch").status_code)
        ts = [threading.Thread(target=go) for _ in range(4)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert len(s.payloads) == 1 and set(codes) <= {200, 409} and 200 in codes
    finally:
        s.stop()


# ---------------------------------------------------------------- item 5
# Consent re-checked at dispatch for every message type; free text is
# marketing unless declared transactional.

def test_b8_5_free_text_promo_to_non_consenting_never_sends():
    cid = _api_customer("3215558401", consent=False)
    # Batch 008b: the operator classifies the promo as marketing.
    mid = client.post("/api/messages/free", json={
        "customer_id": cid, "text": "PROMO 50% off", "text_lang": "en",
        "purpose": "marketing"}).json()["id"]
    assert messages.get_message(main_mod.conn, mid)["purpose"] == "marketing"
    assert client.post(f"/api/messages/{mid}/approve").status_code == 200
    r = client.post(f"/api/messages/{mid}/send")
    assert r.status_code == 403 and "consent" in r.json()["detail"]
    # Even if the status is forced to 'sent', dispatch re-checks consent.
    main_mod.conn.execute("UPDATE messages SET status = 'sent' WHERE id = ?", (mid,))
    main_mod.conn.commit()
    r = client.post(f"/api/messages/{mid}/dispatch")
    assert r.status_code == 403 and "consent" in r.json()["detail"]
    rec = client.get(f"/api/messages/{mid}/delivery").json()["delivery"]
    assert rec["status"] == "failed" and "consent gate" in rec["detail"]


def test_b8_5_consent_withdrawn_after_send_blocks_dispatch(stub):
    c = main_mod.conn
    _bind(c, stub.url, provider="consent-check")
    cust = _cust(c, "3215558402", consent=True)
    m = _sent(c, cust)
    customers.set_consent(c, cust["id"], False, "customer asked to stop")
    with pytest.raises(PermissionError):
        delivery.dispatch(c, m["id"], transport="webhook")
    assert stub.payloads == []


def test_b8_5_declared_transactional_free_text_goes_out_and_bad_purpose_refused():
    cid = _api_customer("3215558403", consent=False)
    r = client.post("/api/messages/free", json={
        "customer_id": cid, "text": "Your part arrived.", "text_lang": "en",
        "purpose": "transactional"})
    mid = r.json()["id"]
    client.post(f"/api/messages/{mid}/approve")
    assert client.post(f"/api/messages/{mid}/send").status_code == 200
    assert client.post(f"/api/messages/{mid}/dispatch").json()["status"] == "delivered"
    rows = main_mod.conn.execute(
        "SELECT detail FROM audit_log WHERE action = 'compose_free_text'"
        " AND entity_id = ?", (mid,)).fetchall()
    assert json.loads(rows[0]["detail"])["purpose"] == "transactional"
    assert client.post("/api/messages/free", json={
        "customer_id": cid, "text": "x", "purpose": "whatever"}).status_code == 400


def test_b8_5_legacy_free_text_without_purpose_is_held_not_defaulted(conn):
    # Batch 008b replaced "no purpose => marketing" with "no purpose => held".
    cust = _cust(conn, "3215558404")
    msg = messages.compose_free_text(conn, cust["id"], "Hello", "en")
    assert msg["purpose"] is None and msg["status"] == "held"
    assert not messages.is_marketing(msg)


# ---------------------------------------------------------------- item 6
# Approvals audited: who, what, when.

def test_b8_6_approval_is_attributed_and_audited():
    cid = _api_customer("3215558501")
    mid = client.post("/api/messages/template", json={
        "customer_id": cid, "template_key": "comeback", "context": {}}).json()["id"]
    r = client.post(f"/api/messages/{mid}/approve",
                    headers=auth_headers("staff", "ana-staff"))
    assert r.status_code == 200
    body = r.json()
    assert body["approved_by"] == "ana-staff" and body["approved_role"] == "staff"
    assert body["approved_at"]
    row = main_mod.conn.execute(
        "SELECT * FROM audit_log WHERE action = 'approve_message'"
        " AND entity_id = ?", (mid,)).fetchone()
    assert row["actor"] == "ana-staff" and row["role"] == "staff"
    detail = json.loads(row["detail"])
    assert detail["approved_hash"] == body["approved_hash"]
    assert detail["approved_at"] == body["approved_at"]
    assert dbmod.verify_audit_chain(main_mod.conn)


def test_b8_6_approval_without_actor_refused_and_unknown_message_400():
    assert anon.post("/api/messages/1/approve",
                     headers={"X-Role": "owner"}).status_code == 401
    assert client.post("/api/messages/999999/approve").status_code == 400


# ---------------------------------------------------------------- item 7
# Privacy gate matches the configured endpoint, not a provider name.

def test_b8_7_literal_webhook_row_for_another_host_does_not_authorize(conn, stub):
    _bind(conn, "https://other-provider.example.invalid/hook", provider="webhook")
    m = _sent(conn, _cust(conn, "3215558601"))
    with pytest.raises(PermissionError) as ei:
        delivery.dispatch(conn, m["id"], transport="webhook")
    assert stub.payloads == []
    assert "127.0.0.1" in str(ei.value) and "/hook" not in str(ei.value)


def test_b8_7_row_bound_to_endpoint_authorizes_whatever_its_name(conn, stub):
    _bind(conn, stub.url, provider="Synthetic SMS Co")
    m = _sent(conn, _cust(conn, "3215558602"))
    assert delivery.dispatch(conn, m["id"], transport="webhook")["status"] == "delivered"
    assert len(stub.payloads) == 1


def test_b8_7_endpoint_matching_rules():
    em = register.endpoint_matches
    assert em("https://api.example.invalid", "https://API.example.invalid:443/v1/sms")
    assert not em("https://api.example.invalid", "http://api.example.invalid/v1")
    assert not em("https://api.example.invalid", "https://api.example.invalid.evil.test/")
    assert not em("https://api.example.invalid:8443", "https://api.example.invalid/")
    assert em("https://api.example.invalid/v1", "https://api.example.invalid/v1/sms")
    assert not em("https://api.example.invalid/v1", "https://api.example.invalid/v10")
    assert not em(None, "https://api.example.invalid") and not em("webhook", "https://x.invalid")
    # Credentials in a URL are never stored on the register.
    assert register.canonical_endpoint("https://user:pw@api.example.invalid/v1?key=abc") \
        == "https://api.example.invalid:443/v1"


# ---------------------------------------------------------------- item 8
# Batch 006 gaps: which terms were reviewed; withdrawal vs in-flight dispatch.

def test_b8_8_review_requires_terms_reference_and_records_it():
    r = client.post("/api/processing-register", json={
        "data_kind": "messages", "provider": "Synthetic SMS Co",
        "endpoint": "https://sms.example.invalid/v1"})
    eid = r.json()["id"]
    assert set(("endpoint", "terms_reference", "reviewed_at", "reviewed_by")) <= set(r.json())
    r = client.post(f"/api/processing-register/{eid}/terms", json={"reviewed": True})
    assert r.status_code == 400 and "terms_reference" in r.json()["detail"]
    r = client.post(f"/api/processing-register/{eid}/terms", json={
        "reviewed": True, "terms_reference": "Synthetic DPA v2 (2026-11-01)"})
    e = r.json()
    assert r.status_code == 200 and e["terms_reference"] == "Synthetic DPA v2 (2026-11-01)"
    assert e["reviewed_by"] == "test-operator" and e["reviewed_at"]
    row = main_mod.conn.execute(
        "SELECT detail FROM audit_log WHERE action = 'provider_terms_reviewed'"
        " AND entity_id = ?", (eid,)).fetchone()
    assert "Synthetic DPA v2" in row["detail"]


def test_b8_8_withdrawal_blocks_a_claimed_in_flight_dispatch(stub, monkeypatch):
    c = main_mod.conn
    e = _bind(c, stub.url, provider="withdraw-claimed")
    m = _sent(c, _cust(c, "3215558801"))
    claimed, go, out = threading.Event(), threading.Event(), []

    def hook():
        claimed.set()
        go.wait(5)
    monkeypatch.setattr(delivery, "_pre_send_hook", hook)

    def run():
        try:
            out.append(delivery.dispatch(main_mod.conn, m["id"], transport="webhook")["status"])
        except PermissionError as ex:
            out.append(f"refused: {ex}")
    t = threading.Thread(target=run)
    t.start()
    assert claimed.wait(5)                       # dispatch is in flight
    register.set_terms_reviewed(c, e["id"], False)   # review withdrawn
    go.set()
    t.join(10)
    assert out and out[0].startswith("refused") and stub.payloads == []


def test_b8_8_withdrawal_during_post_waits_then_blocks_everything_after(monkeypatch):
    s = _Stub(delay=0.6)
    monkeypatch.setenv("MQ_CRM_WEBHOOK_URL", s.url)
    try:
        c = main_mod.conn
        e = _bind(c, s.url, provider="withdraw-on-wire")
        cust = _cust(c, "3215558802")
        m1 = _sent(c, cust)
        times = {}

        def run():
            delivery.dispatch(main_mod.conn, m1["id"], transport="webhook")
            times["dispatch_done"] = time.monotonic()
        t = threading.Thread(target=run)
        t.start()
        while not s.payloads:
            time.sleep(0.01)                     # the POST is on the wire
        register.set_terms_reviewed(main_mod.conn, e["id"], False)
        times["withdrawn"] = time.monotonic()
        t.join(10)
        assert times["withdrawn"] >= times["dispatch_done"]   # linearized
        m2 = _sent(c, cust)
        with pytest.raises(PermissionError):
            delivery.dispatch(c, m2["id"], transport="webhook")
        assert len(s.payloads) == 1
    finally:
        s.stop()
