# Hardening, 2026-11-18

These are fixes from the security review of main `fbc7c1a`. The review found no Critical or High findings. All seven review items (M1, L1–L6) are fixed.

## M1, API docs off

- `app/main.py` sets `FastAPI(docs_url=None, redoc_url=None, openapi_url=None, swagger_ui_oauth2_redirect_url=None)`.
- `/docs`, `/redoc`, `/openapi.json` and `/docs/oauth2-redirect` now return 404, signed in or not.
- Before, they returned 200 without a login, and the docs pages loaded scripts from a CDN.

## L1, security headers on every response

This covers the web UI, static files, the API, and the 401 and 403 denials. The `_SecurityHeaders` middleware is the outermost layer and replaces any weaker copy set further in.

- `Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; manifest-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'`
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`

The CSP has no `'unsafe-inline'`. To make that work, `web/app.js` no longer renders inline `onclick` / `onchange` / `onsubmit` handlers or `style=` attributes:

- The 15 handlers are now `data-act*` attributes handled by three delegated listeners. Only names on an allow-list can be called, and ids are always numbers.
- The two input widths moved to `styles.css` (`input.w-qty`, `input.w-amount`).

## L2, `totp.key` git-ignored

Added to the `.gitignore` in `mq-crm-batch009/` (this copy wins in the assembled tree) and in `mq-crm-batch008/`.

## L3, no plain-text unknown usernames

A failed, locked or blocked login for a username with no account no longer writes the typed text to the audit log or the app log.

- The actor is recorded as `(unknown user)` and the username as `u#<12 hex>`. That value is an HMAC-SHA256 with a random per-process key, which is never stored or printed.
- Repeats of the same text can still be correlated within one server run.
- Known usernames are recorded as before.

## L4, trusted proxies (opt-in, off by default)

The code is in `app/client_ip.py`, used by the sign-in, two-step and two-step-disable throttles.

| Setting | Address the per-address throttle uses |
|---|---|
| `MQ_CRM_TRUSTED_PROXIES` unset or empty (default) | The direct TCP peer. `X-Forwarded-For` is ignored. |
| `MQ_CRM_TRUSTED_PROXIES="127.0.0.1"` (a tunnel on the same machine) or `"10.0.0.0/8"` (a platform load balancer) | When the direct peer is in the list: `X-Forwarded-For`, read right to left. The first hop that is not itself a trusted proxy is the client. When the peer is not in the list: the peer, and `X-Forwarded-For` is ignored. |

- The value is a comma-separated list of IPs or CIDR networks.
- A malformed hop, an all-trusted chain, or more than 100 hops falls back to the direct peer.
- `Forwarded` and `X-Real-IP` are never read.
- An invalid entry refuses startup (`TrustedProxyConfigError`), so a typo can't silently widen or disable the trust.
- **Operators: run uvicorn with `--no-proxy-headers`.** uvicorn has its own proxy-header handling, applied before the app sees the request. By default it trusts `X-Forwarded-For` from 127.0.0.1. With `--no-proxy-headers`, this setting is the only thing that decides.

## L5, exact pins

- **`requirements.txt`** pins every package, direct and transitive, to the exact version the suite passed with (CPython 3.13.5, Linux).
  - Platform markers are kept for `uvloop`, `cffi` and `pycparser`.
  - `colorama` (Windows only, used by pytest) is pinned but untested here.
  - Python 3.11+ is required; the back-ports older Pythons need are not listed.
- **`requirements-lock.txt`** is the same pins with sha256 hashes, generated with `pip-compile --generate-hashes` (pip-tools 7.7.0). Install with:

  ```
  pip install --require-hashes -r requirements-lock.txt
  ```

  The installed set was checked identical to the tested environment.
- **Fragility:** the lock is resolved for Linux/CPython 3.13. Platform-only packages for other systems (Windows `colorama`) are not in it, so on Windows use `requirements.txt`.
- **To upgrade:** change a pin, run the full suite, then regenerate the lock:

  ```
  pip-compile --generate-hashes --allow-unsafe --strip-extras --no-header -o requirements-lock.txt requirements.txt
  ```

  Then restore the header comment.

## L6, 422 without the caller's input

The handler is in `app/validation_errors.py`.

- Status is still 422, and `detail` is still a list. Each item is only `{"loc", "type", "msg"}`:
  - `loc` is `body` / `query` / `path` / `header` / `cookie`, plus field names and list indexes. Anything else becomes `"*"`.
  - `type` is pydantic's stable error code.
  - `msg` is a fixed English sentence chosen by type, not pydantic's text.
- The submitted input (`input`), parser context (`ctx`, e.g. the JSON decoder message) and `url` are never returned.
- As before (`docs/ERROR-LANGUAGES.md`), 422 lists are not translated. The body is the same in every language; clients localize on `type`.
- Security headers still apply.

## Tests

| File | Tests | Covers |
|---|---|---|
| `tests/test_hardening.py` | 16 | M1, L1, L2, L3 |
| `tests/test_hardening_followups.py` | 20 | L4, L5, L6 |

- Every item has deliberate-break checks: the same detector, run on the pre-fix behaviour, must fail.
- L4 is also tested end to end:
  - By default, a peer that rotates spoofed `X-Forwarded-For` values is still locked.
  - With the setting on, the real sprayer behind the proxy is locked and another client behind the same proxy is not.
