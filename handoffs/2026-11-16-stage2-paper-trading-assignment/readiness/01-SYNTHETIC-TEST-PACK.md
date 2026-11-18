# Stage 2 Synthetic Test Pack — acceptance demonstration scripts
**Prepared by Muse, November 16, 2026 · for Moose's Stage 2 batches (Package 4).**
All tests use synthetic alerts in the test environment only. `{{SECRET}}` is a placeholder — the real webhook secret is never written into any test file, report, or chat. Expected P&L uses the stated v1 fill model (last feed price, zero slippage/fees, MNQ $2/pt) unless Moose's batch report states a changed model, in which case expectations are recomputed against the stated model.

**Entry points available today:** `POST /signals/tradingview` (full inbound path) · `POST /signals/test-punch` (native test punch) · `POST /operator/order` + `/operator/control/*` (engine, write-key gated).

| # | Case (Package 4) | Script | Expected |
|---|---|---|---|
| 1 | BUY → one long | One synthetic BUY alert (unique event identity), automation enabled by founder action in test | Exactly one simulated LONG opened; journal entry carries the alert's identity; position qty/entry match the fill model |
| 2 | SELL → one short | One synthetic SELL alert (unique identity), flat book | Exactly one simulated SHORT opened; journal traceable to the alert |
| 3 | Duplicate → nothing | Re-send case 1's alert byte-identical | No new position, no new journal trade; duplicate recorded as duplicate |
| 4 | HOLD → nothing | One synthetic HOLD alert | No position, no order; HOLD recorded as HOLD |
| 5 | CLOSE → position closed | With case 1's long open, send the wired CLOSE | The corresponding position closes; exit journal entry names the originating alert; P&L booked per model |
| 6 | Stop/target fire automatically | Open a position with known SL/TP ticks; drive the price feed through the TP, then repeat through the SL | Exit executes at the bracket price in each run; exit reason (TP/SL) recorded; no manual action |
| 7 | Kill switch + daily limits block | (a) Kill switch ON → send BUY alert. (b) Set daily loss beyond limit → send BUY. (c) Exhaust daily trade count → send BUY | All three blocked with the correct reason; blocks journaled/logged; nothing opens |
| 8 | Journal accuracy + reconciliation | After cases 1–7, dump journal, positions, orders | Every action present, in order, values per model; journal ↔ position ↔ orders agree; zero unexplained differences |
| 9 | **Restart persistence (F1)** | Open a position, set daily P&L negative, restart the backend | Position, daily P&L, trade count, and kill/pause states survive exactly; no silent reset |
| 10 | **Opposing-quantity behavior (F4)** | SHORT 5 open; BUY 2 arrives as a wired alert | Behavior matches the rule Moose defines in his batch report (partial close of 2, or reject, or flatten) — the rule must be stated **before** the run and the result must match it |
| 11 | **Automation defaults OFF (F2)** | Fresh deploy/restart with no founder enable action; send a valid BUY alert | No trade. Then founder enables paper mode; re-send (new identity) → trade per case 1 |

**Reporting:** one results file per batch in `../reports/` — case number, input identity, observed output, PASS/FAIL, and the artifact (journal excerpt or log line) behind each verdict. A FAIL is a finding, not a failure of the process: it goes to Zelator's corrections loop like everything else.
