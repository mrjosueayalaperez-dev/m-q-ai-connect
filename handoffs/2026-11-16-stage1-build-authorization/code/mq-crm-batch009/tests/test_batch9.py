"""Batch 009 — real login.

A  X-Role / X-Actor are ignored (no header gives a role or an audit name)
B  deny by default (401 without a session; 403 for the wrong role)
C  login / logout (bearer + HttpOnly Secure SameSite cookie), server-side revoke
D  session expiry: idle + absolute
E  lockout / rate limiting by account and by address, with backoff
F  hashing: argon2id only, no plaintext password or token stored
G  first-owner bootstrap: one-time CLI, no default password, no HTTP route
H  CSRF on cookie-authenticated state changes
I  role matrix + owner-only user management, invalidation on change
J  nothing secret in logs or the audit trail
K  opt-out / suppression / approval controls still enforced under real auth
"""
import itertools
import json
import logging
import os
import re
import secrets
import subprocess
import sys
import tempfile
from datetime import timedelta

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b9.db"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auth  # noqa: E402
from app import db as dbmod  # noqa: E402
from app import main as main_mod  # noqa: E402
from tests.conftest import anonymous_client, auth_headers  # noqa: E402

WORK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
client = TestClient(main_mod.app)             # harness owner (bearer)
anon = anonymous_client(main_mod.app)
_n = itertools.count(1)
_ip = itertools.count(10)


def _pw():
    return "Synthetic-" + secrets.token_urlsafe(18)


def _phone():
    return f"312555{9000 + next(_n):04d}"


def _uname(prefix="b9"):
    return f"{prefix}-{secrets.token_hex(4)}"


def _client_from(ip=None, https=False):
    """An unauthenticated client from its own address (keeps throttle
    counters of one test away from the others)."""
    return anonymous_client(main_mod.app,
                            base_url="https://testserver" if https else "http://testserver",
                            client=(ip or f"198.51.100.{next(_ip)}", 40000))


def _make_user(role, password=None, username=None):
    pw = password or _pw()
    u = auth.create_user(main_mod.conn, username or _uname(role), pw, role,
                         "Synthetic " + role, "b9-setup", "system")
    return u, pw


def _login(c, username, password, mode="token"):
    return c.post("/api/auth/login", json={"username": username,
                                           "password": password, "mode": mode})


def _bearer(username, password):
    r = _login(_client_from(), username, password)
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def _audit(action, **match):
    rows = [dict(r) for r in main_mod.conn.execute(
        "SELECT * FROM audit_log WHERE action = ? ORDER BY id", (action,))]
    out = []
    for r in rows:
        d = json.loads(r["detail"])
        if all(d.get(k) == v for k, v in match.items()):
            out.append(r)
    return out


class _Clock:
    def __init__(self, monkeypatch):
        self.t = auth._real_clock()
        monkeypatch.setattr(auth, "_clock", lambda: self.t)

    def advance(self, **kw):
        self.t = self.t + timedelta(**kw)


def _concrete(path):
    return re.sub(r"\{[^}]+\}", "1", path)


def _api_routes():
    for route in main_mod.app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api"):
            continue
        for method in sorted(getattr(route, "methods", []) or []):
            if method != "HEAD":
                yield method, path


# ============================================== A: X-Role is ignored

def test_b9_a_self_asserted_role_header_never_authenticates():
    checked = 0
    for method, path in _api_routes():
        if path in main_mod.OPEN_PATHS:
            continue
        r = anon.request(method, _concrete(path), json={},
                         headers={"X-Role": "owner", "X-Actor": "mallory"})
        assert r.status_code == 401, (method, path, r.status_code)
        checked += 1
    assert checked >= 50


def test_b9_a_role_header_cannot_escalate_a_real_session():
    viewer = auth_headers("viewer")
    h = dict(viewer, **{"X-Role": "owner", "X-Actor": "test-operator"})
    assert client.get("/api/export", headers=h).status_code == 403
    assert client.post("/api/customers", json={"name": "Escalate"},
                       headers=h).status_code == 403
    # lower-case / duplicate variants are stripped too
    h2 = dict(viewer, **{"x-role": "owner"})
    assert client.get("/api/users", headers=h2).status_code == 403


