##### CONFIG #####
PROJECT  ?= e-taxis
PACKAGE  ?= src/e_taxis
MODULE   ?= e_taxis
E_TEMPLATES_URL ?= https://github.com/damvolkov/e-templates.git
### The pinned ref of e-templates (.e-templates-ref: a tag, a branch or a commit), read off its public remote
### by `taxis repo` — deterministic git plumbing, never a working tree: a change lands here only by bumping the
### pin. An offline box points the url at the checkout beside it: `make core E_TEMPLATES_URL=file://../e-templates`.
TEMPLATES_REF ?= $(shell cat .e-templates-ref)
CORE_HEAD ?= $(HOME)/.cache/e-taxis/e-templates-head
CORE_SRC ?= $(CORE_HEAD)/systems/core/src/e_core
export E_CORE_SRC := $(CORE_SRC)
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
.PHONY: core-src help install sync lock core common core-check common-check lint type arch validate harden hooks test cov check ci run logo release ci-vars clean

help:
	@printf "$(BOLD)$(CYAN)$(PROJECT)$(RESET) $(GRAY)· uv · cyclopts · ruff · ty · tach · pytest — systems/core materialized into e_taxis from $(CORE_SRC)$(RESET)\n\n"
	@awk 'BEGIN{FS=":.*##"} /^[a-z][a-zA-Z0-9_-]*:.*##/{printf "  $(GREEN)%-12s$(RESET) $(GRAY)%s$(RESET)\n",$$1,$$2}' $(MAKEFILE_LIST)

# — env —
install: core common ## full setup: materialize shared assets + sync deps + git hooks
	@uv sync
	@uv run prek install
	@printf "$(GREEN)✓ ready$(RESET)\n"

sync: ## sync all deps (main + dev)
	@uv sync

lock: core ## refresh uv lockfile (against the current materialized core)
	@uv lock

# — common —
COMMON_SRC ?= $(CORE_HEAD)/systems/core/common

core-src: ## resolve the pinned ref on e-templates' remote and fetch systems/core into the cache via `taxis repo`
	@rm -rf $(CORE_HEAD) && mkdir -p $(CORE_HEAD)
	@uv run taxis repo extract $(E_TEMPLATES_URL) $(TEMPLATES_REF) systems/core --dest $(CORE_HEAD)

core: core-src ## materialize systems/core into e_taxis.{core,ops,adapters,processors} via a structural rewrite
	@uv run python scripts/materialize.py

core-check: core-src ## fail if the materialized sections drifted from systems/core
	@uv run python scripts/materialize.py --check

### prek.toml is not committed in e-templates yet: copied and checked only when its HEAD carries it.
common: core-src ## materialize shared project files from systems/core/common into the project root
	@[ ! -f $(COMMON_SRC)/prek.toml ] || cp $(COMMON_SRC)/prek.toml prek.toml
	@cp $(COMMON_SRC)/gitattributes .gitattributes
	@cp $(COMMON_SRC)/python-version .python-version
	@cp $(COMMON_SRC)/dependabot.yml .github/dependabot.yml
	@cp $(COMMON_SRC)/CODEOWNERS .github/CODEOWNERS

common-check: core-src ## fail if the materialized shared files drifted from systems/core/common
	@{ [ ! -f $(COMMON_SRC)/prek.toml ] || diff $(COMMON_SRC)/prek.toml prek.toml; } \
	 && diff $(COMMON_SRC)/gitattributes .gitattributes \
	 && diff $(COMMON_SRC)/python-version .python-version \
	 && diff $(COMMON_SRC)/dependabot.yml .github/dependabot.yml \
	 && diff $(COMMON_SRC)/CODEOWNERS .github/CODEOWNERS \
	 && printf "$(GREEN)✓ common in sync$(RESET)\n"

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
check: lint type arch validate core-check common-check test ## fast local gate: lint + type + arch + validate + drift + test
ci: lint type arch validate harden core-check common-check cov ## full pipeline: every gate CI runs, in one command

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

clean: ## remove caches + build artifacts + materialized core
	@find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) -exec rm -rf {} + 2>/dev/null || true
	@rm -rf dist build *.egg-info .coverage .coverage.* .ty_cache prek.toml .gitattributes .python-version src/e_taxis/.materialized.json
	@rm -rf src/e_taxis/core src/e_taxis/processors
	@rm -f src/e_taxis/ops/file.py src/e_taxis/ops/image.py src/e_taxis/ops/registry.py src/e_taxis/ops/wrappers.py
	@rm -f src/e_taxis/adapters/anytomd.py src/e_taxis/adapters/base.py src/e_taxis/adapters/docling.py src/e_taxis/adapters/http.py src/e_taxis/adapters/otel.py src/e_taxis/adapters/ports.py src/e_taxis/adapters/redis.py src/e_taxis/adapters/sqlite.py
	@printf "$(GREEN)✓ clean$(RESET)\n"

%:
	@:
