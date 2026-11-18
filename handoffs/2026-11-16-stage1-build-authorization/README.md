# Package 3 — Stage 1 Build Authorization + Working Loop (2026-11-16)
**Status: ISSUED by the founder November 16, 2026. Delivered by Muse. Awaiting Moose's receipt via the Package 1 ACK.**

Contents:
- `00-AUTHORIZATION.md` — the founder's Stage 1 build authorization: scope frame, the build→inspect→correct→verify loop, hard evidence rules, and the founder gates that remain closed.

## How the loop runs in this repo
- **Moose's batch reports** for the Stage 1 build go in this folder under `reports/` (create it with your first batch): one file per batch, named `batch-YYYY-MM-DD-NN.md`, carrying: what was inspected/changed and why · files affected · tests executed with actual results · what remains incomplete · implemented / tested / deployed stated separately.
- **Consolidated corrections** land in this folder under `corrections/` as `corrections-YYYY-MM-DD-NN.md` — one list per cycle, combining Zelator's inspection findings and Muse's evidence verification. Moose works the list; the next batch report states, item by item, what was fixed and what was not, with evidence.
- Delivered files in this folder are never edited after delivery; corrections and reports are new files (the addenda discipline). Fingerprints rule: verify SHA-256 of anything you act on; Muse verifies yours the same way.
- The CRM workstreams stay distinct: Workstream A (reconciliation + audit) and Workstream B (LangChain/Langfuse POC) report under Package 1's folder as already instructed; Stage 1 build batches report here. The CONNECT evaluation (Package 2) remains its own lane.

*One source of truth, no screenshots, no unnecessary relays.*
