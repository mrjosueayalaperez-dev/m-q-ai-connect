"""Batch 008c — founder decisions of Nov 17, 2026, 2:01 PM ET (supersede 2:00).
S: deleted customers keep a minimal do-not-message (suppression) record,
   owner-only, enforced at send AND dispatch, incl. a re-created customer.
L: STOP in EN/ES/PT/HT — keywords and opt-out expressions, whole-message
   matching, case/accent-insensitive; sentences and substrings never match.
Q: suppression is immediate on a valid STOP; the one confirmation is queued
   for HUMAN approval; approving or rejecting it never reopens the channel.
P: the promotional-word list is a screen: a hit HOLDS (never rejects, never
   reclassifies); a human may release a false positive, audited.
Synthetic data only; local outbox transport only."""
import itertools
import json
import os
import sqlite3
import stat
import tempfile

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b8c.db"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as dbmod  # noqa: E402
from app import main as main_mod  # noqa: E402
from app.services import customers, data_rights, delivery, messages, policy  # noqa: E402
from tests.conftest import anonymous_client, auth_headers  # noqa: E402

client = TestClient(main_mod.app)
anon = anonymous_client(main_mod.app)
_n = itertools.count(1)


def _phone():
    return f"321555{8000 + next(_n):04d}"


def _cust(c, phone=None, email=None, consent=True, lang="en"):
    cust, _ = customers.create_customer(c, "Synthetic B8c", phone=phone or _phone(),
                                        email=email, language=lang,
                                        consent_marketing=consent,
                                        consent_source="b8c")
    return cust


def _free(c, cust, text, purpose="transactional"):
    return messages.compose_free_text(c, cust["id"], text, cust["language"],
                                      purpose=purpose)


def _approve_send(c, m):
    messages.approve(c, m["id"], "op", "owner")
    return messages.send(c, m["id"])


def _audit(c, action, entity_id=None):
    q, a = "SELECT * FROM audit_log WHERE action = ?", [action]
    if entity_id is not None:
        q += " AND entity_id = ?"
        a.append(entity_id)
    return [dict(r) for r in c.execute(q + " ORDER BY id", a)]


def _api_cust(phone=None, consent=True, lang="en", email=None):
    r = client.post("/api/customers", json={
        "name": "API B8c", "phone": phone or _phone(), "email": email,
        "language": lang, "consent_marketing": consent, "consent_source": "b8c"})
    return r.json()["customer"]["id"]


def _inbound(cid, text, lang="en"):
    return client.post("/api/messages/inbound",
                       json={"customer_id": cid, "text": text, "lang": lang}).json()


# ===================================================== S: suppression

def test_b8c_s_deletion_retains_minimal_suppression_record(conn):
    cust = _cust(conn, phone="321-555-9301", email="Synth.B8c@Example.test")
    policy.record_channel_opt_out(conn, cust["id"], "sms", "STOP", "op", "owner")
    customers.set_consent(conn, cust["id"], False, "customer asked")
    counts = data_rights.delete_customer(conn, cust["id"], "op", "owner")
    assert counts["suppressions_retained"] == 3
    assert counts["channel_opt_outs"] == 1 and counts["customers"] == 1
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(suppressions)")]
    assert cols == ["id", "contact_hmac", "contact_type", "channel", "scope",
                    "suppressed_at"]                      # no name/id/content
    rows = [dict(r) for r in conn.execute("SELECT * FROM suppressions ORDER BY id")]
    assert {(r["contact_type"], r["channel"], r["scope"]) for r in rows} == {
        ("phone", "sms", "channel"), ("phone", "all", "marketing"),
        ("email", "all", "marketing")}
    blob = json.dumps(rows).lower()
    for raw in ("3215559301", "555-9301", "synth.b8c", "example.test", "synthetic"):
        assert raw not in blob                             # never the raw contact
    assert all(len(r["contact_hmac"]) == 64 for r in rows)
    d = _audit(conn, "delete_customer", cust["id"])[-1]["detail"]
    assert json.loads(d)["suppressions_retained"] == 3 and "9301" not in d
    assert conn.execute("SELECT COUNT(*) FROM customers WHERE id = ?",
                        (cust["id"],)).fetchone()[0] == 0


