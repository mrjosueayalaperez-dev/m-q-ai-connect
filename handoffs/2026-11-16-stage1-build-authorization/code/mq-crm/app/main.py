"""M&Q CRM — HTTP API (FastAPI).

Role-based access is enforced server-side: reads allow any role; mutations
require owner or staff; deletion requires owner. Consequential actions
(payment, send, import, deletion) write to the audit log. This is a Stage 1
local/service deployment — authentication is a deployment concern layered
in front of the role header, stated plainly rather than faked.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db as dbmod
from .services import (ai_assist, billing, bookings, comeback, customers,
                       data_rights, messages, reports, reviews)

DB_PATH = os.environ.get("MQ_CRM_DB", os.path.join(os.path.dirname(__file__), "..", "data", "crm.db"))
os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
conn = dbmod.connect(DB_PATH)

app = FastAPI(title="M&Q CRM", version="0.1.0-stage1")

WRITE_ROLES = {"owner", "staff"}


def require_write(role: str) -> None:
    if role not in WRITE_ROLES:
        raise HTTPException(403, "role may not modify data")


def require_owner(role: str) -> None:
    if role != "owner":
        raise HTTPException(403, "owner role required")


class CustomerIn(BaseModel):
    name: str
    phone: str | None = None
    email: str | None = None
    language: str = "en"
    timezone: str = "America/New_York"
    currency: str = "USD"
    consent_marketing: bool = False
    consent_source: str | None = None


class BookingIn(BaseModel):
    customer_id: int
    title: str
    local_start: str
    tz: str = "America/New_York"


class QuoteItemIn(BaseModel):
    description: str
    qty: int = 1
    unit_amount_minor: int


class PaymentIn(BaseModel):
    amount_minor: int
    method: str = "card"


class TemplateMessageIn(BaseModel):
    customer_id: int
    template_key: str
    context: dict = {}


@app.get("/api/health")
def health():
    return {"ok": True, "product": "M&Q CRM", "stage": "1"}


@app.get("/api/customers")
def list_customers():
    return customers.list_customers(conn)


@app.post("/api/customers")
def create_customer(body: CustomerIn, x_role: str = Header("owner"),
                    x_actor: str = Header("operator")):
    require_write(x_role)
    cust, merged = customers.create_customer(conn, **body.model_dump())
    return {"customer": cust, "merged_duplicate": merged}


@app.post("/api/bookings")
def create_booking(body: BookingIn, x_role: str = Header("owner")):
    require_write(x_role)
    return bookings.create_booking(conn, body.customer_id, body.title,
                                   body.local_start, body.tz)


@app.get("/api/reminders")
def reminders():
    return bookings.due_reminders(conn)


@app.post("/api/quotes")
def create_quote(customer_id: int, currency: str = "USD", x_role: str = Header("owner")):
    require_write(x_role)
    return billing.create_quote(conn, customer_id, currency)


@app.post("/api/quotes/{quote_id}/items")
def add_item(quote_id: int, body: QuoteItemIn, x_role: str = Header("owner")):
    require_write(x_role)
    billing.add_quote_item(conn, quote_id, body.description, body.qty,
                           body.unit_amount_minor)
    return {"quote_id": quote_id, "total_minor": billing.quote_total(conn, quote_id)}


@app.post("/api/quotes/{quote_id}/status")
def quote_status(quote_id: int, status: str, x_role: str = Header("owner")):
    require_write(x_role)
    return billing.set_quote_status(conn, quote_id, status)


@app.post("/api/quotes/{quote_id}/invoice")
def quote_invoice(quote_id: int, x_role: str = Header("owner")):
    require_write(x_role)
    return billing.convert_to_invoice(conn, quote_id)


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: int):
    inv = billing.get_invoice(conn, invoice_id)
    if inv is None:
        raise HTTPException(404, "invoice not found")
    return inv


@app.post("/api/invoices/{invoice_id}/payments")
def pay(invoice_id: int, body: PaymentIn, x_role: str = Header("owner"),
        x_actor: str = Header("operator")):
    require_write(x_role)
    inv = billing.record_payment(conn, invoice_id, body.amount_minor, body.method)
    dbmod.audit(conn, x_actor, x_role, "record_payment", "invoices", invoice_id,
                {"amount_minor": body.amount_minor})
    return inv


@app.get("/api/comeback/lapsed")
def lapsed(inactive_days: int = 90):
    return comeback.lapsed_customers(conn, inactive_days)


@app.post("/api/comeback/import")
async def import_backlog(request: Request, x_role: str = Header("owner"),
                         x_actor: str = Header("operator")):
    require_write(x_role)
    csv_text = (await request.body()).decode("utf-8")
    try:
        report = comeback.import_backlog(conn, csv_text)
    except ValueError as e:
        raise HTTPException(400, str(e))
    dbmod.audit(conn, x_actor, x_role, "import_backlog", "customers", None, report)
    return report


@app.post("/api/messages/template")
def compose_template(body: TemplateMessageIn, x_role: str = Header("owner")):
    require_write(x_role)
    try:
        return messages.compose_template(conn, body.customer_id, body.template_key,
                                         **body.context)
    except PermissionError as e:
        raise HTTPException(403, str(e))


@app.post("/api/messages/{message_id}/approve")
def approve_message(message_id: int, x_role: str = Header("owner")):
    require_write(x_role)
    return messages.approve(conn, message_id)


@app.post("/api/messages/{message_id}/send")
def send_message(message_id: int, x_role: str = Header("owner"),
                 x_actor: str = Header("operator")):
    require_write(x_role)
    try:
        msg = messages.send(conn, message_id)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    dbmod.audit(conn, x_actor, x_role, "send_message", "messages", message_id)
    return msg


@app.post("/api/ai/draft-comeback")
def ai_draft_comeback(customer_id: int, x_role: str = Header("owner")):
    require_write(x_role)
    try:
        return ai_assist.draft_comeback(conn, customer_id)
    except PermissionError as e:
        raise HTTPException(403, str(e))


@app.get("/api/reports/summary")
def summary():
    return reports.summary(conn)


@app.get("/api/export")
def export_all(x_role: str = Header("owner")):
    require_owner(x_role)
    return JSONResponse(data_rights.export_all(conn))


@app.delete("/api/customers/{customer_id}")
def delete_customer(customer_id: int, x_role: str = Header("owner"),
                    x_actor: str = Header("operator")):
    require_owner(x_role)
    return data_rights.delete_customer(conn, customer_id, x_actor, x_role)


WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")
if os.path.isdir(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
