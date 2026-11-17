# M&Q CRM — MOOSE ASSIGNMENT: Batch 004/005 GitHub Evidence Reconciliation (founder assignment, as relayed Nov 17, 2026)
**To:** Moose — Lead Developer · **From:** Josue — Founder · **Review:** Zelator — Independent Technical Reviewer · **Priority:** Next incremental assignment. Filed by Muse into the meeting point.

## Mission
Reconcile Batches 004 and 005 against the actual GitHub repository. Establish that the code, tests, reports, and verified fingerprints correspond to the exact artifacts delivered. This is an evidence-reconciliation assignment, not permission to modify the frozen baseline.

## 1. Establish the exact repository state
For each batch, record: repository and branch · exact commit SHA · relevant file paths · recorded fingerprint and independently recalculated fingerprint, where possible · whether the GitHub files match the delivered artifacts byte-for-byte · any discrepancy between the report, fingerprint record, and repository. Do not assume that a fingerprint proves correctness. It establishes file integrity only when independently matched to the correct artifact.

## 2. Reconcile Batch 004
Identify the implemented changes and their corresponding tests. Verify that the repository contains the exact reviewed version. Map each claimed behavior to its implementation and test evidence.

## 3. Reconcile Batch 005 — Delivery Layer
Inspect the actual implementation and evidence for:
1. Dispatch records and their permanent history.
2. Exact-text snapshots and their relationship to human approval.
3. Outbox transport and truthful delivery-status wording.
4. Webhook refusal when provider terms have not been reviewed and recorded.
5. Zero outbound payloads when provider review is absent.
6. Retry behavior on the original dispatch record.
7. Audit records for successful dispatches, failures, and refusals.

Specifically identify whether any alternate execution path, direct database modification, or retry path could bypass these controls.

## 4. Test evidence
Reconcile the reported 76/76 tests: identify the test command and environment · map tests to the controls they actually exercise · identify missing negative tests and edge cases · confirm whether the Spanish end-to-end smoke is reproducible from the repository state · distinguish automated test results from manual observations. Do not report a test as independently verified unless you actually reproduce it.

## 5. Required report
Deliver: **M&Q CRM — Batch 004/005 GitHub Evidence Reconciliation**, including: exact commit SHAs and fingerprints · file-by-file reconciliation · test evidence and reproducibility · delivery-layer security and privacy findings · discrepancies, missing evidence, and unresolved risks · a clear verdict for each batch: PASS, CONDITIONAL PASS, or FAIL · a list of findings requiring a separate corrective batch. For every finding, include the file path and relevant code or test reference.

## 6. Strict authorization boundaries
- Do not modify the frozen Batch 003, 004, or 005 baselines.
- Do not silently patch defects.
- Do not merge or deploy.
- Do not connect a real external messaging provider.
- Do not transmit real customer data.
- Do not change credentials, provider configurations, or production settings.
- Do not spend money or introduce paid services.
- Use synthetic data for any additional testing.

If a defect is found, document it for a separately authorized corrective batch.

## 7. Readiness gates remain separate
This reconciliation does not authorize: real provider connection · production deployment · commercial release · Portuguese or Haitian Creole native-speaker approval.

## Final instruction
Report only what the repository and reproducible evidence establish.

**Implemented ≠ Tested ≠ Independently Verified ≠ Merged ≠ Deployed.**

Moose reports directly to Josue. Zelator independently challenges the delivered evidence. Josue retains final decision authority.

**Build it. Test it. Verify it. Then earn the right to sell it.**
