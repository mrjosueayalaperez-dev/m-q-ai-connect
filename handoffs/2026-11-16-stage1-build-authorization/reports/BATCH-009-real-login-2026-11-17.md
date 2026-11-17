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

## Batch 009b: owner recovery (server shell only) and two-step login (TOTP)

Josue's answers, 4:50 PM ET (relayed by Chief of Staff): keep sessions at 30 min idle / 12 h
max, keep the lockout settings, add server-shell-only owner password recovery, and add free
authenticator-app two-step login for the owner. New commit on the same branch (draft PR #3).
Status: **IMPLEMENTED / TESTED**. Not merged, deployed or hosted. Synthetic data only.

Files (overlay `code/mq-crm-batch009/`):
- `app/totp.py` (new): RFC 6238 TOTP (stdlib), AES-GCM secret at rest, recovery codes,
  pending login challenges, disable, CLI break-glass.
- `app/auth.py`: the password step no longer creates a sign-in for two-step accounts and
  doesn't reset their failure counter. `cli_reset_password()`. The owner-admin API reset
  refuses owner accounts.
- `app/auth_cli.py`: `reset-password` and `reset-totp --yes` subcommands.
- `app/main.py`: `POST /api/auth/login/verify` (open path, 401 without a live challenge),
  `GET /api/auth/totp`, `POST /api/auth/totp/{enroll,confirm,disable}`; `/me` gains
  `two_step` and an owner warning; a startup warning per owner without two-step.
- `web/`: a second sign-in step form (cookie flow).
- `tests/test_batch9b.py` (new): 18 tests. No legacy test changed.
- `requirements.txt`: adds `cryptography` (Apache-2.0 / BSD, free).
- `docs/REAL-LOGIN.md`: recovery and two-step sections, decisions, hosting checklist.

Tests: 351 existing + 18 new = **369 passed**, 3 of 3 runs (logs in the PR evidence).

Deliberate breaks (each made tests fail):
1. skip the TOTP check at login: 10 tests failed;
2. allow code replay: 1 failed (`replay_of_the_same_code_is_blocked`);
3. accept a reused recovery code: 1 failed (`recovery_code_works_exactly_once`);
4. honour a pending challenge as a session: 1 failed
   (`login_requires_code_and_password_alone_is_not_a_session`).

Decisions for Josue:
- Make owner two-step enrollment **mandatory before hosting**? It's optional now, with loud
  warnings. Recommended: yes.
- Offer two-step to staff and viewers too? It's owner-only now.
- The owner-admin API can no longer reset another **owner's** password (server shell only).
  Keep that?
- Accept a `cryptography` dependency and a second key file (`totp.key` /
  `MQ_CRM_TOTP_KEY`) that has to be backed up with the DB?

Risks:
- Android (PR #2) has no TOTP step, so an enrolled owner can't sign in from the app until
  a follow-up adds it.
- There's no enrollment UI in the web app yet (API only).
- Losing the TOTP key locks enrolled owners out until the CLI break-glass is run. That's
  fail-closed by design, but it has to be backed up.
- The CLI's power equals server-shell access, so protect the host shell.
- TOTP is phishable in real time (it isn't WebAuthn).

## Batch 009c: premium sign-in screen (presentation only)

Josue's 4:58 PM brief: a black-and-gold, two-panel enterprise sign-in, equal in EN / ES / PT / HT,
inside the existing login. **No auth logic changed**: same endpoints, payloads, sessions,
lockout, CSRF, roles and two-step. Status: IMPLEMENTED and TESTED locally; not merged, not deployed.

Files:
- `web/index.html`: new `#login-view` (brand panel + auth card, two-step step, forgot-password
  help panel, factual secure-access line); old `#login-panel` removed; scripts `safe_html.js`,
  `login_i18n.js`, `app.js`, `login.js`.
- `web/login.js` (new): sign-in and two-step UI on the existing endpoints; client validation;
  translated mapping of 401 / 429 + Retry-After / 503 / expired step / network errors; password
  cleared after every attempt; stores only the language and, if ticked, the username.
- `web/login_i18n.js` (new): 63 keys x 4 languages.
- `web/login.css` (new), `web/styles.css` (new in batch009: dashboard palette only, same selectors).
- `web/app.js`: old login / two-step handlers removed; `setSignedIn` / `setSignedOut` hand off to
  `MQLogin` (guarded); a 401 on a live session shows "your session ended".
- `tests/test_batch9c.py` (new): 12 tests. No legacy test changed.
- `docs/REAL-LOGIN.md`: "Sign-in screen" section.

Tests: 369 + 12 = **381 passed** (full suite); auth set (`test_batch9`, `9b`, `9c`,
`security_battery`) 71 passed in each of 3 runs. Deliberate breaks: missing HT key (3 failed),
token written to localStorage (1 failed), `remember` added to the login payload (1 failed).
Browser checks (headless Chromium, synthetic users): 154/154 after review fixes, covering
6 widths with no horizontal scroll, 4 languages x desktop + mobile, validation, wrong password,
lockout, show/hide, forgot panel, two-step + wrong code + recovery mode, sign-in, sign-out, Remember me,
cookie flags, tab order and focus ring.

Translations: PT (Brazilian) and HT (Kreyòl) are **pending native-speaker review**.

Decisions for Josue:
- Username vs email: the field says "Username" (accounts are usernames). Allow email sign-in?
- Remember me only remembers the username (sessions unchanged). Keep it, or remove it?

Known limitations: dynamic dashboard lists and some server messages after sign-in are still
English (pre-existing); no web TOTP enrollment UI; the favicon 404s.
