"""Fetch recent oil & gas headlines from public RSS feeds.

Usage: python fetch_news.py [QUERY] [LIMIT]
  QUERY: optional Google News search topic (e.g. "OPEC+", "LNG Europe", "Permian")
  LIMIT: max headlines per feed (default 8)

Prints JSON: a list of feeds, each with recent items (title, link, published, source).
Uses only the Python standard library.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

FEEDS = {
    "OilPrice.com": "https://oilprice.com/rss/main",
    "EIA Today in Energy": "https://www.eia.gov/rss/todayinenergy.xml",
}
GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}+when:7d&hl=en-US&gl=US&ceid=US:en"


def read_feed(url: str, limit: int) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        root = ET.fromstring(resp.read())
    items = []
    # RSS publishers differ in which fields they include; keep a predictable
    # output shape and add publisher attribution only when it is available.
    for item in root.iter("item"):
        source = item.find("source")
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "published": (item.findtext("pubDate") or "").strip(),
                **({"source": source.text} if source is not None and source.text else {}),
            }
        )
        if len(items) >= limit:
            break
    return items


def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else "oil gas OPEC LNG"
    try:
        # Bound requests so a caller cannot accidentally ask every feed for an
        # excessive response; invalid input uses the documented default.
        limit = max(1, min(20, int(sys.argv[2]))) if len(sys.argv) > 2 else 8
    except ValueError:
        limit = 8
    feeds = dict(FEEDS)
    feeds[f"Google News: {query}"] = GOOGLE_NEWS.format(q=urllib.parse.quote_plus(query))
    out = {"retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "feeds": []}
    for name, url in feeds.items():
        try:
            out["feeds"].append({"feed": name, "items": read_feed(url, limit)})
        except Exception as exc:  # noqa: BLE001 - report per-feed failures to the agent
            # One unavailable publisher should not discard headlines already
            # retrieved from independent feeds.
            out["feeds"].append({"feed": name, "error": str(exc)})
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
