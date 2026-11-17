"""M&Q CRM — HTTP API (FastAPI).

Role-based access is enforced server-side: reads allow any role; mutations
require owner or staff; deletion requires owner. Consequential actions
(payment, send, import, deletion) write to the audit log.

Batch 009 — REAL LOGIN: the role and the audit actor come ONLY from an
authenticated user account (server-side session via an HttpOnly cookie, or
a bearer token). _AuthMiddleware strips any client-supplied X-Role / X-Actor
header before routing, resolves the session, and only then sets the
internal role / actor values the route handlers read. There is no test mode
and no header fallback. See app/auth.py and docs/REAL-LOGIN.md.

Batch 008 — DENY BY DEFAULT: every /api route except /api/health requires
an explicit, valid X-Role (owner | staff | viewer); a missing or unknown
role is 401, never a silent 'owner'. Every write additionally requires a
non-empty X-Actor, so the audit trail names a person. Each request runs on
its OWN SQLite connection, rolled back if left open and closed at the end;
no connection is shared across threads.
"""
from __future__ import annotations

import contextvars
import logging
import os
import threading
from http.cookies import CookieError, SimpleCookie

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth
from . import db as dbmod
from .services import (ai_assist, billing, bookings, comeback, customers,
                       data_rights, delivery, messages, policy, register,
                       reports, reviews)

DB_PATH = os.environ.get("MQ_CRM_DB", os.path.join(os.path.dirname(__file__), "..", "data", "crm.db"))
if DB_PATH == ":memory:":
    # Per-request connections need one shared database, not one per conn.
    DB_PATH = "file:mq_crm_memory?mode=memory&cache=shared"
else:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
_schema_conn = dbmod.connect(DB_PATH)  # creates/migrates the schema once
# Batch 008d: refuse to START with a missing or wrong suppression key for a
# database that already uses one (raises SuppressionKeyError; the message
# names the source and the procedure, never the key).
policy.verify_suppression_key(_schema_conn)
# Batch 009: user accounts + sessions.
auth.ensure_schema(_schema_conn)
_log = logging.getLogger("mq_crm.main")
if not auth.owner_exists(_schema_conn):
    _log.warning("no owner account exists — every API request is denied until"
                 " the first owner is created on the server with:"
                 " python -m app.auth_cli create-owner --username <name>")

_request_conn: contextvars.ContextVar = contextvars.ContextVar(
    "mq_crm_request_conn", default=None)
_thread_conns = threading.local()


def _current_conn():
    c = _request_conn.get()
    if c is not None:
        return c
    c = getattr(_thread_conns, "conn", None)
    if c is None:
        c = dbmod.open_connection(DB_PATH)
        _thread_conns.conn = c
    return c


class _ConnProxy:
    """Module-level `conn` kept for callers (tests, probes, scripts), but it
    is NOT one shared connection: inside a request it resolves to that
    request's connection; elsewhere to a connection owned by the calling
    thread."""

    def __getattr__(self, name):
        return getattr(_current_conn(), name)

    def __enter__(self):
        return _current_conn().__enter__()

    def __exit__(self, *exc):
        return _current_conn().__exit__(*exc)


conn = _ConnProxy()

app = FastAPI(title="M&Q CRM", version="0.1.0-stage1")


