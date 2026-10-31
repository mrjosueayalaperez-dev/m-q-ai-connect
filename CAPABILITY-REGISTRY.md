# M&Q AI CONNECT — Capability Registry

> **STATUS: ADOPTED FRAMEWORK.** Blueprint v1.0 was adopted by the founder on October 31, 2026 (CHANGE-REPORT-2026-10-31.md, Addendum 2). Registration records that a capability is *documented with evidence*; reuse approvals are recorded per entry, below.

The registry of shared capabilities. **Inventory rule (Blueprint §4):** nothing enters this library until it has been used successfully in at least one project and reviewed under the verification standard. Every entry carries: a named **owner**, its **approved consumers**, its **evidence**, and its **last-verification date**.

**Maturity ladder** (Blueprint §3, as amended): DOCUMENTED → IMPLEMENTED → TESTED → INDEPENDENTLY VERIFIED → APPROVED FOR REUSE. Evidence is labeled by class: *founder-reported* is never presented as *independently verified*.

---

## Documented capabilities

### C-LDW-001 — Verified Local-Data Workflow
- **Document:** [capabilities/verified-local-data-workflow.md](capabilities/verified-local-data-workflow.md)
- **Version:** 1.0 · **First documented:** October 31, 2026
- **Category:** Local / Community Patterns
- **Owner:** Muse (documenting agent — steward of this library draft). Approver of record for any status change: the Founder.
- **Proven in:** Community Bridge (the pattern's first and only use so far).
- **Approved consumers:** Approved for reuse by any M&Q project under the adopted blueprint (October 31, 2026) — each adopter collects and owns its own data, inside its own boundary. Community Bridge is the source project, not a consumer. **Phase 1 reuse in progress:** One-Minute Page — candidate built and agent-verified October 31, 2026 (owner-confirmed date-stamp + provenance on the generated page); founder phone test pending; not yet counted as an adoption.
- **Scope:** Any M&Q project publishing local service information — the pattern only. Each project's data is its own and never crosses.
- **Boundary:** Procedure and standards documented here. Datasets, listings, and provenance records never shared.
- **Evidence:**
  - Community Bridge dataset: 9 entries shipped with fetched authoritative sources, stamped "Verified 2026-10-23"; 7 candidates documented UNVERIFIED — EXCLUDED with reasons. *(Agent-verified: build record and provenance file.)*
  - Build checks 82/82 passed; release audit passed. *(Agent-verified.)*
  - Launched October 30, 2026; live bytes re-verified byte-identical to the audited build on October 30 and 31, 2026. *(Agent-verified.)*
  - Founder phone test passed in English and Spanish (typed + voice). *(**Founder-reported** — the founder's own attestation; not independent verification.)*
- **Last verification date:** October 31, 2026 (byte-identity re-check).
- **Maturity:** DOCUMENTED ✔ · IMPLEMENTED ✔ *(within Community Bridge only — the product implements the pattern; no cross-project implementation exists)* · TESTED ✔ *(founder-reported)* · INDEPENDENTLY VERIFIED — **pending** (independent verification of the Community Bridge evidence is still outstanding; adoption does not change an evidence class) · APPROVED FOR REUSE ✔ — **approved October 31, 2026**, under the founder's adoption of Blueprint v1.0, which designates this workflow as the first proof. Reuse means another project follows the documented pattern with its own data; it never moves a dataset.

---

## Emerging capabilities (not yet registered)

Formalization is Phase 2 work (Capability Library v0.1: 3–5 capabilities). These are in real use across the ecosystem; they enter the registry only after the inventory rule is applied to each, one at a time, with owner, consumers, evidence, and last-verification date recorded:

- **Draft → Review → Approve workflow** — the human + AI loop (drafting, critique, founder approval gates) used for launches and publications.
- **Governed drafting from founder-approved knowledge** — consistent drafting against approved materials, doctrine, and style (MOOSE workflow).
- **Bilingual voice/typed local-answer pattern** — ask by voice or text in English or Spanish; answer with a real place, address, and directions (in use in Community Bridge).
- **Bilingual (EN/ES) parity production** — every figure, label, and readout in the student's language (M&Q University standard).
- **Launch pipeline** — the verified multi-channel publication sequence (prepare → founder per-item approval → publish → verify no duplicates), used at the University and Community Bridge launches, October 30, 2026.
- **Educational content & teaching patterns** — lesson structure, animated instructor standard, simulator contracts (M&Q University).
- **Meal-planning engine pattern** — budget/headcount/allergy-aware planning with honest connected/not-connected labeling (Plates for Hope).

## Registry discipline

- Entries are added only with a version and a documentation date; status changes (especially APPROVED FOR REUSE) require the founder's explicit approval.
- A capability's scope can be narrowed at any time; widening it is a new founder decision.
- Sensitive-domain capabilities (medical, financial, crisis, or other regulated information — voice agents included) require specialized security, consent, and regulatory review before they may be listed here. They are never plug-and-play.
- CONNECT has no autonomous powers: it cannot publish, spend money, access project databases, change project doctrine, or execute trades.