def test_b8c_s_recreated_customer_with_same_contact_is_blocked(conn):
    old = _cust(conn, phone="(321) 555-9302", email="again.b8c@example.test")
    policy.record_channel_opt_out(conn, old["id"], "sms", "STOP", "op", "owner")
    customers.set_consent(conn, old["id"], False, "withdrawn")
    data_rights.delete_customer(conn, old["id"])
    # Re-created later — different formatting, consent ticked at creation.
    new = _cust(conn, phone="+1 321.555.9302", consent=True)
    assert new["id"] != old["id"]
    approved = _free(conn, new, "Your part arrived.")
    messages.approve(conn, approved["id"])
    with pytest.raises(PermissionError) as ei:              # at send
        messages.send(conn, approved["id"])
    assert "do-not-message" in str(ei.value)
    conn.execute("UPDATE messages SET status = 'sent' WHERE id = ?", (approved["id"],))
    conn.commit()
    with pytest.raises(PermissionError):                    # at dispatch
        delivery.dispatch(conn, approved["id"])
    assert delivery.get_delivery(conn, approved["id"])["status"] == "failed"
    # Marketing suppression follows the EMAIL too (different phone).
    by_mail = _cust(conn, email=" AGAIN.b8c@example.test ", consent=True)
    promo = _free(conn, by_mail, "We miss you!", "marketing")
    messages.approve(conn, promo["id"])
    with pytest.raises(PermissionError) as ei:
        messages.send(conn, promo["id"])
    assert "marketing" in str(ei.value)
    # ...but a transactional SMS to that new phone is fine (no SMS suppression).
    t = _approve_send(conn, _free(conn, by_mail, "Your car is ready."))
    assert delivery.dispatch(conn, t["id"])["status"] == "delivered"


def test_b8c_s_no_opt_out_means_nothing_retained(conn):
    cust = _cust(conn, phone="3215559303")
    assert data_rights.delete_customer(conn, cust["id"])["suppressions_retained"] == 0
    again = _cust(conn, phone="3215559303")
    t = _approve_send(conn, _free(conn, again, "Your part arrived."))
    assert delivery.dispatch(conn, t["id"])["status"] == "delivered"
    # A revoked (opted back in) event is not retained either.
    c2 = _cust(conn, phone="3215559304")
    policy.record_channel_opt_out(conn, c2["id"], "sms", "STOP", "op", "owner")
    policy.revoke_channel_opt_out(conn, c2["id"], "sms", "op", "owner")
    assert data_rights.delete_customer(conn, c2["id"])["suppressions_retained"] == 0


def test_b8c_s_failed_deletion_rolls_back_the_suppression_too(conn, monkeypatch):
    cust = _cust(conn, phone="3215559305")
    policy.record_channel_opt_out(conn, cust["id"], "sms", "STOP", "op", "owner")

    def boom(*a, **k):
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(data_rights, "_delete_all", boom)
    with pytest.raises(RuntimeError):
        data_rights.delete_customer(conn, cust["id"])
    assert conn.execute("SELECT COUNT(*) FROM suppressions").fetchone()[0] == 0
    assert customers.get_customer(conn, cust["id"]) is not None


