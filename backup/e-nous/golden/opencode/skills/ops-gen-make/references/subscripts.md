# subscripts — wrapping python, bash, and both

A target's recipe is thin: it calls a tool, a shell line, or a script. The rule is where the logic lives.

## Three recipe shapes

```makefile
lint:  ## a tool, args fixed
	@uv run ruff check --fix . && uv run ruff format .

clean: ## a bash line, inline
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

init:  ## a python subscript, args forwarded
	@python3 scripts/init.py $(ARGS)
```

- **Tool** — one or two commands: inline them.
- **A few shell steps** — inline bash, `&&`-chained; `SHELL := bash` guarantees the interpreter.
- **Non-trivial logic** — move it to `scripts/<verb>.py` (or `.sh`) and let the target be a one-line launcher. Logic that grows, branches, or needs types belongs in a real script (→ `script-sh-automation`), never in a tangle of makefile escapes.

## Forwarding arguments

Make treats extra words as goals; capture and neutralize them:

```makefile
ARGS = $(filter-out $@,$(MAKECMDGOALS))   # every word after the target name
run:   ## run the app [args forwarded]
	@uv run python -m $(MODULE) $(ARGS)
%:                                        # swallow those words as no-op goals
	@:
```

So `make run --reload` runs the app with `--reload`, and `make test -k parser` forwards `-k parser`. Without the `%: @:` rule Make would error trying to build `--reload` as a target.

## Make vs a script vs the IDE

- **Make** — the recurrent, necessary, cross-cutting commands everyone runs (setup, gates, run, deploy). One word, discoverable via `help`.
- **A script** — the actual procedure when it is more than a line; Make just names and launches it. Reusable outside Make, testable, typed.
- **The IDE** — running a single test, formatting on save, a debugger: the editor already does these inline. Do not wrap what the IDE resolves in parallel; Make earns its place on the repo-wide, headless, CI-shared tasks.
