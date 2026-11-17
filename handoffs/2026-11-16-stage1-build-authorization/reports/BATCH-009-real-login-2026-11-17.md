# Batch 009 — real login (P0) — 2026-11-17

Approved by Josue 3:32 PM ET (relayed by Chief of Staff). Branch `feat/crm-real-login-2026-11-17`,
stacked on `fix/crm-security-data-2026-11-17` @ 964bac6 (PR #1). DRAFT PR only.
Status: **IMPLEMENTED / TESTED**. Not merged, not deployed, not hosted. Synthetic data only.

Overlay: `code/mq-crm-batch009/` (apply after batch004–008):
- `app/auth.py`: accounts, argon2id, sessions, expiry, throttle/lockout, user management, audit.
- `app/auth_cli.py`: one-time first-owner bootstrap (prompt or `--password-stdin`).
- `app/main.py`: `_AuthMiddleware` (strips X-Role/X-Actor, resolves the session, CSRF) and the
  `/api/auth/*` and `/api/users*` routes.
- `web/`: a sign-in form, the HttpOnly cookie session, X-CSRF-Token on writes; no role picker.
- `tests/test_batch9.py`: 34 new tests. `tests/conftest.py` and 11 legacy test files are
  migrated to real sign-in.
- `requirements.txt`: adds `argon2-cffi` (free, MIT).
- `docs/REAL-LOGIN.md`: the operator doc, including what's still needed before hosting.

Tests: 317 existing + 34 new = **351 passed**, 3 of 3 runs. 19 legacy test functions changed;
each one now signs in as a real user of the role it used to assert with `X-Role`. Two
assertions changed meaning (self-asserted headers now get 401, and the audit actor is the
username, e.g. `ana-staff` instead of `Ana (staff)`), and the UI test now asserts that no
`X-Role`/`X-Actor` header is ever sent.

Deliberate breaks (each one made tests fail): honour X-Role again, skip the lockout, store a
weak hash, skip server-side invalidation on logout, skip the CSRF check, remove idle expiry,
keep other sessions on password change, allow a second bootstrap, write the password to the
audit log, keep sessions on a role change, and accept a cookie token as a bearer token.

Android: not changed in this batch. The app lives on PR #2's branch. Follow-up: a
`BearerTokenAuthProvider` with a sign-in screen (the `AuthProvider` interface was built for
this).
