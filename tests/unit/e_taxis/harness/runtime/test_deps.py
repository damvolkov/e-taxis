"""tests/unit/e_taxis/runtime/deps: injection by type — built on first ask, once per run, unknown types refused."""

from contextlib import AsyncExitStack

import pytest

from e_taxis.adapters.catalog import FileCatalog
from e_taxis.adapters.downloader import WreqDownloader
from e_taxis.adapters.runner import ProcessRunner
from e_taxis.harness.models.ports import CatalogPort, ProbePort, RunnerPort, UndoPort
from e_taxis.harness.models.session import Session
from e_taxis.harness.runtime.deps import Deps
from e_taxis.harness.runtime.journal import StoreJournal
from e_taxis.harness.services.apply import ApplyService
from e_taxis.harness.services.doctor import DoctorService
from e_taxis.harness.services.plan import PlanService
from e_taxis.harness.services.uninstall import UninstallService
from e_taxis.harness.services.verify import VerifyService
from e_taxis.infra.state import State
from e_taxis.ports.store import StorePort
from e_taxis.transpile.adapters.capture import HttpCapture
from e_taxis.transpile.adapters.fence import LandrunFence
from e_taxis.transpile.models.ports import CapturePort
from e_taxis.transpile.services.trial import TrialService
from e_taxis.workflow.adapters.web import WreqWeb
from e_taxis.workflow.assess.bench import AssessBench
from e_taxis.workflow.models.plane import Plane
from e_taxis.workflow.models.ports import ApiPort, CommandPort, LabPort, WebPort
from e_taxis.workflow.services.plane import PlaneRun
from e_taxis.workflow.services.promote import PlanePromote


def _state() -> State:
    return State(session=Session(command="test"))


async def test_deps_builds_each_kind_once_per_run() -> None:
    async with AsyncExitStack() as stack:
        deps = Deps(stack, _state())
        store = await deps.resolve(StorePort)
        assert store is await deps.resolve(StoreJournal)
        assert (await deps.resolve(PlanService)) is await deps.resolve(PlanService)


async def test_deps_binds_the_taxis_ports_and_services() -> None:
    async with AsyncExitStack() as stack:
        deps = Deps(stack, _state())
        assert isinstance(await deps.resolve(CatalogPort), FileCatalog)
        assert isinstance(await deps.resolve(ProbePort), ProbePort)
        assert isinstance(await deps.resolve(VerifyService), VerifyService)
        assert isinstance(await deps.resolve(DoctorService), DoctorService)


async def test_deps_injects_by_name_from_the_declared_type() -> None:
    state = _state()
    async with AsyncExitStack() as stack:
        injected = await Deps(stack, state).inject({"graph": State})
    assert injected == {"graph": state}


async def test_deps_refuses_a_type_without_provider() -> None:
    async with AsyncExitStack() as stack:
        with pytest.raises(TypeError, match="no provider for int"):
            await Deps(stack, _state()).resolve(int)


async def test_deps_binds_the_writing_side(runner) -> None:
    async with AsyncExitStack() as stack:
        deps = Deps(stack, _state())
        assert isinstance(await deps.resolve(ApplyService), ApplyService)
        assert isinstance(await deps.resolve(UninstallService), UninstallService)
        assert isinstance(await deps.resolve(UndoPort), UndoPort)
        assert await deps.resolve(RunnerPort) is runner
        assert isinstance(await deps.resolve(TrialService), TrialService)
        assert isinstance(await deps.resolve(CapturePort), HttpCapture)


async def test_deps_real_runner_and_downloader_outside_the_sandbox() -> None:
    """The sandbox fixture swaps these two rows: the real builders are asked for directly."""
    async with AsyncExitStack() as stack:
        deps = Deps(stack, _state())
        assert isinstance(await Deps._resolve_runner(deps), ProcessRunner)
        assert isinstance(await Deps._resolve_downloader(deps), WreqDownloader)


async def test_deps_binds_the_web() -> None:
    async with AsyncExitStack() as stack:
        assert isinstance(await Deps(stack, _state()).resolve(WebPort), WreqWeb)


async def test_deps_binds_the_planes() -> None:
    async with AsyncExitStack() as stack:
        deps = Deps(stack, _state())
        runner = await deps.resolve(PlaneRun)
        assert "## evaluator/skill" in runner.describe(Plane.EVALUATOR)
        assert isinstance(await deps.resolve(PlanePromote), PlanePromote)


@pytest.mark.parametrize(
    ("terminal", "headless", "expected"),
    [(True, "", "1"), (False, "", ""), (True, "1", "")],
    ids=["terminal", "pipe", "agent-session"],
)
async def test_deps_command_hands_the_human_mandate(
    monkeypatch: pytest.MonkeyPatch, terminal: bool, headless: str, expected: str
) -> None:
    monkeypatch.delenv("TAXIS_HUMAN", raising=False)
    monkeypatch.setenv("TAXIS_HEADLESS", headless or "0")
    monkeypatch.setattr("sys.stdin.isatty", lambda: terminal)
    async with AsyncExitStack() as stack:
        command = await Deps(stack, _state()).resolve(CommandPort)
        said = await command.run("sh", "-c", 'printf %s "$TAXIS_HUMAN"', limit=10.0)
    assert said == expected


@pytest.mark.parametrize(("token", "signed"), [("t0k", "Bearer t0k"), ("", None)], ids=["token", "anonymous"])
async def test_deps_binds_radar_tech(monkeypatch: pytest.MonkeyPatch, token: str, signed: str | None) -> None:
    monkeypatch.setenv("GH_TOKEN", token)
    async with AsyncExitStack() as stack:
        deps = Deps(stack, _state())
        api = await deps.resolve(ApiPort)
        assert api._get_headers("https://api.github.com/x").get("Authorization") == signed  # ty: ignore[unresolved-attribute]
        assert isinstance(await deps.resolve(LabPort), LandrunFence)
        assert isinstance(await deps.resolve(AssessBench), AssessBench)