def test_b9_a_audit_actor_is_the_logged_in_user_not_x_actor():
    u, pw = _make_user("staff")
    h = dict(_bearer(u["username"], pw), **{"X-Actor": "someone-else"})
    r = client.post("/api/customers", json={"name": "Actor B9", "phone": _phone()},
                    headers=h)
    assert r.status_code == 200
    cid = r.json()["customer"]["id"]
    r = client.post(f"/api/customers/{cid}/update", json={"name": "Actor B9b"}, headers=h)
    assert r.status_code == 200
    row = main_mod.conn.execute("SELECT * FROM audit_log WHERE action = 'update_customer'"
                                " AND entity_id = ? ORDER BY id DESC", (cid,)).fetchone()
    assert row["actor"] == u["username"] and row["role"] == "staff"


# ============================================== B: deny by default

def test_b9_b_every_route_denies_without_a_session_and_with_bad_tokens():
    bad = [{}, {"Authorization": "Bearer " + secrets.token_urlsafe(32)},
           {"Authorization": "Basic dXNlcjpwYXNz"}, {"Cookie": "mq_session=forged"}]
    for method, path in _api_routes():
        if path in main_mod.OPEN_PATHS:
            continue
        for h in bad:
            r = anon.request(method, _concrete(path), json={}, headers=h)
            assert r.status_code == 401, (method, path, h, r.status_code)
    r = anon.get("/api/customers")
    assert r.headers.get("www-authenticate", "").startswith("Bearer")
    assert anon.get("/api/health").status_code == 200


def test_b9_b_static_ui_still_served_but_holds_no_data():
    r = anon.get("/")
    assert r.status_code == 200 and "login-form" in r.text


# ============================================== C: login / logout

def test_b9_c_token_login_me_logout_revokes_server_side():
    u, pw = _make_user("viewer")
    c = _client_from()
    r = _login(c, u["username"], pw)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["user"]["role"] == "viewer" and body["token_type"] == "bearer"
    assert "csrf_token" not in body and "set-cookie" not in r.headers
    h = {"Authorization": "Bearer " + body["token"]}
    me = c.get("/api/auth/me", headers=h).json()
    assert me["user"]["username"] == u["username"] and me["session"]["kind"] == "bearer"
    assert c.post("/api/auth/logout", headers=h).status_code == 200
    assert c.get("/api/auth/me", headers=h).status_code == 401
    row = main_mod.conn.execute("SELECT * FROM sessions WHERE token_hash = ?",
                                (auth.token_hash(body["token"]),)).fetchone()
    assert row["revoked_at"] and row["revoked_reason"] == "logout"
    assert _audit("logout", username=u["username"])


def test_b9_c_cookie_login_sets_httponly_secure_samesite_cookie():
    u, pw = _make_user("staff")
    c = _client_from(https=True)
    r = _login(c, u["username"], pw, mode="cookie")
    assert r.status_code == 200
    sc = r.headers["set-cookie"]
    assert sc.startswith("mq_session=")
    low = sc.lower()
    assert "httponly" in low and "secure" in low and "samesite=strict" in low
    assert "path=/api" in low and "max-age=" in low
    assert "token" not in r.json() and r.json()["csrf_token"]
    me = c.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["session"]["kind"] == "cookie"
    # a cookie session cannot be replayed as a bearer token, and vice versa
    tok = c.cookies.get("mq_session")
    assert _client_from().get("/api/auth/me", headers={
        "Authorization": "Bearer " + tok}).status_code == 401
    btok = _login(_client_from(), u["username"], pw).json()["token"]
    assert _client_from(https=True).get("/api/auth/me", headers={
        "Cookie": "mq_session=" + btok}).status_code == 401
    # logout clears the cookie and kills the session
    out = c.post("/api/auth/logout", headers={"X-CSRF-Token": r.json()["csrf_token"]})
    assert out.status_code == 200
    assert _client_from(https=True).get("/api/auth/me", headers={
        "Cookie": "mq_session=" + tok}).status_code == 401


