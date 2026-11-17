"""Your Data Is Yours: full export, and deletion that actually propagates.

Export returns everything the CRM holds about a customer (or the whole
workspace). Deletion removes the customer and every attached record —
bookings, quotes, invoices, payments, messages, reviews, referrals — and
leaves only an audit entry saying it happened. No silent copies.

Batch 008: deliveries (Batch 005) are part of a customer's data — they hold
a text snapshot of what was sent. Export includes them; deletion removes
them FIRST (they reference messages under foreign keys). Deletion is ONE
transaction: every DELETE and the audit row commit together, or — on any
error — all of it rolls back and nothing is left half-deleted for a later
unrelated write to commit. A delivery still in flight blocks deletion
(retry after it settles) rather than racing the transport.
"""
from __future__ import annotations

import sqlite3

from ..db import audit

CHILD_TABLES = ("bookings", "quotes", "invoices", "messages", "reviews", "referrals",
                "channel_opt_outs")  # Batch 008b


def _children(conn: sqlite3.Connection, table: str, customer_id: int) -> list[dict]:
    key = "from_customer_id" if table == "referrals" else "customer_id"
    return [dict(r) for r in conn.execute(
        f"SELECT * FROM {table} WHERE {key} = ?", (customer_id,))]


def export_customer(conn: sqlite3.Connection, customer_id: int) -> dict:
    cust = conn.execute("SELECT * FROM customers WHERE id = ?",
                        (customer_id,)).fetchone()
    if cust is None:
        raise ValueError("customer not found")
    out = {"customer": dict(cust)}
    for table in CHILD_TABLES:
        out[table] = _children(conn, table, customer_id)
    out["quote_items"] = [dict(r) for r in conn.execute(
        "SELECT qi.* FROM quote_items qi JOIN quotes q ON q.id = qi.quote_id"
        " WHERE q.customer_id = ?", (customer_id,))]
    out["invoice_items"] = [dict(r) for r in conn.execute(
        "SELECT ii.* FROM invoice_items ii JOIN invoices i ON i.id = ii.invoice_id"
        " WHERE i.customer_id = ?", (customer_id,))]
    out["payments"] = [dict(r) for r in conn.execute(
        "SELECT p.* FROM payments p JOIN invoices i ON i.id = p.invoice_id"
        " WHERE i.customer_id = ?", (customer_id,))]
    out["deliveries"] = [dict(r) for r in conn.execute(
        "SELECT d.* FROM deliveries d JOIN messages m ON m.id = d.message_id"
        " WHERE m.customer_id = ?", (customer_id,))]
    return out


def export_all(conn: sqlite3.Connection) -> dict:
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM customers WHERE merged_into IS NULL")]
    return {"customers": [export_customer(conn, i) for i in ids]}


class DeletionBlocked(RuntimeError):
    """Deletion refused for now (a delivery is in flight); nothing changed."""


def _delete_all(conn: sqlite3.Connection, customer_id: int) -> dict:
    counts = {}
    # Dependents first, in foreign-key order: deliveries -> messages,
    # items/payments -> quotes/invoices, then direct children, then customer.
    cur = conn.execute(
        "DELETE FROM deliveries WHERE message_id IN (SELECT id FROM messages"
        " WHERE customer_id = ?)", (customer_id,))
    counts["deliveries"] = cur.rowcount
    for table in ("quote_items", "invoice_items"):
        parent = "quotes" if table == "quote_items" else "invoices"
        fk = "quote_id" if table == "quote_items" else "invoice_id"
        cur = conn.execute(
            f"DELETE FROM {table} WHERE {fk} IN (SELECT id FROM {parent}"
            " WHERE customer_id = ?)", (customer_id,))
        counts[table] = cur.rowcount
    cur = conn.execute(
        "DELETE FROM payments WHERE invoice_id IN (SELECT id FROM invoices"
        " WHERE customer_id = ?)", (customer_id,))
    counts["payments"] = cur.rowcount
    for table in CHILD_TABLES:
        key = "from_customer_id" if table == "referrals" else "customer_id"
        cur = conn.execute(f"DELETE FROM {table} WHERE {key} = ?", (customer_id,))
        counts[table] = cur.rowcount
    cur = conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    counts["customers"] = cur.rowcount
    return counts


def delete_customer(conn: sqlite3.Connection, customer_id: int,
                    actor: str = "owner", role: str = "owner") -> dict:
    """Atomic, audited deletion. Raises ValueError when the customer does
    not exist, DeletionBlocked while a delivery is in flight; any other
    error rolls the whole deletion back and re-raises."""
    if conn.in_transaction:
        # Never fold someone else's uncommitted work into this transaction
        # (the Batch 005 defect was exactly that, in reverse).
        raise RuntimeError("deletion refused: connection has an open"
                           " transaction — nothing was changed")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if conn.execute("SELECT 1 FROM customers WHERE id = ?",
                        (customer_id,)).fetchone() is None:
            raise ValueError("customer not found")
        inflight = conn.execute(
            "SELECT COUNT(*) FROM deliveries d JOIN messages m"
            " ON m.id = d.message_id WHERE m.customer_id = ?"
            " AND d.status = 'sending'", (customer_id,)).fetchone()[0]
        if inflight:
            raise DeletionBlocked("a delivery for this customer is in flight"
                                  " — retry once it settles")
        counts = _delete_all(conn, customer_id)
        # Counts only — never names or contact details — in the audit row.
        audit(conn, actor, role, "delete_customer", "customers", customer_id,
              counts, commit=False)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return counts
