"""First-run web bootstrap (founder-ordered fix, 2026-11-18).

A fresh install has NO account, so the sign-in page alone was a dead
end: every login failed with "incorrect credentials" and the page
offered no path forward (the founder hit this on the live deployment).
These tests run against a throwaway EMPTY database (the shared suite
database already has harness accounts) and cover: the status
endpoint's truth before/after, creation + immediate sign-in, permanent
refusal once any owner exists (however the owner was created), and
password policy identical to the CLI bootstrap path (both call
auth.create_user -> auth.validate_password).
"""
import json
import os

import pytest

from app import auth
from app import db as dbmod
from app import main as main_mod
from tests.conftest import anonymous_client

PW = "Granite-Willow-3141"
# An address used by no other test file, so login-failure throttling
# here can never lock a shared account (and vice versa).
_IP = ("192.0.2.231", 41011)


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    path = os.path.join(str(tmp_path), "fresh.db")
    c = dbmod.connect(path)
    auth.ensure_schema(c)
    c.close()
    monkeypatch.setattr(main_mod, "DB_PATH", path)
    return path


def _client():
    return anonymous_client(main_mod.app, base_url="https://testserver",
                            client=_IP)


def test_bootstrap_status_empty_install(fresh_db):
    c = _client()
    res = c.get("/api/auth/bootstrap")
    assert res.status_code == 200
    # Exactly one boolean is disclosed — nothing else.
    assert res.json() == {"owner_exists": False}


def test_bootstrap_creates_owner_and_signs_in(fresh_db):
    c = _client()
    res = c.post("/api/auth/bootstrap",
                 json={"username": "first-owner", "password": PW})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["user"]["username"] == "first-owner"
    assert body["user"]["role"] == "owner"
    assert body["csrf_token"]
    assert "mq_session=" in res.headers["set-cookie"]
    # Signed in: the stored cookie answers /api/auth/me.
    me = c.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "first-owner"
    assert me.json()["session"]["kind"] == "cookie"
    # Status flips to true and stays there.
    assert c.get("/api/auth/bootstrap").json() == {"owner_exists": True}


def test_bootstrap_token_mode_returns_usable_bearer(fresh_db):
    c = _client()
    res = c.post("/api/auth/bootstrap", json={
        "username": "token-owner", "password": PW, "mode": "token"})
    assert res.status_code == 200, res.text
    token = res.json()["token"]
    assert res.json()["token_type"] == "bearer"
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["session"]["kind"] == "bearer"


def test_bootstrap_refused_once_owner_exists(fresh_db):
    c = _client()
    first = c.post("/api/auth/bootstrap",
                   json={"username": "first-owner", "password": PW})
    assert first.status_code == 200
    # A second call right after the first is refused...
    again = c.post("/api/auth/bootstrap",
                   json={"username": "second-owner", "password": PW})
    assert again.status_code == 403
    # ...and the second account was NOT created. (A fresh client: this
    # one holds the owner's cookie session, whose CSRF check would
    # refuse the login POST before it could prove anything.)
    stranger = _client()
    login = stranger.post("/api/auth/login", json={
        "username": "second-owner", "password": PW, "mode": "token"})
    assert login.status_code == 401


def test_bootstrap_refused_when_cli_created_the_owner(fresh_db):
    conn = dbmod.connect(fresh_db)
    try:
        auth.bootstrap_owner(conn, "cli-owner", PW, "CLI Owner")
    finally:
        conn.close()
    c = _client()
    res = c.post("/api/auth/bootstrap",
                 json={"username": "web-owner", "password": PW})
    assert res.status_code == 403
    assert c.get("/api/auth/bootstrap").json() == {"owner_exists": True}


def test_web_bootstrap_closes_the_cli_path_too(fresh_db):
    c = _client()
    res = c.post("/api/auth/bootstrap",
                 json={"username": "web-owner", "password": PW})
    assert res.status_code == 200
    conn = dbmod.connect(fresh_db)
    try:
        with pytest.raises(auth.BootstrapRefused):
            auth.bootstrap_owner(conn, "cli-owner", PW)
    finally:
        conn.close()


@pytest.mark.parametrize("bad", [
    "short",                 # under the 12-character minimum
    "x" * 257,               # over the 256-character maximum
    "password123456",        # common password (digits stripped -> "password")
    "aaaaaaaaaaaa1",         # too few distinct characters
])
def test_bootstrap_password_policy_matches_cli(fresh_db, bad):
    # The CLI path rejects the same password through the shared policy.
    with pytest.raises(auth.PasswordPolicyError):
        auth.validate_password(bad, "policy-owner")
    c = _client()
    res = c.post("/api/auth/bootstrap",
                 json={"username": "policy-owner", "password": bad})
    assert res.status_code == 400, res.text
    # A refused attempt creates nothing: setup is still available.
    assert c.get("/api/auth/bootstrap").json() == {"owner_exists": False}


def test_bootstrap_password_must_not_contain_username(fresh_db):
    with pytest.raises(auth.PasswordPolicyError):
        auth.validate_password("Policy-Owner-9999", "policy-owner")
    c = _client()
    res = c.post("/api/auth/bootstrap", json={
        "username": "policy-owner", "password": "Policy-Owner-9999"})
    assert res.status_code == 400
    assert c.get("/api/auth/bootstrap").json() == {"owner_exists": False}


def test_bootstrap_bad_username_is_400_and_creates_nothing(fresh_db):
    c = _client()
    res = c.post("/api/auth/bootstrap",
                 json={"username": "NO SPACES!", "password": PW})
    assert res.status_code == 400
    assert c.get("/api/auth/bootstrap").json() == {"owner_exists": False}


def test_bootstrap_is_audited_with_web_bootstrap_source(fresh_db):
    c = _client()
    res = c.post("/api/auth/bootstrap",
                 json={"username": "audited-owner", "password": PW})
    assert res.status_code == 200
    conn = dbmod.connect(fresh_db)
    try:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE action = 'owner_bootstrapped'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["actor"] == "web-bootstrap"
        detail = json.loads(rows[0]["detail"])
        assert detail["source"] == "web-bootstrap"
        assert detail["username"] == "audited-owner"
        assert dbmod.audit_chain_status(conn)["ok"] is True
    finally:
        conn.close()
