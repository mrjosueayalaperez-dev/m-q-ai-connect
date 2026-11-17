"""Processing register (Batch 006): the record of which external providers
may touch customer data, and whether their data-processing terms have been
reviewed.

The register is the operable surface of the standing privacy rule. The
delivery layer's gate (services/delivery.py) reads it; this service is how
an owner writes it. Recording a terms review is a consequential trust act:
the API layer restricts it to the owner role and audits every change.
A provider starts unreviewed — review is an explicit act, never a default.

Batch 008 (closes declared gaps 1 and 2 + audit finding on the gate):
- A row is bound to an ENDPOINT (the URL whose scheme/host/port — and path
  prefix, when given — the delivery gate matches against the configured
  webhook URL). The provider name is a label only; it authorizes nothing.
- A review must say WHICH terms were reviewed (terms_reference: document
  name / URL / version) and records reviewed_at / reviewed_by.
- Changing the review state takes the privacy-gate lock exclusively, so a
  withdrawal is linearized against in-flight dispatches (app/gate_lock.py).
"""
from __future__ import annotations

import sqlite3
from urllib.parse import urlsplit

from ..db import now_utc, row_to_dict
from ..gate_lock import GATE_LOCK

_DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_endpoint(url: str | None) -> tuple[str, str, int, str] | None:
    """(scheme, host, port, path-prefix) or None when not a usable http(s)
    URL. Host is lowercased; the default port is made explicit; the path is
    kept without a trailing slash. Userinfo and query are ignored — and
    never echoed anywhere."""
    if not url or not isinstance(url, str):
        return None
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return None
    scheme = (parts.scheme or "").lower()
    host = (parts.hostname or "").lower()
    if scheme not in _DEFAULT_PORTS or not host:
        return None
    return (scheme, host, port or _DEFAULT_PORTS[scheme],
            (parts.path or "").rstrip("/"))


def canonical_endpoint(url: str | None) -> str | None:
    """The form stored on the register: scheme://host:port/path — any
    userinfo, query or fragment (where credentials hide) is dropped."""
    n = normalize_endpoint(url)
    if n is None:
        return None
    return f"{n[0]}://{n[1]}:{n[2]}{n[3]}"


def endpoint_matches(registered: str | None, configured: str | None) -> bool:
    reg, cfg = normalize_endpoint(registered), normalize_endpoint(configured)
    if reg is None or cfg is None:
        return False
    if reg[:3] != cfg[:3]:
        return False
    return not reg[3] or cfg[3] == reg[3] or cfg[3].startswith(reg[3] + "/")


def list_entries(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM processing_register ORDER BY id")]


def add_entry(conn: sqlite3.Connection, data_kind: str, provider: str,
              purpose: str | None = None, notes: str | None = None,
              endpoint: str | None = None) -> dict:
    if not data_kind or not provider:
        raise ValueError("data_kind and provider are required")
    if endpoint is not None and normalize_endpoint(endpoint) is None:
        raise ValueError("endpoint must be an http(s) URL")
    cur = conn.execute(
        "INSERT INTO processing_register (data_kind, provider, purpose,"
        " terms_reviewed, notes, endpoint) VALUES (?, ?, ?, 0, ?, ?)",
        (data_kind, provider, purpose, notes, canonical_endpoint(endpoint)))
    conn.commit()
    return row_to_dict(conn.execute(
        "SELECT * FROM processing_register WHERE id = ?",
        (cur.lastrowid,)).fetchone())


def set_terms_reviewed(conn: sqlite3.Connection, entry_id: int,
                       reviewed: bool, terms_reference: str | None = None,
                       reviewed_by: str | None = None,
                       endpoint: str | None = None) -> dict:
    """Record (reviewed=True) or withdraw (reviewed=False) a terms review.
    A review requires a terms_reference and an endpoint (given here or
    already on the row). A withdrawal waits for any in-flight dispatch to
    finish, then commits — after it returns, no dispatch can pass the gate
    on this row."""
    row = conn.execute("SELECT * FROM processing_register WHERE id = ?",
                       (entry_id,)).fetchone()
    if row is None:
        raise ValueError("processing register entry not found")
    if reviewed:
        ref = (terms_reference or "").strip()
        if not ref:
            raise ValueError("terms_reference is required to record a review"
                             " (which terms — document, URL or version)")
        ep = endpoint if endpoint is not None else row["endpoint"]
        if normalize_endpoint(ep) is None:
            raise ValueError("an http(s) endpoint is required to record a"
                             " review — the review binds to that endpoint")
    with GATE_LOCK.exclusive():
        if reviewed:
            conn.execute(
                "UPDATE processing_register SET terms_reviewed = 1,"
                " terms_reference = ?, endpoint = ?, reviewed_at = ?,"
                " reviewed_by = ?, withdrawn_at = NULL WHERE id = ?",
                (ref, canonical_endpoint(ep), now_utc(), reviewed_by, entry_id))
        else:
            conn.execute(
                "UPDATE processing_register SET terms_reviewed = 0,"
                " withdrawn_at = ? WHERE id = ?", (now_utc(), entry_id))
        conn.commit()
    return row_to_dict(conn.execute(
        "SELECT * FROM processing_register WHERE id = ?", (entry_id,)).fetchone())
