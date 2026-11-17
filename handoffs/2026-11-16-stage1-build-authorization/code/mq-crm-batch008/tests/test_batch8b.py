"""Batch 008b — founder-approved messaging policies (Nov 17, 1:33 PM ET).
Rule 1: classify by PURPOSE; unclear/unset purpose => HELD for review;
        (re)classification audited.
Rule 2: marketing opt-out vs full channel opt-out (STOP); exactly one
        opt-out confirmation per opt-out event; checked at send AND dispatch.
Rule 3: a 'transactional' label must never carry promotional content —
        deterministic check, flag audited, message held.
Synthetic data only; local stub endpoint only."""
import json
import os
import sqlite3
import tempfile

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b8b.db"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as dbmod  # noqa: E402
from app import main as main_mod  # noqa: E402
from app.services import (billing, bookings, customers, data_rights,  # noqa: E402
                          delivery, messages, policy)

client = TestClient(main_mod.app)


def _cust(c, phone, consent=True, lang="en"):
    cust, _ = customers.create_customer(c, "Synthetic B8b", phone=phone,
                                        language=lang, consent_marketing=consent,
                                        consent_source="b8b")
    return cust


def _free(c, cust, text, purpose):
    return messages.compose_free_text(c, cust["id"], text, cust["language"],
                                      purpose=purpose)


def _approve_send(c, m):
    messages.approve(c, m["id"])
    return messages.send(c, m["id"])


def _audit(c, action, mid):
    return [dict(r) for r in c.execute(
        "SELECT * FROM audit_log WHERE action = ? AND entity_id = ? ORDER BY id",
        (action, mid))]


def _api_cust(phone, consent=True, lang="en"):
    return client.post("/api/customers", json={
        "name": "API B8b", "phone": phone, "language": lang,
        "consent_marketing": consent, "consent_source": "b8b"}).json()["customer"]["id"]


# ------------------------------------------------------------- rule 1

def test_b8b_1_unset_purpose_is_held_and_cannot_approve_send_or_dispatch():
    cid = _api_cust("3215559101")
    m = client.post("/api/messages/free", json={
        "customer_id": cid, "text": "See you Tuesday", "text_lang": "en"}).json()
    assert m["status"] == "held" and m["purpose"] is None
    assert m["hold_reason"] == "purpose_unclear"
    assert client.post(f"/api/messages/{m['id']}/approve").status_code == 400
    assert client.post(f"/api/messages/{m['id']}/send").status_code == 403
    assert client.post(f"/api/messages/{m['id']}/dispatch").status_code == 403
    # Even if the status is forced past the hold, send and dispatch re-check.
    c = main_mod.conn
    c.execute("UPDATE messages SET status = 'sent' WHERE id = ?", (m["id"],))
    c.commit()
    r = client.post(f"/api/messages/{m['id']}/dispatch")
    assert r.status_code == 403 and "held for review" in r.json()["detail"]
    assert messages.get_message(c, m["id"])["status"] == "held"
    rec = client.get(f"/api/messages/{m['id']}/delivery").json()["delivery"]
    assert rec["status"] == "failed"


def test_b8b_1_invalid_or_system_purpose_refused_from_operators():
    cid = _api_cust("3215559102")
    for bad in ("misc", "opt_out_confirmation", ""):
        r = client.post("/api/messages/free", json={
            "customer_id": cid, "text": "x", "purpose": bad})
        assert r.status_code == 400, bad


def test_b8b_1_templates_carry_their_purpose(conn):
    cust = _cust(conn, "3215559103")
    bookings.create_booking(conn, cust["id"], "Visit", "2027-03-01 10:00")
    assert messages.compose_template(conn, cust["id"], "reminder")["purpose"] == "transactional"
    assert messages.compose_template(conn, cust["id"], "comeback")["purpose"] == "marketing"
    assert messages.compose_template(conn, cust["id"], "review_request")["purpose"] == "marketing"