class _PerRequestConnection:
    """ASGI middleware: one connection per /api request. Anything a handler
    left uncommitted is ROLLED BACK at the end — it can never be committed
    later by an unrelated write (the Batch 005 deletion defect)."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api"):
            return await self.inner(scope, receive, send)
        c = dbmod.open_connection(DB_PATH)
        token = _request_conn.set(c)
        try:
            await self.inner(scope, receive, send)
        finally:
            _request_conn.reset(token)
            try:
                if c.in_transaction:
                    c.rollback()
            finally:
                c.close()


ROLES = {"owner", "staff", "viewer"}
WRITE_ROLES = {"owner", "staff"}
# No session needed: liveness (returns no data) and the login form itself.
OPEN_PATHS = {"/api/health", "/api/auth/login"}
SESSION_COOKIE = "mq_session"
CSRF_HEADER = "x-csrf-token"
_IDENTITY_HEADERS = {b"x-role", b"x-actor"}  # internal-only; never from clients
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _hdr(headers, name: bytes) -> str | None:
    for k, v in headers:
        if k.lower() == name:
            return v.decode("latin-1")
    return None


def _presented_token(headers) -> tuple[str | None, str | None]:
    """(token, kind) from `Authorization: Bearer` or the session cookie."""
    authz = _hdr(headers, b"authorization")
    if authz:
        scheme, _, value = authz.partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            return value.strip(), "bearer"
        return None, None
    cookie = _hdr(headers, b"cookie")
    if cookie:
        try:
            jar = SimpleCookie()
            jar.load(cookie)
        except CookieError:
            return None, None
        if SESSION_COOKIE in jar:
            return jar[SESSION_COOKIE].value, "cookie"
    return None, None


async def _deny(scope, receive, send, status: int, detail: str,
                retry_after: int | None = None):
    headers = {}
    if status == 401:
        headers["WWW-Authenticate"] = 'Bearer realm="mq-crm"'
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    await JSONResponse({"detail": detail}, status_code=status,
                       headers=headers)(scope, receive, send)


class _AuthMiddleware:
    """Batch 009: authenticate every /api request from a server-side session.

    1. ALWAYS strip client-supplied X-Role / X-Actor (any case) — a client
       cannot assert a role or an audit identity.
    2. Resolve the session from `Authorization: Bearer <token>` or the
       HttpOnly session cookie; a token of the wrong kind is refused.
    3. Cookie sessions: every state-changing request must carry the
       session's CSRF token in X-CSRF-Token, and a cross-site Origin is
       refused. Bearer tokens are not sent automatically by browsers, so
       they are not CSRF-able.
    4. Only then set the internal role / actor values from the user record.
    No session -> 401 (deny by default); OPEN_PATHS excepted."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api"):
            return await self.inner(scope, receive, send)
        raw = list(scope.get("headers") or [])
        headers = [(k, v) for k, v in raw if k.lower() not in _IDENTITY_HEADERS]
        scope = dict(scope)
        scope["headers"] = headers
        scope["state"] = dict(scope.get("state") or {})
        token, kind = _presented_token(headers)
        ident = None
        if token:
            c = _current_conn()
            ident = auth.resolve_session(c, token)
            if ident is not None and ident[1]["kind"] != kind:
                ident = None  # a cookie session used as bearer, or vice versa
        if ident is None:
            if scope["path"] in OPEN_PATHS:
                return await self.inner(scope, receive, send)
            return await _deny(scope, receive, send, 401,
                               "login required — sign in to get a session")
        user, session = ident
        method = scope.get("method", "GET").upper()
        if session["kind"] == "cookie" and method not in _SAFE_METHODS:
            origin = _hdr(headers, b"origin")
            host = _hdr(headers, b"host")
            if origin and host and origin.split("://", 1)[-1] != host:
                return await _deny(scope, receive, send, 403,
                                   "cross-site request refused")
            if not auth.csrf_ok(session, _hdr(headers, CSRF_HEADER.encode())):
                return await _deny(scope, receive, send, 403,
                                   "CSRF token missing or invalid")
        headers.append((b"x-role", user["role"].encode()))
        headers.append((b"x-actor", user["username"].encode()))
        scope["state"]["user"] = user
        scope["state"]["session"] = session
        await self.inner(scope, receive, send)


# Order matters: middleware added LATER wraps the earlier one, so the
# per-request connection is opened first and the auth check runs on it.
app.add_middleware(_AuthMiddleware)
app.add_middleware(_PerRequestConnection)


def _auth_guard(request: Request, x_role: str | None = Header(None),
                x_actor: str | None = Header(None)) -> None:
    """Global dependency on every route: fail-closed role check."""
    if request.url.path in OPEN_PATHS:
        return
    # x_role / x_actor here were set by _AuthMiddleware from the logged-in
    # user (client copies are stripped). Defence in depth: still fail closed.
    if getattr(request.state, "user", None) is None or x_role not in ROLES:
        raise HTTPException(401, "login required")
    if request.method not in ("GET", "HEAD", "OPTIONS") and \
            not (x_actor or "").strip():
        raise HTTPException(401, "login required — the audit trail must name"
                                 " who acted")


app.router.dependencies.append(Depends(_auth_guard))


def require_read(role: str | None) -> None:
    if role not in ROLES:
        raise HTTPException(401, "login required")