def test_b8c_s_explicit_reopt_in_clears_and_is_audited():
    phone = "3215559306"
    cid = _api_cust(phone=phone, email="reopt.b8c@example.test")
    _inbound(cid, "STOP")
    client.post(f"/api/customers/{cid}/consent", json={"granted": False, "source": "asked"})
    assert client.delete(f"/api/customers/{cid}").status_code == 200
    new = _api_cust(phone=phone, email="reopt.b8c@example.test", consent=True)
    m = client.post("/api/messages/free", json={"customer_id": new, "text": "Your part arrived.",
                                                "text_lang": "en", "purpose": "transactional"}).json()
    client.post(f"/api/messages/{m['id']}/approve")
    assert client.post(f"/api/messages/{m['id']}/send").status_code == 403
    r = client.post(f"/api/customers/{new}/channel-opt-in", json={"channel": "sms"})
    assert r.status_code == 200 and r.json()["suppressions_cleared"] == 1
    assert client.post(f"/api/messages/{m['id']}/send").status_code == 200
    assert client.post(f"/api/messages/{m['id']}/dispatch").json()["status"] == "delivered"
    p = client.post("/api/messages/free", json={"customer_id": new, "text": "We miss you!",
                                                "text_lang": "en", "purpose": "marketing"}).json()
    client.post(f"/api/messages/{p['id']}/approve")
    assert client.post(f"/api/messages/{p['id']}/send").status_code == 403
    client.post(f"/api/customers/{new}/consent", json={"granted": True, "source": "re-opt-in"})
    assert client.post(f"/api/messages/{p['id']}/send").status_code == 200
    c = main_mod.conn
    cleared = _audit(c, "suppression_cleared", new)
    assert [json.loads(a["detail"])["scope"] for a in cleared] == ["channel", "marketing"]
    assert all(a["actor"] == "test-operator" and a["role"] == "owner" for a in cleared)
    hmacs = [r["contact_hmac"] for r in c.execute("SELECT contact_hmac FROM suppressions")]
    assert not any(h in a["detail"] for a in cleared for h in hmacs)


def test_b8c_s_suppression_list_is_owner_only_and_never_exported():
    phone = "3215559307"
    cid = _api_cust(phone=phone)
    _inbound(cid, "UNSUBSCRIBE")
    client.delete(f"/api/customers/{cid}")
    r = client.get("/api/admin/suppressions")
    assert r.status_code == 200 and r.json()
    assert all("contact_hmac" not in row for row in r.json())
    assert client.get("/api/admin/suppressions",
                      headers=auth_headers("staff")).status_code == 403
    assert client.get("/api/admin/suppressions",
                      headers=auth_headers("viewer")).status_code == 403
    assert anon.get("/api/admin/suppressions").status_code == 401
    hmacs = [x["contact_hmac"] for x in main_mod.conn.execute(
        "SELECT contact_hmac FROM suppressions")]
    for url in ("/api/export", "/api/customers", "/api/audit"):
        body = client.get(url).text
        assert not any(h in body for h in hmacs), url


def test_b8c_s_hmac_key_is_kept_with_the_database(monkeypatch, tmp_path):
    monkeypatch.delenv("MQ_CRM_SUPPRESSION_KEY", raising=False)
    path = str(tmp_path / "keyed.db")
    c1 = dbmod.connect(path)
    h1 = policy.contact_hmac(c1, "phone", "321-555-9308")
    c1.close()
    policy._KEYS.clear()
    c2 = dbmod.connect(path)
    assert policy.contact_hmac(c2, "phone", "(321) 555 9308") == h1   # stable
    kp = tmp_path / "suppression.key"
    assert stat.S_IMODE(os.stat(kp).st_mode) == 0o600
    monkeypatch.setenv("MQ_CRM_SUPPRESSION_KEY", "synthetic-test-key")
    # Batch 008d: a different key is no longer silently used — it is refused.
    with pytest.raises(policy.SuppressionKeyError):                    # keyed
        policy.contact_hmac(c2, "phone", "3215559308")
    c2.close()


# ========================================= L: STOP in four languages

ALL_PHRASES = [(lang, p) for lang, ps in policy.STOP_PHRASES.items() for p in ps]


@pytest.mark.parametrize("lang,phrase", ALL_PHRASES,
                         ids=[f"{l}:{p}" for l, p in ALL_PHRASES])
