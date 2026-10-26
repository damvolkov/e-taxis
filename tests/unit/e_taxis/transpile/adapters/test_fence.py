"""tests/unit/e_taxis/transpile/adapters/fence: the landrun argv, a fenced run's outcome, the timeout kill, the canary."""

import asyncio
from pathlib import Path

import pytest

from e_taxis.transpile.adapters.fence import LandrunFence
from e_taxis.transpile.models.trial import TrialRun

ENV = {"PATH": "/usr/bin:/bin"}


async def test_fence_wrap_reads_all_writes_named_connects_named() -> None:
    argv = LandrunFence(Path("/bin/landrun")).wrap(["claude", "-p"], writable=[Path("/sb")], ports=[45], env={"A": "1"})
    assert argv[:5] == ["/bin/landrun", "--best-effort", "--ignore-missing", "--rox", "/"]
    assert argv[argv.index("--") :] == ["--", "/usr/bin/env", "-i", "A=1", "claude", "-p"]
    assert tuple(argv[5:7]) == ("--rw", "/sb")
    assert "--connect-tcp" in argv
    assert argv[argv.index("--connect-tcp") + 1] == "45"


async def test_fence_run_keeps_code_and_output(landrun: Path, tmp_path: Path) -> None:
    run = await LandrunFence(landrun).run(
        ["sh", "-c", "echo out; echo err >&2; exit 3"], env=ENV, cwd=tmp_path, writable=[tmp_path], ports=[], limit=10
    )
    assert (run.code, run.stdout, run.stderr) == (3, "out\n", "err\n")


async def test_fence_run_kills_at_its_timeout(landrun: Path, tmp_path: Path) -> None:
    run = await LandrunFence(landrun).run(["sleep", "5"], env=ENV, cwd=tmp_path, writable=[], ports=[], limit=0.3)
    assert run.code is None
    assert run.seconds < 4


async def test_fence_kill_of_a_finished_process_is_quiet(tmp_path: Path) -> None:
    process = await asyncio.create_subprocess_exec("true", start_new_session=True)
    await process.wait()
    LandrunFence._run_kill(process)
    assert process.returncode == 0


@pytest.mark.parametrize(
    ("inside", "outside", "held"), [(0, 1, True), (0, 0, False), (1, 1, False)], ids=["holds", "leaks", "broken"]
)
async def test_fence_canary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, inside: int, outside: int, held: bool
) -> None:
    """Only a write that lands inside and is refused outside proves the fence."""
    codes = iter((inside, outside))

    async def fake_run(self, argv, *, env, cwd, writable, ports, limit) -> TrialRun:
        code = next(codes)
        target = argv[-1].split("> '")[1].rstrip("'")
        if code == 0:
            Path(target).write_text("")
        return TrialRun(argv=tuple(argv), code=code, seconds=0.0)

    monkeypatch.setattr(LandrunFence, "run", fake_run)
    outside_path = tmp_path / "outside"
    assert await LandrunFence(Path("/x")).canary(tmp_path / "in", outside_path) is held
    assert not outside_path.exists()
