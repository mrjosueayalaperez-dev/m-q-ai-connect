import secrets

import pytest
from fastapi.testclient import TestClient

from app.db import connect

# Batch 009 — REAL LOGIN. The API ignores X-Role / X-Actor entirely; the
# role and the audit actor come from the logged-in user's server-side
# session. The test HARNESS therefore creates real user accounts (argon2id
# hashes) and signs in through POST /api/auth/login like any client, then
# sends the bearer token it was issued. There is no test mode in the app.
#
# - Every TestClient is signed in as the harness owner "test-operator"
#   (the same audit name Batches 001-008 used).
# - auth_headers(role, username) signs in a user of that role and returns
#   the Authorization header — the replacement for the old
#   headers={"X-Role": ...} overrides in the role tests.
# - anonymous_client() sends no credentials at all.
#
# The harness password is random per test process, never printed, and the
# accounts exist only in the throwaway test databases.
_HARNESS_PASSWORD = "Harness-" + secrets.token_urlsafe(24)
_DEFAULT_NAMES = {"owner": "test-operator", "staff": "test-staff",
                  "viewer": "test-viewer"}
_tokens: dict = {}

_orig_init = TestClient.__init__


def _raw_client(app, **kwargs) -> TestClient:
    c = TestClient.__new__(TestClient)
    _orig_init(c, app, **kwargs)
    return c


def auth_headers(role: str = "owner", username: str | None = None) -> dict:
    """Sign in (once, cached) as a real user with `role`; return the
    bearer Authorization header for that session."""
    from app import auth
    from app import db as dbmod
    from app import main as main_mod
    username = (username or _DEFAULT_NAMES[role]).lower()
    key = (main_mod.DB_PATH, username)
    c = dbmod.open_connection(main_mod.DB_PATH)
    try:
        tok = _tokens.get(key)
        if tok is not None:
            live = auth.resolve_session(c, tok)
            if live is not None and live[0]["role"] == role:
                return {"Authorization": f"Bearer {tok}"}
        row = c.execute("SELECT role FROM users WHERE username = ?",
                        (username,)).fetchone()
        if row is None:
            auth.create_user(c, username, _HARNESS_PASSWORD, role, None,
                             "test-harness", "system")
        elif row["role"] != role:
            raise AssertionError(f"harness user {username} has role {row['role']}")
    finally:
        c.close()
    r = _raw_client(main_mod.app).post("/api/auth/login", json={
        "username": username, "password": _HARNESS_PASSWORD, "mode": "token"})
    assert r.status_code == 200, r.text
    _tokens[key] = r.json()["token"]
    return {"Authorization": f"Bearer {_tokens[key]}"}


def _authenticated_init(self, app, *args, **kwargs):
    _orig_init(self, app, *args, **kwargs)
    self.headers.setdefault("Authorization", auth_headers("owner")["Authorization"])


TestClient.__init__ = _authenticated_init


def anonymous_client(app, **kwargs) -> TestClient:
    return _raw_client(app, **kwargs)


@pytest.fixture()
def conn():
    c = connect(":memory:")
    yield c
    c.close()
