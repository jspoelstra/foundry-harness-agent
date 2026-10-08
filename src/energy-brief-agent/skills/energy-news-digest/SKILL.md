---
name: energy-news-digest
description: Gather and summarize the latest oil, gas and LNG news headlines from OilPrice.com, EIA Today in Energy and Google News. Use when asked what is happening in energy, for market drivers, or for news on a specific topic like OPEC+, LNG, Permian or sanctions.
---

# Energy News Digest

## Steps

1. Run the `scripts/fetch_news.py` script. Arguments are positional:
   - First argument (optional): a search topic for Google News, for example
     `OPEC+`, `LNG Europe` or `Permian`. The default topic is `oil gas OPEC LNG`.
   - Second argument (optional): the maximum number of headlines per feed. The
     default is 8.
2. Use only headlines the script returns. Never invent news. Keep the source name
   and link for every item you cite.
3. Group the headlines into themes. Typical themes are supply (OPEC+, US shale,
   outages), demand (China, macro), geopolitics and sanctions, gas and LNG,
   policy, and energy transition.
4. For each theme, give one line on why it matters for oil or gas prices
   (bullish, bearish or neutral).

## Output format

```markdown
## Energy news digest: <date>
### <Theme> — <bullish|bearish|neutral>
- [<headline>](<link>) — <source>. <one-line why it matters>
```

Keep the whole digest under 300 words unless the user asks for more.
