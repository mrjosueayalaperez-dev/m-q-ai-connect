"""M&Q CRM — real login (Batch 009).

The role on every request comes ONLY from an authenticated user account:
a server-side session looked up from an HttpOnly cookie (web UI) or a
bearer token (Android / API clients). A client-supplied X-Role or X-Actor
header is stripped before routing and never trusted (see main.py).

What is stored:
- users: username, display name, role, an argon2id password hash (never
  the password), disabled flag, timestamps.
- sessions: the SHA-256 of the session token (never the token itself), the
  user, the kind (cookie | bearer), the per-session CSRF token for cookie
  sessions, created / last-seen / absolute-expiry / revoked timestamps.
- auth_throttle: failed-login counters keyed by SHA-256("user:<name>") and
  SHA-256("ip:<address>") — no raw IP address is stored.

What is never stored or logged: passwords, session tokens, bearer tokens.
The audit log records logins, failures, lockouts, logouts and user / role /
password changes by username and reason code only.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from . import db as dbmod

log = logging.getLogger("mq_crm.auth")

ROLES = ("owner", "staff", "viewer")

# argon2id (argon2-cffi's default type) — RFC 9106 "second recommended"
# style parameters: 64 MiB, 3 passes, 2 lanes.
_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def _int_env(name: str, default: int, lo: int, hi: int) -> int:
    try:
        v = int(os.environ.get(name, default))
    except ValueError:
        v = default
    return max(lo, min(hi, v))


# Session lifetime: idle timeout + absolute limit (bounded so a bad env
# value cannot create a never-expiring session).
IDLE_MINUTES = _int_env("MQ_CRM_SESSION_IDLE_MINUTES", 30, 5, 240)
ABSOLUTE_HOURS = _int_env("MQ_CRM_SESSION_MAX_HOURS", 12, 1, 72)
# Login throttling.
USER_FAIL_LIMIT = 5            # consecutive failures before an account lock
IP_FAIL_LIMIT = 20             # failures from one address before an IP lock
FAIL_WINDOW_MINUTES = 15       # failures older than this are forgotten
LOCK_BASE_SECONDS = 60         # first lock; doubles per repeat lockout
LOCK_MAX_SECONDS = 3600        # cap
LAST_SEEN_RESOLUTION_S = 60    # write last_seen at most once a minute

PASSWORD_MIN = 12
PASSWORD_MAX = 256
_COMMON = {
    "password", "password1", "password123", "passw0rd", "123456789012",
    "qwertyuiop", "letmein", "welcome", "admin", "administrator", "changeme",
    "iloveyou", "monkey", "dragon", "football", "baseball", "trustno1",
    "mqcrm", "m&qcrm", "owner", "default",
}
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")


def _real_clock() -> datetime:
    return datetime.now(timezone.utc)


_clock = _real_clock  # tests replace this to move time forward


def _now() -> datetime:
    return _clock()


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ errors

class AuthError(Exception):
    """An authentication / authorization failure with an HTTP status."""

    def __init__(self, status: int, detail: str, retry_after: int | None = None):
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.retry_after = retry_after


class PasswordPolicyError(ValueError):
    pass


class BootstrapRefused(Exception):
    pass


# ------------------------------------------------------------------ schema

def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " username TEXT NOT NULL UNIQUE,"
        " display_name TEXT,"
        " role TEXT NOT NULL CHECK (role IN ('owner', 'staff', 'viewer')),"
        " password_hash TEXT NOT NULL,"
        " disabled INTEGER NOT NULL DEFAULT 0,"
        " created_at TEXT NOT NULL, updated_at TEXT NOT NULL,"
        " password_changed_at TEXT NOT NULL)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sessions ("
        " token_hash TEXT PRIMARY KEY,"
        " user_id INTEGER NOT NULL REFERENCES users(id),"
        " kind TEXT NOT NULL CHECK (kind IN ('cookie', 'bearer')),"
        " csrf_token TEXT,"
        " created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,"
        " absolute_expires_at TEXT NOT NULL,"
        " revoked_at TEXT, revoked_reason TEXT)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS auth_throttle ("
        " key_hash TEXT PRIMARY KEY,"
        " failures INTEGER NOT NULL DEFAULT 0,"
        " window_start TEXT NOT NULL,"
        " locked_until TEXT,"
        " lockouts INTEGER NOT NULL DEFAULT 0)")
    conn.commit()
    from . import totp  # Batch 009b: two-step login tables
    totp.ensure_schema(conn)


# ------------------------------------------------------------------ audit

def _audit(conn, actor: str, role: str, action: str, user_id: int | None,
           detail: dict | None = None) -> None:
    """Audit + log an auth event. `detail` must never contain a password,
    token, session id or CSRF token — callers pass usernames, roles and
    reason codes only."""
    dbmod.audit(conn, actor, role, action, "users", user_id, detail or {})
    log.info("auth event %s actor=%s target_user_id=%s detail=%s",
             action, actor, user_id, detail or {})


# ------------------------------------------------------------------ passwords

def normalize_username(username: str) -> str:
    u = (username or "").strip().lower()
    if not _USERNAME_RE.match(u):
        raise ValueError("username must be 3-64 characters: lowercase letters,"
                         " digits, '.', '_' or '-'")
    return u


def validate_password(password: str, username: str | None = None) -> None:
    if not isinstance(password, str):
        raise PasswordPolicyError("password required")
    if len(password) < PASSWORD_MIN:
        raise PasswordPolicyError(f"password must be at least {PASSWORD_MIN} characters")
    if len(password) > PASSWORD_MAX:
        raise PasswordPolicyError(f"password must be at most {PASSWORD_MAX} characters")
    low = password.lower()
    if low in _COMMON or low.strip("0123456789!.") in _COMMON:
        raise PasswordPolicyError("password is too common")
    if len(set(password)) < 5:
        raise PasswordPolicyError("password needs more distinct characters")
    if username and username.lower() in low:
        raise PasswordPolicyError("password must not contain the username")


def hash_password(password: str) -> str:
    h = _ph.hash(password)
    if not h.startswith("$argon2id$"):
        raise RuntimeError("password hasher is not argon2id")
    return h


def verify_password(stored_hash: str, password: str) -> bool:
    if not stored_hash or not stored_hash.startswith("$argon2id$"):
        return False  # anything but an argon2id hash is never accepted
    try:
        return _ph.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


_dummy_hash: str | None = None


def _burn_verify(password: str) -> None:
    """Spend the same work as a real check for unknown usernames, so
    response time does not reveal which usernames exist."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = _ph.hash(secrets.token_urlsafe(24))
    verify_password(_dummy_hash, password or "")