def test_b8c_l_every_listed_keyword_and_phrase_opts_out(lang, phrase):
    cid = _api_cust(lang=lang)
    out = _inbound(cid, phrase, lang)["channel_opt_out"]
    assert out["created"] and out["event"]["channel"] == "sms"
    assert lang in out["matched_language"]
    assert out["confirmation"]["status"] == "draft"


VARIANTS = ["STOP", "Stop!", "  stop.  ", "sToP", "STOP ALL".replace(" ", ""),
            "Don't text me", "Don’t text me", "dont TEXT me!!", "opt-out",
            "PARAR", "Alto.", "¡Baja!", "NO MÁS MENSAJES", "no  mas   mensajes",
            "Cancelar suscripción", "Sáquenme de la lista",
            "Não quero mais mensagens.", "NAO QUERO MAIS MENSAGENS", "Descadastrar",
            "Cancelar inscrição", "SAIR",
            "SISPANN", "Kanpe!", "Pa voye m mesaj ankò", "pa voye m' mesaj anko",
            "Mwen pa vle mesaj ankò."]


@pytest.mark.parametrize("text", VARIANTS)
def test_b8c_l_case_accent_punctuation_variants_match(text):
    assert policy.stop_match(text), text
    cid = _api_cust()
    assert _inbound(cid, text)["channel_opt_out"]["created"]


NON_MATCHES = ["Stop by tomorrow?", "Please don't stop the reminders", "stopped",
               "unstoppable", "Can I cancel my appointment?", "the end",
               "Alto el precio", "alto, como 1.80", "Para mañana", "para",
               "basta", "Cancelar la cita del martes", "no más mensajes de texto hoy, gracias",
               "Bajá el volumen", "Pare na esquina", "Vou sair às 5",
               "sair amanhã", "chega", "chega amanhã", "Kanpe la a m ap vini",
               "rete", "anile", "Mwen pa vle mesaj sa a", "no", "não", "non",
               "Your STOP keyword list", "", "   "]


@pytest.mark.parametrize("text", NON_MATCHES)
def test_b8c_l_sentences_substrings_and_ambiguous_words_never_match(text):
    assert policy.stop_match(text) == [], text
    cid = _api_cust()
    assert "channel_opt_out" not in _inbound(cid, text)
    assert client.get(f"/api/customers/{cid}/channel-opt-outs").json() == []


def test_b8c_l_stop_opts_out_that_channel_only(conn):
    cid = _api_cust(email="perchannel.b8c@example.test")
    _inbound(cid, "no más mensajes", "es")
    c = main_mod.conn
    assert policy.active_opt_out(c, cid, "sms") is not None
    assert policy.active_opt_out(c, cid, "email") is None
    opts = client.get(f"/api/customers/{cid}/channel-opt-outs").json()
    assert [o["channel"] for o in opts] == ["sms"]


def test_b8c_l_every_language_list_is_non_empty_and_normalized():
    for lang in ("en", "es", "pt", "ht"):
        assert policy.STOP_PHRASES[lang]
        for p in policy.STOP_PHRASES[lang]:
            assert policy.normalize_inbound(p) == p, p   # stored in matched form


# ============================ Q: immediate suppression, approval queue

def test_b8c_q_stop_suppresses_immediately_before_any_approval():
    cid = _api_cust()
    c = main_mod.conn
    mk = lambda t: client.post("/api/messages/free", json={  # noqa: E731
        "customer_id": cid, "text": t, "text_lang": "en", "purpose": "transactional"}).json()
    approved, sent = mk("Your car is ready."), mk("Your part arrived.")
    client.post(f"/api/messages/{approved['id']}/approve")
    client.post(f"/api/messages/{sent['id']}/approve")
    client.post(f"/api/messages/{sent['id']}/send")
    out = _inbound(cid, "SISPANN", "ht")["channel_opt_out"]
    conf = out["confirmation"]
    # Nothing has been approved yet — the block is already in force.
    assert conf["status"] == "draft" and conf["approved_by"] is None
    assert client.post(f"/api/messages/{approved['id']}/send").status_code == 403
    r = client.post(f"/api/messages/{sent['id']}/dispatch")
    assert r.status_code == 403 and "opted out" in r.json()["detail"]
    queue = client.get("/api/opt-out-confirmations").json()
    assert [q["id"] for q in queue if q["customer_id"] == cid] == [conf["id"]]
    assert delivery.get_delivery(c, conf["id"]) is None        # no auto-send
    assert _audit(c, "channel_opt_out", cid)


