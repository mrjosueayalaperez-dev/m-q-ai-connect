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
- Batch 008: every outbound message carries a PURPOSE ('marketing' or
  'transactional'). Templates derive it (comeback / review_request are
  marketing); free text is MARKETING unless the operator explicitly
  declares it transactional — fail-closed, so a free-text promo can no
  longer bypass consent. Consent is re-checked at send AND at dispatch
  (services/delivery.py) for every message, whatever its type.
- Batch 008: approval records WHO approved (actor + role) and WHEN.
"""
from __future__ import annotations

import sqlite3

from ..db import now_utc, row_to_dict
from ..i18n import render
from . import customers as customers_svc

MARKETING_TEMPLATES = {"comeback", "review_request"}
PURPOSES = ("marketing", "transactional")


def is_marketing(msg: dict) -> bool:
    """Fail-closed purpose test. Anything not provably transactional is
    treated as marketing: a marketing template, an explicit 'marketing'
    purpose, or a legacy outbound free-text row with no purpose recorded."""
    if msg.get("template_key") in MARKETING_TEMPLATES:
        return True
    purpose = msg.get("purpose")
    if purpose == "transactional":
        return False
    if purpose == "marketing":
        return True
    # Legacy rows (pre-008) carry no purpose: an authored non-marketing
    # template is transactional; free text is presumed marketing.
    return msg.get("template_key") is None


def consent_refusal(conn: sqlite3.Connection, msg: dict) -> str | None:
    """None when the message may go out NOW, else the refusal reason.
    Reads the customer's CURRENT consent — never a flag cached earlier."""
    cust = customers_svc.get_customer(conn, msg["customer_id"])
    if cust is None:
        return "customer no longer exists"
    if is_marketing(msg) and not cust["consent_marketing"]:
        return ("customer consent is not current for marketing messages")
    return None


def _insert(conn, customer_id, original_text, original_lang, translated_text,
            translated_lang, mt_disclosed, translation_pending, template_key,
            created_by, status="draft", direction="out", purpose=None):
    cur = conn.execute(
        "INSERT INTO messages (customer_id, direction, original_text, original_lang,"
        " translated_text, translated_lang, mt_disclosed, translation_pending,"
        " template_key, created_by, status, created_at, purpose)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (customer_id, direction, original_text, original_lang, translated_text,
         translated_lang, mt_disclosed, translation_pending, template_key,
         created_by, status, now_utc(), purpose))
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM messages WHERE id = ?",
                                    (cur.lastrowid,)).fetchone())


def _resolve_context(conn: sqlite3.Connection, cust: dict, template_key: str,
                     ctx: dict) -> dict:
    """Fill template fields from the customer's REAL records when the caller
    did not supply them (Batch 004 — replaces the Batch 002 placeholder
    context, where the UI sent '—' for {when}/{total} and drafts carried
    meaningless text). Explicit caller values always win. When a required
    field cannot be resolved from actual records, compose REFUSES with a
    clear reason: a draft quoting a placeholder time or total is a false
    record, and the approval hash would bind a human's approval to it."""
    from ..i18n import format_money
    from . import billing as billing_svc
    from . import bookings as bookings_svc
    if template_key == "reminder":
        if "when" not in ctx or "title" not in ctx:
            booking = bookings_svc.next_upcoming_booking(conn, cust["id"])
            if booking is None:
                raise ValueError(
                    "cannot compose a reminder: the customer has no upcoming booking")
            ctx.setdefault("when", bookings_svc.format_local(booking))
            ctx.setdefault("title", booking["title"])
    elif template_key == "quote_ready":
        if "total" not in ctx or "summary" not in ctx:
            row = conn.execute(
                "SELECT * FROM quotes WHERE customer_id = ?"
                " ORDER BY id DESC LIMIT 1", (cust["id"],)).fetchone()
            if row is None:
                raise ValueError(
                    "cannot compose a quote message: the customer has no quote")
            quote = dict(row)
            items = [dict(i) for i in conn.execute(
                "SELECT * FROM quote_items WHERE quote_id = ?", (quote["id"],))]
            if not items:
                raise ValueError(
                    "cannot compose a quote message: the quote has no items")
            ctx.setdefault("total", format_money(
                billing_svc.quote_total(conn, quote["id"]), quote["currency"]))
            ctx.setdefault("summary", "; ".join(
                f'{i["qty"]} × {i["description"]}' for i in items))
    elif template_key == "invoice_ready":
        if "total" not in ctx:
            row = conn.execute(
                "SELECT * FROM invoices WHERE customer_id = ?"
                " ORDER BY id DESC LIMIT 1", (cust["id"],)).fetchone()
            if row is None:
                raise ValueError(
                    "cannot compose an invoice message: the customer has no invoice")
            invoice = dict(row)
            ctx.setdefault("total", format_money(
                billing_svc.invoice_total(conn, invoice["id"]), invoice["currency"]))
    return ctx


def compose_template(conn: sqlite3.Connection, customer_id: int, template_key: str,
                     created_by: str = "human", **ctx) -> dict:
    cust = customers_svc.get_customer(conn, customer_id)
    if cust is None:
        raise ValueError("customer not found")
    if template_key in MARKETING_TEMPLATES and not cust["consent_marketing"]:
        raise PermissionError(
            "customer has not consented to marketing messages — compose refused")
    lang = cust["language"]
    ctx = _resolve_context(conn, cust, template_key, ctx)
    ctx.setdefault("name", cust["name"])
    text = render(template_key, lang, **ctx)
    # Authored templates exist in both languages, so the rendering in the
    # customer's language IS the original — nothing was machine-translated.
    purpose = "marketing" if template_key in MARKETING_TEMPLATES else "transactional"
    return _insert(conn, customer_id, text, lang, None, None, 0, 0,
                   template_key, created_by, purpose=purpose)