def test_b8b_1_legacy_rows_without_purpose_become_held_on_migration():
    path = os.path.join(tempfile.mkdtemp(), "legacy.db")
    c = dbmod.connect(path)
    cust = _cust(c, "3215559104")
    ids = {}
    for label, status, tpl in (("draft", "draft", None), ("approved", "approved", None),
                               ("sent", "sent", None), ("delivered", "sent", None),
                               ("tpl", "draft", "reminder")):
        cur = c.execute(
            "INSERT INTO messages (customer_id, direction, original_text,"
            " original_lang, template_key, created_by, status, created_at)"
            " VALUES (?, 'out', 'legacy text', 'en', ?, 'human', ?, ?)",
            (cust["id"], tpl, status, dbmod.now_utc()))
        ids[label] = cur.lastrowid
    c.execute("INSERT INTO deliveries (message_id, transport, status, text_snapshot,"
              " attempts, created_at, updated_at) VALUES (?, 'outbox', 'delivered',"
              " 't', 1, ?, ?)", (ids["delivered"], dbmod.now_utc(), dbmod.now_utc()))
    c.commit()
    c.close()
    c = dbmod.connect(path)            # the Batch 008b migration runs here
    st = {k: dict(c.execute("SELECT status, purpose, hold_reason FROM messages"
                            " WHERE id = ?", (v,)).fetchone()) for k, v in ids.items()}
    for k in ("draft", "approved", "sent"):
        assert st[k] == {"status": "held", "purpose": None,
                         "hold_reason": "purpose_unclear"}, k
    assert st["delivered"]["status"] == "sent"         # history untouched
    assert st["tpl"]["purpose"] == "transactional" and st["tpl"]["status"] == "draft"
    c.close()


def test_b8b_1_legacy_sent_row_without_purpose_held_at_dispatch(conn):
    cust = _cust(conn, "3215559105")
    m = _approve_send(conn, _free(conn, cust, "Your part arrived.", "transactional"))
    conn.execute("UPDATE messages SET purpose = NULL WHERE id = ?", (m["id"],))
    conn.commit()
    with pytest.raises(PermissionError):
        delivery.dispatch(conn, m["id"])
    assert messages.get_message(conn, m["id"])["status"] == "held"
    flag = _audit(conn, "message_held_for_review", m["id"])
    assert flag and json.loads(flag[-1]["detail"])["stage"] == "dispatch"


def test_b8b_1_classification_and_reclassification_audited():
    cid = _api_cust("3215559106")
    m = client.post("/api/messages/free", json={
        "customer_id": cid, "text": "Your car is ready", "text_lang": "en"}).json()
    r = client.post(f"/api/messages/{m['id']}/classify", json={"purpose": "transactional"},
                    headers={"X-Role": "staff", "X-Actor": "Ana (staff)"})
    assert r.status_code == 200 and r.json()["status"] == "draft"
    assert client.post(f"/api/messages/{m['id']}/approve").status_code == 200
    r = client.post(f"/api/messages/{m['id']}/classify", json={"purpose": "marketing"})
    body = r.json()
    assert body["status"] == "draft" and body["approved_hash"] is None  # re-approval needed
    rows = _audit(main_mod.conn, "classify_message", m["id"])
    assert [(x["actor"], x["role"]) for x in rows] == [("Ana (staff)", "staff"),
                                                       ("test-operator", "owner")]
    d0, d1 = (json.loads(x["detail"]) for x in rows)
    assert (d0["purpose_from"], d0["purpose_to"], d0["status_from"]) == (None, "transactional", "held")
    assert (d1["purpose_from"], d1["purpose_to"], d1["status_from"]) == ("transactional", "marketing", "approved")
    assert all(x["at_utc"] for x in rows)
    assert client.post(f"/api/messages/{m['id']}/classify",
                       json={"purpose": "transactional"},
                       headers={"X-Role": "viewer"}).status_code == 403
    assert client.post(f"/api/messages/{m['id']}/classify",
                       json={"purpose": "whatever"}).status_code == 400
    assert dbmod.verify_audit_chain(main_mod.conn)


