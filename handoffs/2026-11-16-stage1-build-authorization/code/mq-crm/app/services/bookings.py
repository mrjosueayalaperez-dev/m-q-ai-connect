"""Book & Remind: bookings with operator-runnable reminders.

A booking is created in the customer's local time (IANA zone) and stored as
a UTC instant, so reminders fire on the right day wherever the customer is.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..db import now_utc, row_to_dict


def create_booking(conn: sqlite3.Connection, customer_id: int, title: str,
                   local_start: str, tz: str = "America/New_York") -> dict:
    """local_start: 'YYYY-MM-DD HH:MM' in the given IANA timezone."""
    local_dt = datetime.strptime(local_start, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz))
    utc_dt = local_dt.astimezone(timezone.utc)
    cur = conn.execute(
        "INSERT INTO bookings (customer_id, title, starts_at_utc, tz, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (customer_id, title, utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), tz, now_utc()),
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


def list_bookings(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT b.*, c.name AS customer_name FROM bookings b"
        " JOIN customers c ON c.id = b.customer_id ORDER BY b.starts_at_utc")]
