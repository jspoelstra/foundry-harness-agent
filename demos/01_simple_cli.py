"""Demo 1 - the simplest Harness agent: a command-line chat.

    python demos/01_simple_cli.py                      # interactive REPL
    python demos/01_simple_cli.py "What is WTI?"       # one-shot

`create_harness_agent` gives us planning/todos, context compaction, file memory
and web search out of the box - no skills yet.
"""

from __future__ import annotations

import asyncio
import sys

from _common import BOLD, CYAN, DIM, RESET, make_client, stream_turn
from agent_framework import create_harness_agent


async def main() -> None:
    agent = create_harness_agent(
        make_client(),
        name="energy-chat",
        agent_instructions=(
            "You are a concise, friendly energy-industry assistant for oil & gas engineers. "
            "Answer in short Markdown."
        ),
        max_context_window_tokens=128_000,
        max_output_tokens=8_000,
        disable_file_memory=True,
    )
    session = agent.create_session()

    if len(sys.argv) > 1:
        # In one-shot mode, still create a session for the turn, but don't enter
        # the prompt loop; this makes the demo convenient for scripts and tests.
        await stream_turn(agent, " ".join(sys.argv[1:]), session)
        return

    # Reuse one session across turns so the chat demonstrates conversational
    # context rather than starting from scratch after every prompt.
    print(f"{BOLD}🛢  Energy chat (Harness agent){RESET}  {DIM}- type 'exit' to quit{RESET}\n")
    while True:
        try:
            msg = input(f"{CYAN}you › {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg.lower() in {"exit", "quit", ""}:
            if msg:
                break
            continue
        print(f"{BOLD}agent ›{RESET} ", end="")
        await stream_turn(agent, msg, session)
        print()


if __name__ == "__main__":
    asyncio.run(main())
