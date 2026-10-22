# hooks — the gates that run before a commit lands

Every repo ships one `.pre-commit-config.yaml`, run by **`prek`** — the Rust reimplementation of `pre-commit`, reading the same file. The Python `pre-commit` is never installed: `prek` is a drop-in, faster, and needs no Python environment per hook.

## The base config

The house template (`e-arkhetypo`, `projects/python/core/common/prek.toml`) is the source; a project copies it verbatim and only appends.

```yaml
##### HOOKS #####
repos:
  - repo: local
    hooks:
      - id: ruff
        name: ruff check + format
        entry: uv run ruff check --fix --exit-non-zero-on-fix
        language: system
        types_or: [python, pyi]

      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types_or: [python, pyi]

      - id: ty
        name: ty type check
        entry: uv run ty check
        language: system
        types: [python]
        pass_filenames: false

      - id: tach
        name: tach architecture check
        entry: uv run tach check
        language: system
        pass_filenames: false

      - id: zizmor
        name: workflow hardening scan
        entry: uv run zizmor --persona=regular .github/workflows
        language: system
        files: ^\.github/workflows/.*\.ya?ml$
        pass_filenames: false

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.30.1
    hooks:
      - id: gitleaks
```

## Why this shape

- **`repo: local` + `uv run`.** Every tool runs at the version the lockfile pins — the same ruff in the hook, in `make lint` and in CI. A remote hook repo would pin a second, drifting version.
- **`--exit-non-zero-on-fix`.** A fix the hook made is a change you have not reviewed: the commit stops, you look, you stage.
- **Whole-project checks pass no filenames.** `ty` and `tach` judge the graph, not a file; handing them the staged subset would let a break elsewhere through.
- **zizmor only when workflows move** (`files:`), gitleaks always: a secret in any file is a leak.

## Wiring

| Where | What |
|---|---|
| `pyproject.toml` | `prek>=0.4` in the `dev` group; `zizmor` in `lint` beside ruff, ty, tach |
| `make install` | `uv sync` then `uv run prek install` — the hook is installed with the environment, never by hand |
| `make hooks` | `uv run prek run --all-files` — the whole tree, the way CI sees it |
| CI | runs `make hooks` (or the same tools through `make check`); the hook is the local copy of the gate, not the gate |

Adopting the config on an existing repo: one commit that is formatting only (`uv run ruff format`), its hash in `.git-blame-ignore-revs`, before any logic change rides on top. Ruff also formats the code fences inside Markdown: a repo whose Markdown is data (skills, docs with samples) pins `[tool.ruff] include = ["*.py", "*.pyi", "**/pyproject.toml"]` first, or that commit rewrites prose it does not own.

**Never:** `pip install pre-commit` or `pre-commit install` · a remote ruff/ty hook pinned apart from the lockfile · `--no-verify` to land a red commit · a hook that edits files without failing.
