"""Batch 009b — owner password recovery (server shell only) and two-step
login with an authenticator app (RFC 6238 TOTP).

R  recovery: CLI reset-password works, applies policy, revokes sessions,
   clears lockout, audits source=cli; NO web / email / API recovery path
T  TOTP: RFC vectors, enroll+confirm, login needs a code, wrong codes count
   toward lockout, replay blocked, +-1 step skew, recovery codes single-use,
   challenge expiry, a pending challenge is never a session, the secret is
   never returned again or logged, disable needs password + code, CLI
   break-glass reset-totp, key missing/wrong fails closed, cookie + CSRF
   flow, staff / viewer unaffected
"""
import itertools
import logging
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b9b.db"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auth  # noqa: E402
from app import main as main_mod  # noqa: E402
from app import totp  # noqa: E402
from tests.conftest import anonymous_client  # noqa: E402

WORK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
client = TestClient(main_mod.app)             # harness owner (bearer, no TOTP)
anon = anonymous_client(main_mod.app)
_ip = itertools.count(10)


def _pw():
    return "Synthetic-" + secrets.token_urlsafe(18)


def _uname(prefix="b9b"):
    return f"{prefix}-{secrets.token_hex(4)}"


def _c(https=False):
    return anonymous_client(main_mod.app,
                            base_url="https://testserver" if https else "http://testserver",
                            client=(f"203.0.113.{next(_ip) % 250 + 1}", 41000))


def _make_user(role="owner"):
    pw = _pw()
    u = auth.create_user(main_mod.conn, _uname(role), pw, role, "Synthetic " + role,
                         "b9b-setup", "system")
    return u, pw


def _login(c, username, password, mode="token"):
    return c.post("/api/auth/login", json={"username": username, "password": password,
                                           "mode": mode})


def _bearer(username, password):
    r = _login(_c(), username, password)
    assert r.status_code == 200 and "token" in r.json(), r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def _code(secret_b32, offset=0, at=None):
    step = totp._step((at or auth._now()).timestamp()) + offset
    return totp.hotp(totp._unb32(secret_b32), step)


@pytest.fixture()
def clock(monkeypatch):
    """Freeze the auth clock at the START of a 30 s step (so +-1 is exact);
    move it with clock.advance(seconds)."""
    base = datetime.now(timezone.utc)
    base = base - timedelta(seconds=base.timestamp() % totp.PERIOD) + timedelta(seconds=1)

    class C:
        now = base

        def advance(self, s):
            C.now = C.now + timedelta(seconds=s)
    c = C()
    monkeypatch.setattr(auth, "_clock", lambda: C.now)
    return c


def _enrolled_owner(clock):
    u, pw = _make_user("owner")
    h = _bearer(u["username"], pw)
    r = client.post("/api/auth/totp/enroll", headers=h)
    assert r.status_code == 200, r.text
    secret = r.json()["secret"]
    r = client.post("/api/auth/totp/confirm", json={"code": _code(secret)}, headers=h)
    assert r.status_code == 200, r.text
    clock.advance(totp.PERIOD)          # the confirm code's step is now used
    return u, pw, secret, r.json()["recovery_codes"], h


def _two_step_login(c, u, pw, **second):
    r = _login(c, u["username"], pw)
    assert r.status_code == 200 and r.json()["two_step_required"] is True, r.text
    ch = r.json()["challenge"]
    return ch, c.post("/api/auth/login/verify", json=dict(challenge=ch, **second))


def _audit(action, username):
    return [r for r in main_mod.conn.execute(
        "SELECT * FROM audit_log WHERE action = ? ORDER BY id", (action,))
        if f'"username": "{username}"' in (r["detail"] or "")]


def _cli(*args, stdin="", db=None):
    env = dict(os.environ, MQ_CRM_DB=db or main_mod.DB_PATH)
    return subprocess.run([sys.executable, "-m", "app.auth_cli", *args], cwd=WORK,
                          env=env, input=stdin, capture_output=True, text=True, timeout=60)


