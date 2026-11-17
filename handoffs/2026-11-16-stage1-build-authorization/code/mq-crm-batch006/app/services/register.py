"""Processing register (Batch 006): the record of which external providers
may touch customer data, and whether their data-processing terms have been
reviewed.

The register is the operable surface of the standing privacy rule. The
delivery layer's gate (services/delivery.py) reads it; this service is how
an owner writes it. Recording a terms review is a consequential trust act:
the API layer restricts it to the owner role and audits every change.
A provider starts unreviewed — review is an explicit act, never a default.
"""
from __future__ import annotations

import sqlite3

from ..db import row_to_dict


def list_entries(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM processing_register ORDER BY id")]


def add_entry(conn: sqlite3.Connection, data_kind: str, provider: str,
              purpose: str | None = None, notes: str | None = None) -> dict:
    if not data_kind or not provider:
        raise ValueError("data_kind and provider are required")
    cur = conn.execute(
        "INSERT INTO processing_register (data_kind, provider, purpose,"
        " terms_reviewed, notes) VALUES (?, ?, ?, 0, ?)",
        (data_kind, provider, purpose, notes))
    conn.commit()
    return row_to_dict(conn.execute(
        "SELECT * FROM processing_register WHERE id = ?",
        (cur.lastrowid,)).fetchone())


def set_terms_reviewed(conn: sqlite3.Connection, entry_id: int,
                       reviewed: bool) -> dict:
    row = conn.execute("SELECT * FROM processing_register WHERE id = ?",
                       (entry_id,)).fetchone()
    if row is None:
        raise ValueError("processing register entry not found")
    conn.execute("UPDATE processing_register SET terms_reviewed = ?"
                 " WHERE id = ?", (1 if reviewed else 0, entry_id))
    conn.commit()
    return row_to_dict(conn.execute(
        "SELECT * FROM processing_register WHERE id = ?", (entry_id,)).fetchone())
