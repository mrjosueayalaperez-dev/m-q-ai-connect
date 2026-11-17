# BATCH 006 — Processing register operable · two-way Message Center
**Date:** November 17, 2026 · **Builder:** Muse · **Authorization:** founder's standing build order (unfreeze, Nov 17: "We are keep building"). Built in parallel with Moose's Batch 004/005 reconciliation assignment — this batch's files live in their own folder and do not touch the delivered 003/004/005 records he is reconciling against.
**Status: IMPLEMENTED + TESTED (builder-side) · NOT INDEPENDENTLY VERIFIED · NOT MERGED · NOT DEPLOYED.**

## Why this batch
Batch 005's privacy gate reads the processing register — but until now the register could only be written by direct database access. A gate nobody can operate through the product is a gate that will be bypassed in practice. Batch 006 makes it operable, and completes the Message Center's two-way claim.

## What was built
1. **Processing register API** (`app/services/register.py` + endpoints):
   - `GET /api/processing-register` — readable by any role.
   - `POST /api/processing-register` — **owner-only**, audited (`register_provider`). New entries start with `terms_reviewed = 0` — review is an explicit act, never a default.
   - `POST /api/processing-register/{id}/terms` — **owner-only**, audited (`provider_terms_reviewed` / `provider_terms_unreviewed`). Recording a terms review is a consequential trust act, so it carries the strictest role in the system plus a permanent audit record of who did it.
   - Proven end-to-end: gate closed → webhook dispatch refused · owner records the review → dispatch succeeds · owner un-marks the review → the next dispatch is refused again, with zero additional payloads sent.
2. **Inbound messages** (`POST /api/messages/inbound`, write roles, audited `record_inbound`): customer replies can now be recorded through the API — the service existed since Batch 001 but had no route. Also fixed an honesty defect found on the way: inbound records were stored with the schema's default direction `out`; they now record direction `in`, and the UI badges them "↩ inbound".

## Tests — 82/82 passed (76 prior + 6 new, `tests/test_batch6.py`)
Register starts unreviewed · terms toggle both ways + unknown entry refused · the full gate open/close cycle through the register against a live stub endpoint · register API staff-refused (403) on both writes, owner succeeds, both audit actions present in the chain · inbound recorded with direction `in` / status `received` / created_by `customer` · unknown customer refused · API inbound viewer-refused (403) and audited.
**Live smoke (fresh DB, HTTP):** register entry created unreviewed → owner marks reviewed → PT customer reply recorded inbound ("Sim, concordo") → audit chain healthy (3 audited actions).

## Gates intact
No real provider connected (the register now *can* record a review, but none has been recorded against any real provider, and connecting one remains a founder decision) · no deployment · PT/HT native review outstanding · $0 spent.

## Changed / new files (SHA-256, copies under `code/mq-crm-batch006/`)
| File | SHA-256 |
| --- | --- |
| app/main.py | `74aa2cae1860c6ed4b7543dff5a3cd5c72e7c7afc28ab60cd1bf14dbc1526c1e` |
| app/services/register.py (new) | `d9cef5adee510def8af272f58a637f8262c0a99fe54402caa7cfb2b546ad9a1a` |
| app/services/messages.py | `06fe5040e8fcac37981cb85315b49325f4e72d00738684295f8bde77c16b23da` |
| web/app.js | `c5e1719a2122f8f1d1699c8e85eb61d4a2f1c627a2866813f460261552aaa0e6` |
| tests/test_batch6.py (new) | `8574be55ff298c4c8a54d7033d8c043b0faf37332fa2883fdc30d64302760b9d` |

*KNOWLEDGE IS THE LEGACY.*