# ============================================== R: server-shell recovery

def test_b9b_r_cli_reset_password_revokes_sessions_clears_lockout_and_audits():
    u, pw = _make_user("owner")
    h1, h2 = _bearer(u["username"], pw), _bearer(u["username"], pw)
    for i in range(auth.USER_FAIL_LIMIT):                       # lock the account
        _login(_c(), u["username"], f"Wrong-guess-{i}-xyz")
    assert _login(_c(), u["username"], pw).status_code == 429
    new = _pw()
    r = _cli("reset-password", "--username", u["username"], "--password-stdin",
             stdin=new + "\n")
    assert r.returncode == 0, r.stderr
    assert new not in r.stdout + r.stderr and pw not in r.stdout + r.stderr
    assert "2 session(s) signed out" in r.stdout
    for h in (h1, h2):
        assert client.get("/api/auth/me", headers=h).status_code == 401
    assert _login(_c(), u["username"], pw).status_code == 401      # old password dead
    assert _login(_c(), u["username"], new).status_code == 200     # lockout cleared
    a = _audit("password_reset", u["username"])
    assert a and a[-1]["actor"] == "server-cli" and '"source": "cli"' in a[-1]["detail"]
    assert new not in a[-1]["detail"]


def test_b9b_r_cli_reset_password_applies_policy_and_refuses_bad_input():
    u, pw = _make_user("owner")
    assert _cli("reset-password", "--username", u["username"]).returncode != 0  # no tty
    r = _cli("reset-password", "--username", u["username"], "--password-stdin",
             stdin="short\n")
    assert r.returncode == 2 and "at least" in r.stderr
    r = _cli("reset-password", "--username", u["username"], "--password-stdin",
             stdin=f"{u['username']}-Longer-123\n")
    assert r.returncode == 2 and "username" in r.stderr
    r = _cli("reset-password", "--username", "no-such-user", "--password-stdin",
             stdin=_pw() + "\n")
    assert r.returncode == 2 and "not found" in r.stderr
    assert _login(_c(), u["username"], pw).status_code == 200      # unchanged


def test_b9b_r_no_web_email_or_api_password_recovery_path():
    paths = [getattr(r, "path", "") for r in main_mod.app.routes]
    # /api/audit/recover is the owner-only audit-CHAIN recovery (Batch 008),
    # unrelated to passwords.
    for p in paths:
        if p != "/api/audit/recover":
            assert not re.search(r"forgot|recover|reset", p, re.I), p
    # The only password routes: change your OWN password (needs the current
    # one, signed in) and the owner-admin reset of a NON-owner account.
    assert sorted(p for p in paths if "password" in p) == [
        "/api/auth/password", "/api/users/{user_id}/password"]
    assert main_mod.OPEN_PATHS == {"/api/health", "/api/auth/login",
                                   "/api/auth/login/verify"}
    guesses = ["/api/auth/forgot", "/api/auth/forgot-password", "/api/auth/reset",
               "/api/auth/reset-password", "/api/auth/password/reset",
               "/api/auth/recover", "/api/auth/recovery", "/api/password-reset",
               "/api/users/reset-password"]
    for g in guesses:
        assert anon.post(g, json={"username": "test-operator"}).status_code == 401, g
        assert client.post(g, json={"username": "test-operator"}).status_code in (404, 405), g
    # The owner-admin route can't reset an OWNER (that is the CLI's job).
    o, opw = _make_user("owner")
    r = client.post(f"/api/users/{o['id']}/password", json={"new_password": _pw()})
    assert r.status_code == 403 and "CLI" in r.json()["detail"]
    assert _login(_c(), o["username"], opw).status_code == 200
    # No e-mail sending anywhere in the app.
    src = ""
    for root, _d, files in os.walk(os.path.join(WORK, "app")):
        for f in files:
            if f.endswith(".py"):
                src += open(os.path.join(root, f), encoding="utf-8").read()
    assert "smtplib" not in src and "sendmail" not in src


# ============================================== T: TOTP