def test_b9_c_wrong_password_unknown_user_disabled_all_same_401():
    u, pw = _make_user("viewer")
    d, dpw = _make_user("viewer")
    auth.set_disabled(main_mod.conn, d["id"], True, "b9", "owner")
    msgs = set()
    for name, p in ((u["username"], "Wrong-password-xyz"), ("nobody-" + secrets.token_hex(3), pw),
                    (d["username"], dpw)):
        r = _login(_client_from(), name, p)
        assert r.status_code == 401
        msgs.add(r.json()["detail"])
    assert msgs == {auth.GENERIC_FAILURE}
    reasons = {json.loads(a["detail"])["reason"] for a in _audit("login_failed")}
    assert {"bad_password", "unknown_user", "disabled"} <= reasons


def test_b9_c_login_mode_validated():
    u, pw = _make_user("viewer")
    assert _login(_client_from(), u["username"], pw, mode="magic").status_code == 400


# ============================================== D: expiry

def test_b9_d_idle_expiry(monkeypatch):
    clk = _Clock(monkeypatch)
    u, pw = _make_user("viewer")
    h = _bearer(u["username"], pw)
    clk.advance(minutes=auth.IDLE_MINUTES - 5)
    assert client.get("/api/auth/me", headers=h).status_code == 200   # activity renews
    clk.advance(minutes=auth.IDLE_MINUTES - 5)
    assert client.get("/api/auth/me", headers=h).status_code == 200
    clk.advance(minutes=auth.IDLE_MINUTES + 1)
    assert client.get("/api/auth/me", headers=h).status_code == 401
    tok = h["Authorization"].split()[1]
    row = main_mod.conn.execute("SELECT revoked_reason FROM sessions WHERE token_hash = ?",
                                (auth.token_hash(tok),)).fetchone()
    assert row["revoked_reason"] == "idle_expired"
    clk.advance(minutes=-(auth.IDLE_MINUTES + 1))           # going back does not revive it
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_b9_d_absolute_expiry_even_when_active(monkeypatch):
    clk = _Clock(monkeypatch)
    u, pw = _make_user("viewer")
    h = _bearer(u["username"], pw)
    step = max(1, auth.IDLE_MINUTES // 2)
    elapsed = 0
    while elapsed + step < auth.ABSOLUTE_HOURS * 60:
        clk.advance(minutes=step)
        elapsed += step
        assert client.get("/api/auth/me", headers=h).status_code == 200
    clk.advance(minutes=step)
    assert client.get("/api/auth/me", headers=h).status_code == 401
    tok = h["Authorization"].split()[1]
    assert main_mod.conn.execute("SELECT revoked_reason FROM sessions WHERE token_hash = ?",
                                 (auth.token_hash(tok),)).fetchone()[0] == "absolute_expired"


def test_b9_d_session_lifetime_env_is_bounded():
    assert 5 <= auth.IDLE_MINUTES <= 240 and 1 <= auth.ABSOLUTE_HOURS <= 72
    os.environ["B9_PROBE"] = "999999"
    assert auth._int_env("B9_PROBE", 30, 5, 240) == 240
    os.environ["B9_PROBE"] = "0"
    assert auth._int_env("B9_PROBE", 30, 5, 240) == 5
    del os.environ["B9_PROBE"]


# ============================================== E: lockout / rate limiting

def test_b9_e_account_lockout_with_backoff(monkeypatch):
    clk = _Clock(monkeypatch)
    u, pw = _make_user("staff")
    for i in range(auth.USER_FAIL_LIMIT):
        assert _login(_client_from(), u["username"], f"Wrong-guess-{i}-abcdef").status_code == 401
    # locked: even the CORRECT password is refused, from any address
    r = _login(_client_from(), u["username"], pw)
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert r.json()["detail"] == auth.LOCKED_MESSAGE
    lock = _audit("login_lockout", username=u["username"], scope="account")
    assert lock and json.loads(lock[-1]["detail"])["seconds"] == auth.LOCK_BASE_SECONDS
    assert _audit("login_blocked", username=u["username"])
    clk.advance(seconds=auth.LOCK_BASE_SECONDS + 1)
    for i in range(auth.USER_FAIL_LIMIT):
        _login(_client_from(), u["username"], f"Wrong-again-{i}-abcdef")
    lock = _audit("login_lockout", username=u["username"], scope="account")
    assert json.loads(lock[-1]["detail"])["seconds"] == 2 * auth.LOCK_BASE_SECONDS  # backoff
    clk.advance(seconds=auth.LOCK_BASE_SECONDS + 1)
    assert _login(_client_from(), u["username"], pw).status_code == 429       # still locked
    clk.advance(seconds=auth.LOCK_BASE_SECONDS + 1)
    assert _login(_client_from(), u["username"], pw).status_code == 200       # lock expired


def test_b9_e_unknown_usernames_lock_the_same_way():
    name = "ghost-" + secrets.token_hex(3)
    for i in range(auth.USER_FAIL_LIMIT):
        assert _login(_client_from(), name, f"Guess-{i}-abcdefgh").status_code == 401
    assert _login(_client_from(), name, "Guess-x-abcdefgh").status_code == 429


def test_b9_e_address_rate_limit_across_usernames():
    ip = "203.0.113.77"
    victim, vpw = _make_user("viewer")
    for i in range(auth.IP_FAIL_LIMIT):
        _login(_client_from(ip), f"spray-{i}-{secrets.token_hex(2)}", "Spray-password-123")
    r = _login(_client_from(ip), victim["username"], vpw)
    assert r.status_code == 429
    assert _audit("login_lockout", scope="address")
    assert _login(_client_from(), victim["username"], vpw).status_code == 200  # other address ok


def test_b9_e_success_resets_account_failures():
    u, pw = _make_user("viewer")
    for i in range(auth.USER_FAIL_LIMIT - 1):
        _login(_client_from(), u["username"], f"Nearly-{i}-abcdefgh")
    assert _login(_client_from(), u["username"], pw).status_code == 200
    for i in range(auth.USER_FAIL_LIMIT - 1):
        _login(_client_from(), u["username"], f"Again-{i}-abcdefgh")
    assert _login(_client_from(), u["username"], pw).status_code == 200


# ============================================== F: hashing / storage

def test_b9_f_argon2id_hashes_and_no_plaintext_secrets_stored():
    u, pw = _make_user("staff")
    tok = _bearer(u["username"], pw)["Authorization"].split()[1]
    row = main_mod.conn.execute("SELECT password_hash FROM users WHERE id = ?",
                                (u["id"],)).fetchone()
    assert row["password_hash"].startswith("$argon2id$v=19$m=65536,t=3,p=2$")
    dump = "\n".join(main_mod.conn.iterdump())
    assert pw not in dump and tok not in dump
    assert auth.token_hash(tok) in dump                      # only the SHA-256
    assert all(r[0].startswith("$argon2id$") for r in
               main_mod.conn.execute("SELECT password_hash FROM users"))


def test_b9_f_non_argon2id_hashes_are_never_accepted():
    import hashlib
    pw = _pw()
    for weak in (pw, hashlib.sha256(pw.encode()).hexdigest(),
                 "$2b$12$" + "x" * 53, "$argon2i$v=19$m=65536,t=3,p=2$abc$def", ""):
        assert auth.verify_password(weak, pw) is False
    u, _ = _make_user("viewer")
    main_mod.conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                          (hashlib.sha256(pw.encode()).hexdigest(), u["id"]))
    main_mod.conn.commit()
    assert _login(_client_from(), u["username"], pw).status_code == 401


