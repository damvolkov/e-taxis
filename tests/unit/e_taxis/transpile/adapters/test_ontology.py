"""tests/unit/e_taxis/transpile/adapters/ontology: a workflow manifest made whole — kwargs named, family nodes used."""

from typing import Any

import pytest

from e_taxis.transpile.adapters.ontology import WorkflowOntology
from e_taxis.transpile.models.error import NousError

CONFIG: dict[str, Any] = {
    "kwargs": {"bench": {"type": "bool", "default": "true", "doc": "measure"}, "topic": {"type": "topic", "doc": "t"}},
    "families": {
        "radar": {
            "kwargs": ["topic"],
            "output": {"type": "report", "path": "<rundir>/radar/{name}.json"},
            "nodes": {"stats": {"run": "taxis workflow {{workflow}} stats", "instruction": "interval"}},
        }
    },
}


@pytest.mark.parametrize(
    ("parameters", "expected"),
    [
        (["bench"], {"bench": {"type": "bool", "default": "true", "doc": "measure"}}),
        ({"bench": "measure it"}, {"bench": {"type": "bool", "default": "true", "doc": "measure it"}}),
        ({"bench": {"default": "false"}}, {"bench": {"type": "bool", "default": "false", "doc": "measure"}}),
        ({"local": {"doc": "mine"}}, {"local": {"doc": "mine"}}),
        (None, {}),
    ],
    ids=["named", "doc", "refined", "local", "none"],
)
async def test_ontology_kwargs(parameters: Any, expected: dict[str, Any]) -> None:
    manifest = {"id": "w", "nodes": [], "parameters": parameters}
    whole = WorkflowOntology(CONFIG).expand("w", manifest)["parameters"]
    assert {name: entry for name, entry in whole.items() if name != "query"} == expected
    assert "a small model reads" in whole["query"]["doc"]


async def test_ontology_family_joins_kwargs_output_and_nodes() -> None:
    manifest = {
        "id": "w",
        "family": "radar",
        "parameters": ["bench"],
        "nodes": [{"use": "stats", "depends": ["a"]}, {"use": "stats", "id": "again"}, {"id": "a", "run": "x"}],
    }
    whole = WorkflowOntology(CONFIG).expand("w", manifest)
    assert list(whole["parameters"]) == ["topic", "bench", "query"]
    assert whole["output"] == {"type": "report", "path": "<rundir>/radar/w.json"}
    assert whole["nodes"] == [
        {"run": "taxis workflow {{workflow}} stats", "instruction": "interval", "id": "stats", "depends": ["a"]},
        {"run": "taxis workflow {{workflow}} stats", "instruction": "interval", "id": "again"},
        {"id": "a", "run": "x"},
    ]


@pytest.mark.parametrize(
    ("manifest", "problem"),
    [
        ({"parameters": ["ghost"]}, "kwarg 'ghost' is in no vocabulary"),
        ({"family": "ghost"}, "family 'ghost' is not in the workflows config"),
        ({"family": "radar", "nodes": [{"use": "ghost"}]}, "uses 'ghost', which its family does not define"),
    ],
    ids=["kwarg", "family", "use"],
)
async def test_ontology_refuses(manifest: dict[str, Any], problem: str) -> None:
    with pytest.raises(NousError, match=problem):
        WorkflowOntology(CONFIG).expand("w", {"id": "w", **manifest})