def compose_free_text(conn: sqlite3.Connection, customer_id: int, text: str,
                      text_lang: str, created_by: str = "human",
                      purpose: str = "marketing") -> dict:
    """Free text defaults to MARKETING (fail-closed). The operator must
    declare purpose='transactional' for a service message (part arrived,
    appointment moved) — the declaration is stored and audited by the API."""
    if purpose not in PURPOSES:
        raise ValueError(f"purpose must be one of {PURPOSES}")
    cust = customers_svc.get_customer(conn, customer_id)
    if cust is None:
        raise ValueError("customer not found")
    pending = 1 if text_lang != cust["language"] else 0
    return _insert(conn, customer_id, text, text_lang, None, None, 0, pending,
                   None, created_by, purpose=purpose)


def supply_translation(conn: sqlite3.Connection, message_id: int,
                       translated_text: str) -> dict:
    msg = get_message(conn, message_id)
    if msg["status"] == "sent":
        raise ValueError("a sent message cannot be altered")
    conn.execute(
        "UPDATE messages SET translated_text = ?, translated_lang = ?,"
        " mt_disclosed = 1, translation_pending = 0 WHERE id = ?",
        (translated_text, customers_svc.get_customer(conn, msg["customer_id"])["language"],
         message_id))
    if msg["status"] == "approved":
        # Changing the content invalidates the approval: what was approved
        # is no longer what would be sent. Back to draft; a human must
        # approve the new version.
        conn.execute(
            "UPDATE messages SET status = 'draft', approved_hash = NULL,"
            " approved_by = NULL, approved_role = NULL, approved_at = NULL"
            " WHERE id = ?", (message_id,))
    conn.commit()
    return get_message(conn, message_id)


def _content_hash(msg: dict) -> str:
    import hashlib
    payload = (msg["original_text"] + "\n---\n" + (msg["translated_text"] or ""))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def approve(conn: sqlite3.Connection, message_id: int,
            approved_by: str | None = None,
            approved_role: str | None = None) -> dict:
    msg = get_message(conn, message_id)
    if msg is None:
        raise ValueError("message not found")
    if msg["status"] != "draft":
        raise ValueError(f"only a draft can be approved (status is {msg['status']})")
    if msg["translation_pending"]:
        raise ValueError("translation pending — a human translation is required first")
    # Approval binds to the EXACT content: the hash of original + translation
    # is recorded, and send() re-verifies it. Any later content change
    # invalidates the approval.
    # Batch 008: the approver's identity and the instant are stored ON the
    # message (and the API writes an 'approve_message' audit row).
    conn.execute("UPDATE messages SET status = 'approved', approved_hash = ?,"
                 " approved_by = ?, approved_role = ?, approved_at = ?"
                 " WHERE id = ?", (_content_hash(msg), approved_by,
                                   approved_role, now_utc(), message_id))
    conn.commit()
    return get_message(conn, message_id)


def withdraw(conn: sqlite3.Connection, message_id: int) -> dict:
    """Operator withdraws a draft or an approved message. Terminal: a
    withdrawn message can neither be approved nor sent."""
    msg = get_message(conn, message_id)
    if msg["status"] not in ("draft", "approved"):
        raise ValueError(f"cannot withdraw a message in status {msg['status']}")
    conn.execute("UPDATE messages SET status = 'withdrawn', approved_hash = NULL"
                 " WHERE id = ?", (message_id,))
    conn.commit()
    return get_message(conn, message_id)


def send(conn: sqlite3.Connection, message_id: int) -> dict:
    """Delivery itself is a channel integration outside Stage 1; this marks
    the audited transition. The gate re-verifies EVERY precondition at send
    time rather than trusting flags set earlier:
    - status must be 'approved', reached through approve();
    - no translation may be pending;
    - the content hash recorded at approval must match the content now —
      approval binds to the exact text, and any change invalidates it;
    - for marketing messages (templates AND free text, Batch 008), the
      customer's consent must be CURRENT —
      consent withdrawn after drafting stops the send;
    - the transition itself is one atomic UPDATE ... WHERE status='approved',
      so two simultaneous sends cannot both succeed."""
    import sqlite3 as _sqlite3
    msg = get_message(conn, message_id)
    if msg is None:
        raise PermissionError("send refused: message not found")
    if msg["status"] != "approved":
        raise PermissionError(
            f"send refused: message is '{msg['status']}', a human must approve first")
    if msg["translation_pending"]:
        raise PermissionError(
            "send refused: translation still pending — approval was not"
            " legitimately reachable for this message")
    if not msg["approved_hash"] or msg["approved_hash"] != _content_hash(msg):
        raise PermissionError(
            "send refused: content differs from the approved version"
            " (approval is bound to the exact text)")
    reason = consent_refusal(conn, msg)
    if reason:
        raise PermissionError(f"send refused: {reason}")
    try:
        cur = conn.execute(
            "UPDATE messages SET status = 'sent' WHERE id = ? AND status = 'approved'",
            (message_id,))
        conn.commit()
    except _sqlite3.OperationalError:
        conn.rollback()
        raise PermissionError("send refused: concurrent send in progress")
    if cur.rowcount != 1:
        raise PermissionError("send refused: message state changed concurrently")
    return get_message(conn, message_id)


def record_inbound(conn: sqlite3.Connection, customer_id: int, text: str,
                   lang: str) -> dict:
    if customers_svc.get_customer(conn, customer_id) is None:
        raise ValueError("customer not found")
    return _insert(conn, customer_id, text, lang, None, None, 0, 0, None,
                   "customer", status="received", direction="in")


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
