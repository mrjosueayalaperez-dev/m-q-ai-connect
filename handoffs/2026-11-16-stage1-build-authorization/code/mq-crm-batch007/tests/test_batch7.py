"""Batch 007 tests — customer record editing under One Record protection,
and booking cancellation. Builder-side, as always."""
import os
import tempfile

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b7.db"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main as main_mod  # noqa: E402
from app.services import bookings, customers  # noqa: E402

client = TestClient(main_mod.app)


# ---- Customer update ----

def test_update_language_and_region(conn):
    cust, _ = customers.create_customer(conn, "Upd", phone="3215551401",
                                        language="en")
    updated = customers.update_customer(conn, cust["id"], language="ht",
                                        region="US-FL")
    assert updated["language"] == "ht" and updated["region"] == "US-FL"
    assert updated["phone"] == "3215551401"  # untouched fields stay


def test_update_refuses_duplicate_contact(conn):
    a, _ = customers.create_customer(conn, "A", phone="3215551402")
    b, _ = customers.create_customer(conn, "B", phone="3215551403",
                                     email="b@x.invalid")
    with pytest.raises(ValueError):
        customers.update_customer(conn, b["id"], phone="3215551402")
    with pytest.raises(ValueError):
        customers.update_customer(conn, a["id"], email="B@x.invalid")
    # Keeping your OWN phone is not a conflict.
    same = customers.update_customer(conn, a["id"], phone="3215551402",
                                     name="A Renamed")
    assert same["name"] == "A Renamed"


def test_update_validation(conn):
    cust, _ = customers.create_customer(conn, "Val", phone="3215551404")
    with pytest.raises(ValueError):
        customers.update_customer(conn, cust["id"], language="fr")
    with pytest.raises(ValueError):
        customers.update_customer(conn, cust["id"], nickname="x")
    with pytest.raises(ValueError):
        customers.update_customer(conn, cust["id"])
    with pytest.raises(ValueError):
        customers.update_customer(conn, 99999, name="Ghost")


def test_api_update_roles_and_audit():
    r = client.post("/api/customers", json={
        "name": "API Upd", "phone": "3215551405", "language": "en"})
    cid = r.json()["customer"]["id"]
    r = client.post(f"/api/customers/{cid}/update",
                    json={"language": "pt"}, headers={"X-Role": "viewer"})
    assert r.status_code == 403
    r = client.post(f"/api/customers/{cid}/update",
                    json={"language": "pt", "region": "US-FL"})
    assert r.status_code == 200 and r.json()["language"] == "pt"
    rows = main_mod.conn.execute(
        "SELECT detail FROM audit_log WHERE action = 'update_customer'"
        " AND entity_id = ?", (cid,)).fetchall()
    assert len(rows) == 1
    # The audit trail names the fields changed — never their values.
    assert "pt" not in rows[0]["detail"] and "language" in rows[0]["detail"]


# ---- Booking cancel ----

def test_cancel_booking_lifecycle(conn):
    cust, _ = customers.create_customer(conn, "Bk", phone="3215551406")
    bk = bookings.create_booking(conn, cust["id"], "Visit",
                                 "2027-01-05 10:00", "America/New_York")
    cancelled = bookings.cancel_booking(conn, bk["id"])
    assert cancelled["status"] == "cancelled"
    with pytest.raises(ValueError):
        bookings.cancel_booking(conn, bk["id"])
    bk2 = bookings.create_booking(conn, cust["id"], "Visit 2",
                                  "2027-01-06 10:00", "America/New_York")
    bookings.complete_booking(conn, bk2["id"])
    with pytest.raises(ValueError):
        bookings.cancel_booking(conn, bk2["id"])
    with pytest.raises(ValueError):
        bookings.cancel_booking(conn, 99999)
    # A cancelled booking no longer counts as upcoming.
    assert bookings.next_upcoming_booking(conn, cust["id"]) is None


def test_api_cancel_and_complete():
    r = client.post("/api/customers", json={
        "name": "API Bk", "phone": "3215551407"})
    cid = r.json()["customer"]["id"]
    r = client.post("/api/bookings", json={
        "customer_id": cid, "title": "API Visit",
        "local_start": "2027-02-01 09:00", "tz": "America/New_York"})
    bid = r.json()["id"]
    r = client.post(f"/api/bookings/{bid}/cancel",
                    headers={"X-Role": "viewer"})
    assert r.status_code == 403
    r = client.post(f"/api/bookings/{bid}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    r = client.post(f"/api/bookings/{bid}/cancel")
    assert r.status_code == 400
    r = client.post("/api/bookings", json={
        "customer_id": cid, "title": "API Visit 2",
        "local_start": "2027-02-02 09:00", "tz": "America/New_York"})
    bid2 = r.json()["id"]
    r = client.post(f"/api/bookings/{bid2}/complete")
    assert r.status_code == 200 and r.json()["status"] == "done"
