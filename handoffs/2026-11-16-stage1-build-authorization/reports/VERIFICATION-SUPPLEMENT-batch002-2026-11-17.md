# M&Q CRM — BATCH 002 VERIFICATION SUPPLEMENT: adversarial battery + bilingual journey (Muse, builder-side)
**Date:** November 17, 2026 · **Prompted by:** the independent-verification assessment relayed by the founder (Nov 17, 08:40 ET): attempt to bypass the Message Center, verify the full journey in EN and ES, and preserve the release boundary.

**Labeling, plainly:** this battery was written and run by the BUILDER. It is **builder-side adversarial testing, not independent verification.** Independent verification remains pending — Moose's Workstream 1 reconciliation and Zelator's inspection are the independent layer, and nothing here replaces them. The assessment's distinction stands and is adopted: **fingerprint verification establishes file integrity, not correctness.** This supplement addresses correctness of the communication controls; the audit must still establish both, independently.

**Status after this supplement:** IMPLEMENTED + TESTED (39/39) · NOT INDEPENDENTLY VERIFIED · NOT MERGED · NOT DEPLOYED.

## Attacks attempted and results (as they came out)
First run: **7 passed, 2 failed** — the battery found two real defects. Both were fixed; full suite now **39 passed**.

| # | Attempt | Result |
| --- | --- | --- |
| 1 | Send a draft that was never approved | REFUSED (PermissionError) — held from the start |
| 2 | Send the same message twice (duplicate send) | REFUSED on the second attempt — held |
| 3 | Send an inbound (customer) message | REFUSED — held |
| 4 | Approve an already-approved message | REFUSED — held |
| 5 | AI-draft a comeback message for a customer without marketing consent | REFUSED — held |
| 6 | Viewer role attempts approve / send via the API | REFUSED (403) — held |
| 7 | **Altered approval data:** set status='approved' directly in the database on a message whose translation is still pending, then send | **FAILED OPEN on first run** — the send gate trusted the status flag. **FIXED:** `send()` now re-checks `translation_pending` and refuses; the gate no longer trusts the flag alone |
| 8 | **Failed send leaves an auditable record?** | **NO on first run** — refusals were silent. **FIXED:** the API now writes a `send_message_denied` audit row (actor, role, reason) before returning 403 |

## Bilingual workflow verification
The complete journey runs end-to-end as a test in **both** languages (`tests/test_journey.py`): customer (with an old last-service date) → booking → due reminder composed in the customer's language → quote → accepted → invoice → partial payment (still open) → full payment (paid) → review recorded → lapse detected → comeback draft in the customer's language → approve → send → report averages consistent → export contains the whole story (1 booking, 1 invoice, 2 payments, 2 messages). **EN and ES both pass.**

## One design observation for Batch 003 scoping (not silently fixed)
The assessment lists "send an already rejected draft." **No `rejected` state exists in the system** — a draft can only wait unapproved; there is no operator action to reject/withdraw one. Sending an unapproved draft is refused (attack 1), so the safety property holds, but a reject/withdraw action (with its own audit entry) is a legitimate Batch 003 candidate for the founder/Zelator to scope.

## Changed files (SHA-256)
| File | SHA-256 |
| --- | --- |
| app/services/messages.py | `68b6ff0e36cf660aef95f91deb60fda26d542f20671dfd96c6ee8a7b31508217` |
| app/main.py | `6e72039b69a338f4e3ac0a0a7e61cca178f089873f3bb7c5e9e51d61286580ce` |
| tests/test_security_battery.py | `841f006e561e08a3af87d3cbe0655ef202a750d2e4e8cce3e6caca376145eb8d` |
| tests/test_journey.py | `933f729f5361ff44b6a77c0f6e448a0302fdf9d0cd9448d349b4a94d53692c54` |

## What remains for the independent layer
Moose's reconciliation (Register v1 + 14-item checklist vs Batches 001–002 + this supplement, every requirement with an evidence reference and one honest status) and Zelator's inspection. Batch 003 scope should be set from their findings, per the assessment's recommendation — not before.

*KNOWLEDGE IS THE LEGACY.*