def require_write(role: str | None) -> None:
    require_read(role)
    if role not in WRITE_ROLES:
        raise HTTPException(403, "role may not modify data")


def require_owner(role: str | None) -> None:
    require_read(role)
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
    region: str | None = None
    data_residency: str = "US"


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


# ------------------------------------------------------------------ Batch 009
# Login, logout, session, password, and owner-only user management.

class LoginIn(BaseModel):
    username: str
    password: str
    mode: str = "cookie"   # "cookie" (web UI) | "token" (Android / API)


def _client_ip(request: Request) -> str:
    # The direct peer. A reverse proxy's X-Forwarded-For is NOT trusted
    # here; a hosted deployment must configure that explicitly.
    return request.client.host if request.client else "unknown"


def _login_response(user: dict, sess: dict, mode: str) -> JSONResponse:
    body = {"user": {k: user[k] for k in ("username", "display_name", "role")},
            "idle_minutes": sess["idle_minutes"],
            "absolute_expires_at": sess["absolute_expires_at"]}
    if mode == "token":
        body["token"] = sess["token"]
        body["token_type"] = "bearer"
        resp = JSONResponse(body)
    else:
        body["csrf_token"] = sess["csrf_token"]
        resp = JSONResponse(body)
        resp.set_cookie(SESSION_COOKIE, sess["token"], httponly=True,
                        secure=True, samesite="strict", path="/api",
                        max_age=auth.ABSOLUTE_HOURS * 3600)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request):
    if body.mode not in ("cookie", "token"):
        raise HTTPException(400, "mode must be cookie or token")
    try:
        user = auth.authenticate(conn, body.username, body.password,
                                 _client_ip(request))
    except auth.AuthError as e:
        headers = {"Retry-After": str(e.retry_after)} if e.retry_after else None
        raise HTTPException(e.status, e.detail, headers=headers)
    sess = auth.create_session(conn, user, "bearer" if body.mode == "token"
                               else "cookie")
    return _login_response(user, sess, body.mode)


@app.post("/api/auth/logout")
def logout(request: Request):
    user, session = request.state.user, request.state.session
    auth.logout(conn, user, session)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/api", secure=True,
                       httponly=True, samesite="strict")
    return resp


@app.get("/api/auth/me")
def me(request: Request, response: Response):
    user, session = request.state.user, request.state.session
    response.headers["Cache-Control"] = "no-store"
    out = {"user": {k: user[k] for k in ("username", "display_name", "role")},
           "session": {"kind": session["kind"],
                       "absolute_expires_at": session["absolute_expires_at"],
                       "idle_minutes": auth.IDLE_MINUTES}}
    if session["kind"] == "cookie":
        # Same-origin JS needs this to send X-CSRF-Token after a reload; a
        # cross-site page cannot read it (no CORS is configured).
        out["csrf_token"] = session["csrf_token"]
    return out


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/auth/password")
def change_password(body: PasswordChangeIn, request: Request):
    user, session = request.state.user, request.state.session
    try:
        auth.change_own_password(conn, user["id"], body.current_password,
                                 body.new_password, session["token_hash"])
    except auth.AuthError as e:
        raise HTTPException(e.status, e.detail)
    except auth.PasswordPolicyError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "other_sessions": "signed out"}


class UserIn(BaseModel):
    username: str
    password: str
    role: str
    display_name: str | None = None


class RoleIn(BaseModel):
    role: str


class ResetIn(BaseModel):
    new_password: str


def _user_admin(fn):
    try:
        return fn()
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:  # includes PasswordPolicyError
        raise HTTPException(400, str(e))


@app.get("/api/users")
def users_list(x_role: str | None = Header(None)):
    require_owner(x_role)
    return auth.list_users(conn)


@app.post("/api/users")
def users_create(body: UserIn, x_role: str | None = Header(None),
                 x_actor: str | None = Header(None)):
    require_owner(x_role)
    return _user_admin(lambda: auth.create_user(
        conn, body.username, body.password, body.role, body.display_name,
        x_actor, x_role))


@app.post("/api/users/{user_id}/role")
def users_role(user_id: int, body: RoleIn, x_role: str | None = Header(None),
               x_actor: str | None = Header(None)):
    require_owner(x_role)
    return _user_admin(lambda: auth.set_role(conn, user_id, body.role,
                                             x_actor, x_role))


