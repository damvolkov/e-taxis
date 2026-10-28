"""tests/unit/e_taxis/transpile/services/trial: a phantom over a fake fence — evidence derived from the render, refusals named."""

from typing import TYPE_CHECKING, Any

import msgspec
import pytest

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.models.error import TranspileError
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.run import RunService
from e_taxis.transpile.services.trial import TrialService

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

CC = "specs/tekton/claudecode.yaml"


@pytest.fixture
def trial(fence) -> TrialService:
    return TrialService(RunService(CheckService()), fence, path="/usr/bin")


async def test_trial_holds_when_the_harness_sent_everything(
    trial: TrialService, fence, capture, nous_root: Path, hooked
) -> None:
    tree = await GitNous(nous_root, None).load()
    slots = {**tree.persona["base"]["slots"], **tree.persona["tekton"]["slots"]}
    ids = [ident for entity in ("skill", "agent") for ident in tree.entities[entity]]
    fence.body = msgspec.json.encode({"system": [*slots.values(), *ids]})
    fence.printer = hooked("claudecode", ".claude")
    report = await trial.run(GitNous(nous_root, None), "claudecode", capture)
    assert report.held
    assert report.captured == 2
    expected = {sight.entity: sight.expected for sight in report.sights}
    assert (expected["agent"], expected["hooks"]) == (1, 8)
    assert capture.replies == [None, {"tool": "Bash", "input": {"command": "true", "description": "ghost"}}, None]
    assert fence.envs[0]["ANTHROPIC_BASE_URL"] == capture.url
    assert fence.envs[0]["CLAUDE_CONFIG_DIR"].endswith("/home/.claude")
    assert capture.served == 1


async def test_trial_names_what_the_harness_did_not_show(trial: TrialService, fence, capture, nous_root: Path) -> None:
    fence.body = b'[1, null, "not the ids"]'
    report = await trial.run(GitNous(nous_root, None), "claudecode", capture)
    sights = {sight.entity: sight for sight in report.sights}
    assert not report.held
    assert "builder" in sights["agent"].missing
    assert any(command.endswith("hooks/plans.mjs") for command in sights["hooks"].missing)


async def test_trial_hooks_hold_only_what_the_trace_shows(
    trial: TrialService, fence, capture, nous_root: Path, hooked
) -> None:
    printer = hooked("claudecode", ".claude")
    fence.printer = lambda argv: "\n".join(line for line in printer(argv).splitlines() if "tool_after" not in line)
    report = await trial.run(GitNous(nous_root, None), "claudecode", capture)
    assert next(sight for sight in report.sights if sight.entity == "hooks").missing == ("sh -c 'exit 0' tool_after",)


async def test_trial_command_probe_reads_stdout(
    trial: TrialService, fence, capture, nous_root: Path, hooked, edit: Callable[[str, Callable[[Any], None]], None]
) -> None:
    def unlinger(spec: Any) -> None:
        _ = [probe.pop("linger", None) for probe in spec["trial"]["probes"]]

    edit("specs/tekton/opencode.yaml", unlinger)
    printer = hooked("opencode", ".config/opencode")
    stdout = msgspec.json.encode({"agent": {"builder": {}}, "command": {"ship": {}}}).decode()
    fence.printer = lambda argv: printer(argv) if argv[0] == "cat" else stdout
    ### OpenCode 2.x probes are served: each one's `ready` answers, then the probe runs.
    fence.codes = [0] * 9
    report = await trial.run(GitNous(nous_root, None), "opencode", capture)
    sights = {sight.entity: sight for sight in report.sights}
    assert sights["agent"].held
    assert sights["command"].held
    assert (sights["hooks"].held, sights["hooks"].expected) == (True, 5)
    assert '"builder": {"enabled": false}' not in fence.envs[0]["OPENCODE_CONFIG_CONTENT"]
    assert '"exa": {"enabled": false}' in fence.envs[0]["OPENCODE_CONFIG_CONTENT"]


async def test_trial_refuses_when_the_fence_does_not_hold(trial: TrialService, fence, capture, nous_root: Path) -> None:
    fence.holds = False
    with pytest.raises(TranspileError, match="fence does not hold"):
        await trial.run(GitNous(nous_root, None), "claudecode", capture)
    assert fence.argvs == []


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (lambda s: s.pop("trial"), "no trial"),
        (lambda s: s["trial"]["env"].update({"X": "${ghost}"}), "placeholder"),
    ],
    ids=["no-trial", "placeholder"],
)
async def test_trial_refusals(
    trial: TrialService,
    capture,
    nous_root: Path,
    edit: Callable[[str, Callable[[Any], None]], None],
    change: Callable[[Any], None],
    match: str,
) -> None:
    edit(CC, change)
    with pytest.raises(TranspileError, match=match):
        await trial.run(GitNous(nous_root, None), "claudecode", capture)