# ------------------------------------------------------------------ users

def _public(row) -> dict | None:
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"],
            "display_name": row["display_name"], "role": row["role"],
            "disabled": bool(row["disabled"]), "created_at": row["created_at"],
            "updated_at": row["updated_at"]}


def get_user(conn, user_id: int) -> dict | None:
    return _public(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def list_users(conn) -> list[dict]:
    return [_public(r) for r in conn.execute("SELECT * FROM users ORDER BY id")]


def owner_exists(conn) -> bool:
    return conn.execute("SELECT 1 FROM users WHERE role = 'owner' LIMIT 1").fetchone() is not None


def _active_owner_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'owner'"
                        " AND disabled = 0").fetchone()["n"]


def create_user(conn, username: str, password: str, role: str,
                display_name: str | None, actor: str, actor_role: str) -> dict:
    u = normalize_username(username)
    if role not in ROLES:
        raise ValueError("role must be owner, staff or viewer")
    validate_password(password, u)
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (u,)).fetchone():
        raise ValueError("username already exists")
    at = _iso(_now())
    cur = conn.execute(
        "INSERT INTO users (username, display_name, role, password_hash,"
        " disabled, created_at, updated_at, password_changed_at)"
        " VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
        (u, (display_name or "").strip() or None, role, hash_password(password),
         at, at, at))
    conn.commit()
    _audit(conn, actor, actor_role, "user_created", cur.lastrowid,
           {"username": u, "role": role})
    return get_user(conn, cur.lastrowid)


def bootstrap_owner(conn, username: str, password: str,
                    display_name: str | None = None) -> dict:
    """Create the FIRST owner. Only works while no owner account exists;
    there is no default password and no HTTP route for this."""
    if owner_exists(conn):
        raise BootstrapRefused("an owner account already exists — bootstrap is"
                               " one-time only; the owner manages users in the app")
    user = create_user(conn, username, password, "owner", display_name,
                       "bootstrap-cli", "system")
    _audit(conn, "bootstrap-cli", "system", "owner_bootstrapped", user["id"],
           {"username": user["username"]})
    return user


