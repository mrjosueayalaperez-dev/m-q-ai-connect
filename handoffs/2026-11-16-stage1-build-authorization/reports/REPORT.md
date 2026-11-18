# First-Run Bootstrap Fix — Report

**Date:** 2026-11-18 · **Ordered by:** the founder (after hitting the dead end himself on the live deployment)
**Scope:** local code + tests only. Nothing deployed, nothing pushed, no live system touched.
**Trees modified in place (deployment sources):** `~/workspace/mq-ai-command-dashboard/` and `~/workspace/crm-run/`

---

## The problem

Both products created their first owner only from the server shell
(`python -m app.auth_cli create-owner`). On a fresh deployment the public
sign-in page exists but no account does, so every sign-in attempt failed
with "incorrect credentials" and the page offered no path forward.

## The design, as built (identical shape in both codebases)

### Endpoints

| Endpoint | Behavior |
|---|---|
| `GET /api/auth/bootstrap` | Public. Returns exactly `{"owner_exists": true\|false}` — one boolean, nothing else disclosed. `Cache-Control: no-store`. |
| `POST /api/auth/bootstrap` | Public, body `{username, password, mode}` (`mode` = `"cookie"` default, or `"token"`, same convention as login). Creates the **first** owner and signs them in, returning the exact response the normal login flow returns (cookie session + CSRF token, or bearer token). Added to each app's `OPEN_PATHS`. |

### Refusal semantics

- If **any** owner already exists, POST refuses with **403** and creates
  nothing — permanently. There is no standing public registration: after
  bootstrap, accounts are created by the owner inside the app, exactly
  as before. (403 matches each codebase's existing "owner-only /
  forbidden" convention, e.g. the owner-password-reset refusal.)
- Password/username validation failures return **400** and create
  nothing, so a refused attempt leaves first-run setup available.
- The check-and-create is serialized in `auth.bootstrap_owner_web()` by
  a process-wide lock plus a `BEGIN IMMEDIATE` write transaction, so two
  simultaneous first-run requests cannot both succeed on the
  single-worker deployment.
- The CLI path (`auth.bootstrap_owner` / `app.auth_cli create-owner`)
  is untouched and fully intact; each path also closes the other (a
  web-created owner makes the CLI refuse, and vice versa — both tested).

### Password policy

Reused, not duplicated: web bootstrap calls the same
`create_user() → validate_password()` as the CLI path (12–256 chars,
common-password list, ≥5 distinct characters, no username containment,
same username rules). Tests assert the endpoint rejects exactly the
passwords `auth.validate_password` rejects.

### Audit

Creation is written to each product's hash-chained audit log by the
existing audit path: a `user_created` entry plus an `owner_bootstrapped`
entry whose **actor is `web-bootstrap`** and whose detail carries
`{"username": ..., "source": "web-bootstrap"}`. Tests verify the entry
and that the audit chain still verifies end-to-end.

### Web UI

- **Command Dashboard:** the sign-in overlay checks
  `GET /api/auth/bootstrap` whenever the sign-in gate is shown. If no
  owner exists, the sign-in form is swapped for a "Create the owner
  account" form (username, password, confirm password, one-time-setup
  explainer). Client-side confirm-mismatch is caught before posting;
  server refusal detail (e.g. the exact policy rule) is shown on error.
  Once an owner exists the form is never rendered.
- **CRM:** `login.js` checks the same endpoint on load (and the
  signed-out path respects it). If no owner exists, the setup form
  replaces the sign-in form inside the existing auth card; errors are
  mapped to the page's localized string keys by status (403 → "owner
  already exists", 400 → policy failure, plus the shared lockout /
  network / server keys). On success it hands off to the existing
  `finish()` sign-in completion.
- The CRM's error-translation catalog (`app/error_i18n.py`) gained the
  new refusal message in ES/PT/HT, so API error text stays fully
  translated (its coverage test requires this of every raised message).

---

## Test results (exact counts)

| Suite | Before | After | New tests |
|---|---|---|---|
| M&Q AI Command Dashboard (`~/.venvs/cmd-dash`) | 116 passed | **129 passed** | 13 in `tests/test_bootstrap.py` |
| M&Q CRM (`~/.venvs/moose-crm-verify`, from `~/workspace/crm-run`) | 477 passed | **490 passed** | 13 in `tests/test_bootstrap.py` |

New-test coverage in both suites: status endpoint truthful before/after
(and discloses only the boolean) · bootstrap succeeds on an empty
install and signs in (cookie **and** token modes) · refusal on a second
call immediately after the first, with proof the second account was not
created · refusal when the owner was created via CLI, and CLI refusal
after a web bootstrap · password policy parity with the CLI path
(too short, too long, common, too few distinct characters,
username containment) · bad username → 400, nothing created · audit
entry present with source `web-bootstrap` and chain verification OK ·
four-language catalog parity (existing parity tests, extended catalogs).

### Pre-existing tests updated for the new surface (3 CRM, 0 Command)

The fix intentionally changes the public surface three CRM tests had
pinned; each was updated with a dated comment, none deleted:

- `tests/test_batch9b.py` and `tests/test_batch9c.py` (A2): `OPEN_PATHS`
  expectation now includes `/api/auth/bootstrap`.
