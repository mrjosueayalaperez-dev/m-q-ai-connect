# M&Q AI CONNECT — Integration Registry

Every integration between the shared layer and a project is recorded here: **what is shared, what is explicitly NOT shared, the verification evidence, and the date of last review.** An integration is not "live" until its evidence is recorded. One verified integration at a time (Blueprint §5).

---

## Integration #001 — Verified Local-Data Workflow (Proof #1)

- **Status:** REGISTERED — Phase 1 first proof integration
- **Adopted:** October 31, 2026, by founder decision (Blueprint v1.0 adopted as written; this workflow named Proof #1)
- **Capability:** C-LDW-001 — [capabilities/verified-local-data-workflow.md](capabilities/verified-local-data-workflow.md)
- **Source project:** Community Bridge (the pattern was proven there first)

### What is shared
- The **workflow itself**: collect from authoritative sources → verify every shipped field → hedge conflicts, never guess → exclude and document the unverifiable → date-stamp → publish with provenance and a pull rule.
- The standards inside it: an entry ships only with name + physical address + fetched source; the organization's own page outranks aggregators; phone-only answers fail.

### What is explicitly NOT shared
- Community Bridge's **dataset** (its 9 verified listings), its provenance records, and any future project's dataset. Each adopting project collects and owns its own data, inside its own boundary.
- No user data of any kind — Community Bridge holds none, and this integration moves none.

### Verification evidence
- Community Bridge dataset: 9 entries shipped with fetched authoritative sources, stamped "Verified 2026-10-23"; 7 candidates documented UNVERIFIED — EXCLUDED with reasons.
- Build checks 82/82 passed; release audit passed.
- Launched October 30, 2026; founder phone test passed in English and Spanish (typed + voice; real local places with street addresses, directions, tap-to-call).
- Live bytes re-verified byte-identical to the audited build on October 30 and October 31, 2026.
- Live product: https://mrjosueayalaperez-dev.github.io/Community-Bridge-/

### Boundary audit line
*Show me the exact boundary and the evidence it was respected:* the shared asset is a Markdown procedure in this repository. No database, account, feed, or user record is connected to anything by this integration. The only thing that crossed from Community Bridge into the shared layer is documented know-how.

### Last review
- October 31, 2026 (founding registration).

---

## Explicitly deferred (Blueprint §5 — not integrations, do not build)

- Any cross-bridge user data or identity linking.
- Shared user accounts or single sign-on across projects.
- Automatic agent-to-agent communication that bypasses founder gates.
- Voice agents in sensitive domains, pending specialized review.
