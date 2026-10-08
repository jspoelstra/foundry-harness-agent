---
name: energy-market-brief
description: Produce a concise oil and gas market brief (WTI, Brent, Henry Hub, products, Brent-WTI spread, 3-2-1 crack spread) from live futures prices. Use when asked about energy prices, oil markets, gas markets, or for a market brief / morning note.
---

# Energy Market Brief

You write the kind of one-page morning note an energy trading desk or an upstream
planning team would read with their coffee.

## Steps

1. Run the `scripts/fetch_prices.py` script to get live futures data. Pass one
   argument with the lookback range: `5d`, `1mo` (default), `3mo`, `6mo` or `1y`.
2. Use only the numbers returned by the script. Never invent prices. If a contract
   returns an `error`, say the data was unavailable.
3. If the `energy-news-digest` skill is available, use it too so you can explain
   *why* prices moved.
4. Write the brief in the format below.

## Brief format (Markdown)

```markdown
# Energy Market Brief: <date>

**Bottom line:** <one sentence, the single most important takeaway>

## Prices
| Contract | Latest | 1-day | Period | Range (low–high) |
|---|---|---|---|---|
<one row per contract, % changes with sign, prices to 2 dp>

**Brent–WTI spread:** $X.XX/bbl · **3-2-1 crack:** $X.XX/bbl

## What moved the market
- <3–5 bullets tying price moves to specific headlines, cite source names>

## Signals to watch
- <2–3 bullets: upcoming catalysts, e.g. OPEC+ meeting, EIA storage report, hurricanes, sanctions>

## So what for an energy company
- <2–3 bullets for an O&G operator: upstream margins, refining margins, hedging, gas-to-power>

_Data: Yahoo Finance futures (delayed). News: public RSS. Not investment advice._
```

## Interpretation hints

- A widening Brent–WTI spread usually signals tighter seaborne supply or a US
  export bottleneck.
- A 3-2-1 crack above about $25/bbl points to healthy refining margins. Below
  about $15/bbl means refiners are squeezed.
- Henry Hub moves are driven by weather, storage injections and withdrawals,
  LNG feedgas demand and Permian associated gas.
