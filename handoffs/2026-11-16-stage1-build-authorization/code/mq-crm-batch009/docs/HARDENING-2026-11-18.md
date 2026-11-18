# Hardening, 2026-11-18

These are fixes from the security review of main `fbc7c1a`. The review found no Critical or High findings.

## Fixed in this change

- **M1, API docs off.** `FastAPI(docs_url=None, redoc_url=None, openapi_url=None, swagger_ui_oauth2_redirect_url=None)` in `app/main.py`.
  - `/docs`, `/redoc`, `/openapi.json` and `/docs/oauth2-redirect` now return 404, signed in or not.
  - Before, they returned 200 without a login, and the docs pages loaded scripts from a CDN.
- **L1, security headers on every response.** This covers the web UI, static files, the API, and the 401 and 403 denials. The `_SecurityHeaders` middleware is the outermost layer and replaces any weaker copy set further in.
  - `Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; manifest-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'`
  - `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`
  - The CSP has no `'unsafe-inline'`. To make that work, `web/app.js` no longer renders inline `onclick` / `onchange` / `onsubmit` handlers or `style=` attributes.
    - The 15 handlers are now `data-act*` attributes handled by three delegated listeners. Only names on an allow-list can be called, and ids are always numbers.
    - The two input widths moved to `styles.css` (`input.w-qty`, `input.w-amount`).
- **L2, `totp.key` git-ignored.** Added to the `.gitignore` in `mq-crm-batch009/` (this copy wins in the assembled tree) and in `mq-crm-batch008/`.
- **L3, no plain-text unknown usernames.** A failed, locked or blocked login for a username with no account no longer writes the typed text to the audit log or the app log.
  - The actor is recorded as `(unknown user)` and the username as `u#<12 hex>`. That value is an HMAC-SHA256 with a random per-process key, which is never stored or printed.
  - Repeats of the same text can still be correlated within one server run.
  - Known usernames are recorded as before.

## Tests

`tests/test_hardening.py` has 16 tests. Each fix also has a deliberate-break check: the same detector, run on a broken copy, must fail.

Against the unfixed main, 10 of the 16 fail. The other 6 are checks that a detector catches a deliberately broken input, so they pass on any code.

## Follow-ups (not in this change)

- **L4.** The IP throttle keys on the direct peer. Behind a tunnel or proxy, every client shares one address, so 20 failures lock everyone out. Configure trusted proxy headers once hosting exists.
- **L5.** Pin the dependency versions with hashes. pip-audit found 0 runtime vulnerabilities on 2026-11-18.
- **L6.** FastAPI's default 422 response echoes fragments of the input. A custom handler is optional.
