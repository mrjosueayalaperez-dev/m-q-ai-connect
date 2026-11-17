# M&Q CRM — INSPECTION READINESS MAP: Batch 002 (builder-side readings for the independent inspectors)
**Date:** November 17, 2026 · **Prepared by:** Muse (builder) · **For:** Moose (Workstream 1 reconciliation) and Zelator (independent inspection) · **Batch 003: FROZEN** by the founder-relayed decision of Nov 17 — no new features until independent verification results land. No code was changed in preparing this map.

**How to read this:** each inspection target from the Nov 17 assessment gets the builder's honest reading — HOLDS (builder-tested) · PARTIAL · GAP · UNVERIFIED — with the exact place to look. **These readings are claims to confirm or refute, not verification.** Where my reading says GAP, I have deliberately NOT fixed it: the surface under inspection stays exactly as delivered until the independent layer reports.

## The eight targets

1. **Approval is tied to the exact message content and translation version being sent.**
   **Reading: GAP.** Approval attaches to the message *record*, not to a content fingerprint. Nothing hashes or versions the text at approval time, and `supply_translation` can still alter `translated_text` after approval. An inspector should test: approve → change the translation → send, and observe that the sent text is not the approved text. (`app/services/messages.py`: `approve`, `supply_translation`, `send`.) Candidate remedy class for a future batch: content hash recorded at approval, re-verified at send; translation supply locked after approval.

2. **Changing approval-related database fields cannot bypass authorization.**
   **Reading: PARTIAL.** The translation-pending bypass found by the battery is closed (`send` re-checks `translation_pending`). But the `status` field itself remains a flag: an actor with direct database write access who sets `status='approved'` on an ordinary draft reaches `send` successfully. Within the API this is unreachable (no endpoint sets status except through the guarded transitions). The database file is currently the trust boundary of this single-process design — the inspector should state whether that boundary is acceptable at this stage or must move.

3. **Consent is checked again at send time, not merely at draft creation.**
   **Reading: GAP.** Consent is enforced at compose time only (`compose_template`, marketing templates). `send()` does not re-check the customer's current consent, and no withdraw-consent operation exists yet. Test: create a consented customer, compose a comeback draft, flip `consent_marketing` to 0 in the database, send — it sends. Candidate remedy: re-check consent in `send()` for marketing templates + a consent-withdrawal operation with audit.

4. **Duplicate-send protection under simultaneous requests.**
   **Reading: UNVERIFIED.** Sequential duplicate send is refused and tested. Concurrency is not tested: `send()` reads status, then updates, without an atomic compare-and-set; two truly simultaneous calls could in principle both pass the read. The shared single connection narrows the window in practice but does not formally close it. Candidate remedy: atomic `UPDATE ... WHERE status='approved'` with rowcount check. The inspector should attempt a concurrent double-send (e.g. two threads, one barrier) and report what actually happens.

5. **Failed-send audit records cannot be silently lost or modified by the sending actor.**
   **Reading: PARTIAL.** Through the API, audit rows are append-only — no endpoint reads-modifies or deletes them, and denied sends now write `send_message_denied` rows. At the storage layer, the audit lives in the same database the application writes, so a database-level actor could alter history. Tamper-evidence (hash-chained audit, external sink) does not exist at this stage.

6. **Role restrictions are enforced server-side.**
   **Reading: HOLDS (builder-tested).** Mutations require owner/staff; deletion and full export require owner; the battery includes viewer-role refusals on approve/send. (`app/main.py`: `require_write`, `require_owner`.) Note for the inspector: the role arrives as a header — authentication of the operator is a deployment-layer concern that does not exist yet (nothing is deployed).

7. **EN and ES workflows preserve consistent state throughout the journey.**
   **Reading: HOLDS (builder-tested).** `tests/test_journey.py` runs the full journey in both languages with state assertions at each step. The inspector's independent run of the same journey — ideally driving the API rather than the services — is the confirming evidence.

8. **The export does not expose unauthorized or unintended customer information.**
   **Reading: PARTIAL.** Full export is owner-gated in code (`require_owner` on `/api/export`); per-customer export returns that customer's records and children only. Two honest notes: (a) the export endpoints' role gate has **no dedicated test** in the suite (the delete gate does); (b) export content includes message originals and translations by design — that IS the customer's data under "Your Data Is Yours," but the inspector should confirm nothing beyond the customer's own records rides along (e.g. no other customers' rows, no audit internals — audit rows are not included).

## Release boundary (unchanged)
M&Q CRM Batch 002 (+ verification supplement): **IMPLEMENTED + TESTED (39/39) · NOT INDEPENDENTLY VERIFIED · NOT MERGED · NOT DEPLOYED.** Batch 003 frozen pending the independent results this map supports.

*KNOWLEDGE IS THE LEGACY.*
