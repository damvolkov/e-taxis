"""tests/unit/e_taxis/transpile/services/trial_nomos: overlays bend the render, setup runs, a served probe waits for ready."""

from typing import TYPE_CHECKING

import anyio
import yaml

from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.services import trial as module
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.run import RunService
from e_taxis.transpile.services.trial import TrialService, bind_trial, port_trial, swap_trial, values_trial

if TYPE_CHECKING:
    import pytest


async def test_trial_nomos_utilities() -> None:
    config = {"providers": {"a": {"endpoint": "http://a"}, "b": {"endpoint": "http://b", "x": 1}}}
    assert values_trial(config, ["providers", "*", "endpoint"]) == ["http://a", "http://b"]
    assert values_trial(config, ["providers", "z"]) == []
    assert values_trial(config, ["providers", "a"]) == []
    assert swap_trial({"k": ["http://a", 2], "n": "http://a"}, {"http://a": "X"}) == {"k": ["X", 2], "n": "X"}
    assert bind_trial({"u": ["${llm}/v1", 3]}, {"llm": "L"}) == {"u": ["L/v1", 3]}
    assert 0 < port_trial() < 65536


async def test_trial_nomos_hermes_overlay_swaps_every_endpoint(
    nous_root, fence, capture, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict] = []

    async def spy(self, tree, spec, overlay, bindings) -> None:
        await original(self, tree, spec, overlay, bindings)
        seen.append(yaml.safe_load(await anyio.Path(self._run_bind(overlay["path"], bindings)).read_text()))

    original = TrialService._run_overlay
    monkeypatch.setattr(TrialService, "_run_overlay", spy)
    report = await TrialService(RunService(CheckService()), fence, path="/usr/bin").run(
        GitNous(nous_root, None), "hermes", capture
    )
    endpoints = {provider["base_url"] for provider in seen[0]["providers"].values()}
    assert endpoints == {f"{capture.url}/v1"}
    assert report.backend == "hermes"


async def test_trial_nomos_openhuman_setup_overlay_and_served_probe(
    nous_root, fence, capture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "POLL", 0.0)
    fence.codes = [0, 1, 1, 0]
    report = await TrialService(RunService(CheckService()), fence, path="/usr/bin").run(
        GitNous(nous_root, None), "openhuman", capture
    )
    assert fence.argvs[0][:3] == ("openhuman", "core", "auth")
    assert fence.served == [("openhuman", "core", "run", "--headless-api", "--port", fence.served[0][-1])]
    assert [run.argv[0] for run in report.runs] == ["openhuman", "curl"]
    assert report.captured >= 1


async def test_trial_nomos_waits_end_at_their_limits(fence, capture, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(module, "POLL", 0.0)
    prover = TrialService(RunService(CheckService()), fence, path="/usr/bin")
    fence.codes = [1, 1, 1]
    await prover._run_ready(["x"], env={}, root=tmp_path, home=tmp_path, ports=[1], left=0.0)
    assert len(fence.argvs) == 1
    capture.clear()
    monkeypatch.setattr(module, "POLL", 0.01)
    await prover._run_settle(capture, 0.03)
    assert capture.bodies() == ()
    capture.received.append(b"x")
    await prover._run_settle(capture, 5.0)
    assert capture.bodies()[-1] == b"x"
