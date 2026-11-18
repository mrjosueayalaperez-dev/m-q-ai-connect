"""Simple Reports: the few numbers a solo operator actually checks."""
from __future__ import annotations

import sqlite3

from ..db import now_utc


def summary(conn: sqlite3.Connection, inactive_days: int = 90) -> dict:
    from .comeback import lapsed_customers

    total_customers = conn.execute(
        "SELECT COUNT(*) AS n FROM customers WHERE merged_into IS NULL").fetchone()["n"]
    open_invoices = [dict(r) for r in conn.execute(
        "SELECT currency, COUNT(*) AS count, COALESCE(SUM(t.total), 0) AS total_minor"
        " FROM invoices i JOIN (SELECT invoice_id, SUM(qty * unit_amount_minor) AS total"
        " FROM invoice_items GROUP BY invoice_id) t ON t.invoice_id = i.id"
        " WHERE i.status = 'open' GROUP BY currency")]
    paid = [dict(r) for r in conn.execute(
        "SELECT currency, COALESCE(SUM(amount_minor), 0) AS paid_minor FROM payments"
        " GROUP BY currency")]
    upcoming = conn.execute(
        "SELECT COUNT(*) AS n FROM bookings WHERE status = 'booked'"
        " AND starts_at_utc >= ?", (now_utc(),)).fetchone()["n"]
    avg = conn.execute(
        "SELECT AVG(rating) AS a FROM reviews WHERE status = 'received'").fetchone()["a"]
    return {
        "customers": total_customers,
        "lapsed_customers": len(lapsed_customers(conn, inactive_days)),
        "open_invoices": open_invoices,
        "payments_received": paid,
        "upcoming_bookings": upcoming,
        "average_rating": round(avg, 2) if avg is not None else None,
    }
