from app.services import bookings, customers


def test_booking_converts_local_to_utc(conn):
    cust, _ = customers.create_customer(conn, "Sam", phone="3215550110")
    # December in New York is EST (UTC-5): 09:00 local = 14:00 UTC.
    b = bookings.create_booking(conn, cust["id"], "Haircut", "2026-12-01 09:00",
                                "America/New_York")
    assert b["starts_at_utc"] == "2026-12-01T14:00:00Z"


def test_due_reminders_window(conn):
    cust, _ = customers.create_customer(conn, "Sam", phone="3215550111")
    bookings.create_booking(conn, cust["id"], "Soon", "2026-12-01 09:00",
                            "America/New_York")
    bookings.create_booking(conn, cust["id"], "Far", "2026-12-20 09:00",
                            "America/New_York")
    due = bookings.due_reminders(conn, now="2026-11-30T15:00:00Z", within_hours=24)
    assert len(due) == 1 and due[0]["title"] == "Soon"
    bookings.mark_reminded(conn, due[0]["id"])
    assert bookings.due_reminders(conn, now="2026-11-30T15:00:00Z",
                                  within_hours=24) == []
