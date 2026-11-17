from app.services import customers


def test_customer_created_once_by_phone(conn):
    a, merged_a = customers.create_customer(conn, "Maria Lopez", phone="(321) 555-0100")
    b, merged_b = customers.create_customer(conn, "Maria L.", phone="321-555-0100")
    assert merged_a is False and merged_b is True
    assert a["id"] == b["id"]
    assert len(customers.list_customers(conn)) == 1


def test_duplicate_by_email_case_insensitive(conn):
    customers.create_customer(conn, "Joe", email="Joe@Example.com")
    _, merged = customers.create_customer(conn, "Joseph", email="joe@example.com")
    assert merged is True


def test_merge_fills_only_empty_fields(conn):
    customers.create_customer(conn, "Ana", phone="3215550101")
    cust, merged = customers.create_customer(
        conn, "Ana", phone="3215550101", email="ana@example.com")
    assert merged is True and cust["email"] == "ana@example.com"


def test_language_and_consent_stored(conn):
    cust, _ = customers.create_customer(
        conn, "Luis", phone="3215550102", language="es",
        consent_marketing=True, consent_source="paper form 2026-11-01")
    assert cust["language"] == "es"
    assert cust["consent_marketing"] == 1
    assert cust["consent_source"] == "paper form 2026-11-01"


def test_name_required(conn):
    import pytest
    with pytest.raises(ValueError):
        customers.create_customer(conn, "  ")
