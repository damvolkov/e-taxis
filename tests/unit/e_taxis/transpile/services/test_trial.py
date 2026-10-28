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
    trial: TrialService, fence, capture, nous_root: Path
) -> None:
    tree = await GitNous(nous_root, None).load()
    slots = {**tree.persona["base"]["slots"], **tree.persona["tekton"]["slots"]}
    ids = [ident for entity in ("skill", "agent") for ident in tree.entities[entity]]
    fence.body = msgspec.json.encode({"system": [*slots.values(), *ids]})
    report = await trial.run(GitNous(nous_root, None), "claudecode", capture)
    assert report.held
    assert report.captured == 1
    assert {sight.entity: sight.expected for sight in report.sights}["agent"] == 1
    assert fence.envs[0]["ANTHROPIC_BASE_URL"] == capture.url
    assert fence.envs[0]["CLAUDE_CONFIG_DIR"].endswith("/home/.claude")
    assert capture.served == 1


async def test_trial_names_what_the_harness_did_not_show(trial: TrialService, fence, capture, nous_root: Path) -> None:
    fence.body = b'[1, null, "not the ids"]'
    report = await trial.run(GitNous(nous_root, None), "claudecode", capture)
    assert not report.held
    assert "builder" in next(sight for sight in report.sights if sight.entity == "agent").missing


async def test_trial_command_probe_reads_stdout(trial: TrialService, fence, capture, nous_root: Path) -> None:
    fence.stdout = msgspec.json.encode({"agent": {"builder": {}}, "command": {"ship": {}}}).decode()
    ### OpenCode 2.x probes are served: each one's `ready` answers, then the probe runs.
    fence.codes = [0] * 6
    report = await trial.run(GitNous(nous_root, None), "opencode", capture)
    sights = {sight.entity: sight for sight in report.sights}
    assert sights["agent"].held
    assert sights["command"].held
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
