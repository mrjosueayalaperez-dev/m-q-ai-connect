# BATCH 008 — Corrective batch: deletion, deny-by-default, XSS, concurrency, consent, approval audit, endpoint-bound privacy gate, Batch 006 gaps
**Date:** November 17, 2026 · **Builder:** MNQ Eng (Grok Bot) · **Authorization:** founder approval relayed by Chief of Staff (Nov 17, 1:08 PM ET): fix the defects found by the Nov 17 read-only audit on a NEW draft branch cut from `handoff/moose-crm-package-2026-11-16` @ `3c03375`; draft PR only.
**Status: IMPLEMENTED + TESTED (builder-side) · NOT INDEPENDENTLY VERIFIED · NOT MERGED · NOT DEPLOYED.** Moose's Batch 004/005 reconciliation is untouched. Delivered Batch 001–007 folders are untouched (addenda discipline): every changed file is a full copy under `code/mq-crm-batch008/`, overlaid last.

## How to assemble and run
`code/mq-crm` → overlay `mq-crm-batch004` → `005` → `006` → `007` → `008`, then `pip install -r requirements.txt && pytest -q`.

## What was fixed (one line per item; details in the code docstrings)
1. **Customer deletion after a dispatch (500 since Batch 005).** `data_rights.delete_customer` is ONE `BEGIN IMMEDIATE` transaction: deliveries are deleted first (they reference messages), then items/payments, children, the customer, and the `delete_customer` audit row (written with `commit=False`, counts only). Any error rolls everything back. A delivery still `sending` blocks deletion (409) instead of racing it. Unknown customer → 404. Export now includes `deliveries`. API requests also run on their own connection that is rolled back if left open, so a partial write can never be committed by a later unrelated request.
2. **Deny by default.** A global dependency on every route: `X-Role` must be `owner|staff|viewer` or the request is 401 (no more silent `owner`), and every write must carry a non-empty `X-Actor`. All 30 `Header("owner")` defaults are gone; every GET calls `require_read`; `/api/export` stays owner-only. `/api/health` stays open (liveness only, returns no data). The UI now has Operator + Role controls (default **viewer**) and sends both headers. Authentication in front of the header is still a deployment concern (unchanged, stated).
3. **Stored XSS.** New `web/safe_html.js`: an `html` tagged template escapes every interpolated value; `setHTML()` is the only innerHTML sink and refuses non-`html` strings. All 9 renderers in `app.js` use it; `app.js` contains no `innerHTML`.
4. **Shared SQLite connection.** Per-request connections (ASGI middleware + contextvar) and per-thread connections elsewhere; WAL mode. The module-level `conn` is now a proxy, never one shared connection. Dispatch claims the delivery row with ONE conditional UPDATE (`queued|failed → sending` + claim token; unique index on `deliveries.message_id`), so concurrent dispatches give exactly one transport call; losers get 409 / `DispatchInProgress`. Webhook requests carry `Idempotency-Key: mq-crm-message-<id>`. A `sending` claim older than 300 s may be retried.
5. **Consent bypass.** Messages carry `purpose`. Free text is **marketing unless the operator declares `purpose: "transactional"`** (fail-closed; the declaration is audited). Consent is re-read at send AND at dispatch for every message type (template, free text, AI draft); a refusal is recorded on the delivery (`consent gate`) and audited (`dispatch_denied`).
6. **Approval audit.** `approve_message` audit row (actor, role, approved content hash, timestamp, purpose) plus `approved_by / approved_role / approved_at` on the message.
7. **Privacy gate matched the literal name 'webhook'.** The gate now matches the configured `MQ_CRM_WEBHOOK_URL` against the register row's `endpoint` (scheme, host, port, and path prefix if given). The provider name is a label only. Endpoints are stored without userinfo/query (where credentials hide), and refusals name the host only.
8. **Batch 006 gaps.** (a) Register fields `terms_reference` (required to record a review), `reviewed_at`, `reviewed_by`, `withdrawn_at`, `endpoint`. (b) Withdrawal vs in-flight dispatch: dispatch re-checks the gate under a shared lock right before the transport call, and changing a review takes the lock exclusively (`app/gate_lock.py`). A claimed-but-not-yet-sent dispatch is refused after a withdrawal. A POST already on the wire when the withdrawal arrives completes first, and the withdrawal commits right after it (≤5 s), so nothing passes the gate after the withdrawal commits. Scope: in-process lock (Stage 1 is single-process).

