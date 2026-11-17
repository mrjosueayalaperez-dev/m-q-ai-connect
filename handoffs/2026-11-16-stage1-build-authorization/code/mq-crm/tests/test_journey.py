"""The complete customer journey, run end-to-end in English and in Spanish.
State must stay consistent at every step: booking -> reminder -> quote ->
invoice -> paid -> review -> lapse -> comeback draft -> approval -> send,
and the export must contain the whole story."""
from app.services import (billing, bookings, customers, data_rights,
                          messages, reports, reviews)


def _journey(conn, lang, phone, needle_reminder, needle_comeback):
    cust, _ = customers.create_customer(
        conn, f"Journey {lang}", phone=phone, language=lang,
        consent_marketing=True, consent_source="journey test",
        last_service_at="2025-01-01T00:00:00Z")
    b = bookings.create_booking(conn, cust["id"], "Service", "2026-12-01 09:00",
                                "America/New_York")
    due = bookings.due_reminders(conn, now="2026-11-30T15:00:00Z", within_hours=24)
    assert any(d["id"] == b["id"] for d in due)
    rem = messages.compose_template(conn, cust["id"], "reminder",
                                    when="2026-12-01 09:00", title="Service")
    assert needle_reminder in rem["original_text"]
    assert rem["original_lang"] == lang

    q = billing.create_quote(conn, cust["id"], "USD")
    billing.add_quote_item(conn, q["id"], "Work", 2, 2500)
    billing.set_quote_status(conn, q["id"], "sent")
    billing.set_quote_status(conn, q["id"], "accepted")
    inv = billing.convert_to_invoice(conn, q["id"])
    inv = billing.record_payment(conn, inv["id"], 2000)
    assert inv["status"] == "open"
    inv = billing.record_payment(conn, inv["id"], 3000)
    assert inv["status"] == "paid"

    req = reviews.request_review(conn, cust["id"])
    done = reviews.record_review(conn, req["id"], 5, "ok")
    assert done["status"] == "received"

    from app.services import comeback
    lapsed = comeback.lapsed_customers(conn, inactive_days=90,
                                       now="2026-11-17T00:00:00Z")
    assert any(c["id"] == cust["id"] for c in lapsed)
    draft = messages.compose_template(conn, cust["id"], "comeback")
    assert needle_comeback in draft["original_text"]
    messages.approve(conn, draft["id"])
    sent = messages.send(conn, draft["id"])
    assert sent["status"] == "sent"

    s = reports.summary(conn)
    assert s["average_rating"] == 5.0
    out = data_rights.export_customer(conn, cust["id"])
    assert len(out["bookings"]) == 1 and len(out["invoices"]) == 1
    assert len(out["payments"]) == 2 and len(out["messages"]) == 2


def test_journey_english(conn):
    _journey(conn, "en", "3215550701", "this is a reminder", "we miss you")


def test_journey_spanish(conn):
    _journey(conn, "es", "3215550702", "recordatorio", "extrañamos")
