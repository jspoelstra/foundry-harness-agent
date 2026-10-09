---
title: Build your own agent from this repo
description: Guide for coding agents using this repo as a reference or starting point for a Microsoft Agent Framework Harness agent with Skills, deployed as a Foundry Hosted Agent.
---

## Who this is for

You are a coding agent. A user asked you to build an agent for their use case and pointed you at this repo as a reference. This guide tells you what is here, which parts are reusable boilerplate and which are demo-specific, and how to adapt it without rediscovering the sharp edges.

[AGENTS.md](../AGENTS.md) covers working *inside* this repo. This file covers *building something new* from it.

## What this repo demonstrates

One working, end-to-end pattern:

1. A **Harness agent** built with `create_harness_agent` from the Microsoft Agent Framework (Python).
2. **Skills** (`SKILL.md` plus scripts) that the agent loads on demand (progressive disclosure).
3. A **local dev loop**: command-line demos that run the same agent against a Foundry model deployment.
4. **Shared skills**: skills uploaded to the Foundry project's versioned skills store.
5. A **Foundry Hosted Agent**: the same agent in a container, serving the Responses protocol, downloading its skills from Foundry at startup.
6. **Provisioning and deployment** through `azd` (`azure.yaml`), wrapped in `make` targets.

Use this repo as a reference when the target is Python plus Agent Framework plus Foundry. If the user wants a different language, framework or host, the skill format and the overall flow still transfer, but the code does not.

> [!IMPORTANT]
> Hosted Agents, the Foundry skills API (`project.beta.skills`) and the Harness packages are preview. Check the pinned versions in [requirements.txt](../src/energy-brief-agent/requirements.txt) and the current docs before assuming an API still exists in the same shape.

## Repo map: reuse vs replace

| Path                                                                                 | Role                                                                                 | When adapting                                               |
|--------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|-------------------------------------------------------------|
| [energy_agent.py](../src/energy-brief-agent/energy_agent.py)                         | Agent factory shared by local demos and the hosted entry point                       | Keep the structure. Replace name, description, instructions |
| [main.py](../src/energy-brief-agent/main.py)                                         | Hosted entry point: credentials, skill download with fallback, `ResponsesHostServer` | Reuse almost verbatim. Change the import and logger name    |
| [provision_skills.py](../src/energy-brief-agent/provision_skills.py)                 | Zips each `skills/<name>/` folder and uploads it to Foundry                          | Reuse verbatim                                              |
| [subprocess_script_runner.py](../src/energy-brief-agent/subprocess_script_runner.py) | Runs skill scripts as Python subprocesses (30 s timeout, string args only)           | Reuse. Harden for production (see below)                    |
| [skills/](../src/energy-brief-agent/skills/)                                         | Two domain skills                                                                    | Replace with the user's skills                              |
| [requirements.in](../src/energy-brief-agent/requirements.in) and `requirements.txt`  | Dependencies, including deliberate pins (`openai<3`, `httpx<1`)                      | Keep the pins. Add what the skills need                     |
| [Dockerfile](../src/energy-brief-agent/Dockerfile)                                   | Container image with bytecode precompile for faster cold starts                      | Reuse verbatim                                              |
| [azure.yaml](../azure.yaml)                                                          | azd project: Foundry project, model deployment, hosted agent service and its env     | Rename the service, update `SKILL_NAMES`, pick the model    |
| [Makefile](../Makefile)                                                              | Every workflow as a target (`make help`)                                             | Change `AGENT ?=`. Drop demo-only targets if unwanted       |
| [demos/_common.py](../demos/_common.py)                                              | Local client factory and a streaming printer that shows tool and skill calls inline  | Reuse. Update `AGENT_DIR`                                   |
| [demos/01_simple_cli.py](../demos/01_simple_cli.py)                                  | Minimal Harness chat REPL, no skills                                                 | Reference only                                              |
| [demos/02_skill_agent.py](../demos/02_skill_agent.py)                                | Runs the full agent once and writes an artifact to `output/`                         | Template for a local smoke test of the user's agent         |

## Architecture in one picture

```text
local:   demos/*.py ──▶ build_<agent>(FoundryChatClient + AzureCliCredential, skills_dir=./skills)
hosted:  main.py    ──▶ download SKILL_NAMES from Foundry ──▶ build_<agent>(..., hosted=True)
                         (fallback: skills baked into the image)   └─▶ ResponsesHostServer on :8088
both:    ──▶ Foundry model deployment (AZURE_AI_MODEL_DEPLOYMENT_NAME)
```

The key design choice: **one agent factory, two entry points**. Local and hosted runs share `build_energy_agent`, and only the `hosted=True` flag changes behavior. Keep this split. It makes the local demo a faithful test of the deployed agent.

## Key concepts and APIs

### The Harness agent

