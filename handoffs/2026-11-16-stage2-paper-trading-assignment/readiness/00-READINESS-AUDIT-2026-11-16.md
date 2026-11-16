# Stage 2 Readiness Audit — MNQ Scalp Stacks Dashboard
**By Muse (Chief of Staff), November 16, 2026 · read-only code audit of `Mnqscalpstacks.-Dashboard-emergent` main @ `f3b488e4` (PR #23).**
Purpose: verify Zelator's Nov 16 inspection first-hand and give Moose a precise, evidence-anchored starting map for Package 4. Nothing was changed. Line anchors are `backend/server.py` unless named.

## Verified present (builder: prior work · verified by: Muse, today)
- **Alert inbound** — `POST /signals/tradingview` (L1277): fail-closed secret check; action whitelist BUY/SELL/CLOSE/HOLD/PRICE; PRICE = tape update only; HOLD recorded, never trades; signal-layer kill-switch block; BUY/SELL → `_create_punch` (L1200) which dedupes (same-side cooldown via `check_duplicate_signal`), persists to `db.signals`, fans out to Discord, labels PAPER. A native test entry exists: `POST /signals/test-punch` (L1345).
- **Manual simulated execution** — `POST /operator/order` (L2845), write-key gated. Full safety chain in `_validate_order` (L2740): kill switch → automation-paused (AUTO_ actions) → daily-loss lockout → max daily trades → cooldown → LIMIT sanity. Fill: MARKET = live feed last price (Yahoo NQ=F cache); LIMIT = order price (`_resolve_fill_price`, L2758). Journal entry built with fill, bracket prices, resulting position, daily P&L, phase `SIM_LOG_ONLY`; inserted into `db.operator_orders`. Response states ATI `routed: false` — broker routing disabled. ✓
- **Controls** — `POST /operator/control/{flatten|pause|resume|kill|unkill|reset_session}` (L2869), write-key gated.
- **Brackets calculated** — `_bracket_price` (L2822): SL/TP from ticks (0.25 pt) off the fill, correct side per action; recorded on the journal entry.
- **Strategy doctrine enforced in code** — `strategy_engine.py`: Strategy A confirmation alerts disabled until `STRATEGY_A_PARAMETERS_APPROVED` (L354); Strategy B refuses without supplied `range_high`/`range_low` — "will not invent a range" (L401–403) — and its confirmation alerts are likewise disabled (L475).
- **No signal → order path exists.** `_validate_order`/`_apply_fill` are called only from `operator_order`. Zelator's central finding is confirmed first-hand: the automatic alert → paper execution path is absent, by design.

## Verified missing (the Stage 2 build, mapped to Package 4)
- **A1 Persistence** — position lives in the in-memory `_operator_state` dict (L2781+). Nothing survives a restart.
- **A2 Automatic exits** — SL/TP are computed and journaled, but no code reads `sl_price`/`tp_price` to trigger an exit. No monitoring loop exists.
- **B The connection itself** — no path from a validated punch to an AUTO_ operator order; no alert identity stored on any trade (traceability to build).

## New findings (not in Zelator's inspection — for Moose's first batch)
- **F1 · Risk state is as volatile as position state.** `kill_switch`, `automation_paused`, `daily_pnl`, `daily_trades`, `last_order_at` all live in `_operator_state`. A backend restart silently resets the daily-loss lockout and trade count along with the position. Part A persistence must cover the **risk state**, not only positions.
- **F2 · Automation gate defaults OPEN.** `_operator_state["automation_paused"]` initializes `False` (L2603). Today nothing sends AUTO_ orders, so nothing fires — but the day Part B lands, the founder-enable requirement (Package 4) means the auto path must default to **paused/OFF**, founder-enabled explicitly. Required change, not a detail.
- **F3 · Journal persistence is best-effort.** The `operator_orders` insert is wrapped in try/except that logs a warning and still returns success (L2858–2861). A lost journal write is invisible today. Stage 2 reconciliation (A5) must treat a failed journal write as a defect — make the write transactional with the fill or alarm on failure.
- **F4 · Opposing action flattens regardless of quantity.** In `_apply_fill` (L2784–2801), BUY against a SHORT (any qty) closes the **entire** position and books full P&L; same for SELL against LONG. Part B's one-trade/CLOSE semantics must define quantity-aware behavior explicitly; the test pack adds a case.
- **F5 · Two different CLOSEs.** Alert-side CLOSE (L1336) expires active **signals**; position-side close is `CLOSE_LONG`/`CLOSE_SHORT`/flatten in the operator engine. Stage 2 must wire alert CLOSE → position close deliberately; today they are unrelated acts with the same name.
- **F6 · Fill model, stated.** Current model = last live-feed price, zero slippage, zero fees, MNQ multiplier $2/pt hardcoded in P&L (`_apply_fill`). Acceptable as the v1 model **if stated** (Package 4 A3/A4) and if the demonstration's expected values are computed against it.

## Readiness verdict
**READY TO BUILD.** The foundation Zelator described is real and verified: authenticated inbound, validation, a complete safety chain, a working manual simulator core, doctrine enforced in code. The gaps are exactly the assigned ones (persistence, exit engine, the connection) plus F1–F5 above, all buildable on an isolated branch with synthetic tests. Nothing here requires Emergent, a new platform, or spending. Operating paper still waits for the post-migration host, per Package 4.

*Audit method: full clone of main; targeted reads of the order, validation, ingestion, and strategy paths. Claims graded VERIFIED only where the code itself was read.*
