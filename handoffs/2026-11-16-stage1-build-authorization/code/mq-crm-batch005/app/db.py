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
    approved_hash TEXT,
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
    at_utc TEXT NOT NULL,
    prev_hash TEXT,
    row_hash TEXT
);
CREATE TABLE IF NOT EXISTS processing_register (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_kind TEXT NOT NULL,
    provider TEXT NOT NULL,
    purpose TEXT,
    terms_reviewed INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS audit_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    reason TEXT,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    last_row_id INTEGER,
    rows_json TEXT NOT NULL,
    rows_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id),
    channel TEXT NOT NULL DEFAULT 'sms',
    transport TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    provider_ref TEXT,
    text_snapshot TEXT NOT NULL,
    detail TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Add later-batch columns to databases created by earlier batches."""
    wanted = {"messages": {"approved_hash": "TEXT"},
              "audit_log": {"prev_hash": "TEXT", "row_hash": "TEXT"},
              "customers": {"region": "TEXT", "data_residency": "TEXT"}}
    for table, cols in wanted.items():
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, typ in cols.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
    conn.commit()


def audit(conn: sqlite3.Connection, actor: str, role: str, action: str,
          entity: str, entity_id: int | None, detail: dict | None = None) -> None:
    """Append an audit row, hash-chained to the previous row: altering or
    deleting a historical row breaks the chain and is detectable by
    verify_audit_chain(). Tamper-EVIDENT, not tamper-proof."""
    import hashlib
    detail_json = json.dumps(detail or {})
    at = now_utc()
    prev = conn.execute(
        "SELECT row_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = prev["row_hash"] if prev else "GENESIS"
    payload = "|".join([prev_hash or "GENESIS", actor, role, action, entity,
                        str(entity_id), detail_json, at])
    row_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT INTO audit_log (actor, role, action, entity, entity_id, detail,"
        " at_utc, prev_hash, row_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (actor, role, action, entity, entity_id, detail_json, at,
         prev_hash, row_hash),
    )
    conn.commit()


RECOVERY_ACTION = "audit_chain_recovered"


def _row_payload(r: dict) -> str:
    return "|".join([r["prev_hash"] or "GENESIS", r["actor"], r["role"],
                     r["action"], r["entity"], str(r["entity_id"]),
                     r["detail"], r["at_utc"]])


def _snapshot_for_marker(marker: str | None, snapshots: dict) -> dict | None:
    """A recovery row's prev_hash is 'SNAPSHOT:<id>:<rows_hash>'. Resolve it
    to the snapshot record it binds to, or None if it does not check out."""
    import hashlib
    if not marker or not marker.startswith("SNAPSHOT:"):
        return None
    parts = marker.split(":", 2)
    if len(parts) != 3:
        return None
    try:
        snap = snapshots.get(int(parts[1]))
    except ValueError:
        return None
    if snap is None or snap["rows_hash"] != parts[2]:
        return None
    if hashlib.sha256(snap["rows_json"].encode("utf-8")).hexdigest() != snap["rows_hash"]:
        return None
    return snap


def _chain_first_bad(conn: sqlite3.Connection) -> int | None:
    """Walk the audit chain and return the id of the first row that fails
    verification, or None when the whole chain verifies.

    Recovery segments (see recover_audit_chain): a row with action
    RECOVERY_ACTION binds, through its prev_hash marker, to a forensic
    snapshot of every row preceding it. Rows preceding the LAST recovery
    boundary are attested by those snapshots — the snapshot's rows must
    equal the actual rows, exactly as preserved — and are not re-verified
    hash-by-hash: recovery preserves evidence as found and cannot
    retroactively prove a tampered past. Altering or deleting an attested
    row after the fact breaks the snapshot equality and is detected. Rows
    after the last boundary chain normally from that row's hash."""
    import hashlib
    import json
    rows = [dict(r) for r in conn.execute("SELECT * FROM audit_log ORDER BY id ASC")]
    snapshots = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM audit_snapshots")}
    # Pass 1: validate every recovery boundary's snapshot binding.
    last_boundary = -1
    for i, r in enumerate(rows):
        if r["action"] == RECOVERY_ACTION:
            snap = _snapshot_for_marker(r["prev_hash"], snapshots)
            if snap is None:
                return r["id"]
            if json.loads(snap["rows_json"]) != rows[:i]:
                return r["id"]
            if hashlib.sha256(_row_payload(r).encode("utf-8")).hexdigest() != r["row_hash"]:
                return r["id"]
            last_boundary = i
    # Pass 2: chain-verify only the rows after the last boundary.
    prev_hash = rows[last_boundary]["row_hash"] if last_boundary >= 0 else "GENESIS"
    for r in rows[last_boundary + 1:]:
        if r["prev_hash"] != prev_hash:
            return r["id"]
        if hashlib.sha256(_row_payload(r).encode("utf-8")).hexdigest() != r["row_hash"]:
            return r["id"]
        prev_hash = r["row_hash"]
    return None


def verify_audit_chain(conn: sqlite3.Connection) -> bool:
    return _chain_first_bad(conn) is None


def audit_chain_status(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()
    bad = _chain_first_bad(conn)
    return {"ok": bad is None, "rows": int(rows["n"]), "first_bad_id": bad}


def recover_audit_chain(conn: sqlite3.Connection, actor: str, role: str,
                        reason: str | None = None) -> dict:
    """Recovery procedure for a broken audit chain (Batch 004).

    Detection alone (Batch 003) leaves an operator with a chain that can
    never verify again. Recovery preserves EVERY existing row verbatim as a
    forensic snapshot, then opens a new chain segment whose first row binds
    to that snapshot's hash. Honest limits, stated: recovery does NOT
    retroactively prove the snapshotted rows — it preserves the evidence
    exactly as found and restarts verifiable trust from the snapshot point.
    Refuses to run on an intact chain: recovery is a consequential act, not
    a routine one."""
    import hashlib
    import json
    bad = _chain_first_bad(conn)
    if bad is None:
        raise ValueError("audit chain is intact — nothing to recover")
    rows = [dict(r) for r in conn.execute("SELECT * FROM audit_log ORDER BY id ASC")]
    rows_json = json.dumps(rows, sort_keys=True)
    rows_hash = hashlib.sha256(rows_json.encode("utf-8")).hexdigest()
    at = now_utc()
    cur = conn.execute(
        "INSERT INTO audit_snapshots (created_at, reason, actor, role,"
        " row_count, last_row_id, rows_json, rows_hash)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (at, reason, actor, role, len(rows),
         rows[-1]["id"] if rows else None, rows_json, rows_hash))
    snap_id = cur.lastrowid
    marker = f"SNAPSHOT:{snap_id}:{rows_hash}"
    detail_json = json.dumps({"snapshot_id": snap_id, "first_bad_id": bad,
                              "reason": reason})
    payload = "|".join([marker, actor, role, RECOVERY_ACTION, "audit_log",
                        str(snap_id), detail_json, at])
    row_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT INTO audit_log (actor, role, action, entity, entity_id,"
        " detail, at_utc, prev_hash, row_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (actor, role, RECOVERY_ACTION, "audit_log", snap_id, detail_json, at,
         marker, row_hash))
    conn.commit()
    return {"snapshot_id": snap_id, "rows_preserved": len(rows),
            "first_bad_id": bad, "chain_ok": _chain_first_bad(conn) is None}


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None
