"""M&Q CRM — data layer.

SQLite storage, deliberately boring: no external database, no credentials,
nothing to leak. All timestamps are UTC ISO-8601 instants; local meaning is
carried by an IANA timezone stored per record. All money is integer minor
units (cents) with an ISO 4217 currency code — never floats.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    language TEXT NOT NULL DEFAULT 'en',
    timezone TEXT NOT NULL DEFAULT 'America/New_York',
    currency TEXT NOT NULL DEFAULT 'USD',
    consent_marketing INTEGER NOT NULL DEFAULT 0,
    consent_source TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    last_service_at TEXT,
    merged_into INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    title TEXT NOT NULL,
    starts_at_utc TEXT NOT NULL,
    tz TEXT NOT NULL DEFAULT 'America/New_York',
    status TEXT NOT NULL DEFAULT 'booked',
    reminder_sent INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    status TEXT NOT NULL DEFAULT 'draft',
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quote_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER NOT NULL REFERENCES quotes(id),
    description TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 1,
    unit_amount_minor INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    quote_id INTEGER,
    status TEXT NOT NULL DEFAULT 'open',
    currency TEXT NOT NULL DEFAULT 'USD',
    issued_at TEXT NOT NULL,
    paid_at TEXT
);
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    description TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 1,
    unit_amount_minor INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    amount_minor INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    method TEXT,
    paid_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    direction TEXT NOT NULL DEFAULT 'out',
    channel TEXT NOT NULL DEFAULT 'sms',
    template_key TEXT,
    original_text TEXT NOT NULL,
    original_lang TEXT NOT NULL,
    translated_text TEXT,
    translated_lang TEXT,
    mt_disclosed INTEGER NOT NULL DEFAULT 0,
    translation_pending INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft',
    created_by TEXT NOT NULL DEFAULT 'human',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    status TEXT NOT NULL DEFAULT 'requested',
    rating INTEGER,
    text TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_customer_id INTEGER NOT NULL REFERENCES customers(id),
    code TEXT NOT NULL UNIQUE,
    referred_customer_id INTEGER,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id INTEGER,
    detail TEXT,
    at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS processing_register (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_kind TEXT NOT NULL,
    provider TEXT NOT NULL,
    purpose TEXT,
    terms_reviewed INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);
"""


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: str = ":memory:") -> sqlite3.Connection:
    # check_same_thread=False: the API layer serves from worker threads.
    # Stage 1 is a single-process app; SQLite serializes writes.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def audit(conn: sqlite3.Connection, actor: str, role: str, action: str,
          entity: str, entity_id: int | None, detail: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor, role, action, entity, entity_id, detail, at_utc)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (actor, role, action, entity, entity_id,
         json.dumps(detail or {}), now_utc()),
    )
    conn.commit()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None