@app.post("/api/users/{user_id}/disable")
def users_disable(user_id: int, x_role: str | None = Header(None),
                  x_actor: str | None = Header(None)):
    require_owner(x_role)
    return _user_admin(lambda: auth.set_disabled(conn, user_id, True,
                                                 x_actor, x_role))


@app.post("/api/users/{user_id}/enable")
def users_enable(user_id: int, x_role: str | None = Header(None),
                 x_actor: str | None = Header(None)):
    require_owner(x_role)
    return _user_admin(lambda: auth.set_disabled(conn, user_id, False,
                                                 x_actor, x_role))


@app.post("/api/users/{user_id}/password")
def users_reset_password(user_id: int, body: ResetIn,
                         x_role: str | None = Header(None),
                         x_actor: str | None = Header(None)):
    require_owner(x_role)
    _user_admin(lambda: auth.reset_password(conn, user_id, body.new_password,
                                            x_actor, x_role))
    return {"ok": True, "sessions": "signed out"}


@app.get("/api/customers")
def list_customers(x_role: str | None = Header(None)):
    require_read(x_role)
    return customers.list_customers(conn)


@app.post("/api/customers")
def create_customer(body: CustomerIn, x_role: str | None = Header(None),
                    x_actor: str | None = Header(None)):
    require_write(x_role)
    cust, merged = customers.create_customer(conn, **body.model_dump())
    return {"customer": cust, "merged_duplicate": merged}


class ConsentIn(BaseModel):
    granted: bool
    source: str | None = None


@app.post("/api/customers/{customer_id}/consent")
def set_consent(customer_id: int, body: ConsentIn, x_role: str | None = Header(None),
                x_actor: str | None = Header(None)):
    require_write(x_role)
    cust = customers.set_consent(conn, customer_id, body.granted, body.source)
    dbmod.audit(conn, x_actor, x_role,
                "consent_granted" if body.granted else "consent_withdrawn",
                "customers", customer_id, {"source": body.source})
    if body.granted and cust is not None:
        # Batch 008c: an explicit, audited marketing re-opt-in clears a
        # retained marketing suppression for this customer's contacts.
        policy.clear_suppressions(conn, customer_id, "marketing", None,
                                  x_actor, x_role)
    return cust


@app.get("/api/customers/{customer_id}/export")
def export_customer(customer_id: int, x_role: str | None = Header(None)):
    require_owner(x_role)
    try:
        return JSONResponse(data_rights.export_customer(conn, customer_id))
    except ValueError as e:
        raise HTTPException(404, str(e))


class CustomerUpdateIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    language: str | None = None
    timezone: str | None = None
    currency: str | None = None
    region: str | None = None
    data_residency: str | None = None


@app.post("/api/customers/{customer_id}/update")
def update_customer(customer_id: int, body: CustomerUpdateIn,
                    x_role: str | None = Header(None),
                    x_actor: str | None = Header(None)):
    require_write(x_role)
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        cust = customers.update_customer(conn, customer_id, **fields)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # Audit records WHICH fields changed, never the values (personal data).
    dbmod.audit(conn, x_actor, x_role, "update_customer", "customers",
                customer_id, {"fields": sorted(fields)})
    return cust


@app.post("/api/bookings")
def create_booking(body: BookingIn, x_role: str | None = Header(None)):
    require_write(x_role)
    return bookings.create_booking(conn, body.customer_id, body.title,
                                   body.local_start, body.tz)


@app.get("/api/bookings")
def list_bookings(x_role: str | None = Header(None)):
    require_read(x_role)
    return bookings.list_bookings(conn)


@app.get("/api/reminders")
def reminders(x_role: str | None = Header(None)):
    require_read(x_role)
    return bookings.due_reminders(conn)


