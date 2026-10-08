"""Shared helpers for the command-line demos."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "energy-brief-agent"
OUTPUT_DIR = ROOT / "output"

sys.path.insert(0, str(AGENT_DIR))
load_dotenv(ROOT / ".env")

DIM, BOLD, CYAN, YELLOW, RESET = "\033[2m", "\033[1m", "\033[36m", "\033[33m", "\033[0m"


def make_client():
    from agent_framework.foundry import FoundryChatClient
    from azure.identity import AzureCliCredential

    missing = [k for k in ("FOUNDRY_PROJECT_ENDPOINT", "AZURE_AI_MODEL_DEPLOYMENT_NAME") if not os.getenv(k)]
    if missing:
        sys.exit(f"Missing {', '.join(missing)} in .env - run `make infra` first.")
    return FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=AzureCliCredential(),
    )


def _describe_call(content) -> str:
    name = getattr(content, "name", "") or "tool"
    args = getattr(content, "arguments", None)
    if isinstance(args, dict):
        detail = args.get("skill_name") or args.get("name") or args.get("script_name") or args.get("query") or ""
        if args.get("script_name") and args.get("skill_name"):
            detail = f"{args['skill_name']}/{args['script_name']}"
        return f"{name}({detail})" if detail else name
    return name


async def stream_turn(agent, message: str, session) -> str:
    """Stream one agent turn, showing tool/skill calls inline. Returns the full text."""
    chunks: list[str] = []
    seen_calls: set[str] = set()
    async for update in agent.run(message, session=session, stream=True):
        for content in update.contents or []:
            ctype = getattr(content, "type", "")
            if ctype == "function_call":
                call_id = getattr(content, "call_id", None) or id(content)
                if call_id in seen_calls or not getattr(content, "name", None):
                    continue
                seen_calls.add(call_id)
                print(f"\n{DIM}{YELLOW}  ⚙ {_describe_call(content)}{RESET}", flush=True)
            elif ctype == "text" and content.text:
                chunks.append(content.text)
                print(content.text, end="", flush=True)
    print()
    return "".join(chunks)