`create_harness_agent(client, ...)` returns an agent that already includes planning and todo tools, plan and execute modes, context compaction, file memory, web search and tool auto-approval. You add instructions and a skills provider. See [build_energy_agent](../src/energy-brief-agent/energy_agent.py) for the knobs this repo sets:

* `agent_instructions`: persona plus grounding rules ("never invent numbers, prefer skills over general knowledge").
* `disable_web_search=True`: built-in web search competes with skill scripts and adds citation markers. Turn it back on only if the use case needs open web search.
* `history_provider=InMemoryHistoryProvider(load_messages=False)`: Foundry stores conversation state server-side, so don't replay it locally.
* `max_context_window_tokens`, `max_output_tokens`: size these to the chosen model.
* Hosted only: `disable_file_memory=True`, `disable_mode=True`, `default_options={"store": False}`. The container filesystem is ephemeral and the platform owns history, so the agent stays stateless.
* Any extra keyword argument to the factory overrides a default, for example `build_energy_agent(client, disable_file_memory=True)` in the demos.

### Skills

`SkillsProvider(FileSkillsSource([skills_dir], script_runner=..., script_extensions=(".py",), search_depth=2))` exposes every `<skills_dir>/<name>/SKILL.md`. The model sees only each skill's `name` and `description` until it decides to load one, then it reads the body and runs scripts through the runner. That is why the `description` is the most important line in a skill: it is the routing signal.

This repo sets `disable_*_approval=True` so runs are unattended. Revisit that for any skill with side effects.

### Foundry skills store

`provision_skills.py` deletes and recreates each skill via `project.beta.skills.create_from_files`, so re-running is safe. `main.py` downloads each skill named in `SKILL_NAMES` via `project.beta.skills.download`, unzips it into a temp folder (with a zip-slip guard), and falls back to the baked-in `skills/` if anything fails or takes longer than 45 seconds. It also copies baked-in `scripts/` if a downloaded package lacks them.

### Credentials

* Local: `AzureCliCredential` (run `az login`).
* Hosted: `ManagedIdentityCredential(client_id=FOUNDRY_AGENT_INSTANCE_CLIENT_ID)`. `AgentConfig.from_env().is_hosted` picks the right one.
* The hosted agent's identity needs the **Foundry User** role on the Foundry account to download skills. `make deploy` runs `make rbac` to grant it.

## Recipe: adapt this repo to a new use case

Follow these steps in order. Steps 1 to 5 need only an existing Foundry project and model deployment, so you can iterate on the agent before touching hosted deployment.

1. **Pick names.** Choose an agent name in kebab-case (for example `claims-triage-agent`) and one or more skill names.
2. **Rename the agent folder and references.** Rename `src/energy-brief-agent/` and update every reference:
   * `AGENT ?=` in the [Makefile](../Makefile).
   * The service key, `name`, `project`, `description` and `tags` in [azure.yaml](../azure.yaml).
   * `AGENT_DIR` in [demos/_common.py](../demos/_common.py).
   * The `from energy_agent import ...` lines in `main.py` and the demos, if you rename `energy_agent.py`.
   * `name`, `description` and `ANALYST_INSTRUCTIONS` in the factory, plus the logger name in `main.py`.

   Search for `energy` across the repo afterward to catch stragglers.
3. **Write the instructions.** Keep the pattern: persona, today's date, grounding rules, preference for skills, output style. Put domain procedure and output templates in skills, not in the system prompt.
4. **Write the skills** (see the next section). Delete the energy skills.
5. **Smoke test locally.** Adapt `demos/02_skill_agent.py` with a prompt that exercises every skill, then run `make demo-2`. The streaming printer shows each skill load and script call, so you can confirm the agent actually used the skills.
6. **Provision.** Choose the model in the `ai-project` deployment block of `azure.yaml` and keep `AZURE_AI_MODEL_DEPLOYMENT_NAME` in step. Run `make infra`, which also writes `.env`.
7. **Publish skills.** Set `SKILL_NAMES` in `azure.yaml` to a comma-separated list of the skill folder names, then run `make skills` and `make skills-list`.
8. **Test the hosted server locally.** Run `make run-local` in one terminal and `make invoke-local PROMPT="..."` in another.
9. **Deploy and verify.** Run `make deploy`, then `make invoke PROMPT="..."`. Run `make logs` and look for `Skill '<name>' ready from Foundry`. If you see `falling back to baked-in skills`, check RBAC and `SKILL_NAMES`.
10. **Update docs.** Rewrite the README's run-of-show and file table for the new agent, and keep `AGENTS.md` accurate.

## Writing skills

Layout:

```text
skills/<skill-name>/
  SKILL.md          # front matter + procedure + output format
  scripts/
    <script>.py     # deterministic data access or computation
```

### SKILL.md rules

