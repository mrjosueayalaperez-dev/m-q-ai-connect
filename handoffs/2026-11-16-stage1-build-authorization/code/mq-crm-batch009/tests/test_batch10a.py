"""Batch 010 item 1: POST /api/bookings accepts ISO dates / date-times and
answers malformed input with 400 (never 500); /favicon.ico is served
locally (no CDN). Synthetic data only."""
import os
import tempfile

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b10a.db"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main as main_mod  # noqa: E402
from app.services import bookings  # noqa: E402
from tests.conftest import anonymous_client, auth_headers  # noqa: E402

client = TestClient(main_mod.app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def cid():
    r = client.post("/api/customers", json={"name": "Syn B10 Booker", "phone": "3215559101"})
    assert r.status_code == 200, r.text
    return r.json()["customer"]["id"]


def _book(cid, start, tz="America/New_York"):
    return client.post("/api/bookings", json={
        "customer_id": cid, "title": "Syn visit", "local_start": start, "tz": tz})


@pytest.mark.parametrize("start,expected", [
    ("2027-03-01", "2027-03-01T05:00:00Z"),                 # date only -> 00:00 local (EST)
    ("2027-03-01 10:30", "2027-03-01T15:30:00Z"),           # legacy form still works
    ("2027-03-01T10:30", "2027-03-01T15:30:00Z"),           # the old 500
    ("2027-03-01T10:30:45", "2027-03-01T15:30:45Z"),
    ("2027-03-01T10:30:45.123456", "2027-03-01T15:30:45Z"),  # fraction dropped
    ("2027-07-01T10:30", "2027-07-01T14:30:00Z"),           # DST (EDT)
    ("2027-03-01T10:30:00Z", "2027-03-01T10:30:00Z"),       # explicit UTC
    ("2027-03-01T10:30:00-05:00", "2027-03-01T15:30:00Z"),  # offset
    ("2027-03-01T10:30+01:00", "2027-03-01T09:30:00Z"),
    ("2027-03-01T10:30-0300", "2027-03-01T13:30:00Z"),      # offset without colon
    ("  2027-03-01T10:30  ", "2027-03-01T15:30:00Z"),       # surrounding spaces
])
def test_valid_iso_dates_and_datetimes(cid, start, expected):
    r = _book(cid, start)
    assert r.status_code == 200, r.text
    assert r.json()["starts_at_utc"] == expected
    assert r.json()["tz"] == "America/New_York"


def test_offset_and_local_forms_normalize_to_the_same_instant(cid):
    a = _book(cid, "2027-04-02T09:15:00-04:00").json()["starts_at_utc"]
    b = _book(cid, "2027-04-02 09:15").json()["starts_at_utc"]
    c = _book(cid, "2027-04-02T13:15:00Z").json()["starts_at_utc"]
    assert a == b == c == "2027-04-02T13:15:00Z"


@pytest.mark.parametrize("start", [
    "garbage", "tomorrow", "2027/03/01 10:30", "03-01-2027", "2027-3-1",
    "2027-03-01T10", "2027-03-01T10:30:00+5", "2027-03-01T10:30 EST",
    "2027-03-01T10:30:00Zjunk", "1' OR '1'='1", "2027-03-01\n10:30",
])
def test_garbage_is_400_with_clear_message(cid, start):
    r = _book(cid, start)
    assert r.status_code == 400, r.text
    assert "local_start must be an ISO date or date-time" in r.json()["detail"]


@pytest.mark.parametrize("start", ["", "   "])
def test_empty_is_400(cid, start):
    r = _book(cid, start)
    assert r.status_code == 400
    assert r.json()["detail"].startswith("local_start is required")


@pytest.mark.parametrize("start", [
    "2027-02-30", "2027-02-29T10:00", "2027-13-01", "2027-04-31 09:00",
    "2027-03-01T24:00", "2027-03-01T10:60", "2027-03-01T10:30:61",
    "2027-03-01T10:30+25:00", "0000-01-01",
])
def test_impossible_date_or_time_is_400(cid, start):
    r = _book(cid, start)
    assert r.status_code == 400, r.text
    assert "not a real calendar date or time" in r.json()["detail"]


def test_leap_day_is_accepted(cid):
    assert _book(cid, "2028-02-29T10:00").status_code == 200


def test_unknown_timezone_is_400(cid):
    for tz in ("Mars/Olympus", "", "../../etc/passwd"):
        r = _book(cid, "2027-03-01T10:30", tz)
        assert r.status_code == 400, (tz, r.text)
        assert "timezone" in r.json()["detail"]


def test_wrong_types_are_not_500(cid):
    r = client.post("/api/bookings", json={"customer_id": cid, "title": "x",
                                           "local_start": 20270301})
    assert r.status_code in (400, 422)
    r = client.post("/api/bookings", json={"customer_id": cid, "title": "x"})
    assert r.status_code == 422          # missing field: request validation


def test_unknown_customer_is_404_not_500():
    r = _book(987654321, "2027-03-01T10:30")
    assert r.status_code == 404 and r.json()["detail"] == "customer not found"


def test_bad_booking_writes_nothing(cid):
    before = len(client.get("/api/bookings").json())
    for s in ("garbage", "2027-02-30", ""):
        _book(cid, s)
    assert len(client.get("/api/bookings").json()) == before


def test_permissions_unchanged(cid):
    r = client.post("/api/bookings", headers=auth_headers("viewer"), json={
        "customer_id": cid, "title": "x", "local_start": "2027-03-01T10:30"})
    assert r.status_code == 403
    anon = anonymous_client(main_mod.app)
    r = anon.post("/api/bookings", headers={"X-Role": "owner"}, json={
        "customer_id": cid, "title": "x", "local_start": "2027-03-01T10:30"})
    assert r.status_code == 401


def test_parse_start_service_level():
    assert bookings.parse_start("2027-03-01T10:30", "UTC").isoformat() == "2027-03-01T10:30:00+00:00"
    with pytest.raises(bookings.BookingInputError):
        bookings.parse_start(None)
    with pytest.raises(bookings.BookingInputError):
        bookings.parse_start("2027-02-30")


def test_favicon_served_locally():
    anon = anonymous_client(main_mod.app)          # no sign-in needed
    r = anon.get("/favicon.ico")
    assert r.status_code == 200
    assert r.content[:4] == b"\x00\x00\x01\x00"     # ICO header
    assert 0 < len(r.content) < 20000
    r = anon.get("/favicon.svg")
    assert r.status_code == 200 and b"<svg" in r.content and b"http" not in r.content.replace(
        b"http://www.w3.org/2000/svg", b"")
    html = anon.get("/").text
    assert 'href="favicon.ico"' in html and 'href="favicon.svg"' in html
