# BATCH 004 — Real compose context · audit-chain recovery · region metadata
**Date:** November 17, 2026 · **Builder:** Muse (Stage 1 build reassigned to Muse by founder order, Nov 17) · **Authorization:** founder's unfreeze order, Nov 17 ~11:52 AM ET ("CRM — unfreeze it, we build" · "Do not freeze the CRM — we can be done with it"). The Batch 003 delivery record is untouched; this batch builds on top of it as a separate batch with its own record, per change-control discipline.
**Status: IMPLEMENTED + TESTED (builder-side) · NOT INDEPENDENTLY VERIFIED · NOT MERGED · NOT DEPLOYED.**

Batch 004 closes the three builder-side gaps carried open out of Batches 002–003. Nothing here touches a money path, a send channel, an external provider, or deployment — those gates were not part of the unfreeze and remain the founder's separate decisions.

## 1. Real compose context (closes the Batch 002 placeholder limitation)
Batch 002's UI sent `context: {when: "—", title: "—", summary: "—", total: "—"}` — drafts carried placeholder text, and a human's approval hash would have bound to it. Now:
- The UI sends an empty context; the server resolves fields from the customer's **actual records**: reminder ← next upcoming booking (title + start rendered in the booking's own timezone, e.g. `2026-12-01 09:00 EST`); quote_ready ← latest quote (item summary + formatted total); invoice_ready ← latest invoice total.
- Explicit caller-supplied values always win over resolved ones.
- When a required field **cannot** be resolved (no upcoming booking, no quote, quote with no items, no invoice), compose **refuses** with a clear reason (API: HTTP 400) — a draft quoting a placeholder time or total is a false record, so none is created.

## 2. Audit-chain recovery (closes the Batch 003 flagged gap)
Batch 003 made tampering *detectable* but left no recovery procedure — the reviewer's open item. Now:
- `GET /api/audit/status` reports chain health (`ok`, row count, first bad row id).
- `POST /api/audit/recover` (owner-only) runs the recovery procedure: every existing audit row is preserved **verbatim** as a forensic snapshot (`audit_snapshots`, hash-sealed), and a new chain segment opens with a recovery row bound to that snapshot's hash.
- Verification is segment-aware: rows preceding the last recovery boundary are attested by snapshot equality (any later alteration or deletion of them is detected); rows after it chain normally.
- Recovery **refuses to run on an intact chain**, and its honest limit is stated in the code: recovery preserves evidence as found — it does not retroactively prove a tampered past; it restarts verifiable trust from the snapshot point.

## 3. Region / data-residency metadata (architecture checklist item 1)
`customers.region` and `customers.data_residency` are now real fields: accepted at creation (defaults: region unset, residency "US"), filled on duplicate-merge when empty, carried on the record and in every export. Item 1 of the canonical 14 moves from designed-for to built (metadata level — residency *enforcement* remains a deployment-layer matter).

## Tests — 67/67 passed (49 prior + 18 new, `tests/test_batch4.py`)
Real context: reminder from an actual booking (EN + HT renderings) · explicit context wins · reminder/quote compose refused when unresolvable · quote summary + `USD 50.00` · invoice `USD 1,234.56` · API compose with empty context returns real text · API unresolvable = 400.
Recovery: tamper → status names the first bad row → recover → chain verifies, new activity chains on · recovery on intact chain refused (service + API 400) · staff role refused (403) · post-recovery tamper detected · deleted pre-recovery row detected · snapshot tamper detected.
Region: fields on record + export · defaults · merge fill.
**Live smoke (fresh DB, HTTP):** HT customer with region US-FL created; Kreyòl reminder composed with the real booking — *"Bonjou Smoke HT, sa se yon rapèl pou randevou ou a 2026-12-03 09:00 EST: Randevou…"*; `/api/audit/status` healthy.

One builder note, honestly recorded: the first recovery-walk design re-verified prefix rows hash-by-hash and could never pass after a real tamper; it was redesigned to snapshot-attestation before delivery (two test iterations). The shipped semantics are the ones described above and proven by the tests.

## Changed files (SHA-256, copies under `code/mq-crm-batch004/`)
| File | SHA-256 |
| --- | --- |
| app/db.py | `0710f6b6a16980a053285c5651a46bcd28e463d81e9640528b87b686630d619b` |
| app/main.py | `6a70cff8bab3a3ba327547981360573043fd50c2812191de97ab3a67fb72aacd` |
| app/services/bookings.py | `2e66bb874a01a45b3a9a10d216dfc5b1aa306b109a5b49f3e12bacb3680561d6` |
| app/services/customers.py | `22c677652b9273381bd9ca9bb57ae7a8e1004242eaa44bfde2d0e848b3fc36cb` |
| app/services/messages.py | `d6a3c67692520ca1728bb7b00b305112237dd5b98f04c366882ae5a4affef783` |
| web/app.js | `40bdf357cf556b8f74865fe5aa3205a99be25fb794e4c548f4e13ef7375b971d` |
| tests/test_batch4.py | `61acba7b7eb5a42241e60df9ea6a065df2d412b3ec7470642ce9c9a017b4f5d1` |

## Remaining known limitations (unchanged gates, not oversights)
Send is still an audited state transition — **no SMS/email channel connected** (provider choice + privacy-terms review + founder approval required) · no external AI provider (privacy rule) · operator auth is a role header (deployment layer) · PT/HT native-speaker review still outstanding · SQLite single-process by design for the entry segment · Moose's own CRM implementation still unseen; his reconciliation remains his lane.

*KNOWLEDGE IS THE LEGACY.*
