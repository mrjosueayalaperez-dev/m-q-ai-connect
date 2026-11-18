"""Hardening (2026-11-18) — fixes from the security review of main fbc7c1a.

M1  no auto-generated API docs: /docs, /redoc, /openapi.json are 404
L1  security headers on every response; a CSP with no 'unsafe-inline', and a
    web UI with no inline script / handler / style that such a CSP would block
L2  totp.key is git-ignored
L3  an unknown typed username is never audited or logged in plain text
    (marker + short keyed hash); known usernames still are

Each fix also has a deliberate-break check: the same detector, pointed at a
broken copy, must FAIL — so a passing test means the fix, not a blind test.
"""
import fnmatch
import itertools
import json
import logging
import os
import re
import secrets
import tempfile

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "hardening.db"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auth  # noqa: E402
from app import main as main_mod  # noqa: E402
from tests.conftest import anonymous_client  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB = os.path.join(ROOT, "web")
client = TestClient(main_mod.app)          # harness owner (bearer)
anon = anonymous_client(main_mod.app)
_ip = itertools.count(10)

DOC_PATHS = ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect")


def _client_from():
    return anonymous_client(main_mod.app, client=(f"192.0.2.{next(_ip)}", 40000))


def _login(c, username, password):
    return c.post("/api/auth/login", json={"username": username,
                                           "password": password, "mode": "token"})


# ------------------------------------------------------------------ M1

def _docs_exposed(c) -> list[str]:
    return [p for p in DOC_PATHS if c.get(p).status_code == 200]


def test_m1_docs_endpoints_are_gone_for_anonymous_and_owner():
    assert _docs_exposed(anon) == []
    assert _docs_exposed(client) == []
    for p in DOC_PATHS:
        assert anon.get(p).status_code == 404
    assert main_mod.app.docs_url is None and main_mod.app.redoc_url is None
    assert main_mod.app.openapi_url is None


def test_m1_deliberate_break_default_fastapi_is_detected():
    # A default FastAPI() (the pre-fix setting) must trip the same detector.
    broken = FastAPI()
    exposed = _docs_exposed(TestClient(broken))
    assert "/docs" in exposed and "/openapi.json" in exposed and "/redoc" in exposed


def test_m1_api_still_works():
    assert anon.get("/api/health").status_code == 200
    assert anon.get("/api/customers").status_code == 401
    assert client.get("/api/customers").status_code == 200


# ------------------------------------------------------------------ L1

REQUIRED = {"x-frame-options": "DENY", "x-content-type-options": "nosniff",
            "referrer-policy": "no-referrer"}


def _header_problems(headers) -> list[str]:
    bad = [f"{k} != {v}" for k, v in REQUIRED.items() if headers.get(k) != v]
    csp = headers.get("content-security-policy") or ""
    if not csp:
        return bad + ["no CSP"]
    directives = {d.split()[0]: d.split()[1:] for d in
                  (x.strip() for x in csp.split(";")) if d}
    if "'unsafe-inline'" in csp or "'unsafe-eval'" in csp or "*" in csp.split():
        bad.append("CSP allows unsafe-inline/unsafe-eval/*")
    if directives.get("frame-ancestors") != ["'none'"]:
        bad.append("frame-ancestors not 'none'")
    for d in ("default-src", "object-src", "base-uri"):
        if directives.get(d) != ["'none'"]:
            bad.append(f"{d} not 'none'")
    for d in ("script-src", "style-src", "connect-src"):
        if directives.get(d) != ["'self'"]:
            bad.append(f"{d} not 'self'")
    return bad


def test_l1_headers_on_web_static_api_and_denials():
    responses = {
        "/": anon.get("/"), "/index.html": anon.get("/index.html"),
        "/app.js": anon.get("/app.js"), "/styles.css": anon.get("/styles.css"),
        "/favicon.ico": anon.get("/favicon.ico"),
        "/api/health": anon.get("/api/health"),
        "401 deny": anon.get("/api/customers"),
        "404": anon.get("/no-such-file.html"),
        "404 docs": anon.get("/docs"),
        "owner api": client.get("/api/customers"),
        "login failure": _login(_client_from(), "nobody-" + secrets.token_hex(3),
                                "Synthetic-" + secrets.token_urlsafe(12)),
    }
    for name, r in responses.items():
        assert _header_problems(r.headers) == [], name


