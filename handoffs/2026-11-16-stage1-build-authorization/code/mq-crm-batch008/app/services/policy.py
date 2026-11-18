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
   Batch 008c: the list is an initial SCREEN only — a hit holds, it never
   rejects or reclassifies; a human may release a false positive with an
   audited override bound to the exact content.
4. Batch 008c: deleted customers leave a minimal do-not-message
   (suppression) record — see "suppression" below.
All of it is re-checked at send and at dispatch.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import unicodedata

from ..db import audit, now_utc, row_to_dict
from . import customers as customers_svc

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

# Batch 008c (founder decision, Nov 17 2:01 PM ET): STOP in EN/ES/PT/HT.
# Single keywords AND equivalent opt-out expressions. Matching is ANCHORED
# to the WHOLE inbound message after normalization (accents folded,
# lowercased, apostrophes removed, hyphens -> spaces, surrounding
# punctuation trimmed, whitespace collapsed) — never a substring, so
# "Stop by tomorrow?" or "no más mensajes de texto, gracias" do not match.
# Matching is language-independent: any listed expression from any of the
# four lists opts the customer out, whatever their language preference.
# PENDING NATIVE-SPEAKER REVIEW (ES/PT/HT).
# Deliberately NOT listed (too ambiguous as a whole message): "para"
# (ES/PT "for"), "basta" (ES "enough"), "fin" (ES "end"), "chega" (PT
# "arrives"/"enough"), "rete" (HT "stay"), "anile" (HT "cancel" — would
# catch "cancel my appointment" replies), "no"/"nao"/"non" alone.
STOP_PHRASES = {
    "en": ["stop", "stopall", "unsubscribe", "cancel", "end", "quit",
           "revoke", "optout", "opt out", "stop texting", "stop texting me",
           "stop messaging me", "stop sending messages",
           "stop sending me messages", "no more messages", "no more texts",
           "please stop", "stop please", "unsubscribe me", "remove me",
           "remove me from your list", "remove me from the list",
           "take me off your list", "take me off the list", "do not text me",
           "dont text me", "do not message me", "dont message me",
           "do not contact me", "dont contact me"],
    "es": ["parar", "alto", "baja", "cancelar", "darme de baja", "dar de baja",
           "deme de baja", "no mas mensajes", "no mas textos",
           "no quiero mas mensajes", "no me envien mas mensajes",
           "no me manden mas mensajes", "no me escriban mas",
           "deja de enviarme mensajes", "dejen de enviarme mensajes",
           "quitenme de la lista", "sacame de la lista",
           "saquenme de la lista", "eliminenme de la lista",
           "cancelar suscripcion"],
    "pt": ["pare", "parar", "sair", "cancelar", "descadastrar",
           "nao quero mais mensagens", "nao quero mais receber mensagens",
           "nao me envie mais mensagens", "nao me mande mais mensagens",
           "pare de enviar mensagens", "pare de me enviar mensagens",
           "parem de enviar mensagens", "parem de me enviar mensagens",
           "chega de mensagens", "me tire da lista", "me tirem da lista",
           "quero sair da lista", "cancelar inscricao"],
    "ht": ["sispann", "kanpe", "sispann voye mesaj", "sispann voye m mesaj",
           "sispann ekri m", "pa voye m mesaj anko", "pa voye mesaj anko",
           "pa voye mwen mesaj anko", "m pa vle mesaj anko",
           "mwen pa vle mesaj anko", "mwen pa vle resevwa mesaj anko",
           "retire m nan lis la", "retire mwen nan lis la", "pa ekri m anko"],
}
STOP_KEYWORDS = {p for ps in STOP_PHRASES.values() for p in ps}
_EDGE = " \t\r\n.,;:!?¡¿\"()[]*~"


def normalize_inbound(text: str | None) -> str:
    t = _fold(text or "")
    t = re.sub(r"['\u2019\u2018`\u00b4]", "", t).replace("-", " ")
    t = re.sub(r"\s+", " ", t).strip(_EDGE)
    return re.sub(r"\s+", " ", t).strip()


def stop_match(text: str | None) -> list[str]:
    """Languages whose list contains the WHOLE normalized message ([] = no
    opt-out)."""
    n = normalize_inbound(text)
    return [lang for lang, ps in STOP_PHRASES.items() if n in ps]