def test_b8b_1_classify_refused_for_delivered_and_system_messages(conn):
    cust = _cust(conn, "3215559107")
    m = _approve_send(conn, _free(conn, cust, "Your part arrived.", "transactional"))
    delivery.dispatch(conn, m["id"])
    with pytest.raises(ValueError):
        messages.classify(conn, m["id"], "marketing", "op", "owner")
    out = policy.record_channel_opt_out(conn, cust["id"], "sms", "test", "op", "owner")
    with pytest.raises(ValueError):
        messages.classify(conn, out["confirmation"]["id"], "transactional", "op", "owner")


# ------------------------------------------------------------- rule 2

def test_b8b_2_marketing_opt_out_blocks_promo_but_allows_transactional(conn):
    cust = _cust(conn, "3215559201", consent=True)
    promo = _approve_send(conn, _free(conn, cust, "We miss you!", "marketing"))
    bookings.create_booking(conn, cust["id"], "Visit", "2027-03-02 10:00")
    reminder = messages.compose_template(conn, cust["id"], "reminder")
    messages.approve(conn, reminder["id"])
    customers.set_consent(conn, cust["id"], False, "marketing opt-out")
    with pytest.raises(PermissionError) as ei:           # at dispatch
        delivery.dispatch(conn, promo["id"])
    assert "marketing" in str(ei.value)
    m2 = _free(conn, cust, "Come back soon", "marketing")
    messages.approve(conn, m2["id"])
    with pytest.raises(PermissionError):                 # at send
        messages.send(conn, m2["id"])
    messages.send(conn, reminder["id"])                  # transactional still goes
    assert delivery.dispatch(conn, reminder["id"])["status"] == "delivered"
    t = _approve_send(conn, _free(conn, cust, "Your part arrived.", "transactional"))
    assert delivery.dispatch(conn, t["id"])["status"] == "delivered"


def test_b8b_2_channel_stop_blocks_transactional_at_send_and_dispatch(conn):
    cust = _cust(conn, "3215559202", consent=True)
    sent_before = _approve_send(conn, _free(conn, cust, "Your part arrived.", "transactional"))
    approved_before = _free(conn, cust, "Your car is ready.", "transactional")
    messages.approve(conn, approved_before["id"])
    policy.record_channel_opt_out(conn, cust["id"], "sms", "customer texted STOP",
                                  "op", "owner")
    with pytest.raises(PermissionError) as ei:
        delivery.dispatch(conn, sent_before["id"])
    assert "opted out of SMS" in str(ei.value)
    with pytest.raises(PermissionError):
        messages.send(conn, approved_before["id"])
    promo = _free(conn, cust, "We miss you!", "marketing")
    messages.approve(conn, promo["id"])
    with pytest.raises(PermissionError):
        messages.send(conn, promo["id"])
    assert delivery.get_delivery(conn, sent_before["id"])["status"] == "failed"


def test_b8b_2_channel_stop_allows_exactly_one_confirmation(conn):
    cust = _cust(conn, "3215559203", lang="es")
    out = policy.record_channel_opt_out(conn, cust["id"], "sms", "STOP", "op", "owner")
    conf = out["confirmation"]
    assert out["created"] and conf["purpose"] == "opt_out_confirmation"
    assert conf["opt_out_event_id"] == out["event"]["id"] and conf["original_lang"] == "es"
    again = policy.record_channel_opt_out(conn, cust["id"], "sms", "STOP", "op", "owner")
    assert not again["created"] and again["confirmation"]["id"] == conf["id"]
    _approve_send(conn, conf)
    first = delivery.dispatch(conn, conf["id"])
    assert first["status"] == "delivered"
    second = delivery.dispatch(conn, conf["id"])      # idempotent: no 2nd send
    assert second["id"] == first["id"] and second["attempts"] == 1
    with pytest.raises(sqlite3.IntegrityError):       # no 2nd confirmation row
        conn.execute(
            "INSERT INTO messages (customer_id, direction, original_text,"
            " original_lang, created_by, status, created_at, purpose,"
            " opt_out_event_id) VALUES (?, 'out', 'again', 'en', 'system',"
            " 'sent', ?, 'opt_out_confirmation', ?)",
            (cust["id"], dbmod.now_utc(), out["event"]["id"]))
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM deliveries d JOIN messages m ON"
                        " m.id = d.message_id WHERE m.purpose ="
                        " 'opt_out_confirmation'").fetchone()[0] == 1
    rows = _audit(conn, "channel_opt_out", cust["id"])
    assert len(rows) == 1


