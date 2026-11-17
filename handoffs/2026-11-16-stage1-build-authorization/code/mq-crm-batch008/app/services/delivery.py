"""Delivery layer (Batch 005): a sent message is dispatched to a channel
through a pluggable transport, and every dispatch leaves a delivery record.

Honesty rules, enforced in the record itself:
- A delivery record states the TRANSPORT it went through. 'Delivered'
  means delivered TO THAT TRANSPORT — with the built-in outbox transport
  it means the local outbox, and the record says plainly that no external
  channel is connected and the customer has not received anything on
  their device. A status never claims more than the transport proves.
- The exact text dispatched is snapshotted onto the delivery record, so
  what left the building is verifiable against the approved message.

Privacy rule (standing): no customer message passes through an EXTERNAL
provider before that provider's data-processing terms are reviewed. The
webhook transport therefore refuses to run unless the processing register
holds a row for the provider with terms_reviewed = 1. The outbox
transport never leaves this machine and needs no such row.
"""
from __future__ import annotations

import json
import os
import sqlite3
import urllib.request

from ..db import now_utc, row_to_dict
from ..gate_lock import GATE_LOCK
from . import customers as customers_svc
from . import messages as messages_svc
from . import register as register_svc

OUTBOX_DETAIL = ("Delivered to the local outbox. No external channel is"
                 " connected; the customer has NOT received this message"
                 " on their device.")


def active_transport() -> str:
    return os.environ.get("MQ_CRM_TRANSPORT", "outbox")


def _latest(conn: sqlite3.Connection, message_id: int) -> dict | None:
    return row_to_dict(conn.execute(
        "SELECT * FROM deliveries WHERE message_id = ? ORDER BY id DESC"
        " LIMIT 1", (message_id,)).fetchone())


CLAIM_STALE_SECONDS = 300  # a 'sending' claim older than this may be retried


class DispatchInProgress(ValueError):
    """Another dispatch of the same message holds the claim right now."""


def _configured_webhook_url() -> str | None:
    return os.environ.get("MQ_CRM_WEBHOOK_URL")


def _safe_host(url: str | None) -> str:
    n = register_svc.normalize_endpoint(url)
    return n[1] if n else "(unparseable)"


def _require_terms_reviewed(conn: sqlite3.Connection, url: str | None) -> dict:
    """Batch 008: the gate matches the ACTUAL endpoint, not a provider name.
    A register row authorizes this dispatch only when it is for 'messages',
    its terms are reviewed WITH a terms_reference, and its endpoint matches
    the configured URL's scheme/host/port (and path prefix, if the row has
    one). The refusal names the host only — never the full URL, which may
    carry credentials."""
    rows = conn.execute(
        "SELECT * FROM processing_register WHERE terms_reviewed = 1"
        " AND data_kind = 'messages'").fetchall()
    for row in rows:
        row = dict(row)
        if (row.get("terms_reference") or "").strip() and \
                register_svc.endpoint_matches(row.get("endpoint"), url):
            return row
    raise PermissionError(
        f"dispatch refused: endpoint host '{_safe_host(url)}' has no processing-"
        "register entry with terms reviewed — the privacy rule requires"
        " terms review before any customer message leaves through an"
        " external provider")


def _webhook_dispatch(conn: sqlite3.Connection, msg: dict, text: str,
                      url: str) -> tuple[str, str]:
    """POST the message JSON to the configured webhook URL. Returns
    (provider_ref, detail). Raises on any failure. The caller has already
    passed the gate under the shared gate lock."""
    cust = customers_svc.get_customer(conn, msg["customer_id"]) or {}
    idem = f"mq-crm-message-{msg['id']}"
    payload = {
        "message_id": msg["id"],
        "idempotency_key": idem,
        "channel": msg["channel"],
        "to": cust.get("phone") if msg["channel"] == "sms" else cust.get("email"),
        "lang": msg["translated_lang"] or msg["original_lang"],
        "text": text,
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 # A retry after an ambiguous failure carries the same key,
                 # so a provider that honours it delivers at most once.
                 "Idempotency-Key": idem}, method="POST")
    # Proxy-free opener: a dispatch to the configured endpoint must go
    # there directly, never silently routed through environment proxies.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=5) as resp:
        body = resp.read().decode("utf-8", "replace")
        if resp.status < 200 or resp.status >= 300:
            raise ValueError(f"provider returned HTTP {resp.status}")
    ref = None
    try:
        ref = json.loads(body).get("id")
    except (ValueError, AttributeError):
        ref = None
    return (str(ref) if ref is not None else None,
            f"Delivered to the configured webhook endpoint (HTTP {resp.status}).")


def _stale_cutoff() -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(seconds=CLAIM_STALE_SECONDS)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")


