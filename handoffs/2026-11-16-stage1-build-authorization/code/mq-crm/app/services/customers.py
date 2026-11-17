"""One Record: a customer exists exactly once.

Deduplication rule (stated, deterministic): an incoming record matches an
existing customer when the normalized phone (digits only) matches, or the
normalized email (lowercase, trimmed) matches. On match, the existing record
wins and the new data fills only empty fields — one record, never two.
"""
from __future__ import annotations

import re
import sqlite3

from ..db import now_utc, row_to_dict


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    return digits or None


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    return email.strip().lower() or None


def find_duplicate(conn: sqlite3.Connection, phone=None, email=None,
                   exclude_id: int | None = None) -> dict | None:
    nphone, nemail = normalize_phone(phone), normalize_email(email)
    for row in conn.execute("SELECT * FROM customers WHERE merged_into IS NULL"):
        cust = dict(row)
        if exclude_id is not None and cust["id"] == exclude_id:
            continue
        if nphone and normalize_phone(cust["phone"]) == nphone:
            return cust
        if nemail and normalize_email(cust["email"]) == nemail:
            return cust
    return None


def create_customer(conn: sqlite3.Connection, name: str, phone=None, email=None,
                    language: str = "en", timezone: str = "America/New_York",
                    currency: str = "USD", consent_marketing: bool = False,
                    consent_source: str | None = None, source: str = "manual",
                    last_service_at: str | None = None) -> tuple[dict, bool]:
    """Returns (customer, merged). merged=True when an existing record won."""
    if not name or not name.strip():
        raise ValueError("name is required")
    existing = find_duplicate(conn, phone, email)
    ts = now_utc()
    if existing:
        updates = {}
        for field, value in (("phone", phone), ("email", email),
                             ("last_service_at", last_service_at)):
            if value and not existing.get(field):
                updates[field] = value
        if updates:
            sets = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE customers SET {sets}, updated_at = ? WHERE id = ?",
                         (*updates.values(), ts, existing["id"]))
            conn.commit()
            existing.update(updates)
        return existing, True
    cur = conn.execute(
        "INSERT INTO customers (name, phone, email, language, timezone, currency,"
        " consent_marketing, consent_source, source, last_service_at, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name.strip(), phone, email, language, timezone, currency,
         1 if consent_marketing else 0, consent_source, source, last_service_at, ts, ts),
    )
    conn.commit()
    return get_customer(conn, cur.lastrowid), False


def get_customer(conn: sqlite3.Connection, customer_id: int) -> dict | None:
    return row_to_dict(conn.execute(
        "SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone())


def list_customers(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM customers WHERE merged_into IS NULL ORDER BY name")]


def record_service(conn: sqlite3.Connection, customer_id: int, at: str | None = None) -> dict:
    ts = at or now_utc()
    conn.execute("UPDATE customers SET last_service_at = ?, updated_at = ? WHERE id = ?",
                 (ts, now_utc(), customer_id))
    conn.commit()
    return get_customer(conn, customer_id)


def set_consent(conn: sqlite3.Connection, customer_id: int, granted: bool,
                source: str | None = None) -> dict:
    """Grant or withdraw marketing consent. Withdrawal takes effect
    immediately and is re-checked at send time (services/messages.send)."""
    conn.execute(
        "UPDATE customers SET consent_marketing = ?, consent_source = ?,"
        " updated_at = ? WHERE id = ?",
        (1 if granted else 0, source, now_utc(), customer_id))
    conn.commit()
    return get_customer(conn, customer_id)
