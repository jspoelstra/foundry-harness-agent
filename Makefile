# Energy Market Brief — Microsoft Agent Framework Harness Agent demo
# Run `make` (or `make help`) to see the run-of-show.

SHELL := /bin/bash
.DEFAULT_GOAL := help

AGENT      ?= energy-brief-agent
AGENT_DIR  := src/$(AGENT)
PY         := .venv/bin/python
PROMPT     ?= Produce today's oil & gas market brief.
FOCUS      ?=
FOUNDRY_USER_ROLE := 53ca6127-db72-4b80-b1b0-d745d6d5456d

export PATH := /opt/homebrew/bin:$(PATH)
export UV_INDEX_URL ?= https://packagefeedproxy.microsoft.io/pypi/simple/
export AZURE_DEV_USER_AGENT := microsoft_foundry_skill

AZD := azd
QUIET := 2>&1 | grep -viE "update available|brew |upgrade" || true

.PHONY: help setup env infra rbac skills skills-list demo-1 demo-2 run-local invoke-local \
        deploy invoke logs show playground all clean

help: ## Show this help
	@echo "Energy Market Brief — Harness Agent demo"
	@echo
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "Run-of-show:  make infra rbac skills  →  make demo-1  →  make demo-2  →  make deploy  →  make invoke"

## ---------------------------------------------------------------- setup
setup: ## Create .venv and install pinned dependencies
	@test -d .venv || uv venv --python 3.12 .venv
	uv pip install --python $(PY) -r $(AGENT_DIR)/requirements.txt

env: ## Write .env from the azd environment (endpoint + model deployment)
	@$(AZD) env get-values 2>/dev/null | grep -E '^(FOUNDRY_PROJECT_ENDPOINT|AZURE_AI_MODEL_DEPLOYMENT_NAME)=' > .env
	@cat .env

## ---------------------------------------------------------------- 1. Azure resources
infra: ## [1] Provision Foundry account, project, model deployment (azd provision)
	$(AZD) provision --no-prompt
	@$(MAKE) --no-print-directory env

rbac: ## [1] Grant the hosted agent's identity the Foundry User role (idempotent)
	@acct=$$($(AZD) env get-value AZURE_AI_PROJECT_ID 2>/dev/null | sed 's#/projects/.*##'); \
	pid=$$($(AZD) ai agent show $(AGENT) 2>/dev/null | grep -i "Instance Identity Principal ID" | awk '{print $$NF}'); \
	if [ -z "$$pid" ]; then echo "Agent not deployed yet — run 'make deploy' first."; exit 0; fi; \
	echo "Assigning Foundry User to $$pid on $$acct"; \
	az role assignment create --assignee-object-id $$pid --assignee-principal-type ServicePrincipal \
	  --role $(FOUNDRY_USER_ROLE) --scope $$acct -o none 2>&1 | grep -v "already exists" || true; \
	echo "OK"

## ---------------------------------------------------------------- 2-3. Local agents
demo-1: ## [2] Simple command-line agent (interactive chat)
	$(PY) demos/01_simple_cli.py

demo-2: ## [3] Skill-powered agent → writes output/brief-*.md  (FOCUS="...")
	$(PY) demos/02_skill_agent.py $(if $(FOCUS),"$(FOCUS)",)

## ---------------------------------------------------------------- 5. Shared skills in Foundry
skills: ## [5] Upload skills/ to the Foundry project (shared, versioned)
	cd $(AGENT_DIR) && set -a && source ../../.env && set +a && ../../$(PY) provision_skills.py

skills-list: ## [5] List skills shared in the Foundry project
	cd $(AGENT_DIR) && set -a && source ../../.env && set +a && ../../$(PY) provision_skills.py --list

## ---------------------------------------------------------------- 4. Hosted agent
run-local: ## [4] Run the hosted-agent server locally on :8088 (Ctrl-C to stop)
	$(AZD) ai agent run --no-client

invoke-local: ## [4] Invoke the locally running hosted agent  (PROMPT="...")
	$(AZD) ai agent invoke --local "$(PROMPT)" $(QUIET)

deploy: ## [4] Deploy the agent to Foundry as a Hosted Agent
	$(AZD) deploy $(AGENT) --no-prompt $(QUIET)
	@$(MAKE) --no-print-directory rbac

invoke: ## [4+5] Invoke the hosted agent in Foundry  (PROMPT="...")
	@mkdir -p output
	@$(AZD) ai agent invoke $(AGENT) "$(PROMPT)" 2>&1 | grep -viE "update available|brew |upgrade" | tee output/hosted-brief-$$(date +%Y%m%d-%H%M%S).md

logs: ## [5] Show hosted agent logs (look for "ready from Foundry")
	$(AZD) ai agent monitor $(AGENT) -l 300 $(QUIET)

show: ## Show hosted agent status, version and identity
	$(AZD) ai agent show $(AGENT) $(QUIET)

playground: ## Open the Foundry playground for the agent
	@open "https://ai.azure.com/nextgen/r/qIMXoq1vTPikIP_fcPU9LQ,rg-harness-agent,,cog-qpnzf2kvryvci,harness-demo/build/agents/$(AGENT)/build"

all: setup infra skills deploy invoke ## Full end-to-end: provision → skills → deploy → invoke

clean: ## Remove generated briefs and caches
	rm -rf output/*.md demos/__pycache__ $(AGENT_DIR)/__pycache__