def test_b9_f_password_policy():
    for bad in ("short", "password1234", "aaaaaaaaaaaaaaaa", "x" * 300):
        with pytest.raises(auth.PasswordPolicyError):
            auth.validate_password(bad, "someone")
    with pytest.raises(auth.PasswordPolicyError):
        auth.validate_password("my-name-is-carla-99", "carla")
    auth.validate_password(_pw(), "someone")
    r = client.post("/api/users", json={"username": _uname(), "password": "tooshort",
                                        "role": "viewer"})
    assert r.status_code == 400


# ============================================== G: first-owner bootstrap

def _cli(db, *args, stdin=""):
    env = dict(os.environ, MQ_CRM_DB=db)
    return subprocess.run([sys.executable, "-m", "app.auth_cli", *args], cwd=WORK,
                          env=env, input=stdin, capture_output=True, text=True, timeout=60)


def test_b9_g_fresh_database_has_no_users_and_denies_everything(tmp_path):
    db = str(tmp_path / "fresh.db")
    code = ("import json, app.main as m\n"
            "from fastapi.testclient import TestClient as T\n"
            "c = T(m.app)\n"
            "n = m.conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]\n"
            "print(json.dumps([n, c.get('/api/customers').status_code,"
            " c.post('/api/auth/login', json={'username': 'owner', 'password': 'owner'}).status_code,"
            " c.post('/api/auth/login', json={'username': 'admin', 'password': 'admin'}).status_code]))\n")
    env = dict(os.environ, MQ_CRM_DB=db)
    r = subprocess.run([sys.executable, "-c", code], cwd=WORK, env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout.strip().splitlines()[-1]) == [0, 401, 401, 401]
    assert "no owner account exists" in r.stderr     # loud startup warning


