"""tests/unit/e_taxis/workflow/distill/drift: the project's own drift checks, run read-only and read back."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.distill.drift import DistillDrift

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.adapters.command import ShellCommand


@pytest.mark.parametrize(
    ("said", "expected"),
    [
        ("printf 'x drift:\\n  ops/image.py: missing\\n'", [("ops/image.py", "projects/python/infra: missing")]),
        ("echo something else", [("infra-check", "something else")]),
    ],
    ids=["issues", "verbatim"],
)
async def test_drift_reads_the_projects_own_check(
    command: ShellCommand, tmp_path: Path, said: str, expected: list[tuple[str, str]]
) -> None:
    (tmp_path / "Makefile").write_text(f"infra-check:\n\t@{said}; exit 1\n")
    found = await DistillDrift(command).check(tmp_path)
    assert found.checked
    assert [(f.path, f.template) for f in found.files] == expected


async def test_drift_clean_checks(command: ShellCommand, tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("infra-check:\n\t@true\n")
    found = await DistillDrift(command).check(tmp_path)
    assert (found.checked, found.files) == (True, ())


async def test_drift_without_checks(command: ShellCommand, tmp_path: Path) -> None:
    assert not (await DistillDrift(command).check(tmp_path)).checked
