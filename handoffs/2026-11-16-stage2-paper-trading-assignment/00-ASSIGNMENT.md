# Stage 2 Assignment — Alert-Triggered Paper Trading (MNQ Scalp Stacks Dashboard)
**For Moose (Lead Developer) · from the founder, through Muse · November 16, 2026**

**Origin:** Recommended by Zelator on Nov 16, 2026 from his code inspection of `Mnqscalpstacks.-Dashboard-emergent` (his finding: the alert receiver, validation, and manual simulated execution exist; the automatic alert → paper-trade path was deliberately removed in the October safety hardening; the internal simulator is partial). **Adopted by the founder on Nov 16, 2026 (~9:03 AM ET) into Moose's queue.**
**Queue position:** After (1) the CRM ACK and (2) CRM Stage 1 underway. This is the next Dashboard work — it does not displace the CRM build.

## Objective
When a valid MNQ alert fires, the founder can open the Command Center and see the simulated trade — entry, stop, target, and eventual result — recorded automatically. Entirely inside our own ecosystem first: TradingView alert → our dashboard → simulated MNQ entry → stop/target management → paper-trade journal. **No real orders. No broker routing. Ever.**

## Part A — Complete the internal simulator
Current limitations (Zelator's inspection — verify against the code yourself): position state in server memory · orders recorded `SIM_LOG_ONLY` · stop/target prices calculated and recorded but no verified engine automatically triggers those exits.
Build/fix, on an isolated branch:
1. **Persistent positions** — position state survives restart (database-backed), consistent with orders and journal.
2. **Automatic stop/target exit engine** — verified monitoring that closes simulated positions at stop or target, with the exit reason recorded.
3. **Fill model** — state the assumptions you implement (price source, fill price rule); no silent realism claims.
4. **Fees and slippage** — modeled with the values stated in your report; if you use zero, say so and why.
5. **Reconciliation** — journal ↔ positions ↔ orders agree after every test sequence; discrepancies are defects, reported as such.

## Part B — Connect validated alerts to the paper engine
Authenticated BUY/SELL alert → existing validation (strategy, freshness, direction, entry, risk, duplicate checks) → paper execution (simulated entry, stop loss, target, quantity) → journal entry traceable to the originating alert.
**Mandatory protections (all of them, no exceptions):**
- Automation **OFF by default**; the founder explicitly enables paper mode.
- **No live broker routing or real orders** — the disabled-routing state stays disabled.
- One trade per unique eligible alert; duplicates create nothing.
- HOLD never opens a trade. CLOSE closes only the corresponding simulated position.
- Kill switch, daily loss limit, trade limit, cooldown, and stale-data protections remain active and demonstrably effective.
- Strategy A / Strategy B confirmation alerts stay disabled until their pending parameters are approved. Strategy B is never traded without founder-supplied 15-minute range boundaries and risk parameters — no silent bypass.
- Every simulated trade traceable to its originating alert (alert identity stored on the trade).

## Hard boundaries
Branch + PR only · no merge to a protected branch, no deployment, no spending without founder approval · no live trading at any stage · synthetic/test alerts only for the acceptance demonstration. **Host note:** operating PAPER beyond synthetic tests waits for the post-migration host (Render) — PAPER on Emergent is off the table. The acceptance path for this assignment is the synthetic demonstration in the test environment.
**Fallback (held, not authorized):** if the internal fill model proves insufficiently realistic, report that finding with evidence; NinjaTrader Sim101 via ATI is the named fallback and requires a separate founder decision. Do not switch unilaterally.

## Acceptance — the demonstration (all eight, with test evidence)
1. Test BUY alert creates exactly one simulated long.
2. Test SELL alert creates exactly one simulated short.
3. Repeated alert creates no duplicate.
4. HOLD creates no position.
5. CLOSE closes the simulated position.
6. Stop and target calculations are correct — and fire automatically.
7. Kill switch and daily risk limits prevent prohibited entries.
8. The journal records every action accurately, and reconciliation (Part A.5) passes.
Reports land in this folder's `reports/`; Zelator's consolidated corrections in `corrections/`. Zelator independently reviews the demonstration · Muse verifies the actual results · the founder accepts. Implemented ≠ tested ≠ verified ≠ accepted ≠ deployed.