def test_b9_g_cli_bootstrap_once_with_stdin_password(tmp_path):
    db = str(tmp_path / "boot.db")
    pw = _pw()
    r = _cli(db, "create-owner", "--username", "first-owner")      # no tty, no flag
    assert r.returncode != 0 and "non-interactive" in (r.stderr + r.stdout)
    r = _cli(db, "create-owner", "--username", "first-owner", "--password-stdin",
             stdin="short\n")
    assert r.returncode == 2 and "at least" in r.stderr
    r = _cli(db, "create-owner", "--username", "first-owner", "--password-stdin",
             stdin=pw + "\n")
    assert r.returncode == 0, r.stderr
    assert pw not in r.stdout + r.stderr
    r2 = _cli(db, "create-owner", "--username", "second-owner", "--password-stdin",
              stdin=_pw() + "\n")
    assert r2.returncode == 2 and "already exists" in r2.stderr
    c = dbmod.connect(db)
    rows = [dict(x) for x in c.execute("SELECT username, role, password_hash FROM users")]
    assert [(x["username"], x["role"]) for x in rows] == [("first-owner", "owner")]
    assert rows[0]["password_hash"].startswith("$argon2id$")
    acts = [x["action"] for x in c.execute("SELECT action FROM audit_log")]
    assert "owner_bootstrapped" in acts
    c.close()
    # and the bootstrapped owner can actually sign in to a server on that DB
    code = ("import sys, app.main as m\n"
            "from fastapi.testclient import TestClient as T\n"
            "r = T(m.app).post('/api/auth/login', json={'username': 'first-owner',"
            " 'password': sys.stdin.readline().rstrip(chr(10)), 'mode': 'token'})\n"
            "print(r.status_code, r.json()['user']['role'])\n")
    r = subprocess.run([sys.executable, "-c", code], cwd=WORK, input=pw + "\n",
                       env=dict(os.environ, MQ_CRM_DB=db), capture_output=True,
                       text=True, timeout=60)
    assert r.stdout.split() == ["200", "owner"], r.stderr


def test_b9_g_bootstrap_refused_while_an_owner_exists_and_no_http_route():
    with pytest.raises(auth.BootstrapRefused):
        auth.bootstrap_owner(main_mod.conn, _uname(), _pw())
    paths = [p for _, p in _api_routes()]
    assert not any(re.search(r"setup|bootstrap|register-owner", p) for p in paths)
    src = open(os.path.join(WORK, "app", "auth.py"), encoding="utf-8").read()
    assert not re.search(r"password\s*=\s*['\"][^'\"]+['\"]", src)


# ============================================== H: CSRF

def test_b9_h_cookie_session_writes_need_the_csrf_token():
    u, pw = _make_user("staff")
    c = _client_from(https=True)
    csrf = _login(c, u["username"], pw, mode="cookie").json()["csrf_token"]
    body = {"name": "CSRF B9", "phone": _phone()}
    assert c.post("/api/customers", json=body).status_code == 403
    assert c.post("/api/customers", json=body,
                  headers={"X-CSRF-Token": "forged-" + secrets.token_hex(8)}).status_code == 403
    assert c.post("/api/customers", json=body, headers={
        "X-CSRF-Token": csrf, "Origin": "https://evil.example"}).status_code == 403
    assert c.get("/api/customers").status_code == 200            # reads need no token
    r = c.post("/api/customers", json=body, headers={"X-CSRF-Token": csrf,
                                                     "Origin": "https://testserver"})
    assert r.status_code == 200
    assert c.post("/api/auth/logout").status_code == 403         # logout is a write too
    # /me hands same-origin JS the token after a reload
    assert c.get("/api/auth/me").json()["csrf_token"] == csrf
    # another session's CSRF token does not work
    c2 = _client_from(https=True)
    csrf2 = _login(c2, u["username"], pw, mode="cookie").json()["csrf_token"]
    assert c.post("/api/customers", json={"name": "x", "phone": _phone()},
                  headers={"X-CSRF-Token": csrf2}).status_code == 403