def test_b8c_q_confirmation_still_needs_a_human():
    cid = _api_cust()
    conf = _inbound(cid, "STOP")["channel_opt_out"]["confirmation"]
    assert client.post(f"/api/messages/{conf['id']}/send").status_code == 403
    assert client.post(f"/api/messages/{conf['id']}/dispatch").status_code == 403
    assert anon.post(f"/api/messages/{conf['id']}/approve").status_code == 401
    assert client.post(f"/api/messages/{conf['id']}/approve",
                       headers=auth_headers("viewer")).status_code == 403
    assert client.post(f"/api/messages/{conf['id']}/approve").status_code == 200
    assert client.post(f"/api/messages/{conf['id']}/send").status_code == 200
    assert client.post(f"/api/messages/{conf['id']}/dispatch").json()["status"] == "delivered"
    a = _audit(main_mod.conn, "approve_message", conf["id"])
    assert a and a[-1]["actor"] == "test-operator"


def test_b8c_q_approving_the_confirmation_never_reopens_the_channel(conn):
    cust = _cust(conn, lang="pt")
    out = policy.record_channel_opt_out(conn, cust["id"], "sms", "inbound", "op", "owner")
    conf = out["confirmation"]
    assert conf["original_lang"] == "pt"
    _approve_send(conn, conf)
    assert delivery.dispatch(conn, conf["id"])["status"] == "delivered"
    assert policy.active_opt_out(conn, cust["id"], "sms")["revoked_at"] is None
    t = _free(conn, cust, "Your part arrived.")
    messages.approve(conn, t["id"])
    with pytest.raises(PermissionError):
        messages.send(conn, t["id"])
    again = policy.record_channel_opt_out(conn, cust["id"], "sms", "inbound", "op", "owner")
    assert not again["created"] and again["confirmation"]["id"] == conf["id"]
    assert delivery.dispatch(conn, conf["id"])["attempts"] == 1   # no 2nd send


def test_b8c_q_rejecting_the_confirmation_never_reopens_the_channel(conn):
    cust = _cust(conn, lang="es")
    out = policy.record_channel_opt_out(conn, cust["id"], "sms", "inbound", "op", "owner")
    messages.withdraw(conn, out["confirmation"]["id"])
    assert policy.active_opt_out(conn, cust["id"], "sms") is not None
    t = _free(conn, cust, "Your part arrived.")
    messages.approve(conn, t["id"])
    with pytest.raises(PermissionError):
        messages.send(conn, t["id"])
    again = policy.record_channel_opt_out(conn, cust["id"], "sms", "inbound", "op", "owner")
    assert not again["created"]                     # still one event, one confirmation
    assert conn.execute("SELECT COUNT(*) FROM messages WHERE purpose ="
                        " 'opt_out_confirmation' AND customer_id = ?",
                        (cust["id"],)).fetchone()[0] == 1


def test_b8c_q_recreated_customer_stop_gets_its_own_confirmation(conn):
    old = _cust(conn, phone="3215559309")
    policy.record_channel_opt_out(conn, old["id"], "sms", "STOP", "op", "owner")
    data_rights.delete_customer(conn, old["id"])
    new = _cust(conn, phone="3215559309")
    out = policy.record_channel_opt_out(conn, new["id"], "sms", "STOP", "op", "owner")
    _approve_send(conn, out["confirmation"])
    assert delivery.dispatch(conn, out["confirmation"]["id"])["status"] == "delivered"
    t = _free(conn, new, "Your part arrived.")
    messages.approve(conn, t["id"])
    with pytest.raises(PermissionError):
        messages.send(conn, t["id"])


