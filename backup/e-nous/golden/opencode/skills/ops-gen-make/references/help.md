# help — the menu writes itself

A hand-maintained help text drifts from the targets. Instead, make `help` the default goal and generate it from the targets' own `##` comments — the menu can never be stale because it *is* the targets.

## The pattern

```makefile
.DEFAULT_GOAL := help    # bare `make` prints the menu, never runs a real task by accident

help:  ## list targets
	@awk 'BEGIN{FS=":.*##"} /^[a-z][a-zA-Z0-9_-]*:.*##/ {printf "  \033[32m%-8s\033[0m \033[90m%s\033[0m\n", $$1, $$2}' $(MAKEFILE_LIST)
```

- `FS=":.*##"` splits each line into the target name (`$$1`) and the description after `##` (`$$2`).
- The regex `^[a-z][a-zA-Z0-9_-]*:.*##` matches only annotated recipe targets — internal helpers without `##` stay hidden.
- `$(MAKEFILE_LIST)` scans every included makefile, so split files still produce one menu.
- ANSI (`\033[32m` green name, `\033[90m` grey text) makes it scannable; harmless when piped.

## The rule

Every user-facing target ends its declaration line with `## one-line description`:

```makefile
test:  ## run tests [args forwarded]
```

- Keep the description to a few words — it is the whole documentation most users read.
- No `##` → the target is internal (a dependency of another, or plumbing) and stays off the menu.
- A banner header (`@printf "$(PROJECT) · uv · ruff · ty · pytest\n\n"`) before the awk line gives the menu a title.

The result: `make` with no argument lists exactly the commands, current by construction, at zero maintenance.