CONFIRMATION_TEXT = {
    "en": "You have been unsubscribed and will receive no more {channel} messages from us. Reply START to resubscribe.",
    "es": "Se canceló su suscripción y no recibirá más mensajes por {channel} de nuestra parte. Responda START para volver a suscribirse.",
    "pt": "Sua inscrição foi cancelada e você não receberá mais mensagens por {channel} de nós. Responda START para se inscrever novamente.",
    "ht": "Nou retire ou nan lis la, ou p ap resevwa okenn lòt mesaj {channel} nan men nou. Reponn START pou ou tounen nan lis la.",
}


def is_stop_keyword(text: str | None) -> bool:
    return bool(stop_match(text))


def active_opt_out(conn: sqlite3.Connection, customer_id: int,
                   channel: str) -> dict | None:
    return row_to_dict(conn.execute(
        "SELECT * FROM channel_opt_outs WHERE customer_id = ? AND channel = ?"
        " AND revoked_at IS NULL ORDER BY id DESC LIMIT 1",
        (customer_id, channel)).fetchone())


def record_channel_opt_out(conn: sqlite3.Connection, customer_id: int,
                           channel: str, source: str, actor: str,
                           role: str) -> dict:
    """Record a full channel opt-out EVENT and queue its one confirmation.
    Suppression is IMMEDIATE: the event row blocks the channel at send and
    dispatch from this commit on. The confirmation is a DRAFT in the
    approval queue (human-approved, founder decision Nov 17 2:01 PM ET);
    approving or withdrawing it never changes the opt-out.
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
    """Explicit re-opt-in for a channel: ends the active opt-out event (if
    any) and clears a retained suppression for this customer's contact on
    that channel (if any)."""
    ev = active_opt_out(conn, customer_id, channel)
    cleared = clear_suppressions(conn, customer_id, "channel", channel, actor, role)
    if ev is None:
        if cleared:
            return {"channel": channel, "suppressions_cleared": cleared}
        raise ValueError(f"no active {channel} opt-out for this customer")
    conn.execute("UPDATE channel_opt_outs SET revoked_at = ? WHERE id = ?",
                 (now_utc(), ev["id"]))
    conn.commit()
    audit(conn, actor, role, "channel_opt_in", "customers", customer_id,
          {"channel": channel, "event_id": ev["id"]})
    out = row_to_dict(conn.execute("SELECT * FROM channel_opt_outs WHERE id = ?",
                                   (ev["id"],)).fetchone())
    out["suppressions_cleared"] = cleared
    return out


def list_opt_outs(conn: sqlite3.Connection, customer_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM channel_opt_outs WHERE customer_id = ? ORDER BY id",
        (customer_id,))]


def content_hash(msg: dict) -> str:
    payload = ((msg.get("original_text") or "") + "\n---\n"
               + (msg.get("translated_text") or ""))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---- suppression (do-not-message) list — Batch 008c ---------------------
# Founder decision (Nov 17, 2:01 PM ET): when a customer is DELETED, keep
# the minimum needed to keep honouring their opt-out. One row per
# (protected contact, channel, scope):
#   contact_hmac  HMAC-SHA256(key, "phone:<digits>" | "email:<lower>") —
#                 a keyed hash is STILL personal data (it is a stable
#                 identifier for a known number); never the raw contact
#   contact_type  'phone' | 'email'
#   channel       'sms' | 'email' (scope 'channel') or 'all' (marketing)
#   scope         'channel' (full channel opt-out) | 'marketing'
#   suppressed_at UTC timestamp of the retention
# No name, no customer id, no message content. Enforced at send AND at
# dispatch for every customer whose contact matches — including a customer
# re-created later with the same phone/email. Cleared ONLY by an explicit,
# audited re-opt-in on a customer holding that contact (channel opt-in,
# or a marketing consent grant through the API); creating a customer with
# consent ticked does NOT clear it.
# Key: MQ_CRM_SUPPRESSION_KEY if set; otherwise a random 32-byte key
# generated once in <db dir>/suppression.key (mode 0600). Losing the key
# makes the retained rows unmatchable — back it up with the database.
_MEM_KEY: bytes | None = None
_KEYS: dict[str, bytes] = {}   # kept for compatibility; keys are re-read each use

# Batch 008d: key continuity. The database stores a NON-SECRET check value,
# HMAC-SHA256(key, KEY_CHECK_LABEL), in table suppression_key_check. Every
# use of the key verifies it. A missing key is never silently regenerated
# once the database holds a check value or any suppression row, and a
# wrong key is refused: both raise SuppressionKeyError (a PermissionError,
# so send / dispatch / deletion fail CLOSED). Messages never contain the
# key or the check value. Procedure: docs/SUPPRESSION-KEY-BACKUP-RESTORE.md
KEY_ENV = "MQ_CRM_SUPPRESSION_KEY"
KEY_FILE_NAME = "suppression.key"
KEY_CHECK_LABEL = b"mq-crm/suppression-key-check/v1"
_DOC = "docs/SUPPRESSION-KEY-BACKUP-RESTORE.md"


class SuppressionKeyError(PermissionError):
    """The suppression key is missing or does not match this database."""


def _key_file(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("PRAGMA database_list").fetchone()
    path = row["file"] if row is not None else ""
    return os.path.join(os.path.dirname(path), KEY_FILE_NAME) if path else None


def _key_check_value(key: bytes) -> str:
    return hmac.new(key, KEY_CHECK_LABEL, hashlib.sha256).hexdigest()


def _stored_check(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT check_value FROM suppression_key_check"
                       " WHERE id = 1").fetchone()
    return row["check_value"] if row is not None else None


def _has_suppressions(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM suppressions LIMIT 1").fetchone() is not None


def _load_key(conn: sqlite3.Connection) -> tuple[bytes, str]:
    """(key, human-readable source). Precedence: env var, then key file.
    Generates a key ONLY for a database that has never had one."""
    env = os.environ.get(KEY_ENV)
    if env:
        return env.encode("utf-8"), f"the {KEY_ENV} environment variable"
    kp = _key_file(conn)
    if kp is None:
        global _MEM_KEY
        if _MEM_KEY is None:
            _MEM_KEY = secrets.token_bytes(32)
        return _MEM_KEY, "the in-memory test key"
    if not os.path.exists(kp):
        if _stored_check(conn) is not None or _has_suppressions(conn):
            raise SuppressionKeyError(
                "suppression key missing: this database already holds a"
                " suppression key check and/or retained do-not-message"
                f" records, but neither {KEY_ENV} nor the key file {kp}"
                " is present. Refusing to generate a new key (that would"
                " silently stop honouring retained opt-outs). Restore the"
                f" key from its backup — see {_DOC}.")
        try:
            fd = os.open(kp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(secrets.token_hex(32).encode())
        except FileExistsError:
            pass
    with open(kp, "rb") as f:
        key = f.read().strip()
    if not key:
        raise SuppressionKeyError(f"suppression key file {kp} is empty — restore"
                                  f" it from its backup (see {_DOC})")
    return key, f"the key file {kp}"


def _suppression_key(conn: sqlite3.Connection) -> bytes:
    key, source = _load_key(conn)
    check = _key_check_value(key)
    stored = _stored_check(conn)
    if stored is None:
        # First use for this database: record the check value. (A database
        # written by 008c — never deployed — adopts the key present now.)
        # Inside a caller's transaction (e.g. deletion) the row commits or
        # rolls back with it; otherwise it is committed now.
        caller_txn = conn.in_transaction
        conn.execute("INSERT OR IGNORE INTO suppression_key_check (id,"
                     " check_value, created_at) VALUES (1, ?, ?)",
                     (check, now_utc()))
        if not caller_txn:
            conn.commit()
        stored = _stored_check(conn)
    if not hmac.compare_digest(stored, check):
        raise SuppressionKeyError(
            f"suppression key mismatch: the key from {source} does not match"
            " the key check stored in this database. Retained do-not-message"
            " records cannot be verified, so sending is refused. Restore the"
            f" matching key from its backup — see {_DOC}.")
    return key


def verify_suppression_key(conn: sqlite3.Connection) -> dict:
    """Startup / status check. Raises SuppressionKeyError on a missing or
    wrong key for a database that already uses one. Never returns the key
    or the check value."""
    if _stored_check(conn) is None and not _has_suppressions(conn):
        return {"state": "not_initialized", "suppressions": 0}
    _suppression_key(conn)
    env = bool(os.environ.get(KEY_ENV))
    return {"state": "verified",
            "source": "env" if env else ("file" if _key_file(conn) else "memory"),
            "suppressions": conn.execute(
                "SELECT COUNT(*) FROM suppressions").fetchone()[0]}


def contact_hmac(conn: sqlite3.Connection, kind: str, value: str | None) -> str | None:
    norm = (customers_svc.normalize_phone(value) if kind == "phone"
            else customers_svc.normalize_email(value))
    if not norm:
        return None
    return hmac.new(_suppression_key(conn), f"{kind}:{norm}".encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _channel_contact(conn, cust, channel: str) -> tuple[str, str | None]:
    kind = "email" if channel == "email" else "phone"
    return kind, contact_hmac(conn, kind, cust[kind])


def _all_contacts(conn, cust) -> list[tuple[str, str]]:
    out = []
    for kind in ("phone", "email"):
        h = contact_hmac(conn, kind, cust[kind])
        if h:
            out.append((kind, h))
    return out


def is_suppressed(conn: sqlite3.Connection, cust, channel: str, scope: str) -> bool:
    if scope == "channel":
        _, h = _channel_contact(conn, cust, channel)
        hs = [h] if h else []
        ch = channel
    else:
        hs = [h for _, h in _all_contacts(conn, cust)]
        ch = "all"
    if not hs:
        return False
    q = ",".join("?" * len(hs))
    return conn.execute(
        f"SELECT 1 FROM suppressions WHERE scope = ? AND channel = ?"
        f" AND contact_hmac IN ({q}) LIMIT 1", (scope, ch, *hs)).fetchone() is not None


def retain_suppressions(conn: sqlite3.Connection, customer_id: int) -> int:
    """Called INSIDE the deletion transaction (no commit): copy the
    customer's active opt-outs into the suppression list. Returns rows
    written."""
    cust = conn.execute("SELECT * FROM customers WHERE id = ?",
                        (customer_id,)).fetchone()
    if cust is None:
        return 0
    ts, n = now_utc(), 0
    rows = []
    for ev in conn.execute("SELECT DISTINCT channel FROM channel_opt_outs"
                           " WHERE customer_id = ? AND revoked_at IS NULL",
                           (customer_id,)):
        kind, h = _channel_contact(conn, cust, ev["channel"])
        if h:
            rows.append((h, kind, ev["channel"], "channel"))
    if cust["marketing_opt_out_at"]:
        rows += [(h, kind, "all", "marketing") for kind, h in _all_contacts(conn, cust)]
    for r in rows:
        cur = conn.execute(
            "INSERT OR IGNORE INTO suppressions (contact_hmac, contact_type,"
            " channel, scope, suppressed_at) VALUES (?, ?, ?, ?, ?)", (*r, ts))
        n += cur.rowcount
    return n


def clear_suppressions(conn: sqlite3.Connection, customer_id: int,
                       scope: str, channel: str | None, actor: str,
                       role: str) -> int:
    """Re-opt-in clears the matching suppression rows (deleted — a cleared
    row is not kept). Audited with ids/channel/scope only, never the
    identifier."""
    cust = conn.execute("SELECT * FROM customers WHERE id = ?",
                        (customer_id,)).fetchone()
    if cust is None:
        return 0
    if scope == "channel":
        _, h = _channel_contact(conn, cust, channel)
        hs, ch = ([h] if h else []), channel
    else:
        hs, ch = [h for _, h in _all_contacts(conn, cust)], "all"
    if not hs:
        return 0
    q = ",".join("?" * len(hs))
    ids = [r["id"] for r in conn.execute(
        f"SELECT id FROM suppressions WHERE scope = ? AND channel = ?"
        f" AND contact_hmac IN ({q})", (scope, ch, *hs))]
    if not ids:
        return 0
    conn.execute(f"DELETE FROM suppressions WHERE id IN ({','.join('?' * len(ids))})", ids)
    conn.commit()
    audit(conn, actor, role, "suppression_cleared", "customers", customer_id,
          {"suppression_ids": ids, "scope": scope, "channel": ch,
           "via": "re-opt-in"})
    return len(ids)


def list_suppressions(conn: sqlite3.Connection) -> list[dict]:
    """Owner-only view. The identifier itself is never returned."""
    return [dict(r) for r in conn.execute(
        "SELECT id, contact_type, channel, scope, suppressed_at"
        " FROM suppressions ORDER BY id")]


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
    # Batch 008c: retained do-not-message list (survives deletion; matches
    # a re-created customer by protected contact).
    if purpose != OPT_OUT_CONFIRMATION and is_suppressed(conn, cust, channel, "channel"):
        return (f"contact is on the do-not-message list for {channel.upper()}"
                " (a retained opt-out)", None)
    if purpose == MARKETING and is_suppressed(conn, cust, channel, "marketing"):
        return ("contact is on the do-not-message list for marketing"
                " (a retained opt-out)", None)
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
        # Batch 008c: the keyword list is an initial SCREEN. A human may
        # release a false positive (audited); the release is bound to the
        # exact content, so any later change is screened again.
        if hits and msg.get("promo_override_hash") != content_hash(msg):
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
