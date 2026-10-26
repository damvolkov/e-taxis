"""distill.graph: the code graph both cores and the project are read through — codebase-memory-mcp's CLI.

No parse of our own: `index` (re)indexes e-nous, e-arkhetypo and the project — incremental, so a core that has not
moved costs nothing — and `scan` asks the graph which symbols the run's changes impact. Which files changed is not
the graph's to say: its `detect_changes` diffs the working tree (untracked worktrees, uncommitted edits) and pages
its list, so the changed files come from git over the run's range (`DistillScope.changed`) and only the impacted
symbols from the graph. The miners query the same graph through MCP; this module makes it current and cuts the delta."""

import json
import shlex
import shutil
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any

import anyio

from e_taxis.workflow.distill.scope import DistillScope
from e_taxis.workflow.models.distill import Deltas, Indexes, Scope, Symbol
from e_taxis.workflow.models.error import DistillError

if TYPE_CHECKING:
    from e_taxis.workflow.models.ports import CommandPort

##### DEFAULTS #####
GRAPH: float = 600.0
GIT: float = 30.0
IMPACTED: int = 200


##### TYPES #####
class DistillGraph:
    """`<graph> cli --json <tool> --args-file <json>`, one call per question."""

    __slots__ = ("_binary", "_command")

    def __init__(self, command: CommandPort, binary: str) -> None:
        self._command = command
        self._binary = binary

    ##### PRIVATE METHODS #####

    async def _common_call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        """One tool call; the CLI answers an MCP result whose text is the tool's JSON."""
        with TemporaryDirectory(prefix="e-taxis-graph-") as tmp:
            given = Path(tmp) / "args.json"
            await anyio.Path(given).write_text(json.dumps(args))
            raw = await self._command.run(
                self._binary, "cli", "--quiet", "--json", tool, "--args-file", str(given), limit=GRAPH
            )
        reply = json.loads(raw[raw.index("{") :])
        text = reply["content"][0]["text"]
        match reply.get("isError"):
            case True:
                msg = f"{self._binary} {tool}: {text}"
                raise DistillError(msg)
            case _:
                return json.loads(text)

    async def _index_head(self, repo: Path, rev: str = "HEAD") -> str:
        return (await self._command.run("git", "-C", str(repo), "rev-parse", rev, limit=GIT)).strip()

    async def _index_one(self, repo: Path) -> str:
        await self._common_call("index_repository", {"repo_path": str(repo)})
        return DistillScope.graph_name(repo)

    async def _index_snapshot(self, blueprint: Path, ref: str, cache: Path) -> tuple[Path, str]:
        """The published e-arkhetypo tree, extracted once per commit: what the graph reads is what grade weighs."""
        head = await self._index_head(blueprint, ref)
        folder, stamp = cache / "e-arkhetypo", anyio.Path(cache / "e-arkhetypo.head")
        match await stamp.is_file() and await stamp.read_text() == head:
            case True:
                return folder, head
            case _:
                await anyio.to_thread.run_sync(partial(shutil.rmtree, folder, ignore_errors=True))
                await anyio.Path(folder).mkdir(parents=True)
                archive = f"git -C {shlex.quote(str(blueprint))} archive {shlex.quote(ref)}"
                await self._command.run("bash", "-c", f"{archive} | tar -x -C {shlex.quote(str(folder))}", limit=GRAPH)
                await stamp.write_text(head)
                return folder, head

    ############################################################

    ##### PUBLIC #####

    async def index(self, harness: Path, blueprint: Path, project: Path, ref: str, cache: Path) -> Indexes:
        """Index e-nous and the project as they stand, e-arkhetypo as `ref` publishes it (incremental)."""
        harness, project, blueprint, cache = [
            Path(await (await anyio.Path(path).expanduser()).resolve()) for path in (harness, project, blueprint, cache)
        ]
        snapshot, published = await self._index_snapshot(blueprint, ref, cache)
        named = [
            (await self._index_one(harness), await self._index_head(harness)),
            (await self._index_one(snapshot), published),
            (await self._index_one(project), await self._index_head(project)),
        ]
        return Indexes(harness=named[0][0], blueprint=named[1][0], project=named[2][0], heads=dict(named))

    async def scan(self, scope: Scope, changed: tuple[str, ...]) -> Deltas:
        """The run's changed files (git) and the symbols the graph says they impact."""
        found = await self._common_call(
            "detect_changes",
            {"project": scope.graph, "base_branch": scope.base, "scope": "impact", "format": "json", "limit": IMPACTED},
        )
        impacted = tuple(
            Symbol(
                name=str(item.get("name") or item.get("qn", "")),
                label=str(item.get("label", "")),
                file=str(item.get("file", item.get("file_path", ""))),
            )
            for item in found.get("impacted", found.get("impacted_symbols", []))
            if isinstance(item, dict)
        )
        return Deltas(changed=changed, impacted=impacted)
