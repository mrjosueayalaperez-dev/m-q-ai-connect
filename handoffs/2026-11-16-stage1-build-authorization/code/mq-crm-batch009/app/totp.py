"""M&Q CRM — two-step login with an authenticator app (Batch 009b).

RFC 6238 TOTP (HMAC-SHA1, 6 digits, 30-second steps), implemented with the
standard library, so any free authenticator app works (Google Authenticator,
Microsoft Authenticator, Aegis, 2FAS, FreeOTP...).

Policy (see docs/REAL-LOGIN.md, "Two-step login"):
- Enrollment is for the OWNER role and is optional in this TEST-ONLY build,
  but /api/auth/me and the server log warn loudly while an active owner has
  none. Once enabled it is REQUIRED for every sign-in of that account.
- Enrollment: start (returns the secret once, as an otpauth:// URI) ->
  confirm with a valid code -> enabled, and 10 one-time recovery codes are
  shown once. The secret is never returned again.
- Login: the password alone yields a short-lived pending CHALLENGE (5 min,
  5 attempts), never a session. A valid TOTP code or an unused recovery
  code exchanges it for a session.
- +-1 time step of clock skew. A code (time step) can be used once: the
  last accepted step is stored and anything at or before it is refused.
- Wrong codes count toward the same per-account and per-address lockout as
  wrong passwords, and a correct password does NOT reset the account's
  failure counter for a two-step account (only a full sign-in does), so the
  password cannot be used to keep resetting the code-guessing budget.
- Disable: password + a valid code (API), or the server-shell break-glass
  `python -m app.auth_cli reset-totp`.

Storage:
- totp_factors.secret_enc: AES-256-GCM ciphertext of the secret
  (`cryptography`, Apache-2.0/BSD), associated data bound to the user id.
  Key: MQ_CRM_TOTP_KEY if set, else <db dir>/totp.key (random, mode 0600,
  created only while no factor exists). A non-secret check value per row
  detects a wrong key; a missing / wrong key fails CLOSED (the owner cannot
  sign in; break-glass with the CLI) — it never skips the second step.
- recovery_codes.code_hash: SHA-256(salt:code); codes carry 80 random bits.
- login_challenges.token_hash: SHA-256 of the challenge token.
Never stored or logged in clear: the secret, codes, recovery codes,
challenge tokens.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
import struct
from datetime import timedelta
from urllib.parse import quote

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import auth

log = logging.getLogger("mq_crm.totp")

ISSUER = "M&Q CRM"
DIGITS = 6
PERIOD = 30
SKEW_STEPS = 1                  # accept the previous / next step too
CHALLENGE_SECONDS = 300         # pending second-step window
CHALLENGE_MAX_ATTEMPTS = 5      # wrong codes per challenge before it dies
RECOVERY_CODE_COUNT = 10
ENROLL_ROLES = ("owner",)

KEY_ENV = "MQ_CRM_TOTP_KEY"
KEY_FILE_NAME = "totp.key"
_KEY_CHECK_LABEL = b"mq-crm/totp-key-check/v1"
_MEM_KEY: bytes | None = None


class TotpKeyError(RuntimeError):
    """The TOTP encryption key is missing or does not match the database."""


# ------------------------------------------------------------------ schema

def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS totp_factors ("
        " user_id INTEGER PRIMARY KEY REFERENCES users(id),"
        " secret_enc TEXT NOT NULL, key_check TEXT NOT NULL,"
        " enabled INTEGER NOT NULL DEFAULT 0,"
        " created_at TEXT NOT NULL, enabled_at TEXT,"
        " last_used_step INTEGER NOT NULL DEFAULT -1)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS recovery_codes ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " user_id INTEGER NOT NULL REFERENCES users(id),"
        " salt TEXT NOT NULL, code_hash TEXT NOT NULL,"
        " created_at TEXT NOT NULL, used_at TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS login_challenges ("
        " token_hash TEXT PRIMARY KEY,"
        " user_id INTEGER NOT NULL REFERENCES users(id),"
        " kind TEXT NOT NULL CHECK (kind IN ('cookie', 'bearer')),"
        " created_at TEXT NOT NULL, expires_at TEXT NOT NULL,"
        " attempts INTEGER NOT NULL DEFAULT 0, consumed_at TEXT)")
    conn.commit()


# ------------------------------------------------------------------ RFC 4226 / 6238

def hotp(key: bytes, counter: int, digits: int = DIGITS) -> str:
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    off = mac[-1] & 0x0F
    val = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return f"{val:0{digits}d}"


def _step(ts: float | None = None) -> int:
    if ts is None:
        ts = auth._now().timestamp()
    return int(ts // PERIOD)


def _b32(raw: bytes) -> str:
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _unb32(s: str) -> bytes:
    s = s.strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def _clean_code(code) -> str | None:
    if not isinstance(code, str):
        return None
    c = code.strip().replace(" ", "").replace("-", "")
    return c if len(c) == DIGITS and c.isdigit() else None


def _match_step(secret: bytes, code: str, last_used_step: int) -> int | None:
    """The time step `code` is valid for (within +-SKEW_STEPS) and newer than
    the last accepted one, else None. Constant-time comparisons."""
    now = _step()
    hit = None
    for s in range(now - SKEW_STEPS, now + SKEW_STEPS + 1):
        if hmac.compare_digest(hotp(secret, s), code) and s > last_used_step:
            hit = s
    return hit


# ------------------------------------------------------------------ secret at rest

def _key_file(conn) -> str | None:
    row = conn.execute("PRAGMA database_list").fetchone()
    path = row["file"] if row is not None else ""
    return os.path.join(os.path.dirname(path), KEY_FILE_NAME) if path else None


def _any_factor(conn) -> bool:
    return conn.execute("SELECT 1 FROM totp_factors LIMIT 1").fetchone() is not None


def _load_key(conn, create: bool) -> bytes:
    env = os.environ.get(KEY_ENV)
    if env:
        return hashlib.sha256(b"mq-crm/totp-key/v1|" + env.encode("utf-8")).digest()
    kp = _key_file(conn)
    if kp is None:
        global _MEM_KEY
        if _MEM_KEY is None:
            _MEM_KEY = secrets.token_bytes(32)
        return _MEM_KEY
    if os.path.exists(kp):
        with open(kp, "r", encoding="ascii") as f:
            return bytes.fromhex(f.read().strip())
    if not create or _any_factor(conn):
        raise TotpKeyError(
            f"two-step key missing: neither {KEY_ENV} nor {kp} is present but this"
            " database holds enrolled two-step factors. Restore the key file from"
            " the backup taken with the database, or use the server-shell"
            " break-glass `python -m app.auth_cli reset-totp --username <name>`.")
    fd = os.open(kp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(secrets.token_bytes(32).hex())
    with open(kp, "r", encoding="ascii") as f:
        return bytes.fromhex(f.read().strip())


def _check(key: bytes) -> str:
    return hmac.new(key, _KEY_CHECK_LABEL, hashlib.sha256).hexdigest()[:32]


def _seal(conn, user_id: int, secret: bytes) -> tuple[str, str]:
    key = _load_key(conn, create=True)
    nonce = secrets.token_bytes(12)
    ct = AESGCM(key).encrypt(nonce, secret, f"totp:{user_id}".encode())
    return "v1:" + base64.b64encode(nonce + ct).decode("ascii"), _check(key)


def _open(conn, row) -> bytes:
    key = _load_key(conn, create=False)
    if not hmac.compare_digest(_check(key), row["key_check"]):
        raise TotpKeyError("two-step key does not match this database — restore"
                           " the right key, or use the CLI break-glass reset-totp")
    blob = base64.b64decode(row["secret_enc"].split(":", 1)[1])
    return AESGCM(key).decrypt(blob[:12], blob[12:], f"totp:{row['user_id']}".encode())


# ------------------------------------------------------------------ status

def _factor(conn, user_id: int):
    return conn.execute("SELECT * FROM totp_factors WHERE user_id = ?",
                        (user_id,)).fetchone()


def enabled_for(conn, user_id: int) -> bool:
    r = _factor(conn, user_id)
    return bool(r is not None and r["enabled"])


def status(conn, user: dict) -> dict:
    r = _factor(conn, user["id"])
    left = conn.execute("SELECT COUNT(*) AS n FROM recovery_codes WHERE user_id = ?"
                        " AND used_at IS NULL", (user["id"],)).fetchone()["n"]
    return {"enabled": bool(r is not None and r["enabled"]),
            "pending_enrollment": bool(r is not None and not r["enabled"]),
            "enabled_at": r["enabled_at"] if r is not None else None,
            "recovery_codes_remaining": left if (r is not None and r["enabled"]) else 0,
            "available_for_role": user["role"] in ENROLL_ROLES}


def owners_without_two_step(conn) -> list[str]:
    return [r["username"] for r in conn.execute(
        "SELECT u.username FROM users u LEFT JOIN totp_factors t"
        " ON t.user_id = u.id AND t.enabled = 1"
        " WHERE u.role = 'owner' AND u.disabled = 0 AND t.user_id IS NULL"
        " ORDER BY u.id")]


# ------------------------------------------------------------------ enrollment

def start_enrollment(conn, user: dict) -> dict:
    if user["role"] not in ENROLL_ROLES:
        raise auth.AuthError(403, "two-step login is available for the owner role")
    if enabled_for(conn, user["id"]):
        raise auth.AuthError(409, "two-step login is already enabled — disable it"
                                  " first to enroll a new device")
    raw = secrets.token_bytes(20)          # 160-bit secret (RFC 4226 recommendation)
    try:
        enc, chk = _seal(conn, user["id"], raw)
    except TotpKeyError as e:
        raise auth.AuthError(503, str(e))
    at = auth._iso(auth._now())
    conn.execute("DELETE FROM totp_factors WHERE user_id = ?", (user["id"],))
    conn.execute("INSERT INTO totp_factors (user_id, secret_enc, key_check, enabled,"
                 " created_at) VALUES (?, ?, ?, 0, ?)", (user["id"], enc, chk, at))
    conn.commit()
    auth._audit(conn, user["username"], user["role"], "totp_enroll_started",
                user["id"], {"username": user["username"]})
    secret = _b32(raw)
    label = quote(f"{ISSUER}:{user['username']}", safe="")
    uri = (f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER, safe='')}"
           f"&algorithm=SHA1&digits={DIGITS}&period={PERIOD}")
    return {"otpauth_uri": uri, "secret": secret, "digits": DIGITS,
            "period": PERIOD, "algorithm": "SHA1",
            "next": "add it to an authenticator app, then POST /api/auth/totp/confirm"
                    " with a current code. This secret is shown only now."}


def _new_recovery_codes(conn, user_id: int) -> list[str]:
    conn.execute("DELETE FROM recovery_codes WHERE user_id = ?", (user_id,))
    at = auth._iso(auth._now())
    out = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = _b32(secrets.token_bytes(10)).lower()          # 80 bits, 16 chars
        code = "-".join(raw[i:i + 4] for i in range(0, 16, 4))
        salt = secrets.token_hex(8)
        conn.execute("INSERT INTO recovery_codes (user_id, salt, code_hash, created_at)"
                     " VALUES (?, ?, ?, ?)", (user_id, salt, _rc_hash(salt, code), at))
        out.append(code)
    conn.commit()
    return out


def _rc_norm(code: str) -> str:
    return (code or "").strip().lower().replace("-", "").replace(" ", "")


def _rc_hash(salt: str, code: str) -> str:
    return hashlib.sha256(f"{salt}:{_rc_norm(code)}".encode()).hexdigest()


def confirm_enrollment(conn, user: dict, code: str,
                       keep_session_hash: str | None) -> dict:
    r = _factor(conn, user["id"])
    if r is None or r["enabled"]:
        raise auth.AuthError(409, "no pending two-step enrollment — start one first")
    try:
        secret = _open(conn, r)
    except TotpKeyError as e:
        raise auth.AuthError(503, str(e))
    c = _clean_code(code)
    step = _match_step(secret, c, r["last_used_step"]) if c else None
    if step is None:
        auth._audit(conn, user["username"], user["role"], "totp_enroll_confirm_failed",
                    user["id"], {"username": user["username"], "reason": "bad_code"})
        raise auth.AuthError(400, "that code is not valid — check the device clock"
                                  " and enter the current 6-digit code")
    at = auth._iso(auth._now())
    conn.execute("UPDATE totp_factors SET enabled = 1, enabled_at = ?, last_used_step = ?"
                 " WHERE user_id = ?", (at, step, user["id"]))
    conn.commit()
    codes = _new_recovery_codes(conn, user["id"])
    n = auth.revoke_user_sessions(conn, user["id"], except_hash=keep_session_hash,
                                  reason="two_step_enabled")
    auth._audit(conn, user["username"], user["role"], "totp_enabled", user["id"],
                {"username": user["username"], "recovery_codes_issued": len(codes),
                 "other_sessions_revoked": n})
    return {"enabled": True, "recovery_codes": codes,
            "note": "store these one-time recovery codes offline; each works once."
                    " They are shown only now."}


# ------------------------------------------------------------------ second factor check

def _verify_second_factor(conn, row_user, code, recovery_code) -> str | None:
    """'totp' / 'recovery_code' if valid (and consumes it), else None."""
    f = _factor(conn, row_user["id"])
    if f is None or not f["enabled"]:
        return None
    if code is not None:
        c = _clean_code(code)
        if not c:
            return None
        try:
            secret = _open(conn, f)
        except TotpKeyError as e:
            raise auth.AuthError(503, str(e))
        step = _match_step(secret, c, f["last_used_step"])
        if step is None:
            return None
        cur = conn.execute("UPDATE totp_factors SET last_used_step = ? WHERE user_id = ?"
                           " AND last_used_step < ?", (step, row_user["id"], step))
        conn.commit()
        return "totp" if cur.rowcount == 1 else None
    if recovery_code is not None:
        norm = _rc_norm(recovery_code)
        if len(norm) != 16:
            return None
        for rc in conn.execute("SELECT * FROM recovery_codes WHERE user_id = ?"
                               " AND used_at IS NULL", (row_user["id"],)).fetchall():
            if hmac.compare_digest(rc["code_hash"], _rc_hash(rc["salt"], norm)):
                cur = conn.execute("UPDATE recovery_codes SET used_at = ? WHERE id = ?"
                                   " AND used_at IS NULL",
                                   (auth._iso(auth._now()), rc["id"]))
                conn.commit()
                return "recovery_code" if cur.rowcount == 1 else None
    return None


def _count_failure(conn, raw: str, ip: str, user_id: int | None) -> None:
    for key, limit, scope in ((f"user:{raw}", auth.USER_FAIL_LIMIT, "account"),
                              (f"ip:{ip or 'unknown'}", auth.IP_FAIL_LIMIT, "address")):
        lock_s = auth._record_failure(conn, key, limit)
        if lock_s:
            auth._audit(conn, raw, "anonymous", "login_lockout", user_id,
                        {"username": raw, "scope": scope, "seconds": lock_s})


# ------------------------------------------------------------------ login

CHALLENGE_INVALID = "sign-in step expired or invalid — sign in with your password again"
CODE_INVALID = "invalid code"


def begin_login(conn, user: dict, kind: str) -> dict:
    if kind not in ("cookie", "bearer"):
        raise ValueError("kind must be cookie or bearer")
    token = secrets.token_urlsafe(32)
    now = auth._now()
    exp = now + timedelta(seconds=CHALLENGE_SECONDS)
    conn.execute("UPDATE login_challenges SET consumed_at = ? WHERE user_id = ?"
                 " AND consumed_at IS NULL", (auth._iso(now), user["id"]))
    conn.execute("INSERT INTO login_challenges (token_hash, user_id, kind, created_at,"
                 " expires_at) VALUES (?, ?, ?, ?, ?)",
                 (auth._sha256(token), user["id"], kind, auth._iso(now), auth._iso(exp)))
    conn.commit()
    auth._audit(conn, user["username"], user["role"], "login_two_step_pending",
                user["id"], {"username": user["username"]})
    return {"challenge": token, "expires_in": CHALLENGE_SECONDS,
            "methods": ["totp", "recovery_code"]}


def complete_login(conn, challenge: str, code: str | None,
                   recovery_code: str | None, ip: str) -> tuple[dict, str]:
    """(user, session kind) after a valid second factor; raises AuthError."""
    if not challenge or len(challenge) > 256:
        raise auth.AuthError(401, CHALLENGE_INVALID)
    th = auth._sha256(challenge)
    ch = conn.execute("SELECT * FROM login_challenges WHERE token_hash = ?",
                      (th,)).fetchone()
    if ch is None or ch["consumed_at"]:
        raise auth.AuthError(401, CHALLENGE_INVALID)
    row = conn.execute("SELECT * FROM users WHERE id = ?", (ch["user_id"],)).fetchone()
    now = auth._now()
    if now >= auth._parse(ch["expires_at"]) or row is None or row["disabled"]:
        conn.execute("UPDATE login_challenges SET consumed_at = ? WHERE token_hash = ?",
                     (auth._iso(now), th))
        conn.commit()
        if row is not None:
            auth._audit(conn, row["username"], "anonymous", "login_two_step_failed",
                        row["id"], {"username": row["username"],
                                    "reason": "challenge_expired" if not row["disabled"]
                                    else "disabled"})
        raise auth.AuthError(401, CHALLENGE_INVALID)
    raw = row["username"]
    wait = max(auth._locked_for(conn, f"user:{raw}"),
               auth._locked_for(conn, f"ip:{ip or 'unknown'}"))
    if wait:
        auth._audit(conn, raw, "anonymous", "login_blocked", row["id"],
                    {"username": raw, "reason": "locked", "step": "two_step"})
        raise auth.AuthError(429, auth.LOCKED_MESSAGE, retry_after=wait)
    method = _verify_second_factor(conn, row, code, recovery_code)
    if method is None:
        attempts = ch["attempts"] + 1
        conn.execute("UPDATE login_challenges SET attempts = ?, consumed_at = ?"
                     " WHERE token_hash = ?",
                     (attempts, auth._iso(now) if attempts >= CHALLENGE_MAX_ATTEMPTS
                      else None, th))
        conn.commit()
        auth._audit(conn, raw, "anonymous", "login_two_step_failed", row["id"],
                    {"username": raw, "reason": "bad_code",
                     "method": "recovery_code" if recovery_code is not None else "totp",
                     "attempt": attempts})
        _count_failure(conn, raw, ip, row["id"])
        raise auth.AuthError(401, CODE_INVALID)
    conn.execute("UPDATE login_challenges SET consumed_at = ? WHERE token_hash = ?",
                 (auth._iso(now), th))
    conn.commit()
    auth._clear_failures(conn, f"user:{raw}")
    if method == "recovery_code":
        left = conn.execute("SELECT COUNT(*) AS n FROM recovery_codes WHERE user_id = ?"
                            " AND used_at IS NULL", (row["id"],)).fetchone()["n"]
        auth._audit(conn, raw, row["role"], "recovery_code_used", row["id"],
                    {"username": raw, "remaining": left})
    auth._audit(conn, raw, row["role"], "login_success", row["id"],
                {"username": raw, "two_step": method})
    return auth._public(row), ch["kind"]


# ------------------------------------------------------------------ disable / break-glass

def _wipe(conn, user_id: int) -> None:
    conn.execute("DELETE FROM totp_factors WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM recovery_codes WHERE user_id = ?", (user_id,))
    conn.execute("UPDATE login_challenges SET consumed_at = ? WHERE user_id = ?"
                 " AND consumed_at IS NULL", (auth._iso(auth._now()), user_id))
    conn.commit()


def disable(conn, user: dict, password: str, code: str | None,
            recovery_code: str | None, ip: str) -> None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    if not enabled_for(conn, user["id"]):
        if _factor(conn, user["id"]) is not None:       # abandon a pending enrollment
            _wipe(conn, user["id"])
            return
        raise auth.AuthError(409, "two-step login is not enabled")
    wait = max(auth._locked_for(conn, f"user:{row['username']}"),
               auth._locked_for(conn, f"ip:{ip or 'unknown'}"))
    if wait:
        raise auth.AuthError(429, auth.LOCKED_MESSAGE, retry_after=wait)
    ok_pw = auth.verify_password(row["password_hash"], password or "")
    method = _verify_second_factor(conn, row, code, recovery_code) if ok_pw else None
    if not ok_pw or method is None:
        auth._audit(conn, row["username"], row["role"], "totp_disable_failed", row["id"],
                    {"username": row["username"],
                     "reason": "bad_password" if not ok_pw else "bad_code"})
        _count_failure(conn, row["username"], ip, row["id"])
        raise auth.AuthError(403, "password and a valid code are both required")
    _wipe(conn, user["id"])
    auth._audit(conn, row["username"], row["role"], "totp_disabled", row["id"],
                {"username": row["username"], "source": "api", "verified_with": method})


def cli_reset(conn, username: str) -> dict:
    """Server-shell break-glass (lost phone): remove the factor and recovery
    codes, end every session and pending challenge. Audited, no secrets."""
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        raise LookupError("user not found")
    had = _factor(conn, row["id"]) is not None
    _wipe(conn, row["id"])
    n = auth.revoke_user_sessions(conn, row["id"], reason="two_step_reset")
    auth._audit(conn, "server-cli", "system", "totp_reset", row["id"],
                {"username": row["username"], "source": "cli", "had_factor": had,
                 "sessions_revoked": n})
    return {"username": row["username"], "had_factor": had, "sessions_revoked": n}
