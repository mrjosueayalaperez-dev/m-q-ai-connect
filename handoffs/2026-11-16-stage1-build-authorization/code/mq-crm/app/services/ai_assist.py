"""AI Assistance — drafts only, human always decides.

Stage 1 honesty: these drafts are generated from the authored bilingual
templates on-device. NO customer data is sent to any external AI provider:
the standing privacy rule requires a provider's data-processing terms to be
reviewed (and opt-outs configured) before any customer message routes
through it, and that review has not happened for any provider. Until it
does, 'AI assistance' here means structured drafting help with a human
approval gate — enforced by services/messages.py, which refuses to send
anything that is not 'approved'.
"""
from __future__ import annotations

import sqlite3

from ..i18n import format_money
from . import messages as messages_svc


def draft_comeback(conn: sqlite3.Connection, customer_id: int) -> dict:
    return messages_svc.compose_template(
        conn, customer_id, "comeback", created_by="ai_draft")


def draft_reminder(conn: sqlite3.Connection, customer_id: int, when: str,
                   title: str) -> dict:
    return messages_svc.compose_template(
        conn, customer_id, "reminder", created_by="ai_draft", when=when, title=title)


def draft_invoice_notice(conn: sqlite3.Connection, customer_id: int,
                         total_minor: int, currency: str = "USD") -> dict:
    return messages_svc.compose_template(
        conn, customer_id, "invoice_ready", created_by="ai_draft",
        total=format_money(total_minor, currency))
