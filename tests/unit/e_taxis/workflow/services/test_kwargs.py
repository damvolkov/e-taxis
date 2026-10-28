"""tests/unit/e_taxis/workflow/services/kwargs: kwargs read out of `query` — only the unsaid ones, by the first tier that
answers, the schema closed where the type is, what the caller gave always winning."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.models.error import WorkflowError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.unit.e_taxis.workflow.conftest import FakeChat

    from e_taxis.workflow.models.workflow import Workflow
    from e_taxis.workflow.services.kwargs import WorkflowKwargs

PARAMS = {
    "tech": {"type": "list", "doc": "the technologies"},
    "bench": {"type": "bool", "default": "true", "doc": "measure"},
    "topic": {"type": "topic", "doc": "a topic"},
    "deliver": {"values": ["report", "discord"], "doc": "where"},
    "note": {"doc": "free"},
    "query": {"doc": "the request"},
}


@pytest.mark.parametrize(
    "given",
    [{"tech": "x"}, {"tech": "x", "bench": "true", "topic": "", "deliver": "", "note": "", "query": "q"}],
    ids=["no-query", "nothing-unsaid"],
)
async def test_kwargs_without_need_asks_nothing(
    kwargs_reader: WorkflowKwargs, chat: FakeChat, declare: Callable[..., Workflow], tmp_path: Path, given: dict
) -> None:
    decl = declare([{"id": "a", "run": "true"}], parameters=PARAMS)
    assert await kwargs_reader.fill(decl, given, tmp_path, ("memory",)) == (given, "", 0)
    assert chat.asked == []


async def test_kwargs_fill_reads_the_unsaid_and_keeps_the_given(
    kwargs_reader: WorkflowKwargs, chat: FakeChat, declare: Callable[..., Workflow], tmp_path: Path
) -> None:
    chat.down = {"local"}
    chat.answers["scout"] = {"tech": ["a", "b"], "bench": "false", "topic": "", "deliver": "discord", "note": ""}
    decl = declare([{"id": "a", "run": "true"}], parameters=PARAMS)
    filled, tier, tokens = await kwargs_reader.fill(
        decl, {"query": "a and b", "deliver": "report"}, tmp_path, ("memory",)
    )
    schema = chat.asked[-1][3]
    assert (filled, tier, tokens) == (
        {"tech": "a, b", "bench": "false", "query": "a and b", "deliver": "report"},
        "scout",
        7,
    )
    assert [model for model, *_ in chat.asked] == ["local", "scout"]
    assert schema["required"] == ["tech", "bench", "topic", "note"]
    assert schema["properties"] == {
        "tech": {"type": "array", "items": {"type": "string"}},
        "bench": {"type": "string", "enum": ["", "true", "false"]},
        "topic": {"type": "string", "enum": ["", "memory"]},
        "note": {"type": "string"},
    }
    assert "- tech: the technologies" in chat.asked[-1][1]


async def test_kwargs_every_tier_down_is_refused(
    kwargs_reader: WorkflowKwargs, chat: FakeChat, declare: Callable[..., Workflow], tmp_path: Path
) -> None:
    chat.down = {"local", "scout"}
    decl = declare([{"id": "a", "run": "true"}], parameters=PARAMS)
    with pytest.raises(WorkflowError, match=r"query could not be read: local: local is down; scout: scout is down"):
        await kwargs_reader.fill(decl, {"query": "q"}, tmp_path, ())


async def test_kwargs_enum_values_are_a_closed_set(
    kwargs_reader: WorkflowKwargs, chat: FakeChat, declare: Callable[..., Workflow], tmp_path: Path
) -> None:
    decl = declare([{"id": "a", "run": "true"}], parameters={"deliver": PARAMS["deliver"], "query": PARAMS["query"]})
    await kwargs_reader.fill(decl, {"query": "post it"}, tmp_path, ())
    assert chat.asked[-1][3]["properties"]["deliver"] == {"type": "string", "enum": ["", "report", "discord"]}