@app.post("/api/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int, x_role: str | None = Header(None),
                   x_actor: str | None = Header(None)):
    require_write(x_role)
    try:
        booking = bookings.cancel_booking(conn, booking_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    dbmod.audit(conn, x_actor, x_role, "cancel_booking", "bookings",
                booking_id, {})
    return booking


@app.post("/api/bookings/{booking_id}/complete")
def complete_booking(booking_id: int, x_role: str | None = Header(None),
                     x_actor: str | None = Header(None)):
    require_write(x_role)
    booking = bookings.complete_booking(conn, booking_id)
    if booking is None:
        raise HTTPException(404, "booking not found")
    dbmod.audit(conn, x_actor, x_role, "complete_booking", "bookings",
                booking_id, {})
    return booking


@app.post("/api/quotes")
def create_quote(customer_id: int, currency: str = "USD", x_role: str | None = Header(None)):
    require_write(x_role)
    return billing.create_quote(conn, customer_id, currency)


@app.post("/api/quotes/{quote_id}/items")
def add_item(quote_id: int, body: QuoteItemIn, x_role: str | None = Header(None)):
    require_write(x_role)
    billing.add_quote_item(conn, quote_id, body.description, body.qty,
                           body.unit_amount_minor)
    return {"quote_id": quote_id, "total_minor": billing.quote_total(conn, quote_id)}


@app.post("/api/quotes/{quote_id}/status")
def quote_status(quote_id: int, status: str, x_role: str | None = Header(None)):
    require_write(x_role)
    return billing.set_quote_status(conn, quote_id, status)


@app.post("/api/quotes/{quote_id}/invoice")
def quote_invoice(quote_id: int, x_role: str | None = Header(None)):
    require_write(x_role)
    return billing.convert_to_invoice(conn, quote_id)


@app.get("/api/quotes")
def list_quotes(x_role: str | None = Header(None)):
    require_read(x_role)
    return billing.list_quotes(conn)


@app.get("/api/invoices")
def list_invoices(x_role: str | None = Header(None)):
    require_read(x_role)
    return billing.list_invoices(conn)


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: int, x_role: str | None = Header(None)):
    require_read(x_role)
    inv = billing.get_invoice(conn, invoice_id)
    if inv is None:
        raise HTTPException(404, "invoice not found")
    return inv


@app.post("/api/invoices/{invoice_id}/payments")
def pay(invoice_id: int, body: PaymentIn, x_role: str | None = Header(None),
        x_actor: str | None = Header(None)):
    require_write(x_role)
    inv = billing.record_payment(conn, invoice_id, body.amount_minor, body.method)
    dbmod.audit(conn, x_actor, x_role, "record_payment", "invoices", invoice_id,
                {"amount_minor": body.amount_minor})
    return inv


@app.get("/api/comeback/lapsed")
def lapsed(inactive_days: int = 90, x_role: str | None = Header(None)):
    require_read(x_role)
    return comeback.lapsed_customers(conn, inactive_days)


@app.post("/api/comeback/import")
async def import_backlog(request: Request, x_role: str | None = Header(None),
                         x_actor: str | None = Header(None)):
    require_write(x_role)
    csv_text = (await request.body()).decode("utf-8")
    try:
        report = comeback.import_backlog(conn, csv_text)
    except ValueError as e:
        raise HTTPException(400, str(e))
    dbmod.audit(conn, x_actor, x_role, "import_backlog", "customers", None, report)
    return report


@app.post("/api/messages/template")
def compose_template(body: TemplateMessageIn, x_role: str | None = Header(None)):
    require_write(x_role)
    try:
        return messages.compose_template(conn, body.customer_id, body.template_key,
                                         **body.context)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        # Compose refuses when the real context cannot be resolved (no
        # upcoming booking, no quote, no invoice) — a client error with a
        # clear reason, never a draft carrying placeholder text.
        raise HTTPException(400, str(e))


@app.get("/api/audit/status")
def audit_status(x_role: str | None = Header(None)):
    require_read(x_role)
    return dbmod.audit_chain_status(conn)


class AuditRecoverIn(BaseModel):
    reason: str | None = None


@app.post("/api/audit/recover")
def audit_recover(body: AuditRecoverIn, x_role: str | None = Header(None),
                  x_actor: str | None = Header(None)):
    require_owner(x_role)
    try:
        return dbmod.recover_audit_chain(conn, x_actor, x_role, body.reason)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/messages/{message_id}/approve")
