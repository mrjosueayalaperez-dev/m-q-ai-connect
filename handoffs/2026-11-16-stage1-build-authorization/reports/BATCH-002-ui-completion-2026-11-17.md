# M&Q CRM — STAGE 1 BATCH 002: Operator UI completion + demo seed (Muse, builder)
**Date:** November 17, 2026 · **Builder:** Muse · **Authorization:** founder's order Nov 17 ("let's build on the CRM — keep working on it"), under the Stage 1 terms. The ACK requirement was retired by founder directive the same morning — no ACK gates anything in this batch.

**Status, stated separately:** IMPLEMENTED — yes · TESTED — yes, **30/30 pytest passing** + live server smoke on a seeded synthetic database · INDEPENDENTLY VERIFIED — no (founder + Zelator review stands; Moose's Workstream 1 audit now expressly includes Batch 001 + 002 evidence as inputs, per the founder's Nov 17 directive to Moose) · DEPLOYED — no · MERGED — no.

## What this batch adds
Batch 001 shipped a complete API with a minimal UI (billing was API-only; messages had no panel; bookings could not be created from the UI). Batch 002 makes the **first complete customer journey operable end-to-end in the operator UI**, EN/ES throughout:
- **Bookings:** create form (customer, title, local date/time) + all-bookings list + due reminders.
- **Billing:** full flow in the UI — create quote → add items → mark sent → accept → convert to invoice → record payments → paid state, totals computed from minor units.
- **Message Center panel:** compose template drafts per customer, AI-draft (comeback) button, message list with status / created-by / translation-pending markers, **Approve and Send buttons that only appear in the legal states** (the server still refuses any illegal transition — the UI mirrors the rule, it doesn't replace it).
- **Customers:** per-customer "Request review" and "Referral code" actions.
- **API additions:** list endpoints for bookings, quotes, invoices, messages; free-text compose + human-translation supply; reviews request/record/list; referral creation.
- **Demo seed** (`scripts/seed_demo.py`): builds a fully synthetic database (every record marked SYNTHETIC, `.invalid` emails) exercising the whole journey — one paid invoice, one Spanish comeback draft awaiting approval, a 2-row backlog import. For walkthroughs only; never a real workspace.

## Test evidence (as it came out)
`pytest tests/ -q` → **30 passed** (Batch 001's 27 + 3 new: message-list filtering, booking/quote lists, and a seed test asserting the synthetic demo completes with a paid invoice, a pending draft, and a clean 2/2 import). Live smoke on the seeded DB: `/api/reports/summary` (4 customers, USD 99.00 paid, 1 upcoming booking), `/api/messages` (Spanish comeback draft, original preserved), `/api/invoices` (paid, totals reconcile), UI serves with the Messages tab present.

## Changed / new files (SHA-256)
| File | SHA-256 |
| --- | --- |
| app/i18n.py | `d9681a46510bc060858b624aac439ea050a116ac20b6a4da0ec230cff8b03a74` |
| app/main.py | `16b4c35844ae9713ce8aa69fb1d8c0f156c4d56df7913e54dcefc55b1c0af3a5` |
| app/services/messages.py | `6f36f844846c1d20af1f3959004f405aafa423112fe0f85c1a30332c63b916e5` |
| app/services/bookings.py | `4d17bbc3953871563ab2940bb538936c4373e57c3c0114203146067ac7662180` |
| app/services/billing.py | `991da3b6e7c555d61fa83d91f8a3db4597de6b286a974c2a3670e18f17fbc334` |
| web/index.html | `e30d892b4fdd6d794344f23f50e255e950aa34ea28d068847c0405184c9fef38` |
| web/app.js | `3219bdbd5fa7423572448d0da68b38524709b95ff755aa71168efa6848b217b2` |
| web/styles.css | `5629f3429886c47db96a58bbd082a2e1b9baea84b914ecf5580bb6f07dfdb286` |
| scripts/seed_demo.py | `6680c1fff292ad54316d5b58c67077c477ad4336267f85a207fccf63daf46d91` |
| tests/test_batch2.py | `f62475bbe0556d3c7a9c6048cb95fbc9f05bacaf3b591ec5ad9ccdc7d2e3f0fe` |

## Known limitations (unchanged from Batch 001 unless noted)
1. Message "send" is still the audited state transition — no SMS/email channel connected (separate approval).
2. Template compose from the UI passes placeholder context (`—`) for {when}/{total}-style fields; the API accepts full context. A context-form pass is a Batch 003 candidate, stated plainly rather than hidden.
3. Authentication remains the role header; no deployment exists.
4. AI assistance remains template drafting only — no external provider (privacy rule). Moose's Workstream 2 POC evaluates the LangChain/Langfuse path independently; nothing here depends on it.
5. PT/HT designed-for, not shipped. Region metadata designed-for, not built.

## Next
Founder + Zelator review of Batches 001–002; Moose's Workstream 1 audit reconciles both batches against Register v1 + the 14-item checklist. Corrections return as one consolidated list; Muse implements. Production remains a separate founder decision, always.

*KNOWLEDGE IS THE LEGACY.*
