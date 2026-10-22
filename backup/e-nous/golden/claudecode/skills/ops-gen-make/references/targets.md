# targets — the catalog and the header

The recurrent tasks every repo needs, as single words. Group them with comment banners; keep names short and predictable across projects so muscle memory transfers.

## The header

```makefile
##### CONFIG #####
PROJECT ?= e-api
MODULE  ?= e_api
PORT    ?= 8000
COMPOSE ?= compose.yml
ARGS     = $(filter-out $@,$(MAKECMDGOALS))

SHELL := bash
.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory
export PYTHONPATH := $(CURDIR)/src
.PHONY: help install sync lint type arch test cov check ci run up down build logs clean init
```

- `?=` on config so `PORT=9000 make up` overrides without editing the file.
- One `.PHONY` line naming every command target — they are verbs, not files.

## The conventional set

| Group | Targets | Wraps |
|---|---|---|
| env | `install` `sync` `lock` | `uv sync` / `uv lock` / hooks |
| gates | `lint` `type` `arch` `validate` `hooks` | ruff · ty · tach · validate-pyproject · prek |
| tests | `test` `cov` `benchmark` | pytest (+ `-n auto`, `--cov`, `-m benchmark`) |
| docs | `docs` `docs-build` | the docs tool, serve vs strict build |
| aggregate | `check` `ci` | other targets composed |
| run | `run` `up` `down` `build` `logs` | the app · docker compose |
| housekeeping | `clean` | remove caches/artifacts |
| scripts | `init` … | `python3 scripts/*.py` |

Not every repo needs all of them; a CLI tool drops `up/down`, a library adds `publish`. Keep the names identical where the task is the same.

## Aggregates

```makefile
check: lint type arch test        ## fast local gate
ci:    lint type arch harden cov  ## every gate the pipeline runs
```

Compose from targets, never inline their recipes — one definition per command, reused. `check` is what you run before a commit; `ci` mirrors the pipeline so "green locally" means "green in CI".
