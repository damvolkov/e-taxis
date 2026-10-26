"""tests/unit/e_taxis/workflow/engine/bind: a parameter is data, never code — whatever it holds, wherever it sits.

Defect 4 of the legacy step: `{{param}}` was spliced into `bash -lc` as text, so a value with a quote broke the step
and one with `$(…)` ran. Each case runs the bound command in a real bash and asserts it printed the value itself
and touched nothing."""

from typing import TYPE_CHECKING

import anyio
import pytest

from e_taxis.workflow.engine.bind import ParamBind

if TYPE_CHECKING:
    from pathlib import Path

HOSTILE = [
    'say "hi"',
    "it's",
    "$(touch {canary})",
    "`touch {canary}`",
    "line one\nline two",
    "a\\ b $HOME ${PATH} 'q' \"d\" ; touch {canary} #",
    "",
]
PLACES = {
    "bare": "printf '%s' {{v}}",
    "double": "printf '%s' \"{{v}}\"",
    "single": "printf '%s' '{{v}}'",
    "inline": "printf '%s' \"<{{v}}>\"",
}


@pytest.mark.parametrize(
    "value", HOSTILE, ids=["dquote", "squote", "subshell", "backtick", "newline", "mixed", "empty"]
)
@pytest.mark.parametrize("place", sorted(PLACES))
async def test_bind_shell_value_arrives_as_itself(tmp_path: Path, value: str, place: str) -> None:
    canary = tmp_path / "pwned"
    given = value.replace("{canary}", str(canary))
    command, env = ParamBind.shell(PLACES[place], {"v": given})
    done = await anyio.run_process(["bash", "-c", command], env={"PATH": "/usr/bin:/bin", **env})
    expected = f"<{given}>" if place == "inline" else given
    assert done.stdout.decode() == expected
    assert not canary.exists()


async def test_bind_shell_reads_only_the_named_parameters() -> None:
    command, env = ParamBind.shell("run {{a}} {{ghost}} '{{a}}'", {"a": "1", "b": "2"})
    assert env == {"TAXIS_PARAM_a": "1"}
    assert command == "run \"${TAXIS_PARAM_a}\" {{ghost}} ''\"${TAXIS_PARAM_a}\"''"


async def test_bind_text_substitutes_as_is() -> None:
    assert ParamBind.text("read {{rundir}}/x and {{ghost}}", {"rundir": "/r $(x)"}) == "read /r $(x)/x and {{ghost}}"


@pytest.mark.parametrize(
    ("when", "due"),
    [({}, True), ({"apply": ("true",)}, True), ({"apply": ("false",)}, False), ({"op": ("a", "b")}, False)],
    ids=["none", "match", "miss", "absent"],
)
async def test_bind_due(when: dict[str, tuple[str, ...]], due: bool) -> None:
    assert ParamBind.due(when, {"apply": "true"}) is due
