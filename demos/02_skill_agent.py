"""Demo 2 - a Harness agent with Skills that produces an artifact.

    python demos/02_skill_agent.py                    # default: today's market brief
    python demos/02_skill_agent.py "Focus on natural gas and LNG"

The agent discovers the local skills in src/energy-brief-agent/skills
(`energy-market-brief`, `energy-news-digest`), loads them on demand, runs their
scripts to pull live prices + headlines, and writes a Markdown brief to output/.
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime

from _common import BOLD, DIM, OUTPUT_DIR, RESET, make_client, stream_turn
from energy_agent import LOCAL_SKILLS_DIR, build_energy_agent

DEFAULT_PROMPT = (
    "Produce today's Oil & Gas Market Brief. Use your energy-market-brief skill for live "
    "prices and your energy-news-digest skill for headlines, and follow the brief format "
    "defined in the market-brief skill. Return only the final brief in Markdown."
)


async def main() -> None:
    extra = " ".join(sys.argv[1:]).strip()
    prompt = DEFAULT_PROMPT + (f"\n\nAdditional focus: {extra}" if extra else "")

    skills = sorted(p.parent.name for p in LOCAL_SKILLS_DIR.glob("*/SKILL.md"))
    print(f"{BOLD}🛢  Energy Brief agent{RESET}  {DIM}skills: {', '.join(skills)}{RESET}\n")

    agent = build_energy_agent(make_client(), disable_file_memory=True)
    text = await stream_turn(agent, prompt, agent.create_session())

    OUTPUT_DIR.mkdir(exist_ok=True)
    # A model can preface a requested artifact with chatty text. Save from the
    # first Markdown heading so the file itself remains a clean brief.
    match = re.search(r"^#", text, flags=re.MULTILINE)
    brief = text[match.start():] if match else text
    # Citation tokens belong to the interactive response protocol, not the
    # portable Markdown artifact that users open from output/.
    brief = re.sub(r"\s*\ue200?cite\ue202?turn\d+\w+\d+\ue201?", "", brief)
    out = OUTPUT_DIR / f"brief-{datetime.now():%Y%m%d-%H%M}.md"
    out.write_text(brief.strip() + "\n", encoding="utf-8")
    print(f"\n{BOLD}📄 Brief written to {out.relative_to(OUTPUT_DIR.parent)}{RESET}")


if __name__ == "__main__":
    asyncio.run(main())
