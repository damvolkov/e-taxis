"""tests/unit/e_taxis/transpile/services/check: the fixture checkout holds; every seeded break is caught as its kind.

Each mutation edits one file of the copy the way a real mistake would, and must surface as exactly the finding
kind the model names — the law seen failing for the right reason, not merely failing."""

from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.models.report import ReportKind
from e_taxis.transpile.services.check import CheckService

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

CC, OC, HE, OH = (
    "specs/tekton/claudecode.yaml",
    "specs/tekton/opencode.yaml",
    "specs/nomos/hermes.yaml",
    "specs/nomos/openhuman.yaml",
)


def _move_to_end(rows: list[Any], index: int) -> None:
    rows.append(rows.pop(index))


MUTATIONS: list[tuple[str, Callable[[Any], None], ReportKind, str]] = [
    (HE, lambda s: s["map"]["config"]["unmapped"].pop("tools.calls"), ReportKind.UNCOVERED, "tools.calls"),
    (OC, lambda s: s["map"]["config"]["rows"][1].update({"from": "main.usr"}), ReportKind.ORPHAN, "main.usr"),
    (CC, lambda s: s["map"]["persona"]["rows"][10].pop("glue"), ReportKind.BLOCK, "Voice"),
    (OH, lambda s: _move_to_end(s["map"]["persona"]["rows"], 4), ReportKind.BLOCK, "Personality"),
    (CC, lambda s: s["map"]["config"]["rows"][9].pop("via"), ReportKind.UNUSED, "claude_plugins"),
    (
        CC,
        lambda s: s["map"]["skill"]["rows"][3].update({"via": {"template": "x{value}"}}),
        ReportKind.INVERTIBLE,
        "#title",
    ),
    (OC, lambda s: s["map"]["agent"]["rows"][2].update({"via": "ghost"}), ReportKind.UNDECLARED, "ghost"),
    (HE, lambda s: s["map"]["config"]["rows"][0].update({"to": "nowhere.md#x"}), ReportKind.UNDECLARED, "nowhere.md#x"),
    (CC, lambda s: s["map"].pop("workflow"), ReportKind.PRESENCE, "workflow"),
    (CC, lambda s: s["map"]["skill"].update({"status": "pending"}), ReportKind.INVALID, "skill"),
    (HE, lambda s: s["transforms"]["routes"]["consumes"].append("models.ghost"), ReportKind.ORPHAN, "models.ghost"),
    (CC, lambda s: s["map"]["persona"]["rows"][0].update({"at": 1}), ReportKind.INVALID, "spec"),
    ("core/tekton/config/main.yaml", lambda m: m.update({"colour": "red"}), ReportKind.INVALID, "config/tekton/main"),
    (CC, lambda s: s["map"]["skill"].update({"rows": []}), ReportKind.INVALID, "skill"),
    (OC, lambda s: s.update({"harness": "ghost"}), ReportKind.UNDECLARED, "ghost"),
    (CC, lambda s: s["map"]["config"]["rows"][1].pop("from"), ReportKind.INVALID, "#model"),
]


async def test_check_fixture_holds(nous_root: Path) -> None:
    report = await CheckService().run(GitNous(nous_root, None))
    assert report.blocking == ()
    assert {finding.kind for finding in report.findings} == {ReportKind.SIGNAL}


@pytest.mark.parametrize(
    ("relative", "change", "kind", "path"),
    MUTATIONS,
    ids=[
        "uncovered",
        "orphan-from",
        "glue",
        "split-block",
        "unused",
        "invertible",
        "via",
        "target",
        "presence",
        "status",
        "consumes",
        "row-field",
        "core-key",
        "ready-empty",
        "harness",
        "no-source",
    ],
)
async def test_check_mutation_is_caught_as_its_kind(
    nous_root: Path,
    edit: Callable[[str, Callable[[Any], None]], None],
    relative: str,
    change: Callable[[Any], None],
    kind: ReportKind,
    path: str,
) -> None:
    edit(relative, change)
    report = await CheckService().run(GitNous(nous_root, None))
    assert any(finding.kind is kind and path in f"{finding.path}{finding.where}" for finding in report.blocking), (
        report.blocking
    )


async def test_check_pending_section_without_rows_is_silent(
    nous_root: Path, edit: Callable[[str, Callable[[Any], None]], None]
) -> None:
    edit(CC, lambda s: s["map"]["workflow"].update({"status": "pending", "rows": []}))
    report = await CheckService().run(GitNous(nous_root, None))
    assert [finding for finding in report.blocking if finding.where == "workflow"] == []


async def test_check_slot_in_two_layers_is_refused(
    nous_root: Path, edit: Callable[[str, Callable[[Any], None]], None]
) -> None:
    edit("core/base/persona.yaml", lambda p: p["slots"].update({"origin": "twice"}))
    report = await CheckService().run(GitNous(nous_root, None))
    found = {(finding.backend, finding.kind, finding.path) for finding in report.blocking}
    assert ("core", ReportKind.INVALID, "origin") in found
    assert {("hermes", ReportKind.UNCOVERED, "origin"), ("openhuman", ReportKind.UNCOVERED, "origin")} <= found


async def test_check_unparsable_schema_stops_at_one_finding(
    nous_root: Path, edit: Callable[[str, Callable[[Any], None]], None]
) -> None:
    edit("specs/base.yaml", lambda b: b["kinds"]["Row"].update({"via": {"type": "<prose>"}}))
    report = await CheckService().run(GitNous(nous_root, None))
    assert [(finding.kind, finding.where) for finding in report.findings] == [(ReportKind.INVALID, "schema")]
    assert report.stamp.model == "?"
