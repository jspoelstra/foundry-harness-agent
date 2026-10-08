"""Fetch recent energy futures prices (WTI, Brent, Henry Hub, RBOB, Heating Oil).

Usage: python fetch_prices.py [RANGE]
  RANGE: Yahoo chart range, e.g. 5d, 1mo (default), 3mo, 6mo, 1y

Prints a compact JSON document with latest price, daily / period change,
period high / low, and a short daily close series for each contract.
Uses only the Python standard library.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone

CONTRACTS = {
    "CL=F": "WTI Crude (NYMEX, USD/bbl)",
    "BZ=F": "Brent Crude (ICE, USD/bbl)",
    "NG=F": "Henry Hub Natural Gas (NYMEX, USD/MMBtu)",
    "RB=F": "RBOB Gasoline (NYMEX, USD/gal)",
    "HO=F": "Heating Oil / ULSD (NYMEX, USD/gal)",
}
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range}&interval=1d"
VALID_RANGES = {"5d", "1mo", "3mo", "6mo", "1y"}


def fetch(symbol: str, period: str) -> dict:
    req = urllib.request.Request(URL.format(symbol=symbol, range=period), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    result = data["chart"]["result"][0]
    stamps = result.get("timestamp") or []
    closes = result["indicators"]["quote"][0].get("close") or []
    series = [
        (datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d"), round(c, 3))
        for t, c in zip(stamps, closes)
        if c is not None
    ]
    if not series:
        raise ValueError("no price data")
    values = [v for _, v in series]
    last, prev, first = values[-1], values[-2] if len(values) > 1 else values[-1], values[0]
    return {
        "name": CONTRACTS[symbol],
        "latest": last,
        "as_of": series[-1][0],
        "day_change_pct": round((last - prev) / prev * 100, 2),
        "period_change_pct": round((last - first) / first * 100, 2),
        "period_high": max(values),
        "period_low": min(values),
        "closes": series[-10:],
    }


def main() -> None:
    period = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in VALID_RANGES else "1mo"
    out: dict = {"range": period, "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "contracts": {}}
    for symbol in CONTRACTS:
        try:
            out["contracts"][symbol] = fetch(symbol, period)
        except Exception as exc:  # noqa: BLE001 - report per-contract failures to the agent
            out["contracts"][symbol] = {"name": CONTRACTS[symbol], "error": str(exc)}
    wti = out["contracts"].get("CL=F", {}).get("latest")
    brent = out["contracts"].get("BZ=F", {}).get("latest")
    if wti and brent:
        out["brent_wti_spread"] = round(brent - wti, 2)
    rb = out["contracts"].get("RB=F", {}).get("latest")
    ho = out["contracts"].get("HO=F", {}).get("latest")
    if wti and rb and ho:
        # Classic 3-2-1 crack spread in USD/bbl (42 gal/bbl).
        out["crack_spread_321"] = round((2 * rb * 42 + ho * 42 - 3 * wti) / 3, 2)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