def test_b9_h_bearer_requests_are_not_cookie_bound():
    u, pw = _make_user("staff")
    h = _bearer(u["username"], pw)
    assert client.post("/api/customers", json={"name": "Bearer B9", "phone": _phone()},
                       headers=h).status_code == 200


# ============================================== I: role matrix + user management

def _route_status(h, method, path, json_body=None):
    return client.request(method, path, json=json_body, headers=h).status_code


def test_b9_i_role_matrix_matches_existing_permissions():
    cid = client.post("/api/customers", json={"name": "Matrix B9", "phone": _phone()}
                      ).json()["customer"]["id"]
    heads = {r: auth_headers(r) for r in ("owner", "staff", "viewer")}
    read = [("GET", "/api/customers"), ("GET", "/api/messages"),
            ("GET", "/api/reports/summary"), ("GET", "/api/opt-out-confirmations")]
    write = [("POST", "/api/customers", {"name": "W", "phone": None}),
             ("POST", f"/api/customers/{cid}/update", {"name": "Matrix B9b"})]
    owner_only = [("GET", "/api/export"), ("GET", f"/api/customers/{cid}/export"),
                  ("GET", "/api/admin/suppressions"),
                  ("GET", "/api/admin/suppression-key/status"),
                  ("GET", "/api/users")]
    read.append(("GET", "/api/processing-register"))     # unchanged: any role may read
    for m, p in read:
        assert [_route_status(heads[r], m, p) for r in heads] == [200, 200, 200], p
    for m, p, b in write:
        got = [_route_status(heads[r], m, p, b) for r in heads]
        assert got[0] == 200 and got[1] == 200 and got[2] == 403, (p, got)
    for m, p in owner_only:
        got = [_route_status(heads[r], m, p) for r in heads]
        assert got[0] == 200 and got[1:] == [403, 403], (p, got)
    # deletion: owner only
    assert client.delete(f"/api/customers/{cid}", headers=heads["staff"]).status_code == 403
    assert client.delete(f"/api/customers/{cid}", headers=heads["viewer"]).status_code == 403
    assert client.delete(f"/api/customers/{cid}", headers=heads["owner"]).status_code == 200


def test_b9_i_user_management_is_owner_only_and_audited():
    name = _uname("mgmt")
    body = {"username": name, "password": _pw(), "role": "viewer"}
    for r in ("staff", "viewer"):
        assert client.post("/api/users", json=body, headers=auth_headers(r)).status_code == 403
    r = client.post("/api/users", json=body)
    assert r.status_code == 200 and "password_hash" not in r.json()
    uid = r.json()["id"]
    assert client.post("/api/users", json=body).status_code == 400       # duplicate
    for r_ in ("staff", "viewer"):
        h = auth_headers(r_)
        assert client.post(f"/api/users/{uid}/role", json={"role": "owner"},
                           headers=h).status_code == 403
        assert client.post(f"/api/users/{uid}/disable", headers=h).status_code == 403
        assert client.post(f"/api/users/{uid}/password", json={"new_password": _pw()},
                           headers=h).status_code == 403
    assert client.post(f"/api/users/{uid}/role", json={"role": "boss"}).status_code == 400
    assert client.post("/api/users/999999/role", json={"role": "staff"}).status_code == 404
    created = _audit("user_created", username=name)
    assert created and created[0]["actor"] == "test-operator"


