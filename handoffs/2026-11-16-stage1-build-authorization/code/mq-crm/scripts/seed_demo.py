"""Seed a demo database with SYNTHETIC data only.

Every record is fictional and marked SYNTHETIC in its name. Use this to
click through the UI or demo the system — never point it at a real
workspace database. Usage: MQ_CRM_DB=/tmp/demo.db python -m scripts.seed_demo
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db import connect  # noqa: E402
from app.services import (billing, bookings, comeback, customers,  # noqa: E402
                          messages, reviews)

BACKLOG = """name,phone,email,language,last_service_date
Vecino Demo (SYNTHETIC),321-555-9001,vecino-demo@example.invalid,es,2025-02-10
Old Timer Demo (SYNTHETIC),321-555-9002,oldtimer-demo@example.invalid,en,2024-11-01
"""


def seed(path: str) -> dict:
    conn = connect(path)
    maria, _ = customers.create_customer(
        conn, "Maria Demo (SYNTHETIC)", phone="321-555-9010",
        email="maria-demo@example.invalid", language="es",
        consent_marketing=True, consent_source="demo seed")
    john, _ = customers.create_customer(
        conn, "John Demo (SYNTHETIC)", phone="321-555-9011",
        email="john-demo@example.invalid", language="en",
        consent_marketing=True, consent_source="demo seed",
        last_service_at="2025-05-01T00:00:00Z")
    bookings.create_booking(conn, maria["id"], "Demo appointment (SYNTHETIC)",
                            "2026-12-01 09:00", "America/New_York")
    q = billing.create_quote(conn, john["id"], "USD")
    billing.add_quote_item(conn, q["id"], "Demo service (SYNTHETIC)", 1, 9900)
    billing.set_quote_status(conn, q["id"], "sent")
    billing.set_quote_status(conn, q["id"], "accepted")
    inv = billing.convert_to_invoice(conn, q["id"])
    billing.record_payment(conn, inv["id"], 9900)
    draft = messages.compose_template(conn, maria["id"], "comeback")
    report = comeback.import_backlog(conn, BACKLOG)
    reviews.request_review(conn, john["id"])
    out = {"customers": len(customers.list_customers(conn)),
           "invoice_status": billing.get_invoice(conn, inv["id"])["status"],
           "draft_status": draft["status"], "import_report": report}
    conn.close()
    return out


if __name__ == "__main__":
    db_path = os.environ.get("MQ_CRM_DB", "/tmp/mq-crm-demo.db")
    print(seed(db_path))
