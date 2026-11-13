# CBBTC 24-hour race bot

This Python 3.13 bot trades only CBBTC and keeps at most one long position. It reads the
`agent-fun/bars-replay/v1` stream through the vendored `makefun_bars` shim: the harness sends a
`hello`, then `batch` messages containing the current `bar` and fills, and the bot replies once
per batch with its `orders` (or an empty list). The shim maintains account state and echoes each
batch sequence number.

## Strategy

The bot updates close-based EMA(60), EMA(240), and EMA(480) only when a batch contains a fresh
CBBTC bar. It also tracks the latest 120 closes. After warm-up, it buys with all available cash
when either the close is at least 1.20% below EMA(480) and at least 0.75% above the 120-bar low,
or EMA(60) crosses above EMA(240). It sells the whole position on a 2.0% take profit, a 4.0%
stop loss, or an EMA(60)/EMA(240) cross down. Orders allow up to 10,000 bps of slippage; actual
fees, slippage, pool impact, and next-bar fills are applied by the harness.

## Run locally

From this directory, run:

```sh
python3 main.py < protocol.ndjson
```

The process expects one hello, sequential batches, and a done message on standard input. It
prints only protocol replies on standard output; the vendored shim validates orders and flushes
one reply for each batch.

## Determinism

The strategy uses no clock, environment, network, file input, randomness, or unordered aggregation.
EMA state is updated with a fixed floating-point operation order, while all entry and exit
thresholds use integer arithmetic. Given the same ordered bars and fills, it emits the same orders.
