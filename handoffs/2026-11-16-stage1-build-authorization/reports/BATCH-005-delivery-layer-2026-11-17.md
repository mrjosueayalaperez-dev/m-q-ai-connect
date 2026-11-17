# BATCH 005 — Delivery layer: outbox transport + privacy-gated webhook transport
**Date:** November 17, 2026 · **Builder:** Muse · **Authorization:** founder, Nov 17 ~12:00 PM ET ("Next phase approved"), under the Nov 17 unfreeze order. Interpretation recorded: the next phase is the delivery layer — the largest remaining functional gap (a "sent" message previously left no delivery record and went nowhere). Built at $0 with **no external channel connected, nothing sent to any real customer, and no deployment** — provider connection and deployment remain separate founder gates.
**Status: IMPLEMENTED + TESTED (builder-side) · NOT INDEPENDENTLY VERIFIED · NOT MERGED · NOT DEPLOYED.**

## What was built
Until now, `send` was an audited state transition and the journey ended there. Batch 005 adds the delivery layer behind it:

- **`deliveries` ledger** — every dispatch creates a record: message, channel, transport, status, the **exact text snapshot dispatched**, attempt count, provider reference, and a plain-language detail. What left the building is verifiable against the approved message.
- **Outbox transport (default, built-in)** — delivers to a local outbox on this machine. Its records state honestly: *"Delivered to the local outbox. No external channel is connected; the customer has NOT received this message on their device."* A status never claims more than the transport proves.
- **Webhook transport (external, privacy-gated)** — POSTs the message JSON to a configured endpoint, proxy-free, 5s timeout. It **refuses to run** unless the processing register holds a row for the provider with `terms_reviewed = 1` — the standing privacy rule (no customer message through an external provider before its data-processing terms are reviewed) enforced in code, not copy. A refused dispatch leaves a failed record naming the gate; nothing leaves the building (proven by test: the stub server receives zero payloads).
- **Semantics** — dispatch requires status `sent`; success is idempotent (re-dispatch returns the existing record); failure is retryable on the same record with a growing attempt count, so failure history is never hidden behind a fresh row. Dispatch and delivery failure are audited (`message_dispatched` / `message_delivery_failed` / `dispatch_denied`).
- **API + UI** — `POST /api/messages/{id}/dispatch` (write roles; viewer refused 403), `GET /api/messages/{id}/delivery`, `GET /api/deliveries`. The operator UI chains Send → Dispatch and badges each message with its transport and delivery status.

## Tests — 76/76 passed (67 prior + 9 new, `tests/test_batch5.py`)
Outbox delivery with honest detail + text snapshot · dispatch refused for draft and for approved-but-unsent · idempotent re-dispatch · unknown transport fails *recorded*, not silent · webhook refused with no register row (zero payloads sent) · refused with terms_reviewed = 0 · delivered after review, payload carries the PT text, language, and channel, provider ref recorded · HTTP 500 → failed record, retry succeeds on the same record with attempts = 2 · API flow end-to-end + viewer 403.
**Live smoke (fresh DB, HTTP):** ES customer → booking → reminder composed with the real appointment → approve → send → dispatch → `outbox · delivered · attempts 1` with the honest not-received detail; audit chain healthy.

## What this does NOT do (gates intact)
No real SMS/email provider is connected — connecting one (e.g., a messaging provider account, credentials, any cost) requires the founder's separate approval plus the terms review recorded in the processing register; the gate will refuse until then. No deployment. PT/HT native-speaker review still outstanding. Moose's own CRM implementation still unseen.

## Changed / new files (SHA-256, copies under `code/mq-crm-batch005/`)
| File | SHA-256 |
| --- | --- |
| app/db.py | `16f8d061b39797fd4a73bb71dfd96bdf44f06259ac15d10ef4c1f1af27e161b3` |
| app/main.py | `af100e11d0550cfca60a13a0203e94a0227b40f823c336a66075000981097015` |
| app/services/delivery.py (new) | `b27013f631b334eb73a9b581123f2975258efd2de8df924864bcbd439ef40187` |
| web/app.js | `64c9802ab606aad60d62d3529e952d7328e9f77edb74b6fbfae57c914761b6f4` |
| tests/test_batch5.py (new) | `74684e552c3b2f565eed523fd20ba2571c188a2a150f2ca861f2a6f893f51a28` |

*KNOWLEDGE IS THE LEGACY.*
