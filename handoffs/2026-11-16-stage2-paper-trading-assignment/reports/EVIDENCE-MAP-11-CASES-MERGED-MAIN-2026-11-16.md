# Stage 2 — 11-Case Evidence Map, Executed Against Merged Main
**Date:** November 16, 2026 · **Code under test:** Dashboard repo `main` at `6d4f3c7e` (PR #24 merge, incl. Zelator-review corrections `b35fa4d`) · **Run by:** Muse
**Method:** `backend/tests/test_stage2_paper.py` executed against a clean checkout of merged main — **20/20 PASSED** (plus hardening 51/51 on the same code). This map ties each case in `readiness/01-SYNTHETIC-TEST-PACK.md` to its proving test(s). It is the builder-side evidence pack for Zelator's independent re-review; it does not replace it.

| # | Synthetic case | Proving test(s) on merged main | Result |
| --- | --- | --- | --- |
| 1 | BUY opens exactly one long, traceable to its alert | `test_auto_buy_one_long_with_alert_identity` (journal origin AUTO + `source_alert.signal_id` == punch id; brackets 40 ticks → ±10 pts) | PASS |
| 2 | SELL opens exactly one short | `test_auto_sell_one_short` (short-side bracket orientation verified) | PASS |
| 3 | Duplicate alert creates nothing | `test_duplicate_alert_no_second_trade` (second identical alert → `duplicate`, no auto_execution, 1 order, daily_trades 1) | PASS |
| 4 | HOLD never opens a trade | `test_hold_never_trades` | PASS |
| 5 | CLOSE closes the corresponding position | `test_auto_close_closes_position` (CLOSE_LONG journaled, origin AUTO, position flat) | PASS |
| 6 | Stop-loss and target exit automatically | `test_bracket_take_profit_fires_on_tape` (+$20.00) · `test_bracket_stop_loss_fires_on_tape` (−$20.00) — exits driven by PRICE tape ticks, journaled by the engine with reason | PASS |
| 7 | Kill switch / limits block new trades | `test_kill_switch_blocks_signal` (both layers: signal-layer refuses the alert; operator-layer blocks execution) · `test_daily_loss_limit_blocks_auto` (blocked with reason surfaced) | PASS |
| 8 | Every trade journaled with full economics | `test_auto_buy_one_long_with_alert_identity` (fill, brackets, phase SIM_LOG_ONLY) · the first-trade demonstration file `DEMO-FIRST-TRADE-2026-11-16.md` (journal == state reconciliation printout) | PASS |
| 9 | Restart preserves position AND risk state | `test_state_persistence_roundtrip` (position + daily P&L + trade count + kill switch restored) · `test_hydrate_failure_blocks_automation` (failed restore → automation unavailable) | PASS |
| 10 | Opposing orders respect quantity | `test_opposing_partial_then_flip` (partial close books partial P&L; remainder keeps brackets; leftover flips with correct avg entry) | PASS |
| 11 | Automation defaults OFF; skips are visible | `test_automation_off_by_default_no_trade` (skip reported with reason `automation_off`) · `test_missing_exec_params_no_trade` (skip reported, never silent) | PASS |

**Correction-specific evidence (Zelator PR #24 findings):**
- Fail-closed persistence: `test_persist_failure_forces_automation_off` · `test_persistence_recovery_restores_flag` (recovery restores the flag; automation does NOT auto-resume) — PASS
- Ceilings: `test_oversized_alert_rejected` (qty 50 rejected; 5000-tick bracket rejected) · `test_validate_order_qty_ceiling` — PASS
- Journal failure in the decision: `test_journal_failure_counted` (manual path: visible `journal_ok=False`, `degraded=True`) · `test_auto_journal_failure_halts_automation` (`executed_journal_failed`, automation halted) — PASS

**Status after this map:** IMPLEMENTED · MERGED · builder evidence complete against all 11 cases on the merged code. Remaining gates unchanged: Zelator's independent re-review · deployment (post-migration host) · founder enablement. Synthetic results do **not** count toward the approved 20 PAPER sessions.
