# M&Q CRM — real login (Batch 009)

Status: IMPLEMENTED / TESTED locally with synthetic data. Not merged, not deployed, not hosted.

## What changed

- **The role comes only from a logged-in user.** Every `/api` request is authenticated
  from a server-side session. The `X-Role` and `X-Actor` request headers are **stripped
  before routing and never trusted**, in any mode. There is no test mode and no header
  fallback. The audit "actor" is now the signed-in username.
- **Deny by default.** No session → `401` (with `WWW-Authenticate: Bearer`). Wrong role →
  `403`. The only open routes are `GET /api/health` (returns no data) and
  `POST /api/auth/login`.
- **Roles are unchanged.** `owner`, `staff` and `viewer` map onto the existing permissions
  exactly: any role can read, owner and staff can write, and owner-only routes stay
  owner-only (export, deletion, suppression list/key status, audit recovery, register
  changes, user management).

## Sessions

| Client | How it signs in | What it sends |
|---|---|---|
| Web UI | `POST /api/auth/login {"username","password","mode":"cookie"}` | `mq_session` cookie (HttpOnly, Secure, SameSite=Strict, Path=/api) + `X-CSRF-Token` on every write |
| Android / API | `POST /api/auth/login {..., "mode":"token"}` | `Authorization: Bearer <token>` |

- Tokens are 256-bit random values. Only their **SHA-256** is stored (`sessions.token_hash`);
  the token itself is never stored or logged.
- **Expiry:** an idle timeout (default 30 min) plus an absolute limit (default 12 h). Set them
  with `MQ_CRM_SESSION_IDLE_MINUTES` (bounded to 5–240) and `MQ_CRM_SESSION_MAX_HOURS`
  (bounded to 1–72). Expired sessions are revoked when next presented.
- **Logout** (`POST /api/auth/logout`) revokes the session server-side.
- **Password change** (`POST /api/auth/password`, needs the current password) signs out
  every *other* session. An **owner reset** (`POST /api/users/{id}/password`) signs out *all*
  of that user's sessions. A **role change** or **disable** also signs out all of that user's
  sessions.
- A cookie session cannot be replayed as a bearer token, and vice versa.

## CSRF

Cookie-authenticated `POST`/`PUT`/`PATCH`/`DELETE` requests must carry the per-session CSRF
token in `X-CSRF-Token`. A request whose `Origin` doesn't match the host is refused.
`GET /api/auth/me` returns the token to same-origin JavaScript after a page reload. No CORS
is configured, so other sites can't read it. Bearer requests aren't CSRF-able, because
browsers never attach them automatically.

## Passwords and lockout

- Hashing uses **argon2id** (`argon2-cffi`; 64 MiB, t=3, p=2). Any stored value that isn't an
  argon2id hash is never accepted.
- **Policy:** 12–256 characters, at least 5 distinct characters, not a common password, and
  must not contain the username.
- **Throttling:** 5 consecutive failures lock the **account**, and 20 failures in 15 min lock
  the **client address**. The lock starts at 60 s and doubles on each repeat, up to 1 h; locked
  sign-ins get `429` + `Retry-After`. Unknown usernames are throttled the same way, and an
  unknown user, a wrong password and a disabled account all get the same message, so usernames
  can't be enumerated. Throttle keys are stored as SHA-256 (no raw IP addresses).

## Audit

`login_success`, `login_failed` (reason code), `login_blocked`, `login_lockout`, `logout`,
`user_created`, `role_changed`, `user_disabled`, `user_enabled`, `password_changed`,
`password_change_failed`, `password_reset` and `owner_bootstrapped` are written to the
hash-chained audit log and to the `mq_crm.auth` logger. They record **usernames and reason
codes only**, never passwords, tokens, session ids or CSRF tokens.

## First owner (one time, no default password)

There is no default account, no default password and no HTTP setup route. On the server,
against the same database the API uses:

```bash
MQ_CRM_DB=/path/to/crm.db python -m app.auth_cli create-owner --username <name>
#   prompts twice for the password (not echoed)
# or, non-interactive:
#   printf '%s\n' "$PW" | python -m app.auth_cli create-owner --username <name> --password-stdin
```

