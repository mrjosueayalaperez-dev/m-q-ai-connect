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
from . import customers as customers_svc
from . import messages as messages_svc

OUTBOX_DETAIL = ("Delivered to the local outbox. No external channel is"
                 " connected; the customer has NOT received this message"
                 " on their device.")


def active_transport() -> str:
    return os.environ.get("MQ_CRM_TRANSPORT", "outbox")


def _latest(conn: sqlite3.Connection, message_id: int) -> dict | None:
    return row_to_dict(conn.execute(
        "SELECT * FROM deliveries WHERE message_id = ? ORDER BY id DESC"
        " LIMIT 1", (message_id,)).fetchone())


def _require_terms_reviewed(conn: sqlite3.Connection, provider: str) -> None:
    row = conn.execute(
        "SELECT * FROM processing_register WHERE provider = ?"
        " AND terms_reviewed = 1", (provider,)).fetchone()
    if row is None:
        raise PermissionError(
            f"dispatch refused: provider '{provider}' has no processing-"
            "register entry with terms reviewed — the privacy rule requires"
            " terms review before any customer message leaves through an"
            " external provider")


def _webhook_dispatch(conn: sqlite3.Connection, msg: dict, text: str) -> tuple[str, str]:
    """POST the message JSON to the configured webhook URL. Returns
    (provider_ref, detail). Raises on any failure."""
    _require_terms_reviewed(conn, "webhook")
    url = os.environ.get("MQ_CRM_WEBHOOK_URL")
    if not url:
        raise ValueError("webhook transport selected but MQ_CRM_WEBHOOK_URL"
                         " is not configured")
    cust = customers_svc.get_customer(conn, msg["customer_id"]) or {}
    payload = {
        "message_id": msg["id"],
        "channel": msg["channel"],
        "to": cust.get("phone") if msg["channel"] == "sms" else cust.get("email"),
        "lang": msg["translated_lang"] or msg["original_lang"],
        "text": text,
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
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


def dispatch(conn: sqlite3.Connection, message_id: int,
             transport: str | None = None) -> dict:
    """Dispatch a SENT message through a transport and record the outcome.

    Idempotent for success: re-dispatching a delivered message returns the
    existing record. A failed dispatch may be retried — the same record is
    reused and its attempt count grows, so the failure history is never
    hidden behind a fresh row."""
    msg = messages_svc.get_message(conn, message_id)
    if msg is None:
        raise ValueError("message not found")
    if msg["status"] != "sent":
        raise PermissionError(
            f"dispatch refused: message is '{msg['status']}' — only a sent"
            " message can be dispatched")
    transport = transport or active_transport()
    text = msg["translated_text"] or msg["original_text"]
    existing = _latest(conn, message_id)
    if existing and existing["status"] == "delivered":
        return existing
    ts = now_utc()
    if existing is None:
        cur = conn.execute(
            "INSERT INTO deliveries (message_id, channel, transport, status,"
            " text_snapshot, attempts, created_at, updated_at)"
            " VALUES (?, ?, ?, 'queued', ?, 0, ?, ?)",
            (message_id, msg["channel"], transport, text, ts, ts))
        delivery_id = cur.lastrowid
    else:
        delivery_id = existing["id"]
        conn.execute(
            "UPDATE deliveries SET transport = ?, text_snapshot = ?,"
            " status = 'queued', updated_at = ? WHERE id = ?",
            (transport, text, ts, delivery_id))
    conn.execute("UPDATE deliveries SET attempts = attempts + 1 WHERE id = ?",
                 (delivery_id,))
    conn.commit()
    try:
        if transport == "outbox":
            provider_ref, detail = None, OUTBOX_DETAIL
        elif transport == "webhook":
            provider_ref, detail = _webhook_dispatch(conn, msg, text)
        else:
            raise ValueError(f"unknown transport '{transport}'")
    except PermissionError:
        conn.execute(
            "UPDATE deliveries SET status = 'failed', detail = ?,"
            " updated_at = ? WHERE id = ?",
            ("Dispatch refused by the privacy gate (terms not reviewed).",
             now_utc(), delivery_id))
        conn.commit()
        raise
    except Exception as e:  # transport failure is a recorded outcome
        conn.execute(
            "UPDATE deliveries SET status = 'failed', detail = ?,"
            " updated_at = ? WHERE id = ?",
            (f"{type(e).__name__}: {e}", now_utc(), delivery_id))
        conn.commit()
        return _latest(conn, message_id)
    conn.execute(
        "UPDATE deliveries SET status = 'delivered', provider_ref = ?,"
        " detail = ?, updated_at = ? WHERE id = ?",
        (provider_ref, detail, now_utc(), delivery_id))
    conn.commit()
    return _latest(conn, message_id)


def get_delivery(conn: sqlite3.Connection, message_id: int) -> dict | None:
    return _latest(conn, message_id)


def list_deliveries(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM deliveries ORDER BY id DESC")]
