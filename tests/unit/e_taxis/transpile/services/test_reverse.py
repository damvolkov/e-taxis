"""tests/unit/e_taxis/transpile/services/reverse: after a landing, every seeded move is told apart — core, harness, both."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.models.report import ReportKind
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.land import LandService
from e_taxis.transpile.services.reverse import ReverseService
from e_taxis.transpile.services.run import RunService

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
async def landed(nous_root: Path, tmp_path: Path, runner, store, recorder) -> Path:
    """The fixture core landed for claudecode under a temp HOME; the store holds its base."""
    home = tmp_path / "h"
    await LandService(RunService(CheckService()), runner, store, recorder).apply(
        GitNous(nous_root, None), "claudecode", home
    )
    return home


async def _reverse(nous_root: Path, home: Path, store) -> dict[str, tuple[ReportKind, str]]:
    report = await ReverseService(RunService(CheckService()), store).run(GitNous(nous_root, None), "claudecode", home)
    return {finding.path: (finding.kind, finding.detail) for finding in report.findings}


async def test_reverse_settled_right_after_a_landing(nous_root: Path, landed: Path, store) -> None:
    assert await _reverse(nous_root, landed, store) == {}


async def test_reverse_tells_harness_edits_apart(nous_root: Path, landed: Path, store) -> None:
    claude = landed / ".claude/CLAUDE.md"
    text = claude.read_text()
    text = text.replace("## Honesty\n\n", "## Honesty\n\nA new first line.\n")
    text = text.replace("## Voice\n\n", "## Voice\n\n- edited\n")
    claude.write_text(text + "\n\n## Mine\n\nmine")
    settings = landed / ".claude/settings.json"
    settings.write_text(settings.read_text().replace('"xhigh"', '"low"'))
    found = await _reverse(nous_root, landed, store)
    assert found["CLAUDE.md#Honesty"] == (ReportKind.HARNESS, "the harness moved: absorbable into `honesty`")
    assert found["CLAUDE.md#Voice"][1].startswith("the harness moved: held: one block of 2 slots (voice, critique)")
    assert (
        found["CLAUDE.md#Mine"][1]
        == "the harness moved: added by the harness, no row renders it: it needs a home in the core"
    )
    assert (
        found["settings.json#effortLevel"][1]
        == "the harness moved: the target does not absorb: the next landing overwrites it"
    )


async def test_reverse_tells_core_and_both_apart(nous_root: Path, landed: Path, store) -> None:
    honesty = nous_root / "core/base/persona/logos/honesty.md"
    honesty.write_text(honesty.read_text() + "\n- A core line.\n")
    unity = nous_root / "core/base/persona/self/unity.md"
    unity.write_text(unity.read_text() + "\nCore says.\n")
    claude = landed / ".claude/CLAUDE.md"
    claude.write_text(
        claude.read_text().replace("## One mind, two materials\n\n", "## One mind, two materials\n\nHarness says.\n")
    )
    found = await _reverse(nous_root, landed, store)
    assert found["CLAUDE.md#Honesty"] == (ReportKind.DRIFT, "the core moved: `transpile run --yes` lands it")
    assert found["CLAUDE.md#One mind, two materials"] == (
        ReportKind.DRIFT,
        "both moved since the last landing: decide which wins",
    )


async def test_reverse_without_a_base_and_with_a_missing_file(nous_root: Path, tmp_path: Path, store) -> None:
    home = tmp_path / "bare"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude/CLAUDE.md").write_text("# Someone else")
    found = await _reverse(nous_root, home, store)
    assert found["CLAUDE.md#h1"] == (ReportKind.DRIFT, "no landing recorded: no base to tell who moved")
    assert found["settings.json"] == (ReportKind.MISSING, "not in the live tree")
