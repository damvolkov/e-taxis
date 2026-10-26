"""tests/unit/e_taxis/workflow/adapters/command: argv in, stdout out — a failure says its code, a timeout kills."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.models.error import CommandError

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.adapters.command import ShellCommand


async def test_command_returns_stdout_in_cwd_with_env(command: ShellCommand, tmp_path: Path) -> None:
    said = await command.run("sh", "-c", 'printf "%s %s" "$PWD" "$X"', limit=10.0, cwd=tmp_path, env={"X": "y"})
    assert said == f"{tmp_path} y"


async def test_command_large_stdout_is_not_truncated(command: ShellCommand) -> None:
    said = await command.run("sh", "-c", "head -c 300000 /dev/zero | tr '\\0' x", limit=10.0)
    assert len(said) == 300_000


async def test_command_failure_carries_code_and_stdout(command: ShellCommand) -> None:
    with pytest.raises(CommandError, match="sh exited 3: why") as failed:
        await command.run("sh", "-c", "echo out; echo why >&2; exit 3", limit=10.0)
    assert (failed.value.code, failed.value.stdout) == (3, "out\n")


async def test_command_echo_relays_stderr(command: ShellCommand, capfd: pytest.CaptureFixture[str]) -> None:
    await command.run("sh", "-c", "echo live >&2", limit=10.0, echo="  > ")
    assert capfd.readouterr().err == "  > live\n"


async def test_command_timeout_kills(command: ShellCommand) -> None:
    with pytest.raises(CommandError, match=r"timeout after 0\.2s") as failed:
        await command.run("sleep", "5", limit=0.2)
    assert failed.value.code is None


async def test_command_missing_binary_cannot_start(command: ShellCommand) -> None:
    with pytest.raises(CommandError, match="cannot start"):
        await command.run("no-such-binary-anywhere", limit=1.0)
