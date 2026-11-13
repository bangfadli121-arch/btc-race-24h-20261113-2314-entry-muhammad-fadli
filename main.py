"""Deterministic CBBTC strategy for the agent-fun bars-replay/v1 protocol."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars


SYMBOL = "CBBTC"
FAST_SPAN = 60
SLOW_SPAN = 240
DIP_SPAN = 480
LOW_WINDOW = 120
MAX_SLIPPAGE_BPS = 10_000

fast_ema = None
slow_ema = None
dip_ema = None
previous_fast = None
previous_slow = None
recent_closes = []


def update_ema(current, close, span):
    """Update one EMA using the specified deterministic float operation order."""
    if current is None:
        return float(close)
    return current + (2.0 / (span + 1)) * (close - current)


def on_batch(state, batch):
    """Handle a protocol batch/bar: build EMA history, then return zero or one order.

    The makefun shim handles hello and reply formatting; this function examines only a fresh
    CBBTC bar from this batch and returns the batch's orders.
    """
    global fast_ema, slow_ema, dip_ema, previous_fast, previous_slow, recent_closes

    bar = next((item for item in batch["bars"] if item["symbol"] == SYMBOL), None)
    if bar is None:
        return []

    close = int(bar["c"])
    old_fast, old_slow = fast_ema, slow_ema
    fast_ema = update_ema(fast_ema, close, FAST_SPAN)
    slow_ema = update_ema(slow_ema, close, SLOW_SPAN)
    dip_ema = update_ema(dip_ema, close, DIP_SPAN)
    previous_fast, previous_slow = old_fast, old_slow

    recent_closes.append(close)
    if len(recent_closes) > LOW_WINDOW:
        del recent_closes[0]

    # Warm-up bars still build every indicator and the low window, but never place orders.
    if state.warming_up:
        return []

    holding = state.positions.get(SYMBOL)
    if holding is None:
        low120 = min(recent_closes)
        ema480_int = int(dip_ema)
        dip_bounce = (
            ema480_int > 0
            and (ema480_int - close) * 10_000 // ema480_int >= 120
            and low120 > 0
            and (close - low120) * 10_000 // low120 >= 75
        )
        crossed_up = (
            previous_fast is not None
            and previous_slow is not None
            and fast_ema > slow_ema
            and previous_fast <= previous_slow
        )
        minimum_notional = int(state.hello["fees"]["min_notional_quote_units"])
        if (dip_bounce or crossed_up) and state.cash >= minimum_notional:
            return [{
                "side": "buy",
                "symbol": SYMBOL,
                "notional_quote_units": state.cash,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }]
        return []

    cost = holding.cost
    value = state.value(SYMBOL, holding.qty)
    crossed_down = (
        previous_fast is not None
        and previous_slow is not None
        and fast_ema < slow_ema
        and previous_fast >= previous_slow
    )
    if value * 10_000 >= cost * 10_200 or value * 10_000 <= cost * 9_600 or crossed_down:
        return [{
            "side": "sell",
            "symbol": SYMBOL,
            "qty": holding.qty,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    return []


if __name__ == "__main__":
    # The shim reads hello, then each batch, and writes exactly one reply per batch.
    makefun_bars.run(on_batch)
