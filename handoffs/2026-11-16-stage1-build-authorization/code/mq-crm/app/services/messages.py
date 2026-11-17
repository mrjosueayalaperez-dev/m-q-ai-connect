"""Message Center: two-way messaging in the customer's own language.

Rules enforced in code, not in copy:
- The customer's stored language preference selects the template rendering.
- The ORIGINAL text is always preserved on the record, next to any
  translation — prices, dates, and commitments stay verifiable against it.
- Free text is never machine-translated silently: a draft written in a
  different language than the customer's is stored with translation_pending
  until a human supplies the translation.
- NOTHING sends without a human approval. A message moves
  draft -> approved -> sent, and 'sent' is reachable only from 'approved'.
- Consent is respected: marketing messages to a customer without recorded
  marketing consent are refused at compose time.
"""
from __future__ import annotations

import sqlite3

from ..db import now_utc, row_to_dict
from ..i18n import render
from . import customers as customers_svc

MARKETING_TEMPLATES = {"comeback", "review_request"}


def _insert(conn, customer_id, original_text, original_lang, translated_text,
            translated_lang, mt_disclosed, translation_pending, template_key,
            created_by, status="draft"):
    cur = conn.execute(
        "INSERT INTO messages (customer_id, original_text, original_lang,"
        " translated_text, translated_lang, mt_disclosed, translation_pending,"
        " template_key, created_by, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (customer_id, original_text, original_lang, translated_text,
         translated_lang, mt_disclosed, translation_pending, template_key,
         created_by, status, now_utc()))
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM messages WHERE id = ?",
                                    (cur.lastrowid,)).fetchone())


def compose_template(conn: sqlite3.Connection, customer_id: int, template_key: str,
                     created_by: str = "human", **ctx) -> dict:
    cust = customers_svc.get_customer(conn, customer_id)
    if cust is None:
        raise ValueError("customer not found")
    if template_key in MARKETING_TEMPLATES and not cust["consent_marketing"]:
        raise PermissionError(
            "customer has not consented to marketing messages — compose refused")
    lang = cust["language"]
    ctx.setdefault("name", cust["name"])
    text = render(template_key, lang, **ctx)
    # Authored templates exist in both languages, so the rendering in the
    # customer's language IS the original — nothing was machine-translated.
    return _insert(conn, customer_id, text, lang, None, None, 0, 0,
                   template_key, created_by)


def compose_free_text(conn: sqlite3.Connection, customer_id: int, text: str,
                      text_lang: str, created_by: str = "human") -> dict:
    cust = customers_svc.get_customer(conn, customer_id)
    if cust is None:
        raise ValueError("customer not found")
    pending = 1 if text_lang != cust["language"] else 0
    return _insert(conn, customer_id, text, text_lang, None, None, 0, pending,
                   None, created_by)


def supply_translation(conn: sqlite3.Connection, message_id: int,
                       translated_text: str) -> dict:
    msg = get_message(conn, message_id)
    conn.execute(
        "UPDATE messages SET translated_text = ?, translated_lang = ?,"
        " mt_disclosed = 1, translation_pending = 0 WHERE id = ?",
        (translated_text, customers_svc.get_customer(conn, msg["customer_id"])["language"],
         message_id))
    conn.commit()
    return get_message(conn, message_id)


def approve(conn: sqlite3.Connection, message_id: int) -> dict:
    msg = get_message(conn, message_id)
    if msg["status"] != "draft":
        raise ValueError(f"only a draft can be approved (status is {msg['status']})")
    if msg["translation_pending"]:
        raise ValueError("translation pending — a human translation is required first")
    conn.execute("UPDATE messages SET status = 'approved' WHERE id = ?", (message_id,))
    conn.commit()
    return get_message(conn, message_id)


def send(conn: sqlite3.Connection, message_id: int) -> dict:
    """Delivery itself is a channel integration outside Stage 1; this marks
    the audited transition. It is reachable ONLY from 'approved'."""
    msg = get_message(conn, message_id)
    if msg["status"] != "approved":
        raise PermissionError(
            f"send refused: message is '{msg['status']}', a human must approve first")
    conn.execute("UPDATE messages SET status = 'sent' WHERE id = ?", (message_id,))
    conn.commit()
    return get_message(conn, message_id)


def record_inbound(conn: sqlite3.Connection, customer_id: int, text: str,
                   lang: str) -> dict:
    return _insert(conn, customer_id, text, lang, None, None, 0, 0, None,
                   "customer", status="received")


def get_message(conn: sqlite3.Connection, message_id: int) -> dict | None:
    return row_to_dict(conn.execute("SELECT * FROM messages WHERE id = ?",
                                    (message_id,)).fetchone())


def list_messages(conn: sqlite3.Connection, customer_id: int | None = None) -> list[dict]:
    if customer_id is not None:
        rows = conn.execute(
            "SELECT * FROM messages WHERE customer_id = ? ORDER BY id DESC",
            (customer_id,))
    else:
        rows = conn.execute("SELECT * FROM messages ORDER BY id DESC")
    return [dict(r) for r in rows]
