# Stage 2 — First Paper Trade Demonstration Output
Run: Mon Nov 16, 2026, ~11:05 AM ET · Code: PR #24 branch feature/stage2-paper-simulator-2026-11-16 (commit 7bcacf74) · Mode: synthetic, in-process (mongomock), no live system touched

```
====================================================================
STAGE 2 FIRST PAPER TRADE — SYNTHETIC DEMONSTRATION (PR #24 code)
====================================================================

--- 1. BUY alert -> punch + auto_execution ---
{
  "status": "created",
  "signal_id": "3a9b7da0-0f2b-4de9-8079-c0ffd3526255",
  "side": "long",
  "price": 25000.0,
  "is_test": false,
  "data_label": "PAPER",
  "auto_execution": {
    "status": "executed",
    "order_id": "ec7c2788-7139-4ae4-95b5-328642d30b77",
    "fill_price": 25000.0
  }
}

--- 2. Position after entry (brackets attached) ---
{
  "side": "LONG",
  "qty": 1,
  "avg_entry": 25000.0,
  "unrealized_pnl": 0.0,
  "sl_price": 24990.0,
  "tp_price": 25010.0
}
tick 25004.0: no exit (target 25010.0)
tick 25008.0: no exit (target 25010.0)

--- 3. PRICE tick at target -> automatic exit ---
{
  "ok": true,
  "action": "PRICE",
  "price": 25010.0,
  "exit": {
    "reason": "TAKE_PROFIT",
    "fill_price": 25010.0,
    "pnl": 20.0
  }
}

--- 4. Journal (operator_orders) ---
[
  {
    "action": "BUY",
    "fill_price": 25000.0,
    "origin": "AUTO",
    "phase": "SIM_LOG_ONLY",
    "exit_reason": null,
    "exit_pnl": null,
    "source_alert": {
      "signal_id": "3a9b7da0-0f2b-4de9-8079-c0ffd3526255",
      "action": "BUY",
      "source": "stage2-demo"
    }
  },
  {
    "action": "EXIT_LONG",
    "fill_price": 25010.0,
    "origin": "ENGINE",
    "phase": "SIM_LOG_ONLY",
    "exit_reason": "TAKE_PROFIT",
    "exit_pnl": 20.0,
    "source_alert": null
  }
]

--- 5. Reconciliation ---
journal exit P&L sum : 20.0
state daily_pnl      : 20.0
state daily_trades   : 1
position             : None (flat = True)
journal_failures     : 0

RECONCILED: journal == state. First paper trade complete: LONG 1 @ 25000.0 -> TAKE_PROFIT @ 25010.0 = +$20.00 (simulated).
```