def approve_message(message_id: int, x_role: str | None = Header(None),
                    x_actor: str | None = Header(None)):
    require_write(x_role)
    try:
        msg = messages.approve(conn, message_id, approved_by=x_actor,
                               approved_role=x_role)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # Batch 008: approval is a consequential act — who, what (the exact
    # content hash approved), when (the audit row's timestamp).
    dbmod.audit(conn, x_actor, x_role, "approve_message", "messages",
                message_id, {"approved_hash": msg["approved_hash"],
                             "approved_at": msg["approved_at"],
                             "purpose": msg.get("purpose"),
                             "template_key": msg.get("template_key")})
    return msg


@app.post("/api/messages/{message_id}/withdraw")
def withdraw_message(message_id: int, x_role: str | None = Header(None),
                     x_actor: str | None = Header(None)):
    require_write(x_role)
    msg = messages.withdraw(conn, message_id)
    dbmod.audit(conn, x_actor, x_role, "withdraw_message", "messages", message_id)
    return msg


@app.post("/api/messages/{message_id}/send")
def send_message(message_id: int, x_role: str | None = Header(None),
                 x_actor: str | None = Header(None)):
    require_write(x_role)
    try:
        msg = messages.send(conn, message_id)
    except PermissionError as e:
        # A refused send is a consequential event: it leaves an audit
        # record, so an attempted bypass is visible after the fact.
        dbmod.audit(conn, x_actor, x_role, "send_message_denied", "messages",
                    message_id, {"reason": str(e)})
        raise HTTPException(403, str(e))
    dbmod.audit(conn, x_actor, x_role, "send_message", "messages", message_id)
    return msg


@app.get("/api/messages")
def list_messages(customer_id: int | None = None, x_role: str | None = Header(None)):
    require_read(x_role)
    return messages.list_messages(conn, customer_id)


@app.post("/api/messages/{message_id}/dispatch")
def dispatch_message(message_id: int, x_role: str | None = Header(None),
                     x_actor: str | None = Header(None)):
    require_write(x_role)
    try:
        record = delivery.dispatch(conn, message_id)
    except PermissionError as e:
        dbmod.audit(conn, x_actor, x_role, "dispatch_denied", "messages",
                    message_id, {"reason": str(e)})
        raise HTTPException(403, str(e))
    except delivery.DispatchInProgress as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    dbmod.audit(conn, x_actor, x_role,
                "message_dispatched" if record["status"] == "delivered"
                else "message_delivery_failed",
                "messages", message_id,
                {"transport": record["transport"], "status": record["status"]})
    return record


@app.get("/api/messages/{message_id}/delivery")
def get_delivery(message_id: int, x_role: str | None = Header(None)):
    require_read(x_role)
    return {"delivery": delivery.get_delivery(conn, message_id)}


@app.get("/api/deliveries")
def list_deliveries(x_role: str | None = Header(None)):
    require_read(x_role)
    return delivery.list_deliveries(conn)


class InboundIn(BaseModel):
    customer_id: int
    text: str
    lang: str = "en"


@app.post("/api/messages/inbound")
def record_inbound(body: InboundIn, x_role: str | None = Header(None),
                   x_actor: str | None = Header(None)):
    require_write(x_role)
    try:
        msg = messages.record_inbound(conn, body.customer_id, body.text,
                                      body.lang)
    except ValueError as e:
        raise HTTPException(404, str(e))
    dbmod.audit(conn, x_actor, x_role, "record_inbound", "messages",
                msg["id"], {"customer_id": body.customer_id})
    # Batch 008b: an inbound SMS that is exactly a standard stop keyword
    # (STOP, UNSUBSCRIBE, ...) is a full SMS opt-out.
    # Batch 008c: EN/ES/PT/HT keywords and opt-out expressions, matched
    # against the WHOLE message. Suppression is immediate (the event blocks
    # the channel now); the one confirmation is queued for human approval.
    langs = policy.stop_match(body.text)
    if langs:
        out = policy.record_channel_opt_out(conn, body.customer_id, "sms",
                                            "inbound_keyword", x_actor, x_role)
        out["matched_language"] = langs
        msg = dict(msg, channel_opt_out=out)
    return msg


class RegisterIn(BaseModel):
    data_kind: str
    provider: str
    purpose: str | None = None
    notes: str | None = None
    endpoint: str | None = None


class TermsIn(BaseModel):
    reviewed: bool
    terms_reference: str | None = None
    endpoint: str | None = None


@app.get("/api/processing-register")
def list_register(x_role: str | None = Header(None)):
    require_read(x_role)
    return register.list_entries(conn)