def test_b8b_2_confirmation_void_after_opt_in_and_new_event_gets_its_own(conn):
    cust = _cust(conn, "3215559204")
    ev1 = policy.record_channel_opt_out(conn, cust["id"], "sms", "STOP", "op", "owner")
    _approve_send(conn, ev1["confirmation"])
    policy.revoke_channel_opt_out(conn, cust["id"], "sms", "op", "owner")
    with pytest.raises(PermissionError):    # stale confirmation can't fire
        delivery.dispatch(conn, ev1["confirmation"]["id"])
    t = _approve_send(conn, _free(conn, cust, "Your part arrived.", "transactional"))
    assert delivery.dispatch(conn, t["id"])["status"] == "delivered"
    ev2 = policy.record_channel_opt_out(conn, cust["id"], "sms", "STOP", "op", "owner")
    assert ev2["created"] and ev2["event"]["id"] != ev1["event"]["id"]
    _approve_send(conn, ev2["confirmation"])
    assert delivery.dispatch(conn, ev2["confirmation"]["id"])["status"] == "delivered"


def test_b8b_2_opt_out_is_per_channel(conn):
    cust = _cust(conn, "3215559205")
    policy.record_channel_opt_out(conn, cust["id"], "email", "unsubscribe link",
                                  "op", "owner")
    t = _approve_send(conn, _free(conn, cust, "Your part arrived.", "transactional"))
    assert t["channel"] == "sms"
    assert delivery.dispatch(conn, t["id"])["status"] == "delivered"
    with pytest.raises(ValueError):
        policy.record_channel_opt_out(conn, cust["id"], "pigeon", "x", "op", "owner")


def test_b8b_2_inbound_stop_keyword_is_a_channel_opt_out():
    cid = _api_cust("3215559206")
    r = client.post("/api/messages/inbound", json={
        "customer_id": cid, "text": "Stop by tomorrow?", "lang": "en"})
    assert "channel_opt_out" not in r.json()
    r = client.post("/api/messages/inbound", json={
        "customer_id": cid, "text": " STOP ", "lang": "en"})
    out = r.json()["channel_opt_out"]
    assert out["created"] and out["event"]["source"] == "inbound_keyword"
    opts = client.get(f"/api/customers/{cid}/channel-opt-outs").json()
    assert len(opts) == 1 and opts[0]["revoked_at"] is None
    assert client.post(f"/api/customers/{cid}/channel-opt-in",
                       json={"channel": "sms"}).status_code == 200
    assert client.get(f"/api/customers/{cid}/channel-opt-outs").json()[0]["revoked_at"]


def test_b8b_2_opt_out_records_exported_and_deleted(conn):
    cust = _cust(conn, "3215559207")
    policy.record_channel_opt_out(conn, cust["id"], "sms", "STOP", "op", "owner")
    assert len(data_rights.export_customer(conn, cust["id"])["channel_opt_outs"]) == 1
    counts = data_rights.delete_customer(conn, cust["id"])
    assert counts["channel_opt_outs"] == 1 and counts["messages"] == 1


# ------------------------------------------------------------- rule 3

PROMO_TEXTS = ["Save 50% off this week", "Big SALE on brakes", "Use coupon SPRING",
               "Limited time: buy now", "Special offer for you", "Great deal today",
               "Ask about our discount", "Promo code inside",
               "Tenemos una oferta y un descuento", "Promoción válida hoy",
               "Ganhe desconto com o cupom", "Promoção por tempo limitado",
               "Gen yon rabè ak yon kupon", "Pwomosyon pou ou"]
CLEAN_TEXTS = ["Your part arrived.", "Your car is ready for pickup.",
               "Su pieza llegó.", "Seu carro está pronto.", "Machin ou pare.",
               "Your invoice is ready. Thank you.", "Reply if you need to reschedule."]


