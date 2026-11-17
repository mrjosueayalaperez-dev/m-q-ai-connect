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
- Batch 008b (founder policy, Nov 17 1:33 PM ET; replaces 008's "free text
  defaults to marketing"): every outbound message is classified by PURPOSE
  (services/policy.py). Templates carry a known purpose; free text carries
  the purpose the operator declares. No purpose = HELD (status 'held')
  until an operator classifies it via classify(), which is audited with
  from/to. Purpose, consent, channel opt-outs and the promotional-content
  check are re-evaluated at send AND at dispatch.
- Batch 008: approval records WHO approved (actor + role) and WHEN.
"""
from __future__ import annotations

import sqlite3

from ..db import audit, now_utc, row_to_dict
from ..i18n import render
from . import customers as customers_svc

from . import policy

MARKETING_TEMPLATES = policy.MARKETING_TEMPLATES
PURPOSES = policy.OPERATOR_PURPOSES


def is_marketing(msg: dict) -> bool:
    return msg.get("purpose") == policy.MARKETING


def consent_refusal(conn: sqlite3.Connection, msg: dict) -> str | None:
    """Back-compat name: the full policy refusal reason, or None."""
    return policy.evaluate(conn, msg)[0]


def enforce_policy(conn: sqlite3.Connection, msg: dict, stage: str,
                   actor: str = "system:policy", role: str = "system") -> None:
    """Raise PermissionError when the message may not go out now. When the
    decision is a review hold, the message is put on hold (and the flag
    audited) before refusing."""
    reason, hold_reason = policy.evaluate(conn, msg)
    if hold_reason:
        policy.hold(conn, msg, hold_reason, actor, role, {"stage": stage})
    if reason:
        raise PermissionError(f"{stage} refused: {reason}")


def _initial_hold(conn: sqlite3.Connection, msg: dict, actor: str,
                  role: str) -> dict:
    """Compose-time classification: hold an unclassified message, or a
    'transactional' one carrying promotional content."""
    reason, hold_reason = policy.evaluate(conn, msg)
    if hold_reason:
        policy.hold(conn, msg, hold_reason, actor, role, {"stage": "compose"})
        return get_message(conn, msg["id"])
    return msg


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
    msg = _insert(conn, customer_id, text, lang, None, None, 0, 0,
                  template_key, created_by,
                  purpose=policy.template_purpose(template_key))
    # A transactional template filled with promotional content (e.g. a quote
    # line "Spring discount") is held like any other.
    return _initial_hold(conn, msg, "system:policy", "system")


def compose_free_text(conn: sqlite3.Connection, customer_id: int, text: str,
                      text_lang: str, created_by: str = "human",
                      purpose: str | None = None,
                      actor: str = "system:policy", role: str = "system") -> dict:
    """Free text carries the purpose the OPERATOR declares ('marketing' or
    'transactional'). No purpose is never defaulted: the message is created
    HELD until classified. The declaration is audited by the API."""
    if purpose is not None and purpose not in PURPOSES:
        raise ValueError(f"purpose must be one of {PURPOSES} (or omitted,"
                         " which holds the message for review)")
    cust = customers_svc.get_customer(conn, customer_id)
    if cust is None:
        raise ValueError("customer not found")
    pending = 1 if text_lang != cust["language"] else 0
    msg = _insert(conn, customer_id, text, text_lang, None, None, 0, pending,
                  None, created_by, purpose=purpose)
    return _initial_hold(conn, msg, actor, role)


def classify(conn: sqlite3.Connection, message_id: int, purpose: str,
             actor: str, role: str) -> dict:
    """Operator (re)classification. Audited with from/to, actor, role and
    time. A change clears any approval (the message returns to draft and
    must be re-approved); a 'transactional' label with promotional content
    stays held. Not allowed for system opt-out confirmations, inbound or
    already-delivered messages."""
    if purpose not in PURPOSES:
        raise ValueError(f"purpose must be one of {PURPOSES}")
    msg = get_message(conn, message_id)
    if msg is None:
        raise ValueError("message not found")
    if msg["direction"] != "out" or msg["purpose"] == policy.OPT_OUT_CONFIRMATION:
        raise ValueError("this message's purpose cannot be classified by an operator")
    if msg["status"] not in ("held", "draft", "approved", "sent"):
        raise ValueError(f"cannot classify a message in status {msg['status']}")
    d = conn.execute("SELECT status FROM deliveries WHERE message_id = ?"
                     " ORDER BY id DESC LIMIT 1", (message_id,)).fetchone()
    if d is not None and d["status"] in ("delivered", "sending"):
        raise ValueError("message already delivered or in flight — its"
                         " classification is history")
    conn.execute(
        "UPDATE messages SET purpose = ?, hold_reason = NULL, status = 'draft',"
        " promo_override_hash = NULL, approved_hash = NULL, approved_by = NULL, approved_role = NULL,"
        " approved_at = NULL WHERE id = ?", (purpose, message_id))
    conn.commit()
    after = _initial_hold(conn, get_message(conn, message_id), actor, role)
    audit(conn, actor, role, "classify_message", "messages", message_id,
          {"purpose_from": msg["purpose"], "purpose_to": purpose,
           "status_from": msg["status"], "status_to": after["status"],
           "hold_reason_from": msg["hold_reason"],
           "hold_reason_to": after["hold_reason"]})
    return after


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
    if msg["status"] == "held":
        conn.commit()
        return get_message(conn, message_id)
    if msg["status"] == "approved":
        # Changing the content invalidates the approval: what was approved
        # is no longer what would be sent. Back to draft; a human must
        # approve the new version.
        conn.execute(
            "UPDATE messages SET status = 'draft', approved_hash = NULL,"
            " approved_by = NULL, approved_role = NULL, approved_at = NULL"
            " WHERE id = ?", (message_id,))
    conn.commit()
    # New content is re-checked: a promotional translation of a
    # transactional message is held.
    return _initial_hold(conn, get_message(conn, message_id),
                         "system:policy", "system")


def _content_hash(msg: dict) -> str:
    return policy.content_hash(msg)


def release_promo_hold(conn: sqlite3.Connection, message_id: int, actor: str,
                       role: str, reason: str | None) -> dict:
    """Batch 008c: the promotional-word list is an initial SCREEN. A human
    reviewer may release a false positive (e.g. Spanish 'sale' = 'leaves').
    The release is audited (who, when, why, matched words, content hash),
    keeps the purpose unchanged, and returns the message to DRAFT — it
    still needs a normal approval. It is bound to the exact content: any
    later change (e.g. a new translation) is screened again."""
    if not reason or not reason.strip():
        raise ValueError("a reason is required to release a review hold")
    msg = get_message(conn, message_id)
    if msg is None:
        raise ValueError("message not found")
    if msg["status"] != "held" or msg["hold_reason"] != policy.HOLD_PROMO:
        raise ValueError("only a message held by the promotional-content"
                         " screen can be released this way")
    h = policy.content_hash(msg)
    cur = conn.execute(
        "UPDATE messages SET status = 'draft', hold_reason = NULL,"
        " promo_override_hash = ? WHERE id = ? AND status = 'held'",
        (h, message_id))
    conn.commit()
    if cur.rowcount != 1:
        raise ValueError("message state changed concurrently")
    audit(conn, actor, role, "promo_hold_released", "messages", message_id,
          {"reason": reason.strip(), "purpose": msg["purpose"],
           "matched": policy.promo_hits(msg["original_text"], msg["translated_text"]),
           "content_hash": h, "status_from": "held", "status_to": "draft"})
    return get_message(conn, message_id)


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
    if msg["status"] not in ("draft", "approved", "held"):
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
    enforce_policy(conn, msg, "send")
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