@app.post("/api/processing-register")
def add_register_entry(body: RegisterIn, x_role: str | None = Header(None),
                       x_actor: str | None = Header(None)):
    require_owner(x_role)
    try:
        entry = register.add_entry(conn, body.data_kind, body.provider,
                                   body.purpose, body.notes, body.endpoint)
    except ValueError as e:
        raise HTTPException(400, str(e))
    dbmod.audit(conn, x_actor, x_role, "register_provider",
                "processing_register", entry["id"],
                {"provider": body.provider})
    return entry


@app.post("/api/processing-register/{entry_id}/terms")
def set_register_terms(entry_id: int, body: TermsIn,
                       x_role: str | None = Header(None),
                       x_actor: str | None = Header(None)):
    require_owner(x_role)
    try:
        entry = register.set_terms_reviewed(
            conn, entry_id, body.reviewed, terms_reference=body.terms_reference,
            reviewed_by=x_actor, endpoint=body.endpoint)
    except ValueError as e:
        raise HTTPException(404 if "not found" in str(e) else 400, str(e))
    dbmod.audit(conn, x_actor, x_role,
                "provider_terms_reviewed" if body.reviewed
                else "provider_terms_unreviewed",
                "processing_register", entry_id,
                {"provider": entry["provider"],
                 "endpoint": entry.get("endpoint"),
                 "terms_reference": entry.get("terms_reference")})
    return entry


class FreeTextIn(BaseModel):
    customer_id: int
    text: str
    text_lang: str = "en"
    # Batch 008b: the operator classifies by purpose; omitted => HELD.
    purpose: str | None = None


@app.post("/api/messages/free")
def compose_free(body: FreeTextIn, x_role: str | None = Header(None),
                 x_actor: str | None = Header(None)):
    require_write(x_role)
    try:
        msg = messages.compose_free_text(conn, body.customer_id, body.text,
                                         body.text_lang, purpose=body.purpose,
                                         actor=x_actor, role=x_role)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # The operator's purpose declaration is audited (never the text itself).
    dbmod.audit(conn, x_actor, x_role, "compose_free_text", "messages",
                msg["id"], {"purpose": msg["purpose"], "status": msg["status"],
                            "hold_reason": msg["hold_reason"]})
    return msg


class ClassifyIn(BaseModel):
    purpose: str


@app.post("/api/messages/{message_id}/classify")
def classify_message(message_id: int, body: ClassifyIn,
                     x_role: str | None = Header(None),
                     x_actor: str | None = Header(None)):
    """Operator (re)classification by purpose — audited from/to."""
    require_write(x_role)
    try:
        return messages.classify(conn, message_id, body.purpose, x_actor, x_role)
    except ValueError as e:
        raise HTTPException(404 if "not found" in str(e) else 400, str(e))


class ChannelIn(BaseModel):
    channel: str = "sms"
    source: str | None = None


@app.post("/api/customers/{customer_id}/channel-opt-out")
def channel_opt_out(customer_id: int, body: ChannelIn,
                    x_role: str | None = Header(None),
                    x_actor: str | None = Header(None)):
    """Full channel opt-out (e.g. the customer texted STOP). Drafts the one
    permitted opt-out confirmation for this event."""
    require_write(x_role)
    try:
        return policy.record_channel_opt_out(
            conn, customer_id, body.channel, body.source or "operator",
            x_actor, x_role)
    except ValueError as e:
        raise HTTPException(404 if "not found" in str(e) else 400, str(e))


@app.post("/api/customers/{customer_id}/channel-opt-in")
def channel_opt_in(customer_id: int, body: ChannelIn,
                   x_role: str | None = Header(None),
                   x_actor: str | None = Header(None)):
    require_write(x_role)
    try:
        return policy.revoke_channel_opt_out(conn, customer_id, body.channel,
                                             x_actor, x_role)
    except ValueError as e:
        raise HTTPException(400, str(e))


class ReleaseIn(BaseModel):
    reason: str


@app.post("/api/messages/{message_id}/release-hold")
def release_hold(message_id: int, body: ReleaseIn,
                 x_role: str | None = Header(None),
                 x_actor: str | None = Header(None)):
    """Batch 008c: a human releases a promotional-screen false positive
    (audited; the message returns to draft and still needs approval)."""
    require_write(x_role)
    try:
        return messages.release_promo_hold(conn, message_id, x_actor, x_role,
                                           body.reason)
    except ValueError as e:
        raise HTTPException(404 if "not found" in str(e) else 400, str(e))


