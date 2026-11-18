# M&Q CRM — REVIEWER CHALLENGE INDEX: Batch 003 (for the independent reviewer)
**Date:** November 17, 2026 · **Prepared by:** Muse (builder) · **Status of the build:** IMPLEMENTED + TESTED (49/49) · NOT INDEPENDENTLY VERIFIED · NOT MERGED · NOT DEPLOYED. **Feature expansion is frozen** while this review runs.

Each challenge from the Nov 17 assessment maps to the evidence to attack and the test that currently covers it (builder-side). **Break them if you can; report what actually happens.** A challenge marked COVERED means a builder test exists — your independent run, ideally driving the API and the database rather than the service functions, is the confirming evidence.

| # | Challenge | Where to attack | Builder test on record |
| --- | --- | --- | --- |
| 1 | Translation accuracy & cultural meaning — PT | `app/i18n.py` TEMPLATES + UI ("pt") | Journey PT passes mechanically — **meaning is NOT testable by code** |
| 2 | Translation accuracy & cultural meaning — HT | `app/i18n.py` TEMPLATES + UI ("ht") | Journey HT passes mechanically — **meaning is NOT testable by code** |
| 3 | Approval invalidation after content changes | `services/messages.py` approve/supply_translation/send | test_batch3: change-after-approval, DB text tamper, flag-only tamper — all refused |
| 4 | Consent withdrawal immediately before sending | `services/messages.py` send + `services/customers.py` set_consent | test_batch3: withdraw after approval → send refused |
| 5 | Simultaneous duplicate-send attempts | `services/messages.py` send (atomic UPDATE) | test_batch3: two-thread race, exactly one winner — try more threads, and via the API |
| 6 | Audit-chain tampering and recovery | `app/db.py` audit/verify_audit_chain | test_batch3: tampered row → chain verification fails. **Recovery is undefined** — there is no repair procedure; report whether that is acceptable at this stage |
| 7 | Unauthorized exports | `app/main.py` /api/export, /api/customers/{id}/export | test_batch3: staff/viewer refused, owner served — try header tricks and role confusion |
| 8 | Language consistency across the lifecycle | per-customer `language` through compose in all services | test_journey ×4 languages — try mid-lifecycle language changes and mixed-language free text |

## The one challenge no code can close
Challenges 1–2 require **native speakers** of Portuguese and Haitian Creole reading the actual strings for meaning, tone, and cultural fit. Until that review happens, the honest status is: **PT/HT implemented + mechanically tested · native quality NOT VERIFIED** — and no report from any agent should upgrade that line.

## What the builder asks of the review
Reconcile against Register v1 + the 14-item checklist (Moose WS1) and inspect the implementation independently (Zelator). One consolidated corrections list under `corrections/`; the builder implements; verification re-runs. Production remains a separate founder decision, always.

*KNOWLEDGE IS THE LEGACY.*