* Front matter needs `name` (must equal the folder name) and `description`.
* Keep front matter values **unquoted and free of colons**, or the Foundry upload fails validation.
* Write the `description` as "what it does. Use when ..." so the model knows when to load it.
* In the body, give numbered steps that name the script by relative path (`scripts/fetch_prices.py`) and spell out its positional arguments and defaults.
* Add an explicit grounding rule ("use only numbers the script returns; if a value has an `error`, say it was unavailable").
* Include an output template in a fenced Markdown block when the agent produces an artifact. See [energy-market-brief](../src/energy-brief-agent/skills/energy-market-brief/SKILL.md).
* Skills can reference each other ("if the `energy-news-digest` skill is available, use it too"). That's how the two skills here compose.

### Script rules

The script runner imposes the contract, so write scripts to match it:

* **Arguments are positional strings.** The runner rejects dicts and non-string items. Parse and validate in the script, and fall back to defaults on bad input.
* **Print JSON to stdout.** The agent sees stdout, then stderr, then a non-zero exit code. Structured output is easier for the model to ground on.
* **Report partial failures in the output**, for example a per-item `"error"` field, instead of crashing. One flaky source shouldn't sink the whole run.
* **Finish in under 30 seconds.** Use per-request timeouts (the scripts here use 15 seconds).
* **Run in the agent's interpreter.** The runner uses `sys.executable` with `cwd` set to the script's folder. Any third-party import must be in the agent's `requirements.txt`. The scripts here use only the standard library, which is the easiest path.
* **Make scripts runnable by hand** (`python scripts/foo.py arg`) and document usage in the module docstring. Test them directly before testing through the agent.

## Configuration reference

| Variable                           | Where set                                      | Used by                       |
|------------------------------------|------------------------------------------------|-------------------------------|
| `FOUNDRY_PROJECT_ENDPOINT`         | `.env` (from `make env`), injected when hosted | Everything                    |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME`   | `.env`, and `azure.yaml` service `env`         | Chat client                   |
| `SKILL_NAMES`                      | `azure.yaml` service `env`                     | `main.py` skill download      |
| `FOUNDRY_AGENT_INSTANCE_CLIENT_ID` | Injected by the hosted platform                | Managed identity in `main.py` |

`main.py` treats an unresolved `${VAR}` or `{{VAR}}` placeholder as empty, so a missing azd value degrades to the baked-in skills instead of a crash.

## Gotchas this repo already solved

* **Upload skills before deploying.** The hosted agent fetches them by name at container start.
* **The app directory is read-only when hosted.** Write to `tempfile.gettempdir()`, as `main.py` does for downloaded skills.
* **Missing RBAC fails quietly.** Without Foundry User on the agent identity, skill download fails and the agent falls back to baked-in skills. Check `make logs`.
* **Dependency pins matter.** `azure-ai-projects` imports `httpx` directly while OpenAI 3 uses `httpx2`, hence `openai<3` and `httpx<1`.
* **Model chatter before the artifact.** `02_skill_agent.py` trims everything before the first heading and strips citation markers before writing the file.
* **Python versions.** `azure.yaml` declares `runtime: python_3_13`, while the `Dockerfile` and local venv use 3.12. Keep code and dependencies compatible with both.
* **Harmless hosted log noise:** `ModuleNotFoundError: agents` (optional A365 integration) and "Responses resilience DISABLED".
* **Environment-specific Makefile settings.** `UV_INDEX_URL` points at a Microsoft package proxy, `PATH` prepends `/opt/homebrew/bin`, and `make playground` uses macOS `open`. Override `UV_INDEX_URL` (for example `UV_INDEX_URL=https://pypi.org/simple make setup`) if the user can't reach the proxy.

## Before calling it production-ready

This repo is a demo. Flag these items to the user rather than silently shipping them:

* **Approvals are off.** Re-enable load, script and resource approvals for any skill that writes data, sends messages or spends money.
* **The script runner is a sample.** It runs any `.py` file in the skills folder with the agent's own environment and credentials. Consider sandboxing, an allow-list of scripts, resource limits and scrubbing secrets from output.
* **Skill supply chain.** Anyone who can publish to the Foundry project's skills store changes the agent's behavior at its next start. Restrict write access, and consider pinning versions instead of always taking the default.
* **No evaluations or tracing.** Add evaluation datasets and telemetry before relying on output quality.
* **No tests.** Add unit tests for scripts and a smoke test like `make demo-2` in CI.
* **Public data sources.** The demo reads delayed public feeds. Replace them with licensed or internal sources and handle auth through managed identity or Key Vault, never through values committed to the repo.

## Working conventions

* Drive everything through `make`. Run `make help` first.
* Use the root `.venv` (`make setup`) and `uv` for installs. Regenerate `requirements.txt` from `requirements.in` when you add dependencies.
* Never commit `.env`, `.azure/` or `output/`. `.env.example` is the template.
* After editing a skill, run `make skills` to publish a new version. The hosted agent picks it up the next time its container starts, for example after `make deploy`.