def test_b9_i_role_change_takes_effect_and_revokes_sessions():
    u, pw = _make_user("viewer")
    h = _bearer(u["username"], pw)
    assert client.post("/api/customers", json={"name": "R", "phone": _phone()},
                       headers=h).status_code == 403
    r = client.post(f"/api/users/{u['id']}/role", json={"role": "staff"})
    assert r.status_code == 200 and r.json()["role"] == "staff"
    assert client.get("/api/auth/me", headers=h).status_code == 401      # old session gone
    h2 = _bearer(u["username"], pw)
    assert client.post("/api/customers", json={"name": "R2", "phone": _phone()},
                       headers=h2).status_code == 200
    ch = _audit("role_changed", username=u["username"])
    assert json.loads(ch[-1]["detail"])["from"] == "viewer"


def test_b9_i_disable_kills_sessions_and_login():
    u, pw = _make_user("staff")
    h = _bearer(u["username"], pw)
    assert client.post(f"/api/users/{u['id']}/disable").status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401
    assert _login(_client_from(), u["username"], pw).status_code == 401
    assert client.post(f"/api/users/{u['id']}/enable").status_code == 200
    assert _login(_client_from(), u["username"], pw).status_code == 200
    assert _audit("user_disabled", username=u["username"])
    assert _audit("user_enabled", username=u["username"])


def test_b9_i_last_owner_cannot_be_demoted_or_disabled(tmp_path):
    c = dbmod.connect(str(tmp_path / "owners.db"))
    auth.ensure_schema(c)
    o = auth.bootstrap_owner(c, "solo-owner", _pw())
    with pytest.raises(ValueError):
        auth.set_role(c, o["id"], "staff", "solo-owner", "owner")
    with pytest.raises(ValueError):
        auth.set_disabled(c, o["id"], True, "solo-owner", "owner")
    o2 = auth.create_user(c, "second-owner", _pw(), "owner", None, "solo-owner", "owner")
    auth.set_role(c, o["id"], "staff", "second-owner", "owner")     # now allowed
    with pytest.raises(ValueError):
        auth.set_disabled(c, o2["id"], True, "x", "owner")
    c.close()


def test_b9_i_password_change_revokes_other_sessions_keeps_current():
    u, pw = _make_user("staff")
    h1, h2 = _bearer(u["username"], pw), _bearer(u["username"], pw)
    new = _pw()
    assert client.post("/api/auth/password", json={"current_password": "Wrong-current-pw1",
                                                   "new_password": new},
                       headers=h1).status_code == 403
    assert client.post("/api/auth/password", json={"current_password": pw,
                                                   "new_password": "weak"},
                       headers=h1).status_code == 400
    assert client.post("/api/auth/password", json={"current_password": pw,
                                                   "new_password": new},
                       headers=h1).status_code == 200
    assert client.get("/api/auth/me", headers=h1).status_code == 200
    assert client.get("/api/auth/me", headers=h2).status_code == 401
    assert _login(_client_from(), u["username"], pw).status_code == 401
    assert _login(_client_from(), u["username"], new).status_code == 200


def test_b9_i_owner_reset_revokes_all_sessions():
    u, pw = _make_user("viewer")
    h = _bearer(u["username"], pw)
    new = _pw()
    assert client.post(f"/api/users/{u['id']}/password",
                       json={"new_password": new}).status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401
    assert _login(_client_from(), u["username"], new).status_code == 200
    assert _audit("password_reset", username=u["username"])


# ============================================== J: nothing secret logged

def test_b9_j_no_password_token_or_csrf_in_logs_or_audit(caplog, tmp_path):
    caplog.set_level(logging.DEBUG)
    secrets_seen = []
    u, pw = _make_user("staff")
    secrets_seen.append(pw)
    _login(_client_from(), u["username"], "Wrong-password-abcdef")
    c = _client_from(https=True)
    r = _login(c, u["username"], pw, mode="cookie")
    csrf = r.json()["csrf_token"]
    ctok = c.cookies.get("mq_session")
    secrets_seen += [csrf, ctok, auth.token_hash(ctok)]
    btok = _login(_client_from(), u["username"], pw).json()["token"]
    secrets_seen += [btok, auth.token_hash(btok)]
    new = _pw()
    secrets_seen.append(new)
    client.post("/api/auth/password", json={"current_password": pw, "new_password": new},
                headers={"Authorization": "Bearer " + btok})
    client.post("/api/auth/logout", headers={"Authorization": "Bearer " + btok})
    reset = _pw()
    secrets_seen.append(reset)
    client.post(f"/api/users/{u['id']}/password", json={"new_password": reset})
    for i in range(auth.USER_FAIL_LIMIT + 1):
        _login(_client_from(), u["username"], f"Lockout-try-{i}-abc")
    dump = caplog.text + "\n".join(
        str(tuple(x)) for x in main_mod.conn.execute("SELECT * FROM audit_log"))
    for s in secrets_seen:
        assert s not in dump
    assert "Lockout-try-" not in dump and "Wrong-password-abcdef" not in dump
    assert "login_success" in caplog.text and "login_failed" in caplog.text


