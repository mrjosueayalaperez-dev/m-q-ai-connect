import pytest

from app.services import billing, customers


def _accepted_quote(conn):
    cust, _ = customers.create_customer(conn, "Buyer", phone="3215550120")
    q = billing.create_quote(conn, cust["id"], "USD")
    billing.add_quote_item(conn, q["id"], "Service call", 1, 7500)
    billing.add_quote_item(conn, q["id"], "Filter", 2, 1250)
    billing.set_quote_status(conn, q["id"], "sent")
    billing.set_quote_status(conn, q["id"], "accepted")
    return q


def test_quote_total_minor_units(conn):
    q = _accepted_quote(conn)
    assert billing.quote_total(conn, q["id"]) == 7500 + 2 * 1250


def test_full_chain_to_paid(conn):
    q = _accepted_quote(conn)
    inv = billing.convert_to_invoice(conn, q["id"])
    assert inv["status"] == "open" and inv["total_minor"] == 10000
    inv = billing.record_payment(conn, inv["id"], 4000)
    assert inv["status"] == "open" and inv["paid_minor"] == 4000
    inv = billing.record_payment(conn, inv["id"], 6000)
    assert inv["status"] == "paid" and inv["paid_at"] is not None


def test_unaccepted_quote_cannot_convert(conn):
    cust, _ = customers.create_customer(conn, "B2", phone="3215550121")
    q = billing.create_quote(conn, cust["id"])
    with pytest.raises(ValueError):
        billing.convert_to_invoice(conn, q["id"])