def _target(conn, user_id: int):
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise LookupError("user not found")
    return row


def set_role(conn, user_id: int, role: str, actor: str, actor_role: str) -> dict:
    if role not in ROLES:
        raise ValueError("role must be owner, staff or viewer")
    row = _target(conn, user_id)
    if row["role"] == "owner" and role != "owner" and not row["disabled"] \
            and _active_owner_count(conn) <= 1:
        raise ValueError("cannot demote the last active owner")
    conn.execute("UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
                 (role, _iso(_now()), user_id))
    conn.commit()
    revoke_user_sessions(conn, user_id, reason="role_changed")
    _audit(conn, actor, actor_role, "role_changed", user_id,
           {"username": row["username"], "from": row["role"], "to": role})
    return get_user(conn, user_id)


def set_disabled(conn, user_id: int, disabled: bool, actor: str,
                 actor_role: str) -> dict:
    row = _target(conn, user_id)
    if disabled and row["role"] == "owner" and not row["disabled"] \
            and _active_owner_count(conn) <= 1:
        raise ValueError("cannot disable the last active owner")
    conn.execute("UPDATE users SET disabled = ?, updated_at = ? WHERE id = ?",
                 (1 if disabled else 0, _iso(_now()), user_id))
    conn.commit()
    if disabled:
        revoke_user_sessions(conn, user_id, reason="user_disabled")
    _audit(conn, actor, actor_role, "user_disabled" if disabled else "user_enabled",
           user_id, {"username": row["username"]})
    return get_user(conn, user_id)


def _set_password(conn, row, new_password: str) -> None:
    validate_password(new_password, row["username"])
    at = _iso(_now())
    conn.execute("UPDATE users SET password_hash = ?, password_changed_at = ?,"
                 " updated_at = ? WHERE id = ?",
                 (hash_password(new_password), at, at, row["id"]))
    conn.commit()


def change_own_password(conn, user_id: int, current: str, new: str,
                        keep_session_hash: str | None) -> None:
    row = _target(conn, user_id)
    if not verify_password(row["password_hash"], current or ""):
        _audit(conn, row["username"], row["role"], "password_change_failed",
               user_id, {"username": row["username"], "reason": "bad_current_password"})
        raise AuthError(403, "current password is incorrect")
    _set_password(conn, row, new)
    n = revoke_user_sessions(conn, user_id, except_hash=keep_session_hash,
                             reason="password_changed")
    _audit(conn, row["username"], row["role"], "password_changed", user_id,
           {"username": row["username"], "other_sessions_revoked": n})


def reset_password(conn, user_id: int, new: str, actor: str, actor_role: str) -> None:
    row = _target(conn, user_id)
    if row["role"] == "owner":
        # Batch 009b: an owner's password is recovered ONLY from the server
        # shell (python -m app.auth_cli reset-password) or changed by that
        # owner (POST /api/auth/password). No web / API reset of an owner.
        raise PermissionError("owner passwords are reset only with the server"
                              " CLI (python -m app.auth_cli reset-password)")
    _set_password(conn, row, new)
    n = revoke_user_sessions(conn, user_id, reason="password_reset")
    _audit(conn, actor, actor_role, "password_reset", user_id,
           {"username": row["username"], "sessions_revoked": n})


def cli_reset_password(conn, username: str, new: str) -> dict:
    """Batch 009b: server-shell password recovery (python -m app.auth_cli
    reset-password). Applies the password policy, revokes EVERY session of
    the account, ends pending two-step challenges, clears the account's
    lockout, and audits with source=cli. Does not touch two-step login
    (see reset-totp). There is no web, email or API equivalent."""
    row = conn.execute("SELECT * FROM users WHERE username = ?",
                       (normalize_username(username),)).fetchone()
    if row is None:
        raise LookupError("user not found")
    _set_password(conn, row, new)
    n = revoke_user_sessions(conn, row["id"], reason="password_reset_cli")
    conn.execute("UPDATE login_challenges SET consumed_at = ? WHERE user_id = ?"
                 " AND consumed_at IS NULL", (_iso(_now()), row["id"]))
    conn.commit()
    _clear_failures(conn, f"user:{row['username']}")
    _audit(conn, "server-cli", "system", "password_reset", row["id"],
           {"username": row["username"], "source": "cli", "sessions_revoked": n,
            "lockout_cleared": True})
    return {"username": row["username"], "sessions_revoked": n}