# ============================================== K: suppression under real auth

def test_b9_k_opt_out_and_suppression_enforced_for_logged_in_staff():
    staff = auth_headers("staff")
    phone = _phone()
    cid = client.post("/api/customers", json={"name": "Supp B9", "phone": phone,
                                              "consent_marketing": True,
                                              "consent_source": "b9"},
                      headers=staff).json()["customer"]["id"]
    m = client.post("/api/messages/free", json={"customer_id": cid, "text": "Your part arrived.",
                                                "text_lang": "en", "purpose": "transactional"},
                    headers=staff).json()
    assert client.post(f"/api/messages/{m['id']}/approve", headers=staff).status_code == 200
    out = client.post("/api/messages/inbound", json={"customer_id": cid, "text": "STOP",
                                                     "lang": "en"}, headers=staff).json()
    conf = out["channel_opt_out"]["confirmation"]
    assert conf["status"] == "draft"                    # confirmation needs a human
    r = client.post(f"/api/messages/{m['id']}/send", headers=staff)
    assert r.status_code == 403 and "opted out" in r.json()["detail"]
    # approving the confirmation never reopens the channel
    assert client.post(f"/api/messages/{conf['id']}/approve", headers=staff).status_code == 200
    assert client.post(f"/api/messages/{m['id']}/send", headers=staff).status_code == 403
    # deletion (owner only) keeps the retained suppression for a re-created customer
    assert client.delete(f"/api/customers/{cid}", headers=staff).status_code == 403
    assert client.delete(f"/api/customers/{cid}").status_code == 200
    new = client.post("/api/customers", json={"name": "Supp B9 again", "phone": phone},
                      headers=staff).json()["customer"]["id"]
    m2 = client.post("/api/messages/free", json={"customer_id": new, "text": "Hello again.",
                                                 "text_lang": "en", "purpose": "transactional"},
                     headers=staff).json()
    client.post(f"/api/messages/{m2['id']}/approve", headers=staff)
    r = client.post(f"/api/messages/{m2['id']}/send", headers=staff)
    assert r.status_code == 403 and "do-not-message" in r.json()["detail"]
    assert client.get("/api/admin/suppressions", headers=staff).status_code == 403
    assert client.get("/api/admin/suppressions").status_code == 200
    # a viewer cannot clear it by re-opting in, and a self-asserted owner header does not help
    v = dict(auth_headers("viewer"), **{"X-Role": "owner"})
    assert client.post(f"/api/customers/{new}/channel-opt-in", json={"channel": "sms"},
                       headers=v).status_code == 403
    assert client.post(f"/api/messages/{m2['id']}/send", headers=staff).status_code == 403


def test_b9_k_viewer_cannot_approve_send_or_release():
    v = auth_headers("viewer")
    cid = client.post("/api/customers", json={"name": "View B9", "phone": _phone(),
                                              "consent_marketing": True, "consent_source": "b9"}
                      ).json()["customer"]["id"]
    m = client.post("/api/messages/free", json={"customer_id": cid, "text": "Big SALE today!",
                                                "text_lang": "en", "purpose": "marketing"}).json()
    for path, body in ((f"/api/messages/{m['id']}/approve", None),
                       (f"/api/messages/{m['id']}/send", None),
                       (f"/api/messages/{m['id']}/release-hold", {"reason": "x"})):
        assert client.post(path, json=body, headers=v).status_code == 403