It refuses once any owner exists. Until then the API logs a loud warning at startup and denies
every request. After bootstrap, the owner creates staff/viewer accounts in the app
(`POST /api/users`), changes roles, disables accounts and resets passwords. The last active
owner can't be demoted or disabled.

## User management API (owner only)

`GET /api/users` · `POST /api/users {username,password,role,display_name}` ·
`POST /api/users/{id}/role {role}` · `POST /api/users/{id}/disable` · `POST /api/users/{id}/enable` ·
`POST /api/users/{id}/password {new_password}`. Batch 009b: that admin reset refuses **owner**
accounts (403). An owner's password is reset only from the server shell (below) or changed
by that owner (`POST /api/auth/password`, needs the current password).

## Password recovery: server shell only (Batch 009b)

Josue's decision (4:50 PM ET): no web, email or API password-recovery path. Recovery is a
server-shell command against the same database (`MQ_CRM_DB`):

```bash
python -m app.auth_cli reset-password --username <name>            # prompts twice, not echoed
printf '%s\n' "$NEW_PW" | python -m app.auth_cli reset-password --username <name> --password-stdin
```

It applies the password policy, revokes **every** session of the account and any pending
two-step challenge, clears the account's lockout, and writes an audit entry
(`password_reset`, actor `server-cli`, `source: cli`, session count; never the password).
It does **not** change two-step login. A test asserts there's no forgot / reset / recover
route, that guessed reset URLs are 401 (anonymous) or 404/405 (signed in), that the only
password routes are "change your own" and "owner resets a non-owner", and that the app has
no e-mail sending code.

## Two-step login with an authenticator app (Batch 009b)

RFC 6238 TOTP (SHA-1, 6 digits, 30-second steps), implemented with the standard library
(`app/totp.py`), so any free authenticator app works (Google or Microsoft Authenticator,
Aegis, 2FAS, FreeOTP). No paid service. QR code: not generated server-side; paste the
`otpauth://` URI or the secret into the app, or render the URI with any free/offline QR tool.

**Policy (decision for Josue):** available to the **owner** role. Once enabled it's
**required** on every sign-in of that account. Enrollment is **optional** in this TEST-ONLY
build, but it's warned about loudly: `/api/auth/me` returns
`warnings: ["owner_two_step_not_enrolled"]` and the server logs a WARNING at start-up for
each active owner without it. **Recommended: make enrollment mandatory for owners before any
hosted test server.** Staff and viewer sign-in is unchanged.

Enrollment (signed in as the owner; cookie sessions need the CSRF header as usual):
1. `POST /api/auth/totp/enroll` returns `{otpauth_uri, secret, digits, period}` **once**
   (`Cache-Control: no-store`). Repeating it replaces a pending enrollment. It's refused
   (409) while two-step is already enabled.
2. `POST /api/auth/totp/confirm {code}` with a current code enables it and returns
   **10 one-time recovery codes, once**. Other sessions of the account are signed out; the
   current one stays.
3. `GET /api/auth/totp` shows status and the recovery codes left, never the secret.

Sign-in for an enrolled owner is two steps:
1. `POST /api/auth/login {username,password,mode}` returns
   `{two_step_required: true, challenge, challenge_expires_in: 300, methods}`. That's
   **no session, no cookie, no token**. The challenge only works at the next endpoint; a
   test checks it's refused as a bearer token or cookie everywhere.
2. `POST /api/auth/login/verify {challenge, code}` or `{challenge, recovery_code}`
   returns the normal login response (bearer token or cookie + CSRF, per the `mode`
   chosen in step 1).

Rules:
- **Clock skew:** ±1 step (±30 s) is accepted; ±2 isn't.
- **Replay:** the last accepted time step is stored, and a code for that step or any
  earlier one is refused, so the same code can't be used twice.
