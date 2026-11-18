"""Book & Remind: bookings with operator-runnable reminders.

A booking is created in the customer's local time (IANA zone) and stored as
a UTC instant, so reminders fire on the right day wherever the customer is.

Batch 010: `local_start` accepts ISO 8601 dates and date-times. The 'T' form
used to raise an unhandled error (HTTP 500); any malformed value is now a
BookingInputError, which the API returns as 400 with a clear message.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..db import now_utc, row_to_dict


class BookingInputError(ValueError):
    """Malformed booking input (the API answers 400, never 500)."""


START_FORMAT_HELP = ("local_start must be an ISO date or date-time, e.g. 2026-12-02,"
                     " 2026-12-02 10:30 or 2026-12-02T10:30:00-05:00")
_START_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}"                       # date
    r"(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?"   # optional time
    r"(?:Z|[+-]\d{2}:?\d{2})?)?")               # optional UTC offset


def parse_start(local_start, tz: str = "America/New_York") -> datetime:
    """Normalize a booking start to an aware UTC datetime (whole seconds).

    - '2026-12-02'                    -> 00:00 local time in `tz`
    - '2026-12-02 10:30' or '...T10:30[:SS[.ffffff]]' -> local time in `tz`
    - with 'Z' or an offset ('-05:00', '+0100') -> that exact instant; `tz`
      is still recorded and used for display and reminders.
    Raises BookingInputError for empty, malformed or impossible values and
    for an unknown timezone."""
    if not isinstance(tz, str) or not tz.strip():
        raise BookingInputError("tz is required (an IANA timezone, e.g. America/New_York)")
    try:
        zone = ZoneInfo(tz.strip())
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise BookingInputError("unknown timezone — use an IANA name such as America/New_York")
    value = local_start.strip() if isinstance(local_start, str) else ""
    if not value:
        raise BookingInputError("local_start is required — " + START_FORMAT_HELP)
    if not _START_RE.fullmatch(value):
        raise BookingInputError(START_FORMAT_HELP)
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise BookingInputError("local_start is not a real calendar date or time — "
                                + START_FORMAT_HELP)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=zone)
    return dt.astimezone(timezone.utc).replace(microsecond=0)


def create_booking(conn: sqlite3.Connection, customer_id: int, title: str,
                   local_start: str, tz: str = "America/New_York") -> dict:
    """local_start: an ISO date or date-time (see parse_start)."""
    utc_dt = parse_start(local_start, tz)
    if conn.execute("SELECT 1 FROM customers WHERE id = ?",
                    (customer_id,)).fetchone() is None:
        raise LookupError("customer not found")
    cur = conn.execute(
        "INSERT INTO bookings (customer_id, title, starts_at_utc, tz, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (customer_id, title, utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), tz.strip(), now_utc()),
    )
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM bookings WHERE id = ?",
                                    (cur.lastrowid,)).fetchone())


def due_reminders(conn: sqlite3.Connection, now: str | None = None,
                  within_hours: int = 24) -> list[dict]:
    """Booked appointments starting within the window, not yet reminded."""
    now_dt = datetime.strptime(now or now_utc(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    horizon = (now_dt + timedelta(hours=within_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [dict(r) for r in conn.execute(
        "SELECT b.*, c.name AS customer_name, c.language AS customer_language"
        " FROM bookings b JOIN customers c ON c.id = b.customer_id"
        " WHERE b.status = 'booked' AND b.reminder_sent = 0"
        " AND b.starts_at_utc >= ? AND b.starts_at_utc <= ?"
        " ORDER BY b.starts_at_utc",
        (now_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), horizon))]


def mark_reminded(conn: sqlite3.Connection, booking_id: int) -> None:
    conn.execute("UPDATE bookings SET reminder_sent = 1 WHERE id = ?", (booking_id,))
    conn.commit()


def complete_booking(conn: sqlite3.Connection, booking_id: int) -> dict:
    conn.execute("UPDATE bookings SET status = 'done' WHERE id = ?", (booking_id,))
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM bookings WHERE id = ?",
                                    (booking_id,)).fetchone())


def cancel_booking(conn: sqlite3.Connection, booking_id: int) -> dict:
    """Cancel a booked appointment (Batch 007). Only a live booking can be
    cancelled — a completed or already-cancelled booking refuses, so the
    record of what actually happened is never rewritten."""
    row = conn.execute("SELECT * FROM bookings WHERE id = ?",
                       (booking_id,)).fetchone()
    if row is None:
        raise ValueError("booking not found")
    if row["status"] != "booked":
        raise ValueError(f"cannot cancel a booking with status {row['status']}")
    conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?",
                 (booking_id,))
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM bookings WHERE id = ?",
                                    (booking_id,)).fetchone())


def list_bookings(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT b.*, c.name AS customer_name FROM bookings b"
        " JOIN customers c ON c.id = b.customer_id ORDER BY b.starts_at_utc")]


def next_upcoming_booking(conn: sqlite3.Connection, customer_id: int,
                          now: str | None = None) -> dict | None:
    """The customer's next booked appointment at or after now (UTC)."""
    ts = now or now_utc()
    return row_to_dict(conn.execute(
        "SELECT * FROM bookings WHERE customer_id = ? AND status = 'booked'"
        " AND starts_at_utc >= ? ORDER BY starts_at_utc ASC LIMIT 1",
        (customer_id, ts)).fetchone())


def format_local(booking: dict) -> str:
    """Human rendering of a booking's start in the booking's own timezone,
    e.g. '2026-11-20 14:30 EST' — what a reminder should actually say."""
    utc_dt = datetime.strptime(booking["starts_at_utc"],
                               "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(ZoneInfo(booking["tz"])).strftime("%Y-%m-%d %H:%M %Z")