# ------------------------------------------------------------------ throttle

def _throttle_row(conn, key: str):
    return conn.execute("SELECT * FROM auth_throttle WHERE key_hash = ?",
                        (_sha256(key),)).fetchone()


def _locked_for(conn, key: str) -> int:
    row = _throttle_row(conn, key)
    if row is None or not row["locked_until"]:
        return 0
    left = (_parse(row["locked_until"]) - _now()).total_seconds()
    return int(left) + 1 if left > 0 else 0


def _record_failure(conn, key: str, limit: int) -> int | None:
    """Count a failure; return the lock length in seconds if this failure
    triggered a lock, else None."""
    now = _now()
    kh = _sha256(key)
    row = conn.execute("SELECT * FROM auth_throttle WHERE key_hash = ?", (kh,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO auth_throttle (key_hash, failures, window_start,"
                     " lockouts) VALUES (?, 0, ?, 0)", (kh, _iso(now)))
        row = conn.execute("SELECT * FROM auth_throttle WHERE key_hash = ?", (kh,)).fetchone()
    failures, start = row["failures"], _parse(row["window_start"])
    if now - start > timedelta(minutes=FAIL_WINDOW_MINUTES):
        failures, start = 0, now
    failures += 1
    lock_s = None
    locked_until = row["locked_until"]
    lockouts = row["lockouts"]
    if failures >= limit:
        lock_s = min(LOCK_MAX_SECONDS, LOCK_BASE_SECONDS * (2 ** lockouts))
        locked_until = _iso(now + timedelta(seconds=lock_s))
        lockouts += 1
        failures = 0
        start = now
    conn.execute("UPDATE auth_throttle SET failures = ?, window_start = ?,"
                 " locked_until = ?, lockouts = ? WHERE key_hash = ?",
                 (failures, _iso(start), locked_until, lockouts, kh))
    conn.commit()
    return lock_s


def _clear_failures(conn, key: str) -> None:
    conn.execute("UPDATE auth_throttle SET failures = 0, lockouts = 0,"
                 " locked_until = NULL WHERE key_hash = ?", (_sha256(key),))
    conn.commit()


GENERIC_FAILURE = "invalid username or password"
LOCKED_MESSAGE = "too many failed sign-in attempts — try again later"


def authenticate(conn, username: str, password: str, ip: str) -> dict:
    """Check a username + password. Throttled per account AND per client
    address with exponential backoff. The same generic message is returned
    for an unknown user, a wrong password and a disabled account."""
    raw = (username or "").strip().lower()
    ukey, ikey = f"user:{raw}", f"ip:{ip or 'unknown'}"
    wait = max(_locked_for(conn, ukey), _locked_for(conn, ikey))
    if wait:
        _audit(conn, raw or "(blank)", "anonymous", "login_blocked", None,
               {"username": raw, "reason": "locked"})
        raise AuthError(429, LOCKED_MESSAGE, retry_after=wait)
    row = conn.execute("SELECT * FROM users WHERE username = ?", (raw,)).fetchone()
    ok = False
    if row is None:
        _burn_verify(password)
        reason = "unknown_user"
    else:
        ok = verify_password(row["password_hash"], password or "")
        reason = "bad_password" if not ok else ("disabled" if row["disabled"] else "")
    if not ok or row["disabled"]:
        _audit(conn, raw or "(blank)", "anonymous", "login_failed",
               row["id"] if row is not None else None,
               {"username": raw, "reason": reason})
        for key, limit, scope in ((ukey, USER_FAIL_LIMIT, "account"),
                                  (ikey, IP_FAIL_LIMIT, "address")):
            lock_s = _record_failure(conn, key, limit)
            if lock_s:
                _audit(conn, raw or "(blank)", "anonymous", "login_lockout",
                       row["id"] if row is not None else None,
                       {"username": raw, "scope": scope, "seconds": lock_s})
        raise AuthError(401, GENERIC_FAILURE)
    if _ph.check_needs_rehash(row["password_hash"]):
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                     (hash_password(password), row["id"]))
        conn.commit()
    from . import totp
    if totp.enabled_for(conn, row["id"]):
        # Batch 009b: the password alone is NOT a sign-in for a two-step
        # account. The account's failure counter is deliberately NOT reset
        # here (only a full sign-in resets it), so a known password cannot
        # be used to keep refilling the code-guessing budget.
        _audit(conn, row["username"], row["role"], "login_password_accepted",
               row["id"], {"username": row["username"], "two_step": "pending"})
        return dict(_public(row), two_step_required=True)
    _clear_failures(conn, ukey)
    _audit(conn, row["username"], row["role"], "login_success", row["id"],
           {"username": row["username"]})
    return dict(_public(row), two_step_required=False)


# ------------------------------------------------------------------ sessions

def create_session(conn, user: dict, kind: str) -> dict:
    if kind not in ("cookie", "bearer"):
        raise ValueError("kind must be cookie or bearer")
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32) if kind == "cookie" else None
    now = _now()
    absolute = now + timedelta(hours=ABSOLUTE_HOURS)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, kind, csrf_token, created_at,"
        " last_seen_at, absolute_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (_sha256(token), user["id"], kind, csrf, _iso(now), _iso(now), _iso(absolute)))
    conn.commit()
    return {"token": token, "csrf_token": csrf, "kind": kind,
            "idle_minutes": IDLE_MINUTES, "absolute_expires_at": _iso(absolute)}


