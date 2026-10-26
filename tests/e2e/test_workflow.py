"""tests/e2e/workflow: the workflow branch against the real checkouts — read-only, slow, never in CI.

`workflow list` reads every workflow of the real e-nous; the front of reverse-distill (guard → intake → scan) runs on
the real e-gnosis since 7ef77f6, into a run folder under tmp: scan must list the range's files — the committed ones
git names, never the working tree's — not 0. No agent step runs; nothing is written to either checkout."""

import os
import shutil
from pathlib import Path

import anyio
import pytest

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.adapters.command import ShellCommand
from e_taxis.workflow.distill.graph import DistillGraph
from e_taxis.workflow.distill.scope import DistillScope
from e_taxis.workflow.distill.store import DistillStore
from e_taxis.workflow.engine.reader import WorkflowReader

pytestmark = pytest.mark.slow

##### DEFAULTS #####
NOUS = Path("~/workspaces/damien/e-nous").expanduser()
GNOSIS = Path("~/workspaces/damien/e-gnosis").expanduser()
SINCE = "7ef77f6"
GRAPH = "codebase-memory-mcp"


@pytest.mark.skipif(not (NOUS / "core").is_dir(), reason="no e-nous checkout")
async def test_workflow_list_reads_every_real_workflow() -> None:
    reader = WorkflowReader(await GitNous(NOUS, None).load())
    assert {"reverse-distill", "emaintenance"} <= set(reader.ids())
    graph, _ = reader.read("reverse-distill")
    assert {"guard", "intake", "scan", "mine-harness", "mine-blueprint", "grade"} <= {step.id for step in graph}


@pytest.mark.skipif(not (GNOSIS / ".git").exists() or not shutil.which(GRAPH), reason="no e-gnosis or code graph")
async def test_distill_front_lists_the_range_of_e_gnosis(tmp_path: Path) -> None:
    command, store = ShellCommand(os.environ), DistillStore(tmp_path / "run")
    scope = await DistillScope(command).guard(GNOSIS, (), SINCE, "e2e")
    manifest = await DistillScope(command).intake(scope)
    deltas = await DistillGraph(command, GRAPH).scan(scope, await DistillScope(command).changed(scope))
    _ = [await store.put(name, value) for name, value in (("scope", scope), ("manifest", manifest), ("deltas", deltas))]
    head = scope.branches[0]
    named = await anyio.run_process(("git", "-C", str(GNOSIS), "diff", "--name-only", f"{scope.base}...{head}"))
    counted = await anyio.run_process(("git", "-C", str(GNOSIS), "rev-list", "--count", f"{scope.base}..{head}"))
    assert len(manifest.commits) == int(counted.stdout)
    assert set(deltas.changed) == set(named.stdout.decode().split())
    assert deltas.changed
    assert not any(path.startswith(".claude/") for path in deltas.changed)
