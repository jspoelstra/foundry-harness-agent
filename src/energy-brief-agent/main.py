# Copyright (c) Microsoft. All rights reserved.

"""Energy Brief Harness agent - Foundry Hosted Agent entry point.

At startup the container downloads each Foundry Skill named in ``SKILL_NAMES``
from the project's ``beta.skills`` API (the skills are uploaded by the
``provision_skills.py`` script, i.e. ``make skills``), unpacks them to a temp folder
and wires them into a Harness agent via ``SkillsProvider``. If the download
fails, it falls back to the copy of ``skills/`` baked into the image so the
agent stays healthy.
"""

import asyncio
import io
import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Final

from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.ai.agentserver.core import AgentConfig
from azure.ai.projects.aio import AIProjectClient
from azure.identity import AzureCliCredential, ManagedIdentityCredential
from azure.identity.aio import AzureCliCredential as AioAzureCliCredential
from azure.identity.aio import ManagedIdentityCredential as AioManagedIdentityCredential
from dotenv import load_dotenv

from energy_agent import LOCAL_SKILLS_DIR, build_energy_agent

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("energy-brief-agent")
logging.getLogger("azure").setLevel(logging.WARNING)

# Hosted containers mount the app dir read-only, so unpack to temp.
DOWNLOADED_SKILLS_DIR: Final = Path(tempfile.gettempdir()) / "downloaded_skills"
SKILL_BOOTSTRAP_TIMEOUT_SECONDS: Final = 45.0
IS_HOSTED: Final = AgentConfig.from_env().is_hosted


def _sync_credential():
    # The chat client used by the agent is synchronous; keep its credential
    # flavor aligned with the execution environment rather than prompting in a
    # hosted container that has no interactive Azure CLI session.
    if IS_HOSTED:
        return ManagedIdentityCredential(client_id=os.environ.get("FOUNDRY_AGENT_INSTANCE_CLIENT_ID"))
    return AzureCliCredential()


def _async_credential():
    # Startup provisioning uses the async Azure SDK, so it needs the matching
    # async credential types even though both branches authenticate identically.
    if IS_HOSTED:
        return AioManagedIdentityCredential(client_id=os.environ.get("FOUNDRY_AGENT_INSTANCE_CLIENT_ID"))
    return AioAzureCliCredential()


def _safe_extract_zip(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    """Extract ``zf`` into ``dest_dir``, rejecting entries that escape it (zip-slip guard)."""
    dest_root = dest_dir.resolve()
    for member in zf.infolist():
        # Archives are external input from the skills service. Resolve each
        # destination before extraction so ../ paths cannot overwrite files
        # outside the temporary skill directory.
        member_path = (dest_root / member.filename).resolve()
        if dest_root != member_path and dest_root not in member_path.parents:
            raise RuntimeError(f"Refusing to extract unsafe path '{member.filename}' outside of '{dest_root}'.")
    zf.extractall(dest_dir)


async def _bootstrap_skills(endpoint: str, skill_names: list[str], target_dir: Path) -> None:
    """Download each named skill via ``project.beta.skills`` into ``<target_dir>/<name>/``."""
    if target_dir.exists():  # noqa: ASYNC240
        # Never mix a partial download from an earlier startup with the current
        # version; that could silently pair old scripts with a new SKILL.md.
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)  # noqa: ASYNC240

    async with (
        _async_credential() as credential,
        AIProjectClient(endpoint=endpoint, credential=credential, allow_preview=True) as project,
    ):
        available = [s.name async for s in project.beta.skills.list(read_timeout=10, retry_total=0)]
        logger.info("Foundry skills visible to this agent: %s", available)
        for name in skill_names:
            logger.info("Downloading skill '%s' from Foundry...", name)
            stream = await project.beta.skills.download(name, read_timeout=15, retry_total=0)
            zip_bytes = b"".join([chunk async for chunk in stream])
            skill_dir = target_dir / name
            skill_dir.mkdir()
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                _safe_extract_zip(zf, skill_dir)
            if not (skill_dir / "SKILL.md").is_file():
                raise RuntimeError(f"Downloaded archive for '{name}' has no SKILL.md at the root.")
            files = sorted(str(p.relative_to(skill_dir)) for p in skill_dir.rglob("*") if p.is_file())
            logger.info("Skill '%s' ready from Foundry: %s", name, files)


def _resolved_env(name: str) -> str:
    """Return an env var, treating un-substituted ``${VAR}`` / ``{{VAR}}`` placeholders as empty."""
    value = os.environ.get(name, "").strip()
    if (value.startswith("${") and value.endswith("}")) or (value.startswith("{{") and value.endswith("}}")):
        return ""
    return value


async def _resolve_skills_dir(endpoint: str) -> Path:
    skill_names = [n.strip() for n in _resolved_env("SKILL_NAMES").split(",") if n.strip()]
    if not skill_names:
        logger.warning("SKILL_NAMES is empty; using skills baked into the image.")
        return LOCAL_SKILLS_DIR
    try:
        # Keep skill-service latency from making container startup unbounded.
        # The image-bundled copy lets the agent start even if the preview API is
        # temporarily unavailable.
        await asyncio.wait_for(
            _bootstrap_skills(endpoint, skill_names, DOWNLOADED_SKILLS_DIR),
            timeout=SKILL_BOOTSTRAP_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.exception("Foundry skill download failed; falling back to baked-in skills.")
        return LOCAL_SKILLS_DIR

    # Foundry skill packages may omit helper scripts; reuse the baked-in copy if so.
    for name in skill_names:
        downloaded, local = DOWNLOADED_SKILLS_DIR / name, LOCAL_SKILLS_DIR / name
        if not (downloaded / "scripts").exists() and (local / "scripts").exists():
            # Skill instructions and executable helpers are packaged separately
            # by some versions of the service; retain the vetted local helpers.
            logger.warning("Skill '%s' from Foundry has no scripts/; copying baked-in scripts.", name)
            shutil.copytree(local / "scripts", downloaded / "scripts")
    return DOWNLOADED_SKILLS_DIR


async def main() -> None:
    project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    skills_dir = await _resolve_skills_dir(project_endpoint)
    logger.info("Hosted=%s, skills dir=%s", IS_HOSTED, skills_dir)

    client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model=os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME") or "gpt-5.4-mini",
        credential=_sync_credential(),
    )
    agent = build_energy_agent(client, skills_dir=skills_dir, hosted=True)
    server = ResponsesHostServer(agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())