def test_l1_csrf_denial_carries_headers():
    u = auth.create_user(main_mod.conn, "hard-" + secrets.token_hex(4),
                         pw := "Synthetic-" + secrets.token_urlsafe(18), "staff",
                         None, "hardening", "system")
    c = anonymous_client(main_mod.app, base_url="https://testserver",
                         client=(f"192.0.2.{next(_ip)}", 40000))
    r = c.post("/api/auth/login", json={"username": u["username"], "password": pw,
                                        "mode": "cookie"})
    assert r.status_code == 200
    r = c.post("/api/customers", json={"name": "Synthetic"})   # no CSRF token
    assert r.status_code == 403
    assert _header_problems(r.headers) == []


def test_l1_deliberate_break_missing_or_weak_headers_are_detected():
    assert _header_problems({}) != []
    weak = dict(REQUIRED, **{"content-security-policy":
                             "default-src 'self'; script-src 'self' 'unsafe-inline'"})
    probs = _header_problems(weak)
    assert any("unsafe-inline" in p for p in probs)
    assert any("frame-ancestors" in p for p in probs)
    assert _header_problems({k: v for k, v in REQUIRED.items()
                             if k != "x-frame-options"}) != []


def test_l1_middleware_replaces_a_weaker_header_from_an_inner_layer():
    from fastapi.responses import PlainTextResponse
    inner = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @inner.get("/x")
    def x():
        return PlainTextResponse("x", headers={"X-Frame-Options": "ALLOWALL",
                                               "Content-Security-Policy": "default-src *"})
    inner.add_middleware(main_mod._SecurityHeaders)
    r = TestClient(inner).get("/x")
    assert _header_problems(r.headers) == []
    assert r.headers.get_list("x-frame-options") == ["DENY"]
    # deliberate break: without the middleware the same detector fails
    bare = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    bare.add_api_route("/x", x)
    assert _header_problems(TestClient(bare).get("/x").headers) != []


# Inline code the CSP would block: <script> without src, on*= handlers, style= attrs,
# javascript: URLs. Scans the HTML and the html`` templates in the JS files.
_INLINE = [
    (re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.I), "inline <script>"),
    (re.compile(r"""<[^>]*\son[a-z]+\s*=\s*["']""", re.I), "inline on* handler"),
    (re.compile(r"""<[^>]*\sstyle\s*=\s*["']""", re.I), "inline style attribute"),
    (re.compile(r"<style\b", re.I), "inline <style>"),
    (re.compile(r"javascript:", re.I), "javascript: URL"),
]


def _inline_findings(text: str) -> list[str]:
    return [label for rx, label in _INLINE if rx.search(text)]


def _web_files():
    return [os.path.join(WEB, f) for f in sorted(os.listdir(WEB))
            if f.endswith((".html", ".js"))]


def test_l1_web_ui_has_nothing_the_csp_blocks():
    found = {}
    for path in _web_files():
        hits = _inline_findings(open(path, encoding="utf-8").read())
        if hits:
            found[os.path.basename(path)] = hits
    assert found == {}


def test_l1_deliberate_break_inline_code_is_detected():
    assert _inline_findings('<button onclick="go(1)">x</button>') == ["inline on* handler"]
    assert _inline_findings('<input style="width:70px">') == ["inline style attribute"]
    assert _inline_findings("<script>alert(1)</script>") == ["inline <script>"]
    assert _inline_findings('<script src="app.js"></script>') == []


def test_l1_every_delegated_action_is_allow_listed_and_defined():
    js = open(os.path.join(WEB, "app.js"), encoding="utf-8").read()
    sets = {name: set(re.findall(r'"(\w+)"', body)) for name, body in
            re.findall(r"const (UI_ACTIONS|UI_CHANGE|UI_SUBMIT) = new Set\(\[([^\]]*)\]\)", js, re.S)}
    used = {"UI_ACTIONS": set(re.findall(r'data-act="(\w+)"', js)),
            "UI_CHANGE": set(re.findall(r'data-act-change="(\w+)"', js)),
            "UI_SUBMIT": set(re.findall(r'data-act-submit="(\w+)"', js))}
    assert set(sets) == set(used)
    for k in used:
        assert used[k] and used[k] <= sets[k], k
        for fn in sets[k]:
            assert re.search(rf"window\.{fn}\s*=", js), fn
    # the former inline widths now come from the stylesheet
    css = open(os.path.join(WEB, "styles.css"), encoding="utf-8").read()
    assert "input.w-qty" in css and "input.w-amount" in css


