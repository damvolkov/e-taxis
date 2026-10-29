"""tests/unit/e_taxis/schedule: a units dir per test, a scripted runner in place of systemctl, an e-nous copy to declare in.

Nothing here reaches the real user manager: every argv the adapter runs lands on `ScriptedRunner`, which answers from
`replies` (by argv prefix) and fails what `failing` names; TAXIS_SCHEDULE_UNITS points at the test's own folder."""

import shutil
import sys
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

import pytest

from e_taxis.harness.models.error import RunnerError
from e_taxis.harness.models.ports import RunnerPort
from e_taxis.harness.runtime.deps import Deps
from e_taxis.schedule.adapters.systemd import UserSystemd
from e_taxis.schedule.services.schedule import ScheduleService
from e_taxis.transpile.adapters.nous import GitNous

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_resources import Resources

BINARY = Path("/opt/taxis/bin/taxis")


class ScriptedRunner:
    """RunnerPort that runs nothing: the reply of the longest matching prefix in `replies` (else ""); a prefix in
    `failing` raises."""

    def __init__(self) -> None:
        self.replies: dict[tuple[str, ...], str] = {}
        self.failing: set[tuple[str, ...]] = set()

    async def run(self, argv: tuple[str, ...]) -> str:
        match [prefix for prefix in self.failing if argv[: len(prefix)] == prefix]:
            case []:
                hits = [prefix for prefix in self.replies if argv[: len(prefix)] == prefix]
                return self.replies[max(hits, key=len)] if hits else ""
            case _:
                msg = f"`{' '.join(argv)}` exited 1"
                raise RunnerError(msg)


@pytest.fixture
def scripted(sandbox: None, monkeypatch: pytest.MonkeyPatch) -> ScriptedRunner:
    """The scripted runner, also what every `taxis` run of the test builds as its RunnerPort."""
    runner = ScriptedRunner()

    async def provide(deps: Deps) -> ScriptedRunner:
        return runner

    monkeypatch.setattr(Deps, "PROVIDERS", MappingProxyType({**Deps.PROVIDERS, RunnerPort: provide}))
    return runner


@pytest.fixture
def units(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The test's own units dir, named to every `taxis` run by TAXIS_SCHEDULE_UNITS; created by the first write."""
    folder = tmp_path / "units"
    monkeypatch.setenv("TAXIS_SCHEDULE_UNITS", str(folder))
    return folder


@pytest.fixture
def binary(monkeypatch: pytest.MonkeyPatch) -> Path:
    """The running entrypoint every `taxis` run of the test sees: a fixed absolute path."""
    monkeypatch.setattr(sys, "argv", [str(BINARY)])
    return BINARY


@pytest.fixture
def schedule_nous(resources: Resources, tmp_path: Path) -> Path:
    """A copy of the transpile slice: a valid e-nous checkout declaring `eval-corpus`."""
    root = tmp_path / "nous"
    shutil.copytree(resources.path / "transpile", root)
    return root


@pytest.fixture
def declare(schedule_nous: Path) -> Callable[[str | None], GitNous]:
    """Replace the copy's schedules.yaml with `text` (None: no such module); the checkout read as it stands."""
    path = schedule_nous / "core/tekton/config/schedules.yaml"

    def write(text: str | None) -> GitNous:
        _ = path.unlink() if text is None else path.write_text(text)
        return GitNous(schedule_nous, None)

    return write


@pytest.fixture
def golden(resources: Resources) -> dict[str, bytes]:
    """The rendered pair of `eval-spec` over /srv/e-nous and /opt/taxis/bin/taxis, by file name."""
    return {path.name: path.read_bytes() for path in sorted((resources.path / "schedule").iterdir())}


@pytest.fixture
def systemd(scripted: ScriptedRunner, units: Path) -> UserSystemd:
    return UserSystemd(scripted, units)


@pytest.fixture
def service(systemd: UserSystemd) -> ScheduleService:
    return ScheduleService(systemd, BINARY)