def token_hash(token: str) -> str:
    return _sha256(token)


def resolve_session(conn, token: str | None) -> tuple[dict, dict] | None:
    """Return (user, session) for a live session token, else None. Expired
    sessions are revoked on sight (idle or absolute)."""
    if not token or len(token) > 256:
        return None
    th = _sha256(token)
    s = conn.execute("SELECT * FROM sessions WHERE token_hash = ?", (th,)).fetchone()
    if s is None or s["revoked_at"]:
        return None
    now = _now()
    reason = None
    if now >= _parse(s["absolute_expires_at"]):
        reason = "absolute_expired"
    elif now - _parse(s["last_seen_at"]) > timedelta(minutes=IDLE_MINUTES):
        reason = "idle_expired"
    if reason:
        conn.execute("UPDATE sessions SET revoked_at = ?, revoked_reason = ?"
                     " WHERE token_hash = ?", (_iso(now), reason, th))
        conn.commit()
        return None
    u = conn.execute("SELECT * FROM users WHERE id = ?", (s["user_id"],)).fetchone()
    if u is None or u["disabled"]:
        return None
    if (now - _parse(s["last_seen_at"])).total_seconds() >= LAST_SEEN_RESOLUTION_S:
        conn.execute("UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?",
                     (_iso(now), th))
        conn.commit()
    return _public(u), {"token_hash": th, "kind": s["kind"],
                        "csrf_token": s["csrf_token"],
                        "absolute_expires_at": s["absolute_expires_at"]}


def csrf_ok(session: dict, presented: str | None) -> bool:
    expected = session.get("csrf_token")
    if not expected or not presented:
        return False
    return hmac.compare_digest(expected.encode(), presented.encode())


def revoke_session(conn, th: str, reason: str) -> None:
    conn.execute("UPDATE sessions SET revoked_at = ?, revoked_reason = ?"
                 " WHERE token_hash = ? AND revoked_at IS NULL",
                 (_iso(_now()), reason, th))
    conn.commit()


def revoke_user_sessions(conn, user_id: int, except_hash: str | None = None,
                         reason: str = "revoked") -> int:
    cur = conn.execute(
        "UPDATE sessions SET revoked_at = ?, revoked_reason = ? WHERE user_id = ?"
        " AND revoked_at IS NULL AND token_hash IS NOT ?",
        (_iso(_now()), reason, user_id, except_hash))
    conn.commit()
    return cur.rowcount


def logout(conn, user: dict, session: dict) -> None:
    revoke_session(conn, session["token_hash"], "logout")
    _audit(conn, user["username"], user["role"], "logout", user["id"],
           {"username": user["username"], "kind": session["kind"]})