def test_b9b_t_rfc6238_and_rfc4226_vectors():
    k = b"12345678901234567890"
    assert [totp.hotp(k, i) for i in range(3)] == ["755224", "287082", "359152"]
    assert totp.hotp(k, 59 // 30, 8) == "94287082"
    assert totp.hotp(k, 1111111109 // 30, 8) == "07081804"
    assert totp.hotp(k, 20000000000 // 30, 8) == "65353130"


def test_b9b_t_enroll_and_confirm(clock):
    u, pw = _make_user("owner")
    h = _bearer(u["username"], pw)
    other = _bearer(u["username"], pw)
    me = client.get("/api/auth/me", headers=h).json()
    assert me["two_step"] == {"enabled": False}
    assert me["warnings"] == ["owner_two_step_not_enrolled"]
    r = client.post("/api/auth/totp/enroll", headers=h)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = r.json()
    secret = body["secret"]
    assert body["otpauth_uri"].startswith("otpauth://totp/M%26Q%20CRM%3A" + u["username"])
    assert f"secret={secret}" in body["otpauth_uri"] and "issuer=M%26Q%20CRM" in body["otpauth_uri"]
    assert len(totp._unb32(secret)) == 20
    st = client.get("/api/auth/totp", headers=h).json()
    assert st["pending_enrollment"] and not st["enabled"]
    # not enabled until confirmed: password alone still signs in
    assert "token" in _login(_c(), u["username"], pw).json()
    bad = f"{(int(_code(secret)) + 1) % 10 ** 6:06d}"
    assert client.post("/api/auth/totp/confirm", json={"code": bad},
                       headers=h).status_code == 400
    assert not totp.enabled_for(main_mod.conn, u["id"])
    r = client.post("/api/auth/totp/confirm", json={"code": _code(secret)}, headers=h)
    assert r.status_code == 200
    codes = r.json()["recovery_codes"]
    assert len(codes) == 10 and len(set(codes)) == 10
    assert all(re.fullmatch(r"[a-z2-7]{4}(-[a-z2-7]{4}){3}", c) for c in codes)
    st = client.get("/api/auth/totp", headers=h).json()
    assert st["enabled"] and st["recovery_codes_remaining"] == 10
    assert client.get("/api/auth/me", headers=h).status_code == 200      # this one kept
    assert client.get("/api/auth/me", headers=other).status_code == 401  # others revoked
    me = client.get("/api/auth/me", headers=h).json()
    assert me["two_step"] == {"enabled": True} and "warnings" not in me
    assert client.post("/api/auth/totp/enroll", headers=h).status_code == 409
    assert _audit("totp_enroll_started", u["username"])
    assert _audit("totp_enroll_confirm_failed", u["username"])
    assert _audit("totp_enabled", u["username"])


def test_b9b_t_login_requires_code_and_password_alone_is_not_a_session(clock):
    u, pw, secret, _codes, _h = _enrolled_owner(clock)
    c = _c()
    r = _login(c, u["username"], pw)
    j = r.json()
    assert r.status_code == 200 and j["two_step_required"] is True
    assert "token" not in j and "csrf_token" not in j and "user" not in j
    assert j["challenge_expires_in"] == 300
    assert "set-cookie" not in r.headers and not c.cookies
    ch = j["challenge"]
    # the pending challenge is NOT a session, anywhere
    for hdr in ({"Authorization": "Bearer " + ch}, {"Cookie": "mq_session=" + ch}):
        for m, p in (("GET", "/api/auth/me"), ("GET", "/api/customers"),
                     ("POST", "/api/auth/totp/enroll"), ("POST", "/api/auth/logout")):
            assert anon.request(m, p, headers=hdr).status_code == 401, (m, p, hdr)
    assert c.post("/api/auth/login/verify", json={"challenge": ch}).status_code == 400
    r = c.post("/api/auth/login/verify", json={"challenge": ch, "code": _code(secret)})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"
    h = {"Authorization": "Bearer " + r.json()["token"]}
    assert client.get("/api/auth/me", headers=h).json()["user"]["role"] == "owner"
    # a used challenge can't be replayed
    clock.advance(totp.PERIOD)
    assert c.post("/api/auth/login/verify",
                  json={"challenge": ch, "code": _code(secret)}).status_code == 401
    assert anon.post("/api/auth/login/verify", json={}).status_code == 401
    assert anon.post("/api/auth/login/verify",
                     json={"challenge": secrets.token_urlsafe(32), "code": "123456"}
                     ).status_code == 401
    ok = _audit("login_success", u["username"])
    assert '"two_step": "totp"' in ok[-1]["detail"]
    assert _audit("login_password_accepted", u["username"])
    assert _audit("login_two_step_pending", u["username"])


def test_b9b_t_wrong_codes_count_toward_lockout_and_password_does_not_reset(clock):
    u, pw, secret, _codes, _h = _enrolled_owner(clock)
    bad = f"{(int(_code(secret)) + 7) % 10 ** 6:06d}"
    for i in range(auth.USER_FAIL_LIMIT):
        # a fresh challenge each time: the CORRECT password in between must
        # not refill the guessing budget
        ch, r = _two_step_login(_c(), u, pw, code=bad)
        assert r.status_code == 401 and r.json()["detail"] == "invalid code"
    r = _login(_c(), u["username"], pw)                  # account now locked
    assert r.status_code == 429 and "retry-after" in r.headers
    assert _audit("login_lockout", u["username"])
    fails = _audit("login_two_step_failed", u["username"])
    assert len(fails) == auth.USER_FAIL_LIMIT and '"reason": "bad_code"' in fails[0]["detail"]
    clock.advance(auth.LOCK_BASE_SECONDS + 1)
    ch, r = _two_step_login(_c(), u, pw, code=_code(secret))
    assert r.status_code == 200 and "token" in r.json()


def test_b9b_t_challenge_dies_after_max_attempts(clock):
    u, pw, secret, _codes, _h = _enrolled_owner(clock)
    c = _c()
    ch = _login(c, u["username"], pw).json()["challenge"]
    for i in range(totp.CHALLENGE_MAX_ATTEMPTS):
        assert c.post("/api/auth/login/verify",
                      json={"challenge": ch, "code": f"{i:06d}"}).status_code in (401, 429)
    r = c.post("/api/auth/login/verify", json={"challenge": ch, "code": _code(secret)})
    assert r.status_code in (401, 429) and "token" not in r.json()


def test_b9b_t_replay_of_the_same_code_is_blocked(clock):
    u, pw, secret, _codes, _h = _enrolled_owner(clock)
    code = _code(secret)
    _ch, r = _two_step_login(_c(), u, pw, code=code)
    assert r.status_code == 200
    clock.advance(5)                                    # same 30 s window
    _ch, r = _two_step_login(_c(), u, pw, code=code)
    assert r.status_code == 401
    _ch, r = _two_step_login(_c(), u, pw, code=_code(secret, -1))   # older step too
    assert r.status_code == 401
    clock.advance(totp.PERIOD)
    _ch, r = _two_step_login(_c(), u, pw, code=_code(secret))
    assert r.status_code == 200


def test_b9b_t_clock_skew_of_one_step_allowed_two_steps_refused(clock):
    u, pw, secret, _codes, _h = _enrolled_owner(clock)
    clock.advance(10 * totp.PERIOD)
    _ch, r = _two_step_login(_c(), u, pw, code=_code(secret, -2))
    assert r.status_code == 401
    _ch, r = _two_step_login(_c(), u, pw, code=_code(secret, +2))
    assert r.status_code == 401
    _ch, r = _two_step_login(_c(), u, pw, code=_code(secret, -1))   # phone 30 s slow
    assert r.status_code == 200
    _ch, r = _two_step_login(_c(), u, pw, code=_code(secret, +1))   # phone 30 s fast
    assert r.status_code == 200


def test_b9b_t_recovery_code_works_exactly_once(clock):
    u, pw, _secret, codes, h = _enrolled_owner(clock)
    _ch, r = _two_step_login(_c(), u, pw, recovery_code=codes[0].upper().replace("-", " "))
    assert r.status_code == 200 and "token" in r.json()
    _ch, r = _two_step_login(_c(), u, pw, recovery_code=codes[0])
    assert r.status_code == 401
    st = client.get("/api/auth/totp", headers={"Authorization": "Bearer " + _two_step_login(
        _c(), u, pw, recovery_code=codes[1])[1].json()["token"]}).json()
    assert st["recovery_codes_remaining"] == 8
    used = _audit("recovery_code_used", u["username"])
    assert len(used) == 2 and '"remaining": 9' in used[0]["detail"]
    assert all(codes[0] not in r["detail"] for r in used)


def test_b9b_t_challenge_expires_after_five_minutes(clock):
    u, pw, secret, _codes, _h = _enrolled_owner(clock)
    c = _c()
    ch = _login(c, u["username"], pw).json()["challenge"]
    clock.advance(totp.CHALLENGE_SECONDS + 1)
    r = c.post("/api/auth/login/verify", json={"challenge": ch, "code": _code(secret)})
    assert r.status_code == 401 and "expired" in r.json()["detail"]
    fails = _audit("login_two_step_failed", u["username"])
    assert '"reason": "challenge_expired"' in fails[-1]["detail"]
    _ch, r = _two_step_login(c, u, pw, code=_code(secret))           # fresh one works
    assert r.status_code == 200


def test_b9b_t_secret_and_codes_never_returned_again_stored_clear_or_logged(clock, caplog):
    caplog.set_level(logging.DEBUG)
    u, pw, secret, codes, h = _enrolled_owner(clock)
    ch, r = _two_step_login(_c(), u, pw, code=_code(secret))
    tok = r.json()["token"]
    hb = {"Authorization": "Bearer " + tok}
    _two_step_login(_c(), u, pw, code="000000")
    _two_step_login(_c(), u, pw, recovery_code=codes[3])
    exposed = [client.get("/api/auth/totp", headers=hb).text,
               client.get("/api/auth/me", headers=hb).text,
               client.post("/api/auth/totp/enroll", headers=hb).text]   # 409, no new secret
    raw = totp._unb32(secret)
    needles = [secret, secret.lower(), raw.hex(), ch] + codes + [c.replace("-", "") for c in codes]
    rows = []
    for t in ("audit_log", "totp_factors", "recovery_codes", "login_challenges", "sessions"):
        rows += [str(tuple(x)) for x in main_mod.conn.execute(f"SELECT * FROM {t}")]
    dump = caplog.text + "\n".join(exposed) + "\n".join(rows)
    for n in needles:
        assert n not in dump, n[:6]
    f = main_mod.conn.execute("SELECT * FROM totp_factors WHERE user_id = ?",
                              (u["id"],)).fetchone()
    assert f["secret_enc"].startswith("v1:")
    assert "totp_enabled" in caplog.text and "login_two_step_failed" in caplog.text


def test_b9b_t_disable_needs_password_and_a_valid_code(clock):
    u, pw, secret, codes, h = _enrolled_owner(clock)
    assert client.post("/api/auth/totp/disable", json={"password": pw},
                       headers=h).status_code == 403
    assert client.post("/api/auth/totp/disable", json={"password": pw, "code": "000000"},
                       headers=h).status_code == 403
    assert client.post("/api/auth/totp/disable",
                       json={"password": "Wrong-password-xyz", "code": _code(secret)},
                       headers=h).status_code == 403
    assert totp.enabled_for(main_mod.conn, u["id"])
    assert len(_audit("totp_disable_failed", u["username"])) == 3
    r = client.post("/api/auth/totp/disable", json={"password": pw, "code": _code(secret)},
                    headers=h)
    assert r.status_code == 200 and not totp.enabled_for(main_mod.conn, u["id"])
    assert main_mod.conn.execute("SELECT COUNT(*) FROM recovery_codes WHERE user_id = ?",
                                 (u["id"],)).fetchone()[0] == 0
    a = _audit("totp_disabled", u["username"])
    assert a and '"source": "api"' in a[-1]["detail"]
    r = _login(_c(), u["username"], pw)
    assert "token" in r.json() and "two_step_required" not in r.json()


def test_b9b_t_cli_break_glass_reset_totp(clock):
    u, pw, secret, codes, h = _enrolled_owner(clock)
    r = _cli("reset-totp", "--username", u["username"])
    assert r.returncode == 2 and "--yes" in r.stderr
    assert totp.enabled_for(main_mod.conn, u["id"])
    r = _cli("reset-totp", "--username", u["username"], "--yes")
    assert r.returncode == 0, r.stderr
    assert secret not in r.stdout + r.stderr and codes[0] not in r.stdout
    assert not totp.enabled_for(main_mod.conn, u["id"])
    assert client.get("/api/auth/me", headers=h).status_code == 401          # signed out
    _ch, r2 = None, _login(_c(), u["username"], pw)
    assert "token" in r2.json()                                               # password only now
    a = _audit("totp_reset", u["username"])
    assert a and a[-1]["actor"] == "server-cli" and '"source": "cli"' in a[-1]["detail"]
    assert _cli("reset-totp", "--username", "nobody-here", "--yes").returncode == 2


def test_b9b_t_only_owner_enrolls_staff_and_viewer_unaffected():
    for role in ("staff", "viewer"):
        u, pw = _make_user(role)
        r = _login(_c(), u["username"], pw)
        assert r.status_code == 200 and "token" in r.json()
        h = {"Authorization": "Bearer " + r.json()["token"]}
        assert client.post("/api/auth/totp/enroll", headers=h).status_code == 403
        me = client.get("/api/auth/me", headers=h).json()
        assert me["user"]["role"] == role and "warnings" not in me
        assert client.get("/api/auth/totp", headers=h).json()["available_for_role"] is False


def test_b9b_t_cookie_flow_with_two_step_keeps_csrf(clock):
    u, pw, secret, _codes, _h = _enrolled_owner(clock)
    c = _c(https=True)
    r = _login(c, u["username"], pw, mode="cookie")
    assert r.json()["two_step_required"] and not c.cookies
    r = c.post("/api/auth/login/verify", json={"challenge": r.json()["challenge"],
                                               "code": _code(secret)})
    assert r.status_code == 200 and c.cookies.get("mq_session")
    csrf = r.json()["csrf_token"]
    assert "token" not in r.json()
    assert c.get("/api/auth/me").status_code == 200
    assert c.post("/api/customers", json={"name": "CSRF B9b"}).status_code == 403
    assert c.post("/api/customers", json={"name": "CSRF B9b"},
                  headers={"X-CSRF-Token": csrf}).status_code == 200
    assert c.post("/api/auth/totp/disable", json={"password": pw, "code": _code(secret)}
                  ).status_code == 403                                  # no CSRF


def test_b9b_t_missing_or_wrong_totp_key_fails_closed(clock):
    u, pw, secret, _codes, _h = _enrolled_owner(clock)
    kp = totp._key_file(main_mod.conn)
    assert kp and os.path.exists(kp) and (os.stat(kp).st_mode & 0o777) == 0o600
    backup = kp + ".bak"
    shutil.move(kp, backup)
    try:
        _ch, r = _two_step_login(_c(), u, pw, code=_code(secret))
        assert r.status_code == 503 and "token" not in r.json()
        assert "reset-totp" in r.json()["detail"]
        with open(kp, "w") as f:                                       # wrong key
            f.write(secrets.token_bytes(32).hex())
        clock.advance(totp.PERIOD)
        _ch, r = _two_step_login(_c(), u, pw, code=_code(secret))
        assert r.status_code == 503 and "token" not in r.json()
    finally:
        shutil.move(backup, kp)
    clock.advance(totp.PERIOD)
    _ch, r = _two_step_login(_c(), u, pw, code=_code(secret))
    assert r.status_code == 200
