"""tests/unit/e_taxis/services/apply: install and update steps in requires order — skips skipped, P3 deferred, gates
refused unless opened, fail-fast, every write recorded for undo, each applied part verified."""

import json
from typing import TYPE_CHECKING

import pytest

from e_taxis.adapters.primitives.compose import ComposePrimitive
from e_taxis.models.apply import ApplyOptions, ApplyStatus
from e_taxis.models.catalog import Primitive, Target
from e_taxis.models.error import ApplyError
from e_taxis.models.journal import JournalBlock, JournalCommand, JournalKey
from e_taxis.models.wanted import WantedPart

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.services.apply import ApplyService

ONLY = ApplyOptions(only=frozenset({"tool", "env", "guide"}))
OPEN = ApplyOptions(licences=frozenset({"gated"}), confirms=frozenset({"gated"}))


async def test_apply_plan_narrows_to_only(applier: ApplyService, profile) -> None:
    plan = await applier.plan(profile("house"), Target.CLAUDECODE, ONLY.only)
    assert [step.id for step in plan.steps] == ["tool", "env", "guide"]


async def test_apply_only_naming_no_step_is_refused(applier: ApplyService, profile) -> None:
    with pytest.raises(ApplyError, match="--only names nope"):
        await applier.plan(profile("house"), Target.CLAUDECODE, frozenset({"tool", "nope"}))


async def test_apply_run_writes_in_requires_order_and_records_every_effect(
    applier: ApplyService, profile, runner, recorder, claude_dir: Path
) -> None:
    report = await applier.run(profile("house"), Target.CLAUDECODE, ONLY)
    assert [(step.id, step.status) for step in report.steps] == [
        ("tool", ApplyStatus.APPLIED),
        ("env", ApplyStatus.APPLIED),
        ("guide", ApplyStatus.APPLIED),
    ]
    assert runner.calls == [("uv", "tool", "install", "tool==1.0")]
    assert json.loads((claude_dir / "settings.json").read_text()) == {"env": {"TOOL_ON": "1"}}
    assert "<!-- e-taxis:guide -->\nUse the tool.\n" in (claude_dir / "CLAUDE.md").read_text()
    assert [type(effect) for effect in recorder.effects] == [JournalCommand, JournalKey, JournalBlock]
    assert [(result.id, result.passed) for result in report.verify] == [("tool", True), ("env", True), ("guide", True)]
    assert report.failed == ()


async def test_apply_run_skips_defers_and_refuses_a_closed_gate_before_writing(
    applier: ApplyService, profile, runner, claude_dir: Path
) -> None:
    with pytest.raises(ApplyError, match=r"gated needs --accept-licence gated, --confirm gated, \$GATED_TOKEN set"):
        await applier.run(profile("house"), Target.CLAUDECODE, ApplyOptions())
    assert (runner.calls, claude_dir.exists()) == ([], False)


async def test_apply_run_opened_gate_installs(applier: ApplyService, profile, runner, environ) -> None:
    environ.update(GATED_TOKEN="set")
    report = await applier.run(profile("house"), Target.CLAUDECODE, OPEN)
    statuses = {step.id: step.status for step in report.steps}
    assert statuses == {
        "tool": ApplyStatus.APPLIED,
        "env": ApplyStatus.APPLIED,
        "guide": ApplyStatus.APPLIED,
        "here": ApplyStatus.SKIPPED,
        "svc": ApplyStatus.DEFERRED,
        "gated": ApplyStatus.APPLIED,
    }
    assert (
        "claude",
        "mcp",
        "add-json",
        "--scope",
        "user",
        "gated",
        '{"type":"http","url":"https://gated.invalid/mcp"}',
    ) in runner.calls


async def test_apply_run_refuses_unknown_parts(applier: ApplyService, profile) -> None:
    with pytest.raises(ApplyError, match="ghost has no catalog entry"):
        await applier.run(profile("ghosted"), Target.CLAUDECODE, ApplyOptions())


async def test_apply_run_stops_at_the_first_failure(applier: ApplyService, profile, runner, claude_dir: Path) -> None:
    runner.failing.add(("uv",))
    report = await applier.run(profile("house"), Target.CLAUDECODE, ONLY)
    assert [step.status for step in report.steps] == [ApplyStatus.FAILED, ApplyStatus.NOT_RUN, ApplyStatus.NOT_RUN]
    assert "exited 1" in report.steps[0].detail
    assert (report.failed, report.verify, claude_dir.exists()) == (("tool",), (), False)


async def test_apply_run_failure_keeps_what_earlier_steps_recorded(
    applier: ApplyService, listed, runner, recorder, environ
) -> None:
    environ.update(GATED_TOKEN="set")
    runner.failing.add(("claude",))
    source = listed(WantedPart(id="tool", source="t"), WantedPart(id="gated", source="t"))
    report = await applier.run(source, Target.CLAUDECODE, OPEN)
    assert [step.status for step in report.steps] == [ApplyStatus.APPLIED, ApplyStatus.FAILED]
    assert recorder.effects == [
        JournalCommand(argv=("uv", "tool", "install", "tool==1.0"), undo=("uv", "tool", "uninstall", "tool"))
    ]


async def test_apply_run_reports_a_failed_verify(applier: ApplyService, profile) -> None:
    report = await applier.run(profile("flaky"), Target.CLAUDECODE, ApplyOptions())
    assert ([step.status for step in report.steps], report.failed) == ([ApplyStatus.APPLIED], ("flaky",))


async def test_apply_run_update_reaches_the_primitive(applier: ApplyService, listed, runner) -> None:
    report = await applier.run(listed(WantedPart(id="here", source="t", pin="9")), Target.CLAUDECODE, ApplyOptions())
    assert (report.steps[0].status, runner.calls) == (ApplyStatus.APPLIED, [("npm", "install", "-g", "here@1")])


async def test_apply_run_without_a_recipe_for_the_target_fails(applier: ApplyService, listed) -> None:
    source = listed(WantedPart(id="split", source="t", pin="9"))
    report = await applier.run(source, Target.CLAUDECODE, ApplyOptions())
    assert (report.steps[0].status, report.steps[0].detail) == (ApplyStatus.FAILED, "no recipe for claudecode")


async def test_apply_run_a_primitive_not_supported_yet_is_deferred(applier: ApplyService, primitives, listed) -> None:
    primitives[Primitive.UV_TOOL] = ComposePrimitive()
    report = await applier.run(listed(WantedPart(id="tool", source="t")), Target.CLAUDECODE, ApplyOptions())
    assert (report.steps[0].status, report.verify) == (ApplyStatus.DEFERRED, ())


async def test_apply_run_a_filesystem_refusal_is_a_failed_step(applier: ApplyService, listed, claude_dir: Path) -> None:
    (claude_dir / "settings.json").mkdir(parents=True)
    report = await applier.run(listed(WantedPart(id="env", source="t")), Target.CLAUDECODE, ApplyOptions())
    assert [step.id for step in report.steps] == ["tool", "env"]
    assert (report.steps[1].status, "Is a directory" in report.steps[1].detail) == (ApplyStatus.FAILED, True)
