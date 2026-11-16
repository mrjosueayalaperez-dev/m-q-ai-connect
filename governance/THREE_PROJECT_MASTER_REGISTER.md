# M&Q Three-Project Master Register — Baseline: November 16, 2026

**The standing project record for M&Q CRM · M&Q AI CONNECT · MNQ Scalp Stacks Dashboard.**
Maintained by **Muse** (Chief of Staff) in this repository — the shared source of truth. Moose and Zelator entries are attributed; Moose adopts and verifies his lanes on return (Nov 17, 2026). Founder: Josue Ayala-Perez, final authority.

**Status vocabulary — strict, never interchangeable.** An item carries only the highest status its evidence supports:
**IMPLEMENTED** (built, exists in code/record) · **TESTED** (exercised, results recorded) · **INDEPENDENTLY VERIFIED** (checked by an agent other than the builder, against the artifact itself) · **FOUNDER ACCEPTED** (the founder's own test/decision) · **DEPLOYED** (live where its users are).
Companion rules: DELIVERED ≠ RECEIVED · PREPARED ≠ SENT · a waived precondition is recorded WAIVED, NOT MET · no unfinished project is ever described as complete.

**Evidence requirement:** every status claim names its artifact — a commit SHA, a test result, a live check, a dated founder decision. Claims without artifacts are PROPOSED.

---

## 1 · M&Q CRM
**Owner:** Moose (build) · **Review:** Zelator (independent) · **Coordination/evidence:** Muse · **Authority:** Founder.
**One line:** A CRM for solo → enterprise businesses whose niche is the comeback — reaching a business's existing lapsed-customer backlog — with the M&Q Language Bridge (EN · ES · PT · HT) at its core. Entry segment first: solo/small service businesses.

| Item | Status | Evidence |
|---|---|---|
| Research evidence base (20 lanes, Muse) | IMPLEMENTED | Round 1–3 packages + lane files, Nov 15–16 |
| Master Evidence Register v1 (30 claims + 14-item architecture checklist) | IMPLEMENTED · FROZEN | SHA-256 `6bd0cf99…`, delivered in Package 1 |
| Register v2 shell (POC intake, qualifications) | IMPLEMENTED | SHA-256 `e6386961…` |
| Product name + ecosystem architecture (working direction) | FOUNDER ACCEPTED (as direction, Nov 15) | Founder adoption; build gate separate |
| Stage 0 validation (founder-conducted conversations) | IMPLEMENTED (kit + scoring pack) · 0 conversations held | Field kit SHA `b8d40b27…`; scoring pack SHA `9bc65d48…` |
| Stage 1 build authorization | FOUNDER ACCEPTED (Nov 16, deliberate sequence override) | Package 3, commit `9f3cd805…` |
| Stage 1 acceptance checklist (incl. backlog-import demonstration safeguard) | IMPLEMENTED | SHA-256 `89d3f824…`, commits `a5595f27…` + `ff3030af…` |
| Moose receipt (ACK.md) | **MISSING** — Moose on timeout until Nov 17 | ACK watch running; template prepared (a template is not an acknowledgment) |
| Stage 1 implementation | **NOT STARTED** (authorized; not claimed otherwise) | No Moose branch/PR/reports as of Nov 16 |
| LangChain/Langfuse POC (synthetic data only) | ASSIGNED, NOT STARTED | Package 1 POC brief, SHA-256 `beec8367…` |
| Price band $19–$29 | PROPOSED — willingness-to-pay UNVERIFIED | Register v1 |

**Outstanding acceptance requirements:** Moose's ACK (his own hashes) · Stage 1 batches passing the acceptance checklist section by section · backlog import passing ONLY on the demonstrated synthetic test (validation rejections with reasons · duplicate rule · outcome report) · POC judged on the five adopted questions · privacy-professional review before any production deployment · founder gates unchanged: no production deployment, protected merges, destructive changes, purchases, contracts, or external contact without his approval.
**Next actions:** Nov 17 — Moose ACK, then Stage 1 batch 1 under `reports/` · Zelator reviews each batch · Muse verifies results · Stage 0 conversations proceed in parallel and feed corrections.

## 2 · M&Q AI CONNECT
**Owner:** Muse (meeting point + records) · **Evaluation:** Moose · **Review:** Zelator · **Authority:** Founder.
**One line:** The shared intelligence and coordination layer — independent projects, controlled task-authorized access, defined interfaces. NOT one giant AI.

| Item | Status | Evidence |
|---|---|---|
| CONNECT blueprint v1.0 | FOUNDER ACCEPTED (formally adopted Nov 13) | Adoption record |
| GitHub meeting point (this repo + handoff protocol) | IMPLEMENTED · TESTED · INDEPENDENTLY VERIFIED | Deliveries + read-back hash checks; Zelator inspection Nov 16 |
| Packages 1–3 (CRM package · architecture evaluation · Stage 1 authorization) | IMPLEMENTED (delivered) · 11/11 files hash-verified by Muse · independently inspected by Zelator | Branch `handoff/moose-crm-package-2026-11-16`; status note Nov 16 |
| Temporal orchestration evaluation (Package 2) | ASSIGNED to Moose, NOT STARTED | Package 2, commit `c0946ab9…` |
| Zelator's Temporal-centered recommendation + read-only "Agent Bridge" POC | PROPOSED — evaluation only, NOT adopted | Filed response, SHA-256 `dd5501d0…` |
| Temporal namespace `mq-ai-command-center.parib` | **UNVERIFIED** claim (previously discussed design detail) | Moose's first establishment task: is the existing Temporal environment still accessible — with evidence |

**Outstanding acceptance requirements:** Moose's evaluation answering the six assigned questions with evidence · no architecture adoption without founder decision · no integration build authorized by this register.
**Next actions:** Moose evaluation batch on return · founder decides any POC from evidence, not enthusiasm.

## 3 · MNQ Scalp Stacks Dashboard
**Owner:** Moose (build) · **Review:** Zelator · **Verification:** Muse · **Authority:** Founder.
**One line:** The trading dashboard and Command Center — SIM/PAPER discipline, live execution DISABLED, no profit promises, ever.

| Item | Status | Evidence |
|---|---|---|
| Webhook hardening PRs #20/#21 (fail-closed secret · HTTPS-only Discord · dedup · staleness · single-runner) | IMPLEMENTED · merged to main | Main HEAD `f3b488e4…` (PR #23) |
| Copilot hardening PR #22 (login-gated /ai/analyze · EN/ES · 30-day retention) | IMPLEMENTED · DEPLOYED (Vercel surface) · Copilot remains OFF | PR #22, Nov 14 |
| Vercel TradingView receiver | DEPLOYED (live) | https://mnqscalpstacks.com/api/signals/tradingview |
| GitHub↔Discord engineering webhook | IMPLEMENTED · TESTED · founder-confirmed in channel | Nov 14; URL rotation still owed |
| Gate 3 (test-alert proof) | **CLOSED AS WAIVED — not verified** (host being left) | Founder-confirmed HOLD received/checked Nov 14 |
| PAPER end-to-end on the current stack | **NOT TESTED** | Awaiting migration host |
| Migration off Emergent (Atlas + Render) | IN PROGRESS — **PAUSED by founder** Nov 16 at the founder-hands secrets step | Backups hashed (48 signals); Render service created, secrets unset |
| Automatic alert → paper-trade execution | **NOT IMPLEMENTED** (deliberately removed in the October safety hardening) | Zelator code inspection, Nov 16 |
| Internal simulator completeness (persistent positions · automatic stop/target exits) | PARTIAL — exits calculated/recorded, auto-trigger engine NOT VERIFIED; orders SIM_LOG_ONLY | Zelator code inspection, Nov 16 |
| Bot B — Strategy B paper detector (separate lane) | IMPLEMENTED · TESTED (detector + 20 tests; live runner: zero trades, no range supplied — as designed) | Branch `feature/bot-b-outer-range-extremes` |
| Stage 2 — finish internal simulator + connect validated alerts to paper execution (NinjaTrader Sim101 via ATI as fallback) | **FOUNDER ACCEPTED** — adopted into Moose's queue Nov 16, 2026; build NOT STARTED | Assignment = Package 4 (commit `22a52fb6…`); acceptance = 8-point synthetic demonstration (BUY/SELL/HOLD/CLOSE/duplicates/stops-targets/risk limits/journal) |
| Strategy B parameters (15m range, risk, exits) | **MISSING** — founder-supplied only; never invented | Bot B waits |

**Outstanding acceptance requirements:** Founder decisions — Stage 2 adoption · migration resume (his hands, guided live) · F2 Atlas-URI ruling · seeded demo-data decision (rides migration). PAPER runs only on the post-migration host; PAPER on Emergent is off the table. Live trading is not authorized at any stage of this register.
**Next actions:** Stage 2 is in Moose's queue (Package 4 — branch + synthetic tests only; deployment separately gated; running PAPER waits for the post-migration host) · migration resumes only on the founder's word.

---

## Family Bridge — PARKED, NOT ABANDONED
v2.6 LIVE (Nov 15, 2026) · founder phone test PASSED · set aside by the founder's order. Parked items: HT/PT native review (waived-not-met) · preparedness + First-48-Hours content (v2.7 candidates) · Family Defense listing decision (founder's call only). Not part of the three active projects; nothing here is abandoned, and nothing reopens without the founder.

## Update rule
This register changes only when evidence lands: a delivery, a test result, an independent verification, a founder decision. The editor names the evidence and the date. Statuses never move on summaries, relays, or enthusiasm.
