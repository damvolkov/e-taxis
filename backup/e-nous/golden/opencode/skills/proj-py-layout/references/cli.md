# cli — command-line tool

Two shapes: a `cli/` layer inside a larger `src/` package (the usual — a daemon or service you also drive from the terminal), or a standalone `cli/`-rooted tool.

## Inside a package (the common case)

```
src/e_<name>/
├── cli/
│   ├── main.py           # the Typer/Cyclopts app — the only place that knows it
│   ├── helpers.py
│   └── commands/         # grouped subcommands: run.py, config.py, session.py
├── core/                 # settings, logger
└── models/
```

## Standalone tool

```
e-<name>/
├── cli/
│   ├── main.py           # entrypoint (project.scripts → cli = "cli.main:cli")
│   ├── settings.py       # single BaseSettings
│   ├── commands/         # one file per command group
│   └── utils/
└── tests/                # unit/ + conftest, same discipline
```

## Non-negotiables

- **Explicit command registration** — commands are plain functions; `main.py` adds each with `app.command(fn)` / `app.add_typer(sub)`. No `@app.command` decorator scattered across modules → `arch-py-hexagonal`.
- **One command group per file** in `commands/`; the file is the noun, the functions the verbs (`run`, `config`, `session`).
- **Output is `rich`; logs are `structlog`** — user-facing tables/console via `rich`, diagnostics via the logger. Two channels, never mixed → `obs-py-logging`.
- **Entrypoint in pyproject** — `[project.scripts]` exposes the command; the package stays importable.
- **Settings** — a single `BaseSettings` for a small tool; the composed `config/` set once it grows.