@app.get("/api/opt-out-confirmations")
def pending_opt_out_confirmations(x_role: str | None = Header(None)):
    """Batch 008c: the approval queue of opt-out confirmations (one per
    event). Approving or withdrawing one never changes the opt-out."""
    require_read(x_role)
    return [dict(r) for r in conn.execute(
        "SELECT m.id, m.customer_id, m.channel, m.original_lang, m.status,"
        " m.opt_out_event_id, o.opted_out_at, o.revoked_at FROM messages m"
        " JOIN channel_opt_outs o ON o.id = m.opt_out_event_id"
        " WHERE m.purpose = 'opt_out_confirmation' AND m.status IN"
        " ('draft', 'approved') ORDER BY m.id")]


@app.get("/api/admin/suppression-key/status")
def suppression_key_status(x_role: str | None = Header(None)):
    """Batch 008d: OWNER ONLY. 'verified' / 'not_initialized' and the key
    SOURCE (env | file) — never the key or its check value."""
    require_owner(x_role)
    try:
        return policy.verify_suppression_key(conn)
    except policy.SuppressionKeyError as e:
        raise HTTPException(503, str(e))


@app.get("/api/admin/suppressions")
def get_suppressions(x_role: str | None = Header(None)):
    """Batch 008c: retained do-not-message list. OWNER ONLY; the protected
    identifier itself is never returned."""
    require_owner(x_role)
    return policy.list_suppressions(conn)


@app.get("/api/customers/{customer_id}/channel-opt-outs")
def get_channel_opt_outs(customer_id: int, x_role: str | None = Header(None)):
    require_read(x_role)
    return policy.list_opt_outs(conn, customer_id)


class TranslationIn(BaseModel):
    translated_text: str


@app.post("/api/messages/{message_id}/translation")
def supply_translation(message_id: int, body: TranslationIn,
                       x_role: str | None = Header(None)):
    require_write(x_role)
    return messages.supply_translation(conn, message_id, body.translated_text)


@app.post("/api/ai/draft-comeback")
def ai_draft_comeback(customer_id: int, x_role: str | None = Header(None)):
    require_write(x_role)
    try:
        return ai_assist.draft_comeback(conn, customer_id)
    except PermissionError as e:
        raise HTTPException(403, str(e))


class ReviewRequestIn(BaseModel):
    customer_id: int


class ReviewRecordIn(BaseModel):
    rating: int
    text: str = ""


@app.post("/api/reviews/request")
def request_review(body: ReviewRequestIn, x_role: str | None = Header(None)):
    require_write(x_role)
    return reviews.request_review(conn, body.customer_id)


@app.post("/api/reviews/{review_id}/record")
def record_review(review_id: int, body: ReviewRecordIn, x_role: str | None = Header(None)):
    require_write(x_role)
    return reviews.record_review(conn, review_id, body.rating, body.text)


@app.get("/api/reviews")
def list_reviews(x_role: str | None = Header(None)):
    require_read(x_role)
    return [dict(r) for r in conn.execute("SELECT * FROM reviews ORDER BY id DESC")]


@app.post("/api/referrals")
def create_referral(customer_id: int, x_role: str | None = Header(None)):
    require_write(x_role)
    return reviews.create_referral_code(conn, customer_id)


@app.get("/api/reports/summary")
def summary(x_role: str | None = Header(None)):
    require_read(x_role)
    return reports.summary(conn)


@app.get("/api/export")
def export_all(x_role: str | None = Header(None)):
    require_owner(x_role)
    return JSONResponse(data_rights.export_all(conn))


@app.delete("/api/customers/{customer_id}")
def delete_customer(customer_id: int, x_role: str | None = Header(None),
                    x_actor: str | None = Header(None)):
    require_owner(x_role)
    try:
        return data_rights.delete_customer(conn, customer_id, x_actor, x_role)
    except policy.SuppressionKeyError as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))
    except data_rights.DeletionBlocked as e:
        raise HTTPException(409, str(e))


WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")
if os.path.isdir(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
