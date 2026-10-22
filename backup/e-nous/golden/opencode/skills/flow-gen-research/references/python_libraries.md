# python_libraries — researching a Python package

The recipe for one question: *what should I import for X, and is it healthy?* Three steps, in order. Every number carries the date it was read.

## Pipeline

```
DISCOVER  → best-of-python (ranked) + OSSInsight (trending)      # what exists
MEASURE   → deps.dev + pypistats + GitHub API (no auth)          # is it healthy
DECIDE    → KPI rubric + preference: builtin > Rust/C > pure Py  # which one
```

## Recipe 1 — DISCOVER candidates

Read the raw ranked catalog first; it already did the scoring for ~400 projects across 28 categories, regenerated every Thursday. The agent reads the raw `README.md` or `projects.yaml`.

| Source | Use | Raw URL |
|---|---|---|
| **best-of-python** | ranked general catalog (project-quality score from GitHub + package managers) | `https://raw.githubusercontent.com/lukasmasuch/best-of-python/main/README.md` |
| best-of-python-dev | dev tooling (lint, type, test, build) | `https://raw.githubusercontent.com/lukasmasuch/best-of-python-dev/main/README.md` |
| best-of-web-python | web frameworks, ASGI, clients | `https://raw.githubusercontent.com/lukasmasuch/best-of-web-python/main/README.md` |
| best-of-ml-python | ML / NLP / inference | `https://raw.githubusercontent.com/lukasmasuch/best-of-ml-python/main/README.md` |
| machine-readable | the same scores as data | append `/projects.yaml` to any list above |
| OSSInsight | trending, collections, repo comparison; no key, 600 req/h per IP | `https://ossinsight.io/collections` |

**Caveat — OSSInsight:** since mid-2025 it under-captured stars/PRs/issues events. Use it to *discover* trends, never as a KPI of record.

**Search tips.** Start from the *category*, not the package name — the list groups by problem, so you meet alternatives you didn't know. Grep the raw README for the problem noun (`"JSON"`, `"dataframe"`, `"retry"`). The 🥇/🥈/🥉 rank and the `⭐` + `📈` badges encode the quality score — read them before opening any repo.

## Recipe 2 — MEASURE (no-auth APIs, the source of truth)

deps.dev is the single best health-and-security source: stars, forks, licence and the OpenSSF Scorecard in one call. pypistats is the best real-adoption proxy.

| KPI | Endpoint |
|---|---|
| package metadata, versions, licence | `https://api.deps.dev/v3/systems/pypi/packages/{pkg}` |
| stars, forks, **OpenSSF Scorecard**, links | `https://api.deps.dev/v3/projects/github.com%2F{owner}%2F{repo}` |
| open issues, `pushed_at`, releases, contributors | `https://api.github.com/repos/{owner}/{repo}` (+`/releases`, `/contributors`) |
| recent downloads (day/week/month) | `https://pypistats.org/api/packages/{pkg}/recent` |
| Python-version / wheel compatibility | `https://pypi.org/pypi/{pkg}/json` |

GitHub unauthenticated is 60 req/h; wire the official **GitHub MCP** (`github/github-mcp-server`, token) only when the extra detail is worth it.

## Recipe 3 — DECIDE (KPI rubric, ordered by weight)

| KPI | Source | Orientative threshold |
|---|---|---|
| Last commit / release | GitHub, PyPI | < 6 months |
| Downloads / month | pypistats | relative to alternatives |
| Dependents | deps.dev / best-of | relative |
| OpenSSF Scorecard | deps.dev | ≥ 5/10 |
| Open-issue ratio | GitHub / best-of | < 20 % |
| Active contributors | GitHub | ≥ 3 (bus factor) |
| Stars | GitHub | tie-break only |
| Backend | README / wheels | builtin → Rust/C → pure Python |
| Typing & wheels | PyPI | bonus: `py.typed`, abi3, cp313t free-threaded |

Apply it in code with the scoring script — it fans these endpoints out concurrently and emits the ranked table as JSON. For head-to-head, `secchi compare pypi:duckdb pypi:polars --format json` does the same in one CLI call.

## MCP options (evaluate before trusting; most are lightly maintained)

Prefer the skill + `fetch`/script above. Add an MCP only for orchestration you cannot script cheaply.

| MCP | Gives | Auth |
|---|---|---|
| `ossinsight-mcp` | trending, collections, repo comparison, star/PR/issue ranking | none |
| `supply-chain-mcp-server` | deps.dev + Libraries.io SourceRank + typosquatting | mostly none |
| `mcp-pypi` / `pypi-query-mcp-server` | metadata, versions, deps, Python compat (no quality KPIs) | none |
| `secchi` | `compare` + health-threshold `check` for two packages | none |
| Socket MCP | per-package security & quality scores | key |
| `github/github-mcp-server` | authoritative repo detail (issues, releases, contributors) | token |

Wire-up is one row in `core/tekton/config/mcp.yaml` — the exact version inside `command`, plus a `smoke` call — that the transpiler renders into both coders; `context7` (up-to-date, version-pinned library docs) is already wired as a base MCP and is the fastest way to confirm a shortlisted library's real current API.
