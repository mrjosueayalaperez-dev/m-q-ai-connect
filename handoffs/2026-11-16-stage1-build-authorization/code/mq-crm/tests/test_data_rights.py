from app.services import (billing, bookings, customers, data_rights, messages)


def _rich_customer(conn):
    cust, _ = customers.create_customer(
        conn, "Full Record", phone="3215550220", language="en",
        consent_marketing=True, consent_source="web form")
    bookings.create_booking(conn, cust["id"], "Visit", "2026-12-05 10:00")
    q = billing.create_quote(conn, cust["id"])
    billing.add_quote_item(conn, q["id"], "Work", 1, 5000)
    billing.set_quote_status(conn, q["id"], "accepted")
    inv = billing.convert_to_invoice(conn, q["id"])
    billing.record_payment(conn, inv["id"], 5000)
    messages.compose_template(conn, cust["id"], "comeback")
    return cust


def test_export_contains_everything(conn):
    cust = _rich_customer(conn)
    out = data_rights.export_customer(conn, cust["id"])
    assert out["customer"]["name"] == "Full Record"
    assert len(out["bookings"]) == 1
    assert len(out["invoices"]) == 1 and len(out["payments"]) == 1
    assert len(out["messages"]) == 1


def test_delete_propagates_and_audits(conn):
    cust = _rich_customer(conn)
    counts = data_rights.delete_customer(conn, cust["id"])
    assert counts["customers"] == 1 and counts["invoices"] == 1
    assert customers.get_customer(conn, cust["id"]) is None
    assert conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"] == 0
    audit = conn.execute(
        "SELECT * FROM audit_log WHERE action = 'delete_customer'").fetchall()
    assert len(audit) == 1
