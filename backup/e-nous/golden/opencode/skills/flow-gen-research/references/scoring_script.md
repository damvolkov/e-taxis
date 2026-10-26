# scoring_script — apply the KPI rubric in code

One self-contained `uv run` script that fans the no-auth endpoints out concurrently, applies the rubric from `python_libraries.md`, and prints the ranked shortlist as JSON. No package to install, no MCP, no key.

## Script

```python
# /// script
# requires-python = ">=3.13"
# dependencies = ["wreq", "orjson"]
# ///
"""Rank Python package candidates by health/adoption KPIs. Usage: uv run rank.py polars pandas."""
import asyncio
import datetime as dt
import sys
from dataclasses import asdict, dataclass
from typing import Any

import orjson as json
import wreq
from wreq.redirect import Policy

_DEPS_PKG = "https://api.deps.dev/v3/systems/pypi/packages/{pkg}"
_DEPS_VERSION = "https://api.deps.dev/v3/systems/pypi/packages/{pkg}/versions/{version}"
_DEPS_PROJECT = "https://api.deps.dev/v3/projects/github.com%2F{repo}"
_PYPISTATS = "https://pypistats.org/api/packages/{pkg}/recent"


@dataclass(frozen=True, slots=True, kw_only=True)
class Health:
    pkg: str
    repo: str | None = None
    stars: int | None = None
    scorecard: float | None = None
    downloads_last_month: int | None = None
    measured_at: str = ""

    @property
    def rank_key(self) -> tuple[float, int, int]:
        """Weight: Scorecard, then downloads, then stars as the tie-break."""
        return (self.scorecard or 0.0, self.downloads_last_month or 0, self.stars or 0)


async def _repo_of(http: wreq.Client, pkg: str) -> str | None:
    """deps.dev lists versions unordered: the repo lives on the default version's SOURCE_REPO link."""
    listing = await (await http.get(_DEPS_PKG.format(pkg=pkg))).json()
    default = next((v for v in listing.get("versions", []) if v.get("isDefault")), None)
    if default is None:
        return None
    detail = await (await http.get(_DEPS_VERSION.format(pkg=pkg, version=default["versionKey"]["version"]))).json()
    origins = (l["url"] for l in detail.get("links", []) if "github.com" in l.get("url", ""))
    return next((u.removeprefix("https://github.com/").rstrip("/") for u in origins), None)


async def measure(http: wreq.Client, pkg: str) -> Health:
    repo = await _repo_of(http, pkg)
    today = dt.date.today().isoformat()
    if repo is None:
        return Health(pkg=pkg, measured_at=today)
    async with asyncio.TaskGroup() as tg:
        project = tg.create_task(http.get(_DEPS_PROJECT.format(repo="%2F".join(repo.split("/")))))
        loads = tg.create_task(http.get(_PYPISTATS.format(pkg=pkg)))
    proj, dl = await (await project).json(), await (await loads).json()
    return Health(pkg=pkg, repo=repo, stars=proj.get("starsCount"),
                  scorecard=(proj.get("scorecard") or {}).get("overallScore"),
                  downloads_last_month=dl["data"]["last_month"], measured_at=today)


async def rank(pkgs: list[str]) -> list[dict[str, Any]]:
    async with wreq.Client(timeout=dt.timedelta(seconds=20), redirect=Policy.limited()) as http:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(measure(http, pkg)) for pkg in pkgs]
    ordered = sorted((t.result() for t in tasks), key=lambda h: h.rank_key, reverse=True)
    return [asdict(h) for h in ordered]


if __name__ == "__main__":
    print(json.dumps(asyncio.run(rank(sys.argv[1:])), option=json.OPT_INDENT_2).decode())
```

Extend it by adding one endpoint per KPI still missing (`pushed_at`, `open_issues`, contributors from `api.github.com/repos/{repo}`) as new `create_task` calls inside the same `TaskGroup` — concurrency stays flat.

## MCP wiring (base servers)

Two base MCPs are wired for every agent — kept minimal on purpose (`context7` for live docs, `serena` for concrete-code semantic navigation + project memory). Research-specific MCPs from `python_libraries.md` are opt-in.

The script above already reads these same endpoints over plain HTTP, so wire a server only when the
orchestration cannot be scripted cheaply. Before that: score it like any other candidate (last release,
contributors, who maintains it).

**One row in `core/tekton/config/mcp.yaml` — never a hand-edit.** The house way is not `claude mcp add`
and not touching the root configs (`~/.claude/.mcp.json`, `~/.eagents/opencode.jsonc`): the transpiler
renders the one row into *both* coders — opencode's top-level `mcp`, and claudecode's user scope, which it
writes itself through `claude mcp add-json --scope user`. A hand-edited artifact is overwritten on the next
apply, and scope is the render's decision, not yours.

```yaml
# releases as of 2026-10-14 (npm, PyPI) — re-verify, then pin what you actually checked
ossinsight:
  command: [uvx, --from, "ossinsight-mcp==0.2.1", ossinsight-mcp]
  smoke: { tool: <one read-only tool you called by hand first> }
supply-chain:
  command: [npx, -y, "supply-chain-mcp-server@0.2.1"]
  smoke: { tool: <one read-only tool you called by hand first> }
# GitHub official (repo detail, token): github/github-mcp-server — its own row: url: or command: + env:
```

A research MCP is third-party code that then runs with the agent's privileges, so the row pins the exact
version inside `command`: `uvx` and `npx` without a pin fetch whatever the registry calls *latest* at every
start — a change you never approved. And the row carries a `smoke`: the deterministic config eval fires that
one tool call right after the handshake (`op eval run config`), so a server that died or moved under you
turns red at the gate instead of mid-session.
