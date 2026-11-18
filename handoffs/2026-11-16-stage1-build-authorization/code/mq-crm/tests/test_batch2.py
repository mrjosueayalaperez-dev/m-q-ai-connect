from app.services import billing, bookings, customers, messages


def test_list_messages_filter(conn):
    a, _ = customers.create_customer(conn, "List A", phone="3215550501",
                                     consent_marketing=True, consent_source="t")
    b, _ = customers.create_customer(conn, "List B", phone="3215550502",
                                     consent_marketing=True, consent_source="t")
    messages.compose_template(conn, a["id"], "comeback")
    messages.compose_template(conn, b["id"], "comeback")
    assert len(messages.list_messages(conn)) == 2
    only_a = messages.list_messages(conn, a["id"])
    assert len(only_a) == 1 and only_a[0]["customer_id"] == a["id"]


def test_list_bookings_and_quotes(conn):
    cust, _ = customers.create_customer(conn, "List C", phone="3215550503")
    bookings.create_booking(conn, cust["id"], "Visit", "2026-12-02 10:00")
    q = billing.create_quote(conn, cust["id"])
    billing.add_quote_item(conn, q["id"], "Work", 3, 1000)
    assert len(bookings.list_bookings(conn)) == 1
    quotes = billing.list_quotes(conn)
    assert quotes[0]["total_minor"] == 3000 and quotes[0]["customer_name"] == "List C"
    assert billing.list_invoices(conn) == []


def test_seed_demo_is_synthetic_and_complete(tmp_path):
    from scripts.seed_demo import seed
    out = seed(str(tmp_path / "demo.db"))
    assert out["invoice_status"] == "paid"
    assert out["draft_status"] == "draft"
    assert out["import_report"]["imported"] == 2
    assert out["customers"] == 4
