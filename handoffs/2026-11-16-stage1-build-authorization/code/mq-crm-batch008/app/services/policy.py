"""Messaging policy (Batch 008b — founder-approved Nov 17, 2026, 1:33 PM ET).

1. PURPOSE, not message type, decides the rules.
   - 'marketing': promotional / sales / solicitation / advertising content.
     Needs current marketing consent.
   - 'transactional': service updates, customer-requested replies,
     account-related messages. Allowed without marketing consent.
   - 'opt_out_confirmation': SYSTEM purpose only — the one confirmation
     permitted after a full channel opt-out, once per opt-out event.
   An unclear or unset purpose is never defaulted: the message is HELD
   (status 'held') until an operator classifies it.
2. Two separate opt-outs.
   - Marketing opt-out (customers.consent_marketing = 0): blocks marketing;
     transactional messages still go.
   - Full channel opt-out (channel_opt_outs row, e.g. SMS STOP): blocks
     EVERYTHING on that channel except the single opt-out confirmation
     linked to that event.
3. A transactional label must never carry promotional content. A
   deterministic keyword/pattern check (EN/ES/PT/HT) runs on the original
   AND translated text; a hit holds the message for review (audited).
All of it is re-checked at send and at dispatch.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata

from ..db import audit, now_utc, row_to_dict

MARKETING, TRANSACTIONAL, OPT_OUT_CONFIRMATION = (
    "marketing", "transactional", "opt_out_confirmation")
OPERATOR_PURPOSES = (MARKETING, TRANSACTIONAL)
ALL_PURPOSES = OPERATOR_PURPOSES + (OPT_OUT_CONFIRMATION,)
MARKETING_TEMPLATES = {"comeback", "review_request"}
CHANNELS = ("sms", "email")

HOLD_UNCLEAR = "purpose_unclear"
HOLD_PROMO = "promotional_content_in_transactional"

# Matched on lowercased, accent-stripped text with word boundaries. Stated
# limits: a keyword list catches common promo wording, not every promo; it
# can also flag an innocent use ("we'll deal with it") — a flag only HOLDS
# the message for a human, it never sends or deletes anything.
PROMO_PATTERNS = [
    # English
    r"\bsales?\b", r"%\s*off\b", r"\bdiscounts?\b", r"\bdiscounted\b",
    r"\bpromos?\b", r"\bpromotions?\b", r"\bpromotional\b", r"\bcoupons?\b",
    r"\bpromo ?codes?\b", r"\blimited[- ]time\b", r"\bbuy now\b",
    r"\boffers?\b", r"\bdeals?\b", r"\bclearance\b", r"\bfree gift\b",
    r"\bspecial price\b", r"\bbogo\b",
    # Spanish
    r"\bofertas?\b", r"\bdescuentos?\b", r"\bpromocion(es)?\b",
    r"\bcupon(es)?\b", r"\brebajas?\b", r"\btiempo limitado\b",
    r"\bcompre? (ya|ahora)\b", r"\bliquidacion\b",
    # Portuguese
    r"\bdescontos?\b", r"\bpromocao\b", r"\bpromocoes\b", r"\bcupo(m|ns)\b",
    r"\btempo limitado\b", r"\bcompre (ja|agora)\b", r"\bliquidacao\b",
    # Haitian Creole
    r"\brabe\b", r"\bpwomosyon\b", r"\bpwomo\b", r"\bkoupon\b",
    r"\bvann an rabe\b",
]
_PROMO_RE = re.compile("|".join(PROMO_PATTERNS))


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def promo_hits(*texts: str | None) -> list[str]:
    hits = []
    for t in texts:
        if t:
            hits += [m.group(0) for m in _PROMO_RE.finditer(_fold(t))]
    return sorted(set(hits))


def template_purpose(template_key: str) -> str:
    return MARKETING if template_key in MARKETING_TEMPLATES else TRANSACTIONAL


# ---- channel opt-outs -------------------------------------------------

STOP_KEYWORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit",
                 "revoke", "optout", "opt out", "opt-out"}

CONFIRMATION_TEXT = {
    "en": "You have been unsubscribed and will receive no more {channel} messages from us. Reply START to resubscribe.",
    "es": "Se canceló su suscripción y no recibirá más mensajes por {channel} de nuestra parte. Responda START para volver a suscribirse.",
    "pt": "Sua inscrição foi cancelada e você não receberá mais mensagens por {channel} de nós. Responda START para se inscrever novamente.",
    "ht": "Nou retire ou nan lis la, ou p ap resevwa okenn lòt mesaj {channel} nan men nou. Reponn START pou ou tounen nan lis la.",
}


def is_stop_keyword(text: str | None) -> bool:
    return _fold((text or "").strip()).strip(" .!") in STOP_KEYWORDS


def active_opt_out(conn: sqlite3.Connection, customer_id: int,
                   channel: str) -> dict | None:
    return row_to_dict(conn.execute(
        "SELECT * FROM channel_opt_outs WHERE customer_id = ? AND channel = ?"
        " AND revoked_at IS NULL ORDER BY id DESC LIMIT 1",
        (customer_id, channel)).fetchone())


def record_channel_opt_out(conn: sqlite3.Connection, customer_id: int,
                           channel: str, source: str, actor: str,
                           role: str) -> dict:
    """Record a full channel opt-out EVENT and draft its one confirmation.
    Idempotent while an opt-out is active: a repeated STOP does not create a
    second event or a second confirmation. Returns {event, confirmation,
    created}."""
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {CHANNELS}")
    cust = conn.execute("SELECT * FROM customers WHERE id = ?",
                        (customer_id,)).fetchone()
    if cust is None:
        raise ValueError("customer not found")
    existing = active_opt_out(conn, customer_id, channel)
    if existing:
        conf = row_to_dict(conn.execute(
            "SELECT * FROM messages WHERE opt_out_event_id = ? AND purpose = ?",
            (existing["id"], OPT_OUT_CONFIRMATION)).fetchone())
        return {"event": existing, "confirmation": conf, "created": False}
    ts = now_utc()
    cur = conn.execute(
        "INSERT INTO channel_opt_outs (customer_id, channel, source,"
        " opted_out_at) VALUES (?, ?, ?, ?)", (customer_id, channel, source, ts))
    event_id = cur.lastrowid
    lang = cust["language"] if cust["language"] in CONFIRMATION_TEXT else "en"
    text = CONFIRMATION_TEXT[lang].format(channel=channel.upper())
    cur = conn.execute(
        "INSERT INTO messages (customer_id, direction, channel, original_text,"
        " original_lang, translated_text, translated_lang, mt_disclosed,"
        " translation_pending, template_key, created_by, status, created_at,"
        " purpose, opt_out_event_id) VALUES (?, 'out', ?, ?, ?, NULL, NULL, 0,"
        " 0, NULL, 'system', 'draft', ?, ?, ?)",
        (customer_id, channel, text, lang, ts, OPT_OUT_CONFIRMATION, event_id))
    conn.commit()
    audit(conn, actor, role, "channel_opt_out", "customers", customer_id,
          {"channel": channel, "source": source, "event_id": event_id,
           "confirmation_message_id": cur.lastrowid})
    return {"event": row_to_dict(conn.execute(
                "SELECT * FROM channel_opt_outs WHERE id = ?", (event_id,)).fetchone()),
            "confirmation": row_to_dict(conn.execute(
                "SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()),
            "created": True}


def revoke_channel_opt_out(conn: sqlite3.Connection, customer_id: int,
                           channel: str, actor: str, role: str) -> dict | None:
    ev = active_opt_out(conn, customer_id, channel)
    if ev is None:
        raise ValueError(f"no active {channel} opt-out for this customer")
    conn.execute("UPDATE channel_opt_outs SET revoked_at = ? WHERE id = ?",
                 (now_utc(), ev["id"]))
    conn.commit()
    audit(conn, actor, role, "channel_opt_in", "customers", customer_id,
          {"channel": channel, "event_id": ev["id"]})
    return row_to_dict(conn.execute("SELECT * FROM channel_opt_outs WHERE id = ?",
                                    (ev["id"],)).fetchone())


def list_opt_outs(conn: sqlite3.Connection, customer_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM channel_opt_outs WHERE customer_id = ? ORDER BY id",
        (customer_id,))]


# ---- the policy decision -------------------------------------------------

def evaluate(conn: sqlite3.Connection, msg: dict) -> tuple[str | None, str | None]:
    """(refusal_reason, hold_reason). Both None = the message may go out NOW.
    hold_reason set = the message must be HELD for operator review.
    Reads current consent and opt-out state — never a cached flag."""
    purpose = msg.get("purpose")
    if purpose not in ALL_PURPOSES:
        return ("message is held for review: its purpose is unclear or unset",
                HOLD_UNCLEAR)
    if msg.get("hold_reason"):
        return (f"message is held for review ({msg['hold_reason']})", None)
    cust = conn.execute("SELECT * FROM customers WHERE id = ?",
                        (msg["customer_id"],)).fetchone()
    if cust is None:
        return ("customer no longer exists", None)
    channel = msg.get("channel") or "sms"
    opt = active_opt_out(conn, msg["customer_id"], channel)
    if purpose == OPT_OUT_CONFIRMATION:
        if opt is None or msg.get("opt_out_event_id") != opt["id"]:
            return ("opt-out confirmation is no longer valid: it belongs to an"
                    " opt-out event that is not the customer's active one", None)
    elif opt is not None:
        return (f"customer has opted out of {channel.upper()} — only the one-time"
                " opt-out confirmation may be sent on this channel", None)
    if purpose == MARKETING and not cust["consent_marketing"]:
        return ("customer consent is not current for marketing messages", None)
    if purpose in (TRANSACTIONAL, OPT_OUT_CONFIRMATION):
        hits = promo_hits(msg.get("original_text"), msg.get("translated_text"))
        if hits:
            return ("message is held for review: promotional content in a"
                    f" transactional message ({', '.join(hits)})", HOLD_PROMO)
    return (None, None)


def hold(conn: sqlite3.Connection, msg: dict, hold_reason: str,
         actor: str = "system:policy", role: str = "system",
         detail: dict | None = None) -> None:
    """Put a message on review hold (status 'held'; any approval cleared)
    and audit the flag."""
    conn.execute(
        "UPDATE messages SET status = 'held', hold_reason = ?,"
        " approved_hash = NULL, approved_by = NULL, approved_role = NULL,"
        " approved_at = NULL WHERE id = ?", (hold_reason, msg["id"]))
    conn.commit()
    d = {"hold_reason": hold_reason, "status_from": msg.get("status"),
         "purpose": msg.get("purpose")}
    if hold_reason == HOLD_PROMO:
        d["matched"] = promo_hits(msg.get("original_text"),
                                  msg.get("translated_text"))
    d.update(detail or {})
    audit(conn, actor, role, "message_held_for_review", "messages", msg["id"], d)