def _claim(conn: sqlite3.Connection, msg: dict, transport: str,
           text: str) -> tuple[str | None, dict | None]:
    """Atomically claim the message's delivery row. Returns (token, None)
    when THIS caller owns the attempt, or (None, record) when the message
    is already delivered. Raises DispatchInProgress when another caller
    holds a live claim. The claim is one conditional UPDATE: two callers on
    two connections cannot both win it."""
    import uuid
    ts = now_utc()
    token = uuid.uuid4().hex
    if _latest(conn, msg["id"]) is None:
        conn.execute(
            "INSERT OR IGNORE INTO deliveries (message_id, channel, transport,"
            " status, text_snapshot, attempts, created_at, updated_at)"
            " VALUES (?, ?, ?, 'queued', ?, 0, ?, ?)",
            (msg["id"], msg["channel"], transport, text, ts, ts))
    cur = conn.execute(
        "UPDATE deliveries SET status = 'sending', claim_token = ?,"
        " transport = ?, text_snapshot = ?, attempts = attempts + 1,"
        " detail = NULL, updated_at = ?"
        " WHERE id = (SELECT id FROM deliveries WHERE message_id = ?"
        "             ORDER BY id DESC LIMIT 1)"
        " AND (status IN ('queued', 'failed')"
        "      OR (status = 'sending' AND updated_at < ?))",
        (token, transport, text, ts, msg["id"], _stale_cutoff()))
    conn.commit()
    if cur.rowcount == 1:
        return token, None
    existing = _latest(conn, msg["id"])
    if existing and existing["status"] == "delivered":
        return None, existing
    raise DispatchInProgress(
        "dispatch already in progress for this message — not sent twice")


def _finish(conn: sqlite3.Connection, delivery_id: int, token: str,
            status: str, detail: str, provider_ref: str | None = None) -> None:
    conn.execute(
        "UPDATE deliveries SET status = ?, provider_ref = ?, detail = ?,"
        " updated_at = ? WHERE id = ? AND claim_token = ?",
        (status, provider_ref, detail, now_utc(), delivery_id, token))
    conn.commit()


def _pre_send_hook() -> None:
    """Test seam: called after the claim, before the final gate re-check.
    No-op in production."""


def dispatch(conn: sqlite3.Connection, message_id: int,
             transport: str | None = None) -> dict:
    """Dispatch a SENT message through a transport and record the outcome.

    Idempotent (Batch 008, hardened): the delivery row is claimed with one
    atomic conditional UPDATE, so concurrent dispatches of one message
    produce exactly one transport call; a delivered message returns its
    existing record; a failed dispatch may be retried — the same record is
    reused and its attempt count grows, so the failure history is never
    hidden behind a fresh row.

    Every precondition is RE-CHECKED from the database immediately before
    the transport call, under the shared privacy-gate lock: the message is
    still 'sent', the customer still exists, consent is current for a
    marketing message (any type — template or free text), and for an
    external transport the register row bound to the endpoint is reviewed.
    """
    msg = messages_svc.get_message(conn, message_id)
    if msg is None:
        raise ValueError("message not found")
    if msg["status"] != "sent":
        raise PermissionError(
            f"dispatch refused: message is '{msg['status']}' — only a sent"
            " message can be dispatched")
    transport = transport or active_transport()
    text = msg["translated_text"] or msg["original_text"]
    token, done = _claim(conn, msg, transport, text)
    if done is not None:
        return done
    delivery_id = _latest(conn, message_id)["id"]
    _pre_send_hook()
    with GATE_LOCK.shared():
        fresh = messages_svc.get_message(conn, message_id)
        try:
            if fresh is None or fresh["status"] != "sent":
                raise PermissionError("dispatch refused: message is no longer"
                                      " in 'sent' state")
            # Purpose / consent / channel opt-out / promo check, re-read now.
            messages_svc.enforce_policy(conn, fresh, "dispatch")
            url = None
            if transport == "webhook":
                url = _configured_webhook_url()
                if not url:
                    raise ValueError("webhook transport selected but"
                                     " MQ_CRM_WEBHOOK_URL is not configured")
                _require_terms_reviewed(conn, url)
        except PermissionError as e:
            gate = "privacy gate" if "processing-register" in str(e) else "consent gate"
            if gate == "privacy gate":
                detail = "Dispatch refused by the privacy gate (terms not reviewed for this endpoint)."
            else:
                detail = f"Dispatch refused by the {gate}: {e}"
            _finish(conn, delivery_id, token, "failed", detail)
            raise
        except Exception as e:
            _finish(conn, delivery_id, token, "failed", f"{type(e).__name__}: {e}")
            return _latest(conn, message_id)
        try:
            if transport == "outbox":
                provider_ref, detail = None, OUTBOX_DETAIL
            elif transport == "webhook":
                provider_ref, detail = _webhook_dispatch(conn, fresh, text, url)
            else:
                raise ValueError(f"unknown transport '{transport}'")
        except Exception as e:  # transport failure is a recorded outcome
            # Never echo the URL: urllib errors can include it.
            msg_txt = str(e)
            if url:
                msg_txt = msg_txt.replace(url, "<configured endpoint>")
            _finish(conn, delivery_id, token, "failed",
                    f"{type(e).__name__}: {msg_txt}")
            return _latest(conn, message_id)
        _finish(conn, delivery_id, token, "delivered", detail, provider_ref)
    return _latest(conn, message_id)


def get_delivery(conn: sqlite3.Connection, message_id: int) -> dict | None:
    return _latest(conn, message_id)


def list_deliveries(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM deliveries ORDER BY id DESC")]
