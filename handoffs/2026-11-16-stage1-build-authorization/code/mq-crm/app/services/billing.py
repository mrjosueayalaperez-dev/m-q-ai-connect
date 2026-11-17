"""Quote -> Invoice -> Paid, end to end.

Amounts are integer minor units with an ISO currency code. An invoice is
'paid' only when recorded payments sum to its full total; partial payments
leave it 'open' — the money state is computed, never asserted.
"""
from __future__ import annotations

import sqlite3

from ..db import now_utc, row_to_dict


def create_quote(conn: sqlite3.Connection, customer_id: int, currency: str = "USD") -> dict:
    cur = conn.execute(
        "INSERT INTO quotes (customer_id, currency, created_at) VALUES (?, ?, ?)",
        (customer_id, currency, now_utc()))
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM quotes WHERE id = ?",
                                    (cur.lastrowid,)).fetchone())


def add_quote_item(conn: sqlite3.Connection, quote_id: int, description: str,
                   qty: int, unit_amount_minor: int) -> None:
    if qty <= 0 or unit_amount_minor < 0:
        raise ValueError("qty must be positive and amount non-negative")
    conn.execute(
        "INSERT INTO quote_items (quote_id, description, qty, unit_amount_minor)"
        " VALUES (?, ?, ?, ?)", (quote_id, description, qty, unit_amount_minor))
    conn.commit()


def quote_total(conn: sqlite3.Connection, quote_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(qty * unit_amount_minor), 0) AS t FROM quote_items"
        " WHERE quote_id = ?", (quote_id,)).fetchone()
    return int(row["t"])


def set_quote_status(conn: sqlite3.Connection, quote_id: int, status: str) -> dict:
    if status not in ("draft", "sent", "accepted", "declined"):
        raise ValueError(f"invalid quote status {status}")
    conn.execute("UPDATE quotes SET status = ? WHERE id = ?", (status, quote_id))
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM quotes WHERE id = ?",
                                    (quote_id,)).fetchone())


def convert_to_invoice(conn: sqlite3.Connection, quote_id: int) -> dict:
    quote = row_to_dict(conn.execute("SELECT * FROM quotes WHERE id = ?",
                                     (quote_id,)).fetchone())
    if quote is None:
        raise ValueError("quote not found")
    if quote["status"] != "accepted":
        raise ValueError("only an accepted quote converts to an invoice")
    cur = conn.execute(
        "INSERT INTO invoices (customer_id, quote_id, currency, issued_at)"
        " VALUES (?, ?, ?, ?)",
        (quote["customer_id"], quote_id, quote["currency"], now_utc()))
    invoice_id = cur.lastrowid
    for item in conn.execute("SELECT * FROM quote_items WHERE quote_id = ?", (quote_id,)):
        conn.execute(
            "INSERT INTO invoice_items (invoice_id, description, qty, unit_amount_minor)"
            " VALUES (?, ?, ?, ?)",
            (invoice_id, item["description"], item["qty"], item["unit_amount_minor"]))
    conn.execute("UPDATE quotes SET status = 'converted' WHERE id = ?", (quote_id,))
    conn.commit()
    return get_invoice(conn, invoice_id)


def get_invoice(conn: sqlite3.Connection, invoice_id: int) -> dict | None:
    inv = row_to_dict(conn.execute("SELECT * FROM invoices WHERE id = ?",
                                   (invoice_id,)).fetchone())
    if inv is None:
        return None
    inv["total_minor"] = invoice_total(conn, invoice_id)
    inv["paid_minor"] = invoice_paid(conn, invoice_id)
    return inv


def invoice_total(conn: sqlite3.Connection, invoice_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(qty * unit_amount_minor), 0) AS t FROM invoice_items"
        " WHERE invoice_id = ?", (invoice_id,)).fetchone()
    return int(row["t"])


def invoice_paid(conn: sqlite3.Connection, invoice_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_minor), 0) AS t FROM payments WHERE invoice_id = ?",
        (invoice_id,)).fetchone()
    return int(row["t"])


def record_payment(conn: sqlite3.Connection, invoice_id: int, amount_minor: int,
                   method: str = "card") -> dict:
    inv = get_invoice(conn, invoice_id)
    if inv is None:
        raise ValueError("invoice not found")
    if amount_minor <= 0:
        raise ValueError("payment must be positive")
    conn.execute(
        "INSERT INTO payments (invoice_id, amount_minor, currency, method, paid_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (invoice_id, amount_minor, inv["currency"], method, now_utc()))
    if invoice_paid(conn, invoice_id) >= invoice_total(conn, invoice_id):
        conn.execute("UPDATE invoices SET status = 'paid', paid_at = ? WHERE id = ?",
                     (now_utc(), invoice_id))
    conn.commit()
    return get_invoice(conn, invoice_id)


def list_quotes(conn: sqlite3.Connection) -> list[dict]:
    out = []
    for r in conn.execute(
            "SELECT q.*, c.name AS customer_name FROM quotes q"
            " JOIN customers c ON c.id = q.customer_id ORDER BY q.id DESC"):
        q = dict(r)
        q["total_minor"] = quote_total(conn, q["id"])
        q["items"] = [dict(i) for i in conn.execute(
            "SELECT * FROM quote_items WHERE quote_id = ?", (q["id"],))]
        out.append(q)
    return out


def list_invoices(conn: sqlite3.Connection) -> list[dict]:
    out = []
    for r in conn.execute("SELECT id FROM invoices ORDER BY id DESC"):
        out.append(get_invoice(conn, r["id"]))
    return out