- **Wrong codes count toward the lockout** (the same per-account and per-address counters
  as wrong passwords: 5 per account, 20 per address, backoff). A correct password does
  **not** reset the account's failure counter for a two-step account (only a full sign-in
  does), so a stolen password can't keep refilling the guessing budget. Each challenge
  also dies after 5 wrong codes, or **5 minutes**.
- **Recovery codes:** 10 codes of 80 random bits (`xxxx-xxxx-xxxx-xxxx`), stored as
  salted SHA-256, each usable once (atomic). Using one is audited with the count left.
- **Disable:** `POST /api/auth/totp/disable {password, code | recovery_code}` needs
  **both**. Wrong attempts are audited and count toward the lockout.
- **Break-glass (lost phone):** `python -m app.auth_cli reset-totp --username <name> --yes`
  removes the factor and recovery codes and signs the account out everywhere. Audited
  (`totp_reset`, actor `server-cli`, `source: cli`). Without `--yes` it refuses.

Storage and keys:
- The secret is encrypted at rest with AES-256-GCM (`cryptography`, Apache-2.0/BSD,
  free), with associated data binding it to the user id. It's never returned after
  enrollment and never logged (tested against logs, audit rows, every auth table and
  API responses).
- Key: `MQ_CRM_TOTP_KEY` (env, preferred on a host) or `<db dir>/totp.key` (random,
  mode 0600, created only while no factor exists). **Back it up with the database**, like
  the suppression key. A missing or wrong key **fails closed**: an enrolled owner gets 503
  with the break-glass instructions and never a session without the second step. A per-row,
  non-secret check value detects a wrong key.
- Audit actions (never a secret, code, recovery code or challenge): `totp_enroll_started`,
  `totp_enroll_confirm_failed`, `totp_enabled`, `login_password_accepted`,
  `login_two_step_pending`, `login_two_step_failed` (reason `bad_code` /
  `challenge_expired`), `login_success` (with `two_step: totp | recovery_code`),
  `recovery_code_used`, `totp_disable_failed`, `totp_disabled`, `totp_reset`,
  `login_lockout`.
- Web UI: the sign-in form now asks for the code when the server requires it (cookie
  flow). Enrollment is API-only for now (follow-up: an owner Settings screen).
- **Android (PR #2, 547a645) has no TOTP step yet.** An enrolled owner can't sign in from
  the app until a follow-up adds the second step there. Staff and viewers are unaffected.

## Unchanged

Opt-out, retained suppression (do-not-message), suppression-key fail-closed checks, and
human approval of every message (including the one opt-out confirmation) are untouched. The
tests show they hold under real sessions.

## Still needed before a hosted HTTPS test server (separate approval)

1. **TLS** at the host or proxy (HTTPS only, HSTS). The session cookie is `Secure`, so
   the web UI only keeps a session over HTTPS (or `http://localhost` in most browsers).
2. **Client address behind a proxy:** the throttle uses the direct peer address. Behind
   a reverse proxy, configure trusted proxy headers, or every user shares one address
   bucket.
3. **Secrets and keys on the host:** the suppression key goes in the platform's secret store
   or env (`MQ_CRM_SUPPRESSION_KEY`), never in the repo or image. Bootstrap the owner over the
   host shell.
4. **Backups:** back up the DB and suppression key per `SUPPRESSION-KEY-BACKUP-RESTORE.md`,
   stored separately and encrypted. User and session tables are in the same DB.
5. **CORS** stays off (same-origin). If it's ever enabled, never combine wildcard origins
   with credentials.
6. **Logging:** set `mq_crm.auth` to INFO and keep request headers out of access logs.
7. **Edge rate limiting** in front of `/api/auth/login` (argon2 is deliberately expensive).
8. **Owner recovery:** done in Batch 009b (server-shell `reset-password` / `reset-totp`).
   The host needs shell access limited to the owner or operator.
9. **Android:** bearer login is on PR #2 (547a645). The TOTP second step is a follow-up.
   Use HTTPS only.
11. **Two-step:** decide whether owner enrollment becomes mandatory before hosting
    (recommended), and keep `MQ_CRM_TOTP_KEY` in the host's secret store with backups.
10. Synthetic data only until the data-processing terms are approved.
