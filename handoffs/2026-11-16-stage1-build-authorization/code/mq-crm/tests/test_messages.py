import pytest

from app.services import customers, messages


def _es_customer(conn, consent=True):
    cust, _ = customers.create_customer(
        conn, "Lucia", phone="3215550210", language="es",
        consent_marketing=consent, consent_source="verbal")
    return cust


def test_template_renders_in_customer_language(conn):
    cust = _es_customer(conn)
    msg = messages.compose_template(conn, cust["id"], "comeback")
    assert msg["original_lang"] == "es"
    assert "extrañamos" in msg["original_text"]
    assert msg["status"] == "draft"


def test_marketing_requires_consent(conn):
    cust = _es_customer(conn, consent=False)
    with pytest.raises(PermissionError):
        messages.compose_template(conn, cust["id"], "comeback")


def test_send_blocked_until_approved(conn):
    cust = _es_customer(conn)
    msg = messages.compose_template(conn, cust["id"], "reminder",
                                    when="2026-11-20 10:00", title="Cita")
    with pytest.raises(PermissionError):
        messages.send(conn, msg["id"])
    messages.approve(conn, msg["id"])
    sent = messages.send(conn, msg["id"])
    assert sent["status"] == "sent"


def test_free_text_other_language_waits_for_translation(conn):
    cust = _es_customer(conn)
    msg = messages.compose_free_text(conn, cust["id"], "Your part arrived.", "en")
    assert msg["translation_pending"] == 1
    assert msg["original_text"] == "Your part arrived."  # original preserved
    with pytest.raises(ValueError):
        messages.approve(conn, msg["id"])
    msg = messages.supply_translation(conn, msg["id"], "Su pieza llegó.")
    assert msg["translation_pending"] == 0 and msg["mt_disclosed"] == 1
    assert msg["original_text"] == "Your part arrived."  # still preserved
    messages.approve(conn, msg["id"])