# ------------------------------------------------------------------ L2

def _ignored(gitignore_text: str, name: str) -> bool:
    pats = [ln.strip() for ln in gitignore_text.splitlines()
            if ln.strip() and not ln.strip().startswith("#")]
    return any(fnmatch.fnmatch(name, p.rstrip("/")) for p in pats)


def test_l2_totp_key_and_other_secrets_are_git_ignored():
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    for name in ("totp.key", "suppression.key", "crm.db", "crm.db-wal", "data"):
        assert _ignored(gi, name), name


def test_l2_deliberate_break_missing_line_is_detected():
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    broken = "\n".join(ln for ln in gi.splitlines() if ln.strip() != "totp.key")
    assert not _ignored(broken, "totp.key")


# ------------------------------------------------------------------ L3

def _audit_and_log_text(caplog) -> str:
    rows = main_mod.conn.execute("SELECT actor, detail FROM audit_log").fetchall()
    return caplog.text + "\n".join(f"{r['actor']} {r['detail']}" for r in rows)


def test_l3_unknown_username_never_in_audit_or_log(caplog):
    caplog.set_level(logging.INFO)
    typed = "Typed-Secret-" + secrets.token_hex(6)     # e.g. a password in the wrong box
    c = _client_from()
    for _ in range(auth.USER_FAIL_LIMIT + 1):            # failures, lockout, blocked
        _login(c, typed, "Synthetic-" + secrets.token_urlsafe(12))
    text = _audit_and_log_text(caplog)
    assert typed.lower() not in text and typed not in text
    ref = auth.unknown_username_ref(typed.lower())
    rows = [dict(r) for r in main_mod.conn.execute(
        "SELECT actor, action, detail FROM audit_log WHERE detail LIKE ?", (f"%{ref}%",))]
    actions = {r["action"] for r in rows}
    assert {"login_failed", "login_lockout", "login_blocked"} <= actions
    assert all(r["actor"] == auth.UNKNOWN_USER_MARKER for r in rows)
    assert all(json.loads(r["detail"])["username"] == ref for r in rows)
    assert "unknown_user" in {json.loads(r["detail"]).get("reason") for r in rows}


def test_l3_ref_is_stable_per_text_short_and_not_the_text():
    a1, a2 = auth.unknown_username_ref("someone"), auth.unknown_username_ref("someone")
    b = auth.unknown_username_ref("someone-else")
    assert a1 == a2 != b
    assert re.fullmatch(r"u#[0-9a-f]{12}", a1) and "someone" not in a1


def test_l3_known_username_is_still_recorded(caplog):
    caplog.set_level(logging.INFO)
    u = auth.create_user(main_mod.conn, "known-" + secrets.token_hex(4),
                         "Synthetic-" + secrets.token_urlsafe(18), "viewer",
                         None, "hardening", "system")
    assert _login(_client_from(), u["username"], "Wrong-" + secrets.token_urlsafe(12)).status_code == 401
    rows = [dict(r) for r in main_mod.conn.execute(
        "SELECT actor, detail FROM audit_log WHERE action = 'login_failed' AND actor = ?",
        (u["username"],))]
    assert rows and json.loads(rows[-1]["detail"]) == {"username": u["username"],
                                                        "reason": "bad_password"}
    assert u["username"] in caplog.text


def test_l3_deliberate_break_plain_text_name_is_detected(monkeypatch, caplog):
    # Put back the pre-fix behaviour (record whatever was typed): the same
    # leak check must now find the typed text.
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(auth, "_audit_name", lambda conn, raw: (raw or "(blank)", raw))
    typed = "leak-check-" + secrets.token_hex(6)
    _login(_client_from(), typed, "Synthetic-" + secrets.token_urlsafe(12))
    assert typed in _audit_and_log_text(caplog)
