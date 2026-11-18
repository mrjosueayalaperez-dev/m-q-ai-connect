# M&Q CRM — STAGE 1 BATCH 003: Four first-class languages + control tightening (Muse, builder)
**Date:** November 17, 2026 · **Authorization:** the founder's own words, Nov 17, 08:47 ET — *"after you fix this, and tighten everything up, you can unfrozen and go with batch number three. Proceed with it after everything is fixed"* — following (a) his **Four-Language Requirement directive** (EN · ES · PT · HT as first-class languages; "Language is the purpose, not an accessory") and (b) the eight inspection targets in the relayed assessment. The fixes came first in this batch's work order; Batch 003 scope followed them in the same delivery.

**Status, stated separately:** IMPLEMENTED — yes · TESTED — yes, **49/49 pytest passing** + live smoke (HT customer + Kreyòl draft over HTTP) · INDEPENDENTLY VERIFIED — **no** (the independent layer — Moose WS1 reconciliation, Zelator inspection — now has a tightened surface to examine; this batch does not verify itself) · DEPLOYED — no · MERGED — no.

## Part 1 — Four first-class languages
- **Templates:** all five customer-facing templates (reminder, quote ready, invoice ready, comeback, review request) now authored in **Portuguese and Haitian Creole** alongside EN/ES. A PT or HT customer receives content in their language at every step — not a translated menu over English content.
- **UI:** the full operator string catalog exists in all four languages with **identical key sets, enforced by test**; the UI language toggle is now EN/ES/PT/HT; the customer form offers all four.
- **Journeys:** the complete customer journey test now runs in **all four languages** (EN/ES/PT/HT), each asserting in-language reminder and comeback content and consistent state.
- **Backlog import** already accepted pt/ht language codes; now the whole lifecycle honors them.
- **Honest limit:** PT/HT strings are **authored, not native-reviewed**. Native-speaker review remains a standing requirement before any production claim — recorded here, in the README, and in the code, not buried.

## Part 2 — Tightening (the readiness map's GAPs/PARTIALs, addressed)
1. **Approval is bound to the exact content.** `approve()` records a SHA-256 hash of original + translation; `send()` re-verifies it. Changing a translation after approval **invalidates the approval** (message returns to draft, hash cleared). Tampering with the text in the database after approval → send refused. Setting `status='approved'` directly in the DB without `approve()` leaves the hash empty → send refused.
2. **Consent is re-checked at send time.** Marketing sends re-read the customer's *current* consent; a new consent grant/withdraw operation (`POST /api/customers/{id}/consent`, audited both ways) takes effect immediately — withdrawal after drafting *or after approval* stops the send.
3. **Duplicate-send is atomic.** The send transition is a single `UPDATE ... WHERE status='approved'`; a two-thread race test proves **exactly one winner**.
4. **Audit is tamper-evident.** Audit rows are hash-chained (each row hashes the previous row's hash + its fields); `verify_audit_chain()` detects alteration — proven by a test that tampers with a row and watches verification fail. Tamper-*evident*, not tamper-proof — stated as such.
5. **Export gates tested.** The previously untested role gates on both export endpoints now have dedicated tests (staff/viewer refused, owner served).
6. **Withdraw action** (the Batch 003 candidate held from the supplement): drafts and approved messages can be withdrawn; withdrawn is terminal — no approve, no send — and the action is audited.

## Test evidence (as it came out)
`pytest tests/ -q` → **49 passed**, first full run, no fixes needed mid-run. New coverage: 4-language parity (2) · PT + HT journeys (2) · consent-at-send · content-binding (change-after-approval, DB text tamper, flag-only tamper) · concurrent duplicate send · audit-chain tamper detection · withdraw terminality · export role gates (8 in `tests/test_batch3.py`). Live smoke: HT customer created over HTTP; comeback draft rendered in Kreyòl; UI serves the HT toggle.

## Changed / new files (SHA-256)
| File | SHA-256 |
| --- | --- |
| README.md | `c6a416325de7efdb87bdb895c177fa60f618a81683199682c4ed895ff4294c26` |
| app/db.py | `7c566c51acaa59d679b816ba40d3a2578790cfdae7aabb66c154b43aec73a0af` |
| app/i18n.py | `cc4d57fa95c7c458c651a4b40c14588b101beac36af4295ab1280e31ddcfa156` |
| app/main.py | `09c6288af9e4a73fedca6e50f120fed39a1ca114bea5cc1c17a7d39bcdd1ebb1` |
| app/services/messages.py | `722e9387f59ca1d357462de3e28d17bed7204ad441beeea678f87c4fe77d0784` |
| app/services/customers.py | `4d72b8727e338bfd5271653f55360ae7cb45121d8a2808702c4e9c4ca447a3bb` |
| web/index.html | `39de1e59f8464dfff3418aecb77eea63072c68a18760c2a4c18d52c115a01c33` |
| web/app.js | `5c4c602a6e0b5b145357189471af46d84232691b5eb44cce59fe7d8c8aaf05cb` |
| tests/test_i18n_parity.py | `403e10f156407fd8d32e7e750290d6945dc983941d4d8f1d0543a42f66feb462` |
| tests/test_journey.py | `a30b8b955d7f774e55b25850ae3ca984592d65c4be24c0d94db3e9631e0380ea` |
| tests/test_batch3.py | `e8c874409d9c09c5f9b63036670a78c79d6a5b4c57e2ee8fedeead6d46dab009` |

## For the evidence register (Workstream 4 of the four-language directive)
Four-language requirement status for Moose's Register update: EN — implemented + builder-tested · ES — implemented + builder-tested · PT — implemented + builder-tested, native review outstanding · HT — implemented + builder-tested, native review outstanding · **no language is independently verified**. The founder's WS1 audit list (registration, scheduling, quotes/invoices, payment communication, reviews, comeback, Message Center, translation review/approval/send, exports/reports) is covered by the journey + battery + batch-003 tests at the builder level in all four languages for the message-bearing steps; quotes/invoices/reports carry amounts and data, not prose, and render identically across languages by design.

## Remaining known limitations
No SMS/email channel (send = audited transition) · no external AI provider (privacy rule) · operator authentication is a deployment-layer step (nothing deployed) · region metadata designed-for · PT/HT native review outstanding · single-process SQLite by design for the entry segment.

*KNOWLEDGE IS THE LEGACY.*
