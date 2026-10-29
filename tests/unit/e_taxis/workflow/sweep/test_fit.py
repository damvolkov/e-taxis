"""tests/unit/e_taxis/workflow/sweep/fit: have · considered · new by token matching over the corpus, the live trees and
past reports — never from memory."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.models.sweep import Findings, FindingStatus
from e_taxis.workflow.sweep.fit import SweepFit

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.models.sweep import Finding


@pytest.fixture
def worlds(tmp_path: Path, tree) -> tuple[Path, Path, Path, Path]:
    """(nous, live tree, reports root, this run): the corpus names Langfuse, an MCP server and a stack on
    nvidia; the live tree an
    installed plugin; a past sweep named Spanline; this run's own report names everything and is not read."""
    nous, live, reports = tmp_path / "nous", tmp_path / "live", tmp_path / "nous" / ".reports"
    tree(
        nous,
        {
            "core/tekton/skills/obs-py-logging/references/lib.md": "| `langfuse` | traces |\n",
            "core/common/stack.yaml": "services: {qdrant: {image: qdrant/qdrant}, vllm: {runtime: nvidia}}\n",
            "core/tekton/config/mcp.yaml": "servers: {e-gnosis: {}}\n",
            "core/tekton/skills/x/SKILL.md": "Phoenix is not read: no lib.md.\n",
        },
    )
    tree(live, {"plugins/installed_plugins.json": '{"tracekit@market": {}}', "projects/history.jsonl": "Phoenix"})
    run = reports / "workflows" / "radar-field" / "now"
    tree(
        reports,
        {
            "workflows/radar-field/past/radar/report.json": '{"findings": [{"title": "Spanline"}]}',
            "workflows/radar-tech/old/report.md": "# Assessed: Headlong\n",
            "workflows/radar-field/now/report.md": "Phoenix Arize everything",
            "workflows/reverse-distill/r/report.md": "Arize",
        },
    )
    return nous, live, reports, run


@pytest.mark.parametrize(
    ("fields", "status", "incumbent"),
    [
        ({"title": "Langfuse"}, FindingStatus.HAVE, "langfuse — core/tekton/skills/obs-py-logging/references/lib.md"),
        (
            {"title": "X", "links": ("https://github.com/qdrant/qdrant",)},
            FindingStatus.HAVE,
            "qdrant — core/common/stack.yaml",
        ),
        (
            {"title": "Langfuse", "entities": ("traces", "Qdrant")},
            FindingStatus.HAVE,
            "langfuse (+ traces) — core/tekton/skills/obs-py-logging/references/lib.md",
        ),
        ({"title": "X", "entities": ("e-gnosis",)}, FindingStatus.NEW, ""),
        ({"title": "auto ontology", "entities": ("NVIDIA", "MCP")}, FindingStatus.NEW, ""),
        ({"title": "Tracekit"}, FindingStatus.HAVE, "tracekit — {live}/plugins/installed_plugins.json"),
        (
            {"title": "Spanline"},
            FindingStatus.CONSIDERED,
            "spanline — {reports}/workflows/radar-field/past/radar/report.json",
        ),
        (
            {"title": "Headlong"},
            FindingStatus.CONSIDERED,
            "headlong — {reports}/workflows/radar-tech/old/report.md",
        ),
        ({"title": "Headlong harness", "entities": ("Headlong",)}, FindingStatus.NEW, ""),
        ({"title": "Phoenix"}, FindingStatus.NEW, ""),
        ({"title": "Arize"}, FindingStatus.NEW, ""),
        ({"title": "AI", "entities": ("ql",)}, FindingStatus.NEW, ""),
    ],
    ids=[
        "lib",
        "stack-repo",
        "entities-fill-incumbent",
        "entity-alone",
        "live-false-positive",
        "live",
        "past-sweep",
        "past-assess",
        "past-entity-alone",
        "unread",
        "other-workflows",
        "short",
    ],
)
async def test_fit_marks_each_finding(
    worlds: tuple[Path, Path, Path, Path],
    finding: Callable[..., Finding],
    fields: dict[str, object],
    status: FindingStatus,
    incumbent: str,
) -> None:
    nous, live, reports, run = worlds
    fit = await SweepFit.load(nous, (live, nous / "absent"), reports, run)
    (marked,) = fit.fit(Findings(findings=(finding(**({"links": ()} | fields)),), notes="n")).findings
    assert (marked.status, marked.incumbent) == (status, incumbent.format(live=live, reports=reports))
