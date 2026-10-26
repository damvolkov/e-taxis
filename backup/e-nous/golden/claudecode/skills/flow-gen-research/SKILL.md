---
name: flow-gen-research
description: "Gen: survey the state of the art before adding a dependency — discover, score by health/adoption KPIs, decide. Use before picking a Python library, framework, database, queue, model or MCP."
metadata:
  family: philosophy
---

# flow-gen-research

Never add a dependency you have not surveyed. Discover, measure, decide — in that order, with a date attached to every number.

## Rules

1. **Three layers, never one source.** Popularity (rankings) + expert maturity (radars) + technical evidence (benchmarks, Jepsen) + project health (deps.dev, GitHub) + lifecycle (endoflife). One source is an opinion, not a decision.
2. **The pipeline is fixed:** DISCOVER candidates → MEASURE KPIs → DECIDE against the project's preference order (builtin → Rust/C-backed → pure Python; managed vs self-hosted; async-first).
3. **Skill + `fetch`/`uv run` over chaining third-party MCPs.** The no-auth API endpoints in the references are the source of truth; add the official GitHub MCP only when you need deeper repo detail. Less attack surface, no foreign maintainers.
4. **Stars are a tie-breaker, never a KPI.** Stars are cumulative; maintenance is current. Rank by last release, downloads, dependents, Scorecard, open-issue ratio and bus factor — stars only to break ties.
5. **Distrust vendor benchmarks.** Trust independent, reproducible ones: Jepsen for correctness under fault; ClickBench / TPC / ANN-Benchmarks / TechEmpower / OpenMessaging for performance.
6. **Cite the date of every datum.** Rankings, leaderboards and download counts decay; a number without a date is noise.
7. **Route by target.** Python package → `references/python_libraries.md`. Third-party tech (DB, queue, framework, model, MCP) → `references/third_party_tech.md`. Applying the rubric in code → `references/scoring_script.md`.

## Sample

```python
# MEASURE: pull one candidate's health from no-auth sources, in parallel. Attach the date.
import asyncio
import datetime as dt
import wreq
from wreq.redirect import Policy

async def measure(pkg: str, repo: str) -> dict[str, object]:
    """repo = 'owner/name'. deps.dev → stars/forks/OpenSSF Scorecard; pypistats → recent downloads."""
    key = repo.replace("/", "%2F")  # deps.dev wants the whole 'github.com/owner/name' as one segment
    async with wreq.Client(timeout=dt.timedelta(seconds=10), redirect=Policy.limited()) as http:
        async with asyncio.TaskGroup() as tg:
            health = tg.create_task(http.get(f"https://api.deps.dev/v3/projects/github.com%2F{key}"))
            loads = tg.create_task(http.get(f"https://pypistats.org/api/packages/{pkg}/recent"))
    project, downloads = await (await health).json(), await (await loads).json()
    return {
        "pkg": pkg,
        "scorecard": (project.get("scorecard") or {}).get("overallScore"),
        "stars": project.get("starsCount"),
        "downloads_last_month": downloads["data"]["last_month"],
        "measured_at": dt.date.today().isoformat(),
    }
```

## References

- `references/python_libraries.md` — Python packages: best-of discovery, deps.dev/pypistats/GitHub KPIs, the KPI rubric, MCP options
- `references/third_party_tech.md` — DBs, queues, frameworks, models, MCPs: landscapes, radars, Jepsen, independent benchmarks, endoflife
- `references/scoring_script.md` — the `uv run` script that fans out the no-auth APIs and emits the ranked rubric as JSON
- No `lib.md` — this skill *is* the vendor-selection method; its library lists live in `python_libraries.md`/`third_party_tech.md`, not a fixed matrix.