@pytest.mark.parametrize("text", PROMO_TEXTS)
def test_b8b_3_promotional_words_in_transactional_are_held_and_audited(conn, text):
    cust = _cust(conn, "3215559301")
    m = _free(conn, cust, text, "transactional")
    assert m["status"] == "held"
    assert m["hold_reason"] == "promotional_content_in_transactional"
    flag = _audit(conn, "message_held_for_review", m["id"])
    assert flag and json.loads(flag[0]["detail"])["matched"]
    with pytest.raises(ValueError):
        messages.approve(conn, m["id"])


@pytest.mark.parametrize("text", CLEAN_TEXTS)
def test_b8b_3_plain_service_text_is_not_flagged(text):
    assert policy.promo_hits(text) == []


def test_b8b_3_all_authored_transactional_templates_are_clean():
    from app.i18n import TEMPLATES
    for key, langs in TEMPLATES.items():
        if policy.template_purpose(key) == "transactional":
            for lang, text in langs.items():
                assert policy.promo_hits(text) == [], (key, lang)
    for text in policy.CONFIRMATION_TEXT.values():
        assert policy.promo_hits(text) == []


def test_b8b_3_promotional_translation_of_transactional_is_held(conn):
    cust = _cust(conn, "3215559302", lang="pt")
    m = messages.compose_free_text(conn, cust["id"], "Your car is ready.", "en",
                                   purpose="transactional")
    m = messages.supply_translation(conn, m["id"], "Seu carro está pronto. Desconto de 20%!")
    assert m["status"] == "held"


def test_b8b_3_promo_check_runs_at_send_and_at_dispatch(conn):
    cust = _cust(conn, "3215559303")
    # at send: content changed after approval with a matching hash (tamper)
    m = _free(conn, cust, "Your part arrived.", "transactional")
    messages.approve(conn, m["id"])
    conn.execute("UPDATE messages SET original_text = 'Part arrived - 30% off brakes'"
                 " WHERE id = ?", (m["id"],))
    fresh = messages.get_message(conn, m["id"])
    conn.execute("UPDATE messages SET approved_hash = ? WHERE id = ?",
                 (messages._content_hash(fresh), m["id"]))
    conn.commit()
    with pytest.raises(PermissionError):
        messages.send(conn, m["id"])
    assert messages.get_message(conn, m["id"])["status"] == "held"
    # at dispatch
    m2 = _approve_send(conn, _free(conn, cust, "Your car is ready.", "transactional"))
    conn.execute("UPDATE messages SET original_text = 'Car ready. Buy now!' WHERE id = ?",
                 (m2["id"],))
    conn.commit()
    with pytest.raises(PermissionError):
        delivery.dispatch(conn, m2["id"])
    assert messages.get_message(conn, m2["id"])["status"] == "held"
    stages = [json.loads(r["detail"]).get("stage")
              for r in _audit(conn, "message_held_for_review", m["id"])
              + _audit(conn, "message_held_for_review", m2["id"])]
    assert stages == ["send", "dispatch"]


def test_b8b_3_reclassifying_flagged_message_as_marketing_applies_consent(conn):
    no_consent = _cust(conn, "3215559304", consent=False)
    m = _free(conn, no_consent, "Spring sale on tires", "transactional")
    assert m["status"] == "held"
    m = messages.classify(conn, m["id"], "marketing", "op", "owner")
    assert m["status"] == "draft" and m["hold_reason"] is None
    messages.approve(conn, m["id"])
    with pytest.raises(PermissionError):
        messages.send(conn, m["id"])                 # no marketing consent
    m3 = _free(conn, no_consent, "Spring sale on tires", "transactional")
    m3 = messages.classify(conn, m3["id"], "transactional", "op", "owner")
    assert m3["status"] == "held"                    # relabel can't launder it


def test_b8b_3_quote_template_with_promotional_item_is_held(conn):
    cust = _cust(conn, "3215559305")
    q = billing.create_quote(conn, cust["id"])
    billing.add_quote_item(conn, q["id"], "Brake pads (spring discount)", 1, 5000)
    m = messages.compose_template(conn, cust["id"], "quote_ready")
    assert m["purpose"] == "transactional" and m["status"] == "held"
