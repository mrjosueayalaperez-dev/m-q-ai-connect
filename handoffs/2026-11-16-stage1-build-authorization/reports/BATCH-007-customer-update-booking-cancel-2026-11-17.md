# BATCH 007 — Customer record editing (One Record protected) · booking cancellation
**Date:** November 17, 2026 · **Builder:** Muse · **Authorization:** founder's standing build order (unfreeze, Nov 17: "We are keep building"), given while Moose reconciles Batches 004/005. This batch's files live in their own folder; the delivered 003–006 records are untouched.
**Status: IMPLEMENTED + TESTED (builder-side) · NOT INDEPENDENTLY VERIFIED · NOT MERGED · NOT DEPLOYED.**

## Why this batch
Two everyday operations were impossible through the product: fixing anything on a customer record (a wrong name, a changed phone, a language preference — including the region field Batch 004 added, which could be set at creation but never corrected), and cancelling a booking (bookings could be created and completed, never cancelled).

## What was built
1. **Customer update** (`POST /api/customers/{id}/update`, write roles, audited):
   - Editable: name, phone, email, language, timezone, currency, region, data residency. Anything else is refused by name.
   - **One Record is enforced on edits, not just creation:** assigning a phone or email that already belongs to another customer is refused with the owning record named — the operator merges instead of duplicating. Keeping your own contact details while editing other fields is not a conflict.
   - Language must be one of the four first-class languages.
   - The audit entry records **which fields changed, never their values** — the trail proves an edit happened without copying personal data into the log.
   - UI: each customer row now carries a language selector (EN/ES/PT/HT) wired to this endpoint — the operator-facing half of language-preference consistency.
2. **Booking cancellation** (`POST /api/bookings/{id}/cancel`, write roles, audited): only a live `booked` appointment can be cancelled; cancelling a completed or already-cancelled booking is refused, so history is never rewritten. A cancelled booking immediately stops counting as upcoming and leaves the reminder queue. A `complete` endpoint was also exposed (the service existed unrouted). UI: Cancel button on live bookings.

## Tests — 88/88 passed (82 prior + 6 new, `tests/test_batch7.py`)
Update happy path incl. region · duplicate phone refused · duplicate email refused (case-insensitive) · own-phone no-conflict · unsupported language / uneditable field / empty update / unknown customer all refused · API viewer 403 + audit contains field names and provably not values · cancel lifecycle (booked → cancelled; re-cancel refused; completed cannot cancel; unknown refused; cancelled leaves upcoming) · API cancel/complete flow with role checks.
**Live smoke (fresh DB, HTTP):** customer updated EN → ES + region set · booking cancelled · audit chain healthy.

## Gates intact
No provider connected · no deployment · PT/HT native review outstanding · $0 spent.

## Changed / new files (SHA-256, copies under `code/mq-crm-batch007/`)
| File | SHA-256 |
| --- | --- |
| app/main.py | `8235276491bc964ec66a2f4f17a5fd411a7a20024adf9ab4d9ca7f927c3c28b4` |
| app/services/customers.py | `7f862545a2bcb44b856cb9bb001279dfb07ae2c6208733c61f215eea18e0fb53` |
| app/services/bookings.py | `49c5b5fc5653172ba452ceeee16bebb9ac1f1a4b71b7779fad2ed5fd53f5cb33` |
| web/app.js | `337a00a5188c2f9d0c86c0ddf63bbfa349cf9ad4d9e975d43710e2e4730617` |
| tests/test_batch7.py (new) | `94685d5de2c883fd3f69803faa38f3fb1efbb1f55d7f78c94eb96ab52c4be261` |

*KNOWLEDGE IS THE LEGACY.*
