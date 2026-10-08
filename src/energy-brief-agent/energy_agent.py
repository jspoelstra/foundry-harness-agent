"""Shared factory for the Energy Brief Harness agent.

Used by the command-line demos (``demos/``) and by the hosted entry point
(``main.py``) so that local runs and the Foundry Hosted Agent behave the same.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from agent_framework import (
    FileSkillsSource,
    InMemoryHistoryProvider,
    SkillsProvider,
    create_harness_agent,
)
from agent_framework.foundry import FoundryChatClient

from subprocess_script_runner import subprocess_script_runner

LOCAL_SKILLS_DIR = Path(__file__).parent / "skills"

ANALYST_INSTRUCTIONS = f"""\
You are "Brent", an energy-markets analyst copilot for Forward Deployed Engineers
working with oil & gas customers. Today is {date.today():%A %d %B %Y}.

- Ground every number in tool or skill output. Never invent prices or headlines.
- Prefer your skills (load them, then run their scripts) over general knowledge.
- Write crisp, desk-ready Markdown. Lead with the bottom line.
- Speak the language of the industry (upstream, midstream, downstream, cracks,
  spreads, Henry Hub, Permian, LNG feedgas, OPEC+), but stay accessible.
"""


def build_skills_provider(skills_dir: Path) -> SkillsProvider:
    """Expose every ``<skills_dir>/<name>/SKILL.md`` (and its ``scripts/``) to the agent."""
    return SkillsProvider(
        FileSkillsSource(
            [str(skills_dir)],
            script_runner=subprocess_script_runner,
            script_extensions=(".py",),
            search_depth=2,
        ),
        # Auto-approve so the demo runs unattended (CLI + hosted).
        disable_load_skill_approval=True,
        disable_run_skill_script_approval=True,
        disable_read_skill_resource_approval=True,
    )


def build_energy_agent(
    client: FoundryChatClient,
    *,
    skills_dir: Path | None = LOCAL_SKILLS_DIR,
    hosted: bool = False,
    **overrides: Any,
):
    """Create the Harness agent.

    The Harness gives us, for free: a planning/todo tool, plan/execute modes,
    context compaction, file memory, web search and tool auto-approval. We add
    our own domain Skills on top.
    """
    kwargs: dict[str, Any] = {
        "name": "energy-brief-agent",
        "description": "Oil & gas market analyst that writes daily market briefs.",
        "agent_instructions": ANALYST_INSTRUCTIONS,
        # Foundry stores conversation state server-side, so don't replay history locally.
        "history_provider": InMemoryHistoryProvider(load_messages=False),
        # Skills are the source of truth for market data; built-in web search adds
        # citation markers and competes with the skill scripts.
        "disable_web_search": True,
        "max_context_window_tokens": 128_000,
        "max_output_tokens": 16_000,
    }
    if skills_dir is not None:
        kwargs["skills_provider"] = build_skills_provider(skills_dir)
    if hosted:
        # In the hosted container the platform owns conversation history and the
        # filesystem is ephemeral, so keep the agent stateless.
        kwargs.update(
            disable_file_memory=True,
            disable_mode=True,
            default_options={"store": False},
        )
    kwargs.update(overrides)
    return create_harness_agent(client, **kwargs)