# ======================== P: promo screen holds; a human releases

def test_b8c_p_false_positive_is_held_not_rejected_then_released_by_a_human():
    cid = _api_cust(lang="es")
    m = client.post("/api/messages/free", json={
        "customer_id": cid, "text": "Su carro sale del taller a las 3.",
        "text_lang": "es", "purpose": "transactional"}).json()
    assert m["status"] == "held"                          # held, not withdrawn
    assert m["hold_reason"] == "promotional_content_in_transactional"
    assert m["purpose"] == "transactional"                # not reclassified
    assert client.post(f"/api/messages/{m['id']}/send").status_code == 403
    url = f"/api/messages/{m['id']}/release-hold"
    assert client.post(url, json={"reason": "  "}).status_code == 400
    assert client.post(url, json={"reason": "x"},
                       headers=auth_headers("viewer")).status_code == 403
    assert anon.post(url, json={"reason": "x"}).status_code == 401
    r = client.post(url, json={"reason": "'sale' = leaves (departs), not a sale"})
    assert r.status_code == 200
    rel = r.json()
    assert rel["status"] == "draft" and rel["purpose"] == "transactional"
    assert rel["approved_by"] is None                     # still needs approval
    assert client.post(f"/api/messages/{m['id']}/send").status_code == 403
    client.post(f"/api/messages/{m['id']}/approve")
    assert client.post(f"/api/messages/{m['id']}/send").status_code == 200
    assert client.post(f"/api/messages/{m['id']}/dispatch").json()["status"] == "delivered"
    a = _audit(main_mod.conn, "promo_hold_released", m["id"])
    d = json.loads(a[-1]["detail"])
    assert a[-1]["actor"] == "test-operator" and a[-1]["role"] == "owner"
    assert d["matched"] == ["sale"] and "leaves" in d["reason"]
    assert d["status_from"] == "held" and d["status_to"] == "draft"


def test_b8c_p_release_is_bound_to_the_exact_content(conn):
    cust = _cust(conn, lang="es")
    m = _free(conn, cust, "Su carro sale a las 3.")
    m = messages.release_promo_hold(conn, m["id"], "rev", "owner", "sale = leaves")
    sent = _approve_send(conn, m)
    conn.execute("UPDATE messages SET original_text = original_text || ' 50% off'"
                 " WHERE id = ?", (sent["id"],))
    conn.commit()
    with pytest.raises(PermissionError) as ei:
        delivery.dispatch(conn, sent["id"])
    assert "promotional" in str(ei.value)
    assert messages.get_message(conn, sent["id"])["status"] == "held"


def test_b8c_p_release_only_applies_to_promo_holds(conn):
    cust = _cust(conn)
    unclear = _free(conn, cust, "See you Tuesday", None)
    assert unclear["hold_reason"] == "purpose_unclear"
    with pytest.raises(ValueError):
        messages.release_promo_hold(conn, unclear["id"], "rev", "owner", "why")
    draft = _free(conn, cust, "Your part arrived.")
    with pytest.raises(ValueError):
        messages.release_promo_hold(conn, draft["id"], "rev", "owner", "why")


def test_b8c_p_screen_never_auto_rejects_or_reclassifies(conn):
    cust = _cust(conn, consent=True)
    for text in ("Big SALE on brakes", "Use coupon SPRING", "Save 50% off"):
        m = _free(conn, cust, text)
        assert m["status"] == "held" and m["purpose"] == "transactional"
        assert m["status"] not in ("withdrawn", "rejected")
    promo = _free(conn, cust, "Big SALE on brakes", "marketing")   # declared marketing
    assert promo["status"] == "draft" and promo["hold_reason"] is None
