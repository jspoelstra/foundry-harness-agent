# Energy Brief Agent: a Microsoft Foundry Harness Agent demo

A show-and-tell demo of the [Microsoft Agent Framework Harness Agent](https://learn.microsoft.com/en-us/agent-framework/get-started/harness?pivots=programming-language-python) for an Oil and Gas audience. The agent pulls live energy prices and headlines through **Skills** and writes a Markdown **market brief**. It runs locally first, then as a **Foundry Hosted Agent** that downloads its skills from the Foundry project at startup.

Everything is driven by `make`. Run `make help` to see the targets.

## Run of show

| # | What you show                         | Command                                     | Artifact                         |
|---|---------------------------------------|---------------------------------------------|----------------------------------|
| 1 | Provision Azure resources             | `make infra` then `make env`                | Foundry account, project, model  |
| 2 | Simple command-line agent             | `make demo-1`                               | Interactive chat                 |
| 3 | Agent that uses Skills                | `make demo-2` (optional `FOCUS="LNG"`)      | `output/brief-*.md`              |
| 5 | Share skills through Foundry          | `make skills` then `make skills-list`       | Versioned skills in the project  |
| 4 | Deploy as a Foundry Hosted Agent      | `make deploy`                               | Hosted agent `energy-brief-agent`|
| 4+5 | Invoke the hosted agent             | `make invoke` (optional `PROMPT="..."`)     | `output/hosted-brief-*.md`       |
| - | Prove skills came from Foundry        | `make logs`                                 | `Skill '...' ready from Foundry` |
| - | Open the Foundry playground           | `make playground`                           | Browser                          |

Upload the skills (step 5) **before** you deploy. The hosted agent fetches them by name when its container starts.

`make all` runs the whole provision, skills, deploy and invoke sequence in one go.

## Architecture

```text
 src/energy-brief-agent/skills/            Foundry project (harness-demo)
   energy-market-brief/  ── make skills ──▶  Skills store (versioned, shared)
   energy-news-digest/                            │
        │                                         │ download at startup (SKILL_NAMES)
        ▼                                         ▼
 demos/02_skill_agent.py              Hosted Agent: energy-brief-agent
 (local Harness agent)                (main.py + Agent Framework hosting)
        │                                         │
        └──────── gpt-5.4-mini (Foundry model deployment) ◀───┘
```

* **Harness agent** (`energy_agent.py`): an Agent Framework agent with a skills provider and a script runner. Skills load progressively: the model sees only the skill name and description until it decides to use a skill.
* **Skills** follow the `SKILL.md` format and come with Python scripts:
  * `energy-market-brief` gets WTI, Brent, Henry Hub, products, energy equities and FX from delayed Yahoo Finance data, and defines the brief format.
  * `energy-news-digest` gets oil, gas and LNG headlines from public RSS feeds.
* **Shared skills** (`provision_skills.py`): uploads each skill folder to the Foundry project's skills store using `azure-ai-projects` (`project.beta.skills`).
* **Hosted agent** (`main.py`): on startup it downloads the skills listed in `SKILL_NAMES` from Foundry, then serves the Responses protocol. If the download fails, it falls back to the copies built into the image.

## Prerequisites

* Azure Developer CLI (`azd`) 1.29 or later, with the `azure.ai.agents` extension
* Azure CLI, logged in (`az login`)
* [uv](https://docs.astral.sh/uv/)
* Rights to create resources and role assignments in the target resource group

## First-time setup

```bash
make setup     # create .venv and install dependencies
make infra     # azd provision into rg-harness-agent
make env       # write .env (project endpoint + model deployment)
make skills    # upload skills to Foundry
make deploy    # deploy the hosted agent (also grants its identity access)
make invoke    # get a brief from the hosted agent
```

`make env` generates `.env` from the azd environment. To set it up by hand, copy `.env.example` to `.env` and fill in your values. `.env` is gitignored.

## Files

| Path                                             | Purpose                                                   |
|--------------------------------------------------|-----------------------------------------------------------|
| `azure.yaml`                                     | azd project: Foundry project, model, hosted agent         |
| `demos/01_simple_cli.py`                         | Part 2: minimal command-line chat agent                   |
| `demos/02_skill_agent.py`                        | Part 3: skill-powered agent that writes a brief           |
| `src/energy-brief-agent/energy_agent.py`         | Shared agent factory (instructions, skills, script runner) |
| `src/energy-brief-agent/main.py`                 | Hosted agent entry point; downloads skills from Foundry   |
| `src/energy-brief-agent/provision_skills.py`     | Uploads or lists skills in the Foundry project            |
| `src/energy-brief-agent/skills/`                 | The two skills (`SKILL.md` and scripts)                   |

## Caveats

* Hosted Agents, the Foundry skills API and the Harness packages are **preview** features, and their APIs may change.
* Market data is delayed and comes from public sources. The briefs are a demo artifact, **not investment advice**.
* The hosted agent's logs include harmless warnings (`ModuleNotFoundError: agents` from the optional A365 integration, "Responses resilience DISABLED").
* `SKILL.md` front matter values must be unquoted and must not contain colons, or the upload fails validation.