## Tests — 113/113 passed (88 prior + 25 new, `tests/test_batch8.py`)
- Baseline before any change (assembled 001–007): **88 passed**.
- After: **113 passed** (`--ignore=tests/test_batch8.py`: 88 passed). Run 3× consecutively, green each time.
- The 25 new tests were also run against the UNFIXED 001–007 build: **25 failed**, as expected.
- **Legacy test changes, stated plainly** (no assertion line was changed):
  - `tests/conftest.py`: the harness now authenticates every TestClient as an explicit owner (`X-Role: owner`, `X-Actor: test-operator`). Per-request role headers in the old tests still override it.
  - `tests/test_batch5.py::_register_terms` and three setup calls in `tests/test_batch6.py` now bind the register row to the stub endpoint and pass a synthetic `terms_reference`. Those 5 tests encoded the exact behaviour item 7/8 removes (a nameless 'webhook' row with no terms reference authorizing any URL).

## Gates intact
No provider connected · no deployment · no secrets · synthetic data only · $0 spent. PT/HT native review still outstanding.

## Changed / new files (SHA-256, copies under `code/mq-crm-batch008/`)
| File | SHA-256 |
| --- | --- |
| app/db.py | `ed3d06bf36c9d7af16f3e0073bad908a4525f048bfa1849df3500c977837761b` |
| app/gate_lock.py | `33790b81a6548588803f1d3be2560260b2203cbdc074c0f2e71573d4daadd91f` |
| app/main.py | `1d9d7ba199cd87cc7144cf111acfb66bf5a85b598c906e280f772fc69aff846e` |
| app/services/data_rights.py | `c9d7b97ffcb87aa96d05391a96fb6328dedfc81fcb19b19ff534452da94bc748` |
| app/services/delivery.py | `3087357e8c5642377f31a565170bb01f7e4d47c112efc1390fdbdc662fb4df7a` |
| app/services/messages.py | `6f363678e3329f30d8667b83b0afcdd6a7620932e66f598523726000301fffe5` |
| app/services/register.py | `5f5286a5d5c69de1e71701559f98c20b5dbb4a1e94431b67c8719e7ffba39b87` |
| tests/conftest.py | `6af3276662c1e00c911b72363652c8ce1cb5969d80001bdacd42b1fb45dc712b` |
| tests/test_batch5.py | `fff200a68b0ad61999dc4d9dd1d0501bfa16aca1853ee82cb37f55c7bdb5a539` |
| tests/test_batch6.py | `78481632c6f7f5d0f7ac19bc65174298496cd240d831404fe96633eb33f4ebd6` |
| tests/test_batch8.py | `07d5e96766f03679a744732a7adda37dd7c3ba7a6dd8ab0a5ae0ead16d607101` |
| web/app.js | `cc9c042b4c6805d5e0f8f291671349d3dda94eeae30aa70a40236f0998c6e43a` |
| web/index.html | `d580f46501b685cb181e20bb82023963d67fa74e56efe89f8c18b23a530e1e7d` |
| web/safe_html.js | `8b4a53f7b1ece2dd4f01d7eed3daca9d0eaaf00c09d16970d93a175389c2c40b` |
| web/styles.css | `e7ea9271b07a25b4d610f854cada94fab7111a8f2aec722a68a306e9b16f4618` |

*KNOWLEDGE IS THE LEGACY.*
