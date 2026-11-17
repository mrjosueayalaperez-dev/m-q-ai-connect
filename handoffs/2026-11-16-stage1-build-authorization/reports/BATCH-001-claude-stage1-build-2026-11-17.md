# M&Q CRM — STAGE 1 BATCH 001: Initial build (Muse, builder)
**Date:** November 17, 2026 · **Builder:** Muse (Chief of Staff) · **Authorization:** Stage 1 authorization (Package 3, Nov 16) as reassigned by the founder's direct order, Nov 17, 2026: the pending ACK precondition was **bypassed by the founder — recorded WAIVED, NOT MET** — and the build reassigned from Moose to Muse ("he's waiting on you to make that and you waiting on him to make that"). All other Stage 1 terms stand: no production deployment, no protected-branch merge, no purchases, synthetic data only, no credentials in any repo.

**Status, stated separately:** IMPLEMENTED — yes (below) · TESTED — yes, 27/27 pytest passing + live server smoke (below) · INDEPENDENTLY VERIFIED — **no** (Zelator's inspection is the next loop step; the founder + Zelator review layer stands) · DEPLOYED — **no** · MERGED — **no** (code sits in this package on the handoff branch and in Muse's workspace at `~/workspace/mq-crm`).

## What was built (entry segment, per the authorization's scope frame)
FastAPI + SQLite service with an EN/ES operator UI:
- **One Record** — dedup on normalized phone/email; merge fills only empty fields.
- **Book & Remind** — local-time booking (IANA) stored as UTC; due-reminder query.
- **Quote → Invoice → Paid** — integer minor units + ISO currency; paid only when payments sum to total.
- **Comeback Engine + backlog import** — lapsed detection (incl. never-served imports); CSV import with validation, duplicate resolution, outcome report.
- **Message Center EN/ES** — per-customer language; authored bilingual templates; originals preserved beside translations; wrong-language free text waits for a human translation; **send is code-blocked until a human approves**; marketing refuses without recorded consent.
- **Reviews & Referrals** · **Simple Reports** · **Your Data Is Yours** (full export; deletion propagates + audited).
- **AI Assistance** — template-based drafts marked `ai_draft`, same approval gate. **No external AI provider connected** (privacy rule: no provider's terms reviewed yet) — limitation stated, not hidden.

## Test evidence (as it came out)
`pytest tests/ -q` → **27 passed** (final run, Nov 17, 2026). Coverage maps to the acceptance checklist: One Record dedup (5) · bookings/TZ (2) · billing chain (3) · **backlog-import safeguard: received 6 / imported 2 / merged 1 / rejected 3 with reasons** (3) · messages: ES rendering, consent gate, approval gate, translation-pending (4) · data rights export/delete/audit (2) · EN/ES parity (2) · AI draft gate + reviews/referrals + reports (3) · API + RBAC + import endpoint (3). One defect found and fixed during the run (SQLite cross-thread connection for the API layer). Live smoke: uvicorn boot, `GET /api/health` OK, customer create over HTTP OK, UI served.

## Files (SHA-256) — code under `code/mq-crm/` in this folder
| File | SHA-256 |
| --- | --- |
| README.md | `3142098f957220fdc9625c9303ec71bb6f5e344059a4fd2552c0a5aee365c9fe` |
| requirements.txt | `49d4280ecee2281bddb9c4e6031c6ba7b28ad29b5910551ee040f53129434bc8` |
| app/db.py | `4a20444f224a75b7b7a1059d687c073756c074adbba3dc7b7d79a4237b4d82b4` |
| app/i18n.py | `78de852a5fb6dd8777b5ab43bf52fa10d81dc1baa317ccd4a0bd2c44d1ea88ef` |
| app/main.py | `6e30c881d20d7f081c03f20ac97e5472a78c74b8a105bbff6e6c85fecebc68d6` |
| app/services/ai_assist.py | `9f77a3cc86c5f44bab5a4d91373e7b24bf3b9f9939e85a69ed820847318ac00a` |
| app/services/billing.py | `2199d72fd0ded6cf41f3bd0edae7d7b406c5e6210d217caf41ceab056cd74331` |
| app/services/bookings.py | `0f521f0b5f20d2c8fd94fe6cb727d314a00cef308f277ea3c6403a866d709ef4` |
| app/services/comeback.py | `b0cf22c08469adddb2999c9eb7bbbfcf3e0071ae1e66c4a723e61737341894ea` |
| app/services/customers.py | `f54f8ce01925cd09fd17b53f1a0aa9983c802374f9846d9beb0b101f7f74ee85` |
| app/services/data_rights.py | `1d23ae58af2f3d3a6870ac3808e3ad0c2ec19b91efc31e93c2d07f427fa6f6a3` |
| app/services/messages.py | `df9f3ddf2f473128a6203349b8f010ff519ea1b3faf0c10a4fa94fdf876b4a25` |
| app/services/reports.py | `4ba18e907851d6347d2653123a4628879307d692b7638f9b992666ea8ee2834b` |
| app/services/reviews.py | `0f19c77e01ce5017e8a0b2f2aaa5680690a55a74bb5eaac497f6605bee46ff9c` |
| web/app.js | `8cda8042f3fdde87b3ea715c3a717fb95aceaae91bf4338a995708b3c03bc1c2` |
| web/index.html | `267c2fc71ffe641d28c30be4a44276aaf75c988491e7ccedee27259737bec1c3` |
| web/styles.css | `385dc4a1566af15bfecbb087ed6178e1fe0889b010e3e311d4ccce621efd7ebd` |
| tests (10 files) | hashes in the delivery verification record; suite listed in the package tree |

(Empty `__init__.py` files share the standard empty-file hash `e3b0c442…`.)

## Known limitations (listed, not buried)
1. Message "send" performs the audited draft→approved→sent transition; **no SMS/email channel is connected** — delivery integration is a later, separately approved step.
2. Authentication is a role header (`X-Role`) enforced server-side; real operator authentication belongs to the deployment layer and does not exist yet. Nothing is deployed.
3. AI assistance is template drafting only — no LLM provider, per the privacy rule (no provider terms reviewed). The LangChain/Langfuse POC (Workstream B) remains a separate lane.
4. Region/data-residency metadata: **designed-for, not built** (no hosted deployment exists). PT/HT: designed-for in the language architecture, **not shipped, not claimed**. No HT spoken-output claim anywhere.
5. UI billing panel is minimal — the billing API is complete and tested; the UI covers customers, bookings/reminders, comeback + import, reports, and export fully.
6. SQLite is single-process: right-sized for the entry segment, not an enterprise-scale claim.
7. **Moose's pre-existing CRM implementation has never been seen by Muse.** His Workstream A reconciliation/audit (claim-by-claim vs Register v1 + the 14-item audit of his build) remains owed and is NOT replaced by this build; where the two builds differ, that reconciliation decides.

## Next loop step
Zelator's independent inspection of this batch + the founder's review. Corrections return as one consolidated list under `corrections/`; Muse implements; verification re-runs. Production remains a separate founder decision, always.

*KNOWLEDGE IS THE LEGACY.*
