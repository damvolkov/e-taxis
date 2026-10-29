##### CONFIG #####
PROJECT  ?= e-taxis
PACKAGE  ?= src/e_taxis
MODULE   ?= e_taxis
ARKHETYPO_URL ?= https://github.com/damvolkov/e-arkhetypo.git
### The pinned ref of arkhetypo (.arkhetypo-ref: a tag, a branch or a commit), read off its public remote
### by `taxis repo` — deterministic git plumbing, never a working tree: a change lands here only by bumping the
### pin. An offline box points the url at the checkout beside it: `make infra ARKHETYPO_URL=file://../e-arkhetypo`.
ARKHETYPO_REF ?= $(shell cat .arkhetypo-ref)
INFRA_HEAD ?= $(HOME)/.cache/e-taxis/arkhetypo-head
E_INFRA_SRC ?= $(INFRA_HEAD)/projects/python/infra/src/e_infra
export E_INFRA_SRC
INFRA_ROOT := $(abspath $(E_INFRA_SRC)/../..)
### a source handed in from outside (a checkout, CI) is read as is: only the cache is fetched from the pin.
INFRA_FETCH := $(if $(filter environment command,$(firstword $(origin E_INFRA_SRC))),,infra-src)
TESTARGS  =
LOGO_ARGS =
NAMES     =
ARGS      = $(filter-out $@,$(MAKECMDGOALS))

RESET   := \033[0m
BOLD    := \033[1m
GREEN   := \033[0;32m
CYAN    := \033[0;36m
GRAY    := \033[0;90m
RED     := \033[0;31m

SHELL := bash
.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory
export PYTHONPATH := $(CURDIR)/src

##### TARGETS #####
.PHONY: infra-src help install sync lock infra infra-check lint type arch validate harden hooks test cov check ci run logo release ci-vars clean

help:
	@printf "$(BOLD)$(CYAN)$(PROJECT)$(RESET) $(GRAY)· uv · cyclopts · ruff · ty · tach · pytest — arkhetypo's e-infra materialized into e_taxis from $(E_INFRA_SRC)$(RESET)\n\n"
	@awk 'BEGIN{FS=":.*##"} /^[a-z][a-zA-Z0-9_-]*:.*##/{printf "  $(GREEN)%-12s$(RESET) $(GRAY)%s$(RESET)\n",$$1,$$2}' $(MAKEFILE_LIST)

# — env —
install: infra ## full setup: materialize shared assets + sync deps + git hooks
	@uv sync
	@uv run prek install
	@printf "$(GREEN)✓ ready$(RESET)\n"

sync: ## sync all deps (main + dev)
	@uv sync

lock: infra ## refresh uv lockfile (against the current materialized infra)
	@uv lock

# — infra —
infra-src: ## resolve the pinned ref on arkhetypo's remote and fetch its infra blueprint into the cache via `taxis repo`
	@rm -rf $(INFRA_HEAD) && mkdir -p $(INFRA_HEAD)
	@uv run taxis repo extract $(ARKHETYPO_URL) $(ARKHETYPO_REF) projects/python/infra --dest $(INFRA_HEAD)

infra: $(INFRA_FETCH) ## materialize arkhetypo's e-infra into e_taxis.{infra,ops,adapters,processors} via a structural rewrite, and the shared root files into the project root
	@uv run python scripts/materialize.py
	@cp $(INFRA_ROOT)/prek.toml prek.toml
	@cp $(INFRA_ROOT)/.gitattributes .gitattributes
	@cp $(INFRA_ROOT)/.python-version .python-version
	@cp $(INFRA_ROOT)/.github/dependabot.yml .github/dependabot.yml
	@cp $(INFRA_ROOT)/.github/CODEOWNERS .github/CODEOWNERS

infra-check: $(INFRA_FETCH) ## fail if the materialized sections or the shared root files drifted from arkhetypo's infra
	@uv run python scripts/materialize.py --check
	@diff $(INFRA_ROOT)/prek.toml prek.toml \
	 && diff $(INFRA_ROOT)/.gitattributes .gitattributes \
	 && diff $(INFRA_ROOT)/.python-version .python-version \
	 && diff $(INFRA_ROOT)/.github/dependabot.yml .github/dependabot.yml \
	 && diff $(INFRA_ROOT)/.github/CODEOWNERS .github/CODEOWNERS \
	 && printf "$(GREEN)✓ infra in sync$(RESET)\n"

# — gates —
lint: ## ruff check + format
	@uv run ruff check --fix $(PACKAGE) scripts tests
	@uv run ruff format $(PACKAGE) scripts tests

type: ## ty type check
	@uv run ty check

arch: ## enforce import architecture (tach)
	@uv run tach check

validate: ## validate pyproject.toml against schema
	@uv run validate-pyproject pyproject.toml

harden: ## zizmor audit of GitHub Actions workflows
	@uv run zizmor --persona=regular .github/workflows

hooks: ## run all prek hooks on every file (ruff, ty, tach, zizmor, gitleaks)
	@uv run prek run --all-files

# — tests —
test: ## run tests [TESTARGS='-k expr']
	@uv run pytest tests $(TESTARGS) -n auto -q

cov: ## run tests with coverage gate (fail under 100%)
	@uv run pytest tests --cov --cov-report=term-missing

# — aggregate —
check: lint type arch validate infra-check test ## fast local gate: lint + type + arch + validate + drift + test
ci: lint type arch validate harden infra-check cov ## full pipeline: every gate CI runs, in one command

# — release —
release: ## cut a GitHub release via the release workflow [args: patch|minor|major]
	@gh workflow run release.yml -f bump=$(or $(ARGS),patch)
	@sleep 5
	@gh run watch --exit-status $$(gh run list --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId')

ci-vars: ## list optional CI/CD gates (all inert by default) and their defaults
	@printf "$(BOLD)optional CI/CD gates$(RESET) $(GRAY)— enable: gh variable set NAME --body true · manifest: .github/ci.vars.example$(RESET)\n\n"
	@grep -E '^[A-Z][A-Z0-9_]*=' .github/ci.vars.example

# — run —
run: ## run the cli, `taxis` [args: forwarded, e.g. make run project list]
	@uv run taxis $(ARGS)

logo: ## deterministic wordmarks into assets/ [names: make logo NAMES="taxis templates" — knobs: LOGO_ARGS="--force"; bare names as goals only while they spell no target]
	@uv run taxis logo $(ARGS) $(NAMES) $(LOGO_ARGS)

clean: ## remove caches + build artifacts + materialized infra
	@find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) -exec rm -rf {} + 2>/dev/null || true
	@rm -rf dist build *.egg-info .coverage .coverage.* .ty_cache prek.toml .gitattributes .python-version src/e_taxis/.materialized.json
	@rm -rf src/e_taxis/infra src/e_taxis/processors
	@rm -f src/e_taxis/ops/crypto.py src/e_taxis/ops/file.py src/e_taxis/ops/image.py src/e_taxis/ops/registry.py src/e_taxis/ops/wrappers.py
	@rm -f src/e_taxis/adapters/anytomd.py src/e_taxis/adapters/awa.py src/e_taxis/adapters/base.py src/e_taxis/adapters/docling.py src/e_taxis/adapters/http.py src/e_taxis/adapters/otel.py src/e_taxis/adapters/pgqueuer.py src/e_taxis/adapters/ports.py src/e_taxis/adapters/postgres.py src/e_taxis/adapters/queue.py src/e_taxis/adapters/redis.py src/e_taxis/adapters/sqlite.py
	@printf "$(GREEN)✓ clean$(RESET)\n"

%:
	@:
