"""tests/unit/e_taxis/adapters/runner: real, harmless argv — output on exit 0, a RunnerError otherwise."""

import asyncio

import pytest

from e_taxis.adapters.ports import RunnerPort
from e_taxis.adapters.runner import ProcessRunner
from e_taxis.models.error import RunnerError


async def test_runner_satisfies_the_port() -> None:
    assert isinstance(ProcessRunner(), RunnerPort)


async def test_runner_run_returns_the_output() -> None:
    assert await ProcessRunner().run(("sh", "-c", "echo out; echo err >&2")) == "out\nerr\n"


@pytest.mark.parametrize(
    ("argv", "match"),
    [
        (("sh", "-c", "echo why; exit 3"), r"`sh -c 'echo why; exit 3'` exited 3: why"),
        (("false",), r"`false` exited 1$"),
        (("e-taxis-no-such-binary",), r"cannot start"),
    ],
    ids=["exit-with-output", "exit-silent", "missing"],
)
async def test_runner_run_failure(argv: tuple[str, ...], match: str) -> None:
    with pytest.raises(RunnerError, match=match):
        await ProcessRunner().run(argv)


async def test_runner_run_cancelled_kills_the_child() -> None:
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.1):
            await ProcessRunner().run(("sleep", "5"))
