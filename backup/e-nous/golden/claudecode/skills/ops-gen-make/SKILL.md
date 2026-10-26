---
name: ops-gen-make
description: "Gen: Makefile as task runner — single-word phony targets, self-documenting help, arg forwarding, aggregate flows, wrapping uv/scripts/docker. Use when adding a repo command or writing a Makefile."
metadata:
  family: delivery
---

# ops-gen-make

The repo's front door: one memorable word per recurrent task, so anyone operates the project without recalling the underlying command. Make is a task runner here, not a build system — the logic lives in the tool or script each target wraps. The tools themselves have their own skills (`test-py-tdd`, containers → `ops-gen-containers`, scripting → `script-sh-automation`); Make only orchestrates. The wrapped toolchain → `references/lib.md`.

## Rules

1. **A target is a verb the user types.** One single-word phony target per recurrent task — `make test`, `make up`, `make lint`; the name is the intent, the recipe wraps the real command. → `references/targets.md`
2. **`help` is the default goal and self-documents.** `.DEFAULT_GOAL := help`; tag each target with `## description` and render the menu with one `awk` line — never hand-maintain a help text. → `references/help.md`
3. **Wrap tools and scripts, never reimplement them.** A recipe runs `uv run …`, a bash line, or a python subscript (`scripts/*.py`); the memorable word is the only thing Make adds. Python/bash/both — the target hides which. → `references/subscripts.md`
4. **Aggregate the common flows.** `check` = the fast local gate (lint + type + test), `ci` = every gate the pipeline runs; compose a target from other targets (`check: lint type test`), never copy their recipes.
5. **Forward args to the wrapped command.** `ARGS = $(filter-out $@,$(MAKECMDGOALS))` plus a catch-all `%: @:` so `make run --port 9000` and `make test -k name` pass through untouched.
6. **Recipes are `.PHONY`; config is overridable.** Declare every command target phony so a same-named file never shadows it; put tunables as `?=` vars at the top (`PORT ?= 8000`) so the environment can override.
7. **Quiet, colored, portable, one job each.** `@` silences echo, `MAKEFLAGS += --no-print-directory`, `SHELL := bash`, ANSI `printf` for status; each target does one legible thing. Recurrent and necessary only — not what the IDE already does inline.

## Sample

```makefile
.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory
SHELL := bash
PORT ?= 8000
ARGS = $(filter-out $@,$(MAKECMDGOALS))
.PHONY: help lint test check run

help:  ## list targets
	@awk 'BEGIN{FS=":.*##"} /^[a-z][a-zA-Z0-9_-]*:.*##/{printf "  \033[32m%-8s\033[0m %s\n",$$1,$$2}' $(MAKEFILE_LIST)
lint:  ## ruff check + format
	@uv run ruff check --fix . && uv run ruff format .
test:  ## run tests [args forwarded]
	@uv run pytest $(ARGS)
check: lint test  ## fast local gate
run:   ## run the app [args forwarded]
	@uv run python -m myapp $(ARGS)
%:
	@:
```

`help` reads its own `##` comments; `check` composes `lint` and `test`; the `%: @:` rule lets `make test -k foo` forward `-k foo`. One word each, self-documented.

## References

- `references/targets.md` — the target catalog: env, gates, test, run, docker, clean; grouping, phony, `?=` config
- `references/help.md` — the self-documenting `help` pattern: `DEFAULT_GOAL`, `##` annotations, the awk line
- `references/subscripts.md` — launching python/bash subscripts, arg forwarding, Make vs a script vs the IDE
- `references/lib.md` — the toolchain Make wraps: GNU Make, `uv`, ruff/ty/tach/pytest, docker, `just` alternative