- `tests/test_batch9c.py` (S2): the sign-in client's endpoint set now
  includes `/api/auth/bootstrap`.
- `tests/test_batch9.py` (G): "no HTTP bootstrap route" rewritten to the
  new contract — the route exists but refuses (403) while an owner
  exists, in both directions (HTTP and function level).
- `tests/test_batch8.py` (B8.2): the deny-by-default route sweep now
  skips `/api/auth/bootstrap` alongside `/api/health` and
  `/api/auth/login`, with a comment pointing at the new coverage.

---

## Changed files

### M&Q AI Command Dashboard (`~/workspace/mq-ai-command-dashboard/`)

| File | Change |
|---|---|
| `app/auth.py` | Added `bootstrap_owner_web()` (lock + write-transaction check-and-create, actor/source `web-bootstrap`); `threading` import; CLI `bootstrap_owner` docstring updated. |
| `app/main.py` | `/api/auth/bootstrap` added to `OPEN_PATHS`; `BootstrapIn` model; GET status + POST create-and-sign-in routes next to login; startup warning now mentions the sign-in-page option. |
| `web/index.html` | New hidden `bootstrap-form` (title, explainer, username, password, confirm, error, submit) inside the auth card. |
| `web/app.js` | `showAuth()` now runs `checkBootstrap()`; bootstrap submit handler with confirm-mismatch check and server-detail error display; success reuses `finishLogin()`. |
| `web/i18n/en.json`, `es.json`, `pt.json`, `ht.json` | 5 new keys each (below), same single-line sorted format. |
| `tests/test_bootstrap.py` | **New** — 13 tests against a throwaway empty database. |

### M&Q CRM (`~/workspace/crm-run/` — files to file back as the next overlay batch)

| File | Change |
|---|---|
| `app/auth.py` | Added `bootstrap_owner_web()` (same design; CRM audit signature actor/role form); `threading` import; CLI `bootstrap_owner` docstring updated. |
| `app/main.py` | `/api/auth/bootstrap` added to `OPEN_PATHS`; `BootstrapIn` model; GET status + POST create-and-sign-in routes after `/api/health`; startup warning updated. |
| `app/error_i18n.py` | One catalog entry: the web-bootstrap refusal message in ES/PT/HT. |
| `web/index.html` | New hidden `setup-form` in the auth card (title, intro, username, password + hint, confirm, error, submit). |
| `web/login.js` | Setup view added to `show()`; `checkBootstrap()` on load; `onSetup()` handler (validation, confirm match, localized error mapping); signed-out view respects the bootstrap state; setup error target registered. |
| `web/login_i18n.js` | 9 new keys × 4 languages (below), same generated format. |
| `tests/test_bootstrap.py` | **New** — 13 tests against a throwaway empty database. |
| `tests/test_batch8.py` | B8.2 sweep skip-list + comment (see above). |
| `tests/test_batch9.py` | G test rewritten to the new contract (see above). |
| `tests/test_batch9b.py` | `OPEN_PATHS` expectation updated (see above). |
| `tests/test_batch9c.py` | A2 `OPEN_PATHS` and S2 endpoint-set expectations updated (see above). |

---

## New UI string keys

**Command Dashboard** (`web/i18n/*.json`, all four catalogs — 69 keys each, parity-tested):

- `auth_bootstrap_title` — "Create the owner account"
- `auth_bootstrap_note` — the one-time first-run explainer
- `auth_bootstrap_create` — "Create owner account"
- `auth_confirm_password` — "Confirm password"
- `auth_password_mismatch` — "The passwords do not match."

**CRM** (`web/login_i18n.js`, all four locales — 72 keys each, parity-tested):

- `setup_title`, `setup_intro`, `setup_password_hint`, `setup_create`,
  `setup_creating`, `confirm_password`, `err_password_mismatch`,
  `err_setup_taken`, `err_setup_failed`

Plus one server-error catalog entry in CRM `app/error_i18n.py` (the
web-bootstrap refusal message, ES/PT/HT).

## Honest limitations

- **PT/HT strings are authored, not native-reviewed** — the standing
  caveat for both products; native-speaker review remains outstanding
  and is flagged in the files' existing headers. (ES likewise remains
  machine-assisted per the CRM catalog's own note.)
- **Atomicity is single-process/single-worker by design** (lock +
  `BEGIN IMMEDIATE`), matching the current deployments. A future
  multi-worker deployment would need the same guard pushed into the
  database (e.g. a partial unique index on `role='owner'`); out of
  scope here.
- **First-come risk is inherent to any first-run bootstrap**: on a
  brand-new public deployment, whoever reaches the sign-in page first
  can claim the owner account. This is the industry-standard trade-off
  the founder ordered to remove the dead end; the window closes
  permanently at first use, and the CLI path remains for controlled
  installs. Deployments should create the owner immediately after
  first start.
- The bootstrap status endpoint necessarily reveals whether an owner
  exists (one boolean) — that is the minimum the sign-in page needs to
  avoid the dead end, and it is the only thing it returns.
- Not deployed and not pushed, per instructions. The CRM changes live
  only in `~/workspace/crm-run/` and are listed above for filing as the
  next overlay batch.
