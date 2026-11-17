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
`POST /api/users/{id}/password {new_password}`

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
8. **Owner recovery:** decide on a break-glass path if the only owner loses their password
   (not implemented).
9. **Android:** plug its `AuthProvider` into bearer login (follow-up on PR #2), and use
   HTTPS only.
10. Synthetic data only until the data-processing terms are approved.
