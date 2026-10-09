# AGENTS.md

Guidance for coding agents working in this repo.

> Building your own agent and using this repo as a reference or template? Read [docs/BUILD_YOUR_OWN_AGENT.md](docs/BUILD_YOUR_OWN_AGENT.md) first. It maps what to reuse, gives an adaptation recipe, and lists the gotchas.

* Use `make` targets (see `make help`) rather than raw commands.
* Python 3.12+ with the root `.venv` (`make setup`). Use `uv` for installs.
* The agent code lives in `src/energy-brief-agent/`. Demos import it via `demos/_common.py`.
* Skills live in `src/energy-brief-agent/skills/<name>/SKILL.md`. Keep the front matter values unquoted and free of colons. After editing a skill, run `make skills` to publish a new version.
* The hosted agent's settings (`SKILL_NAMES`, model) are in `azure.yaml`. Redeploy with `make deploy`.
* Never commit `.env`, `.azure/` or `output/`.
