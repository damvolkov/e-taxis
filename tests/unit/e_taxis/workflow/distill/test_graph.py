"""tests/unit/e_taxis/workflow/distill/graph: the code-graph CLI — indexing the three repos, the impacted symbols.

The graph's own `changed_files` (the working tree, paged) never reaches the deltas: the changed files are the run's
range, handed in from git."""

import json
from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.distill.graph import DistillGraph
from e_taxis.workflow.models.distill import Scope, Symbol
from e_taxis.workflow.models.error import DistillError

if TYPE_CHECKING:
    from pathlib import Path

GRAPH = ("codebase-memory-mcp", "cli", "--quiet", "--json")


async def test_graph_scan_keeps_the_range_and_reads_impacted(fake_command) -> None:
    said = {
        "changed_files": [".claude/worktrees/agent-x/", "wip.py"],
        "impacted": [
            {"qn": "p.src.a.py.f", "label": "Function", "file": "src/a.py"},
            {"name": "g", "file_path": "b.py"},
            "junk",
        ],
    }
    fake_command.answers[(*GRAPH, "detect_changes")] = "log line\n" + json.dumps(
        {"content": [{"text": json.dumps(said)}]}
    )
    scope = Scope(project="/p", graph="p", branches=("b",), base="abc")
    deltas = await DistillGraph(fake_command, "codebase-memory-mcp").scan(scope, ("a.py", "c.py"))
    assert deltas.changed == ("a.py", "c.py")
    assert deltas.impacted == (
        Symbol(name="p.src.a.py.f", label="Function", file="src/a.py"),
        Symbol(name="g", file="b.py"),
    )


async def test_graph_tool_error_is_a_distill_error(fake_command) -> None:
    fake_command.answers[(*GRAPH, "detect_changes")] = json.dumps(
        {"isError": True, "content": [{"text": "no project p"}]}
    )
    with pytest.raises(DistillError, match="detect_changes: no project p"):
        await DistillGraph(fake_command, "codebase-memory-mcp").scan(
            Scope(project="/p", graph="p", branches=(), base="a"), ()
        )


async def test_graph_index_names_the_three_and_snapshots_once(fake_command, tmp_path: Path) -> None:
    ok = json.dumps({"content": [{"text": "{}"}]})
    fake_command.answers[(*GRAPH, "index_repository")] = ok
    fake_command.answers[("git",)] = "abc123\n"
    paths = [tmp_path / name for name in ("e-nous", "e-arkhetypo", "proj")]
    _ = [path.mkdir() for path in paths]
    graph = DistillGraph(fake_command, "codebase-memory-mcp")
    nous, blueprint, project = paths
    indexes = await graph.index(nous, blueprint, project, "origin/main", tmp_path / "cache")
    again = await graph.index(nous, blueprint, project, "origin/main", tmp_path / "cache")
    archives = [argv for argv, _ in fake_command.calls if argv[0] == "bash"]
    assert indexes == again
    assert indexes.harness.endswith("-e-nous")
    assert indexes.blueprint.endswith("-cache-e-arkhetypo")
    assert indexes.project.endswith("-proj")
    assert set(indexes.heads.values()) == {"abc123"}
    assert len(archives) == 1
    assert "archive origin/main | tar -x -C" in archives[0][2]
