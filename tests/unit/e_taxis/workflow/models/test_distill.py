"""tests/unit/e_taxis/workflow/models/distill: closed targets, the chain's unions, reach and plane from the place."""

from typing import Any

import msgspec
import pytest

from e_taxis.workflow.models.distill import (
    PARTS,
    BlueprintArea,
    BlueprintTarget,
    Candidate,
    HarnessKind,
    HarnessPart,
    HarnessTarget,
    Plane,
    Reach,
    Relation,
)
from e_taxis.workflow.models.entity import Entity


async def test_distill_every_entity_has_its_parts() -> None:
    assert set(PARTS) == set(Entity)


@pytest.mark.parametrize(
    ("target", "problem"),
    [
        (HarnessTarget(entity=Entity.SKILL, id="api-py-server", part=HarnessPart.REFERENCE, name="litestar"), ""),
        (HarnessTarget(id="x"), "needs `entity`"),
        (HarnessTarget(entity=Entity.SKILL), "needs `id`"),
        (HarnessTarget(entity=Entity.SKILL, id="s", part=HarnessPart.REFERENCE, name="s:x"), "carries an id"),
        (HarnessTarget(entity=Entity.AGENT, id="scout", part=HarnessPart.NODE, name="n"), "has no part node"),
        (HarnessTarget(entity=Entity.SKILL, id="s", part=HarnessPart.REFERENCE), "needs `name`"),
        (HarnessTarget(kind=HarnessKind.STACK), ""),
        (BlueprintTarget(area=BlueprintArea.PROJECT, unit="api", layer="src"), ""),
        (BlueprintTarget(area=BlueprintArea.PROJECT, unit="voice"), "no project voice"),
        (BlueprintTarget(area=BlueprintArea.PROJECT, unit="voice", new=True), ""),
        (BlueprintTarget(area=BlueprintArea.PROJECT, unit="core", layer="nope"), "no layer nope"),
        (BlueprintTarget(area=BlueprintArea.STACK, unit="llm/vllm"), ""),
        (BlueprintTarget(area=BlueprintArea.STACK, unit="nope/x"), "no stack category nope"),
        (BlueprintTarget(area=BlueprintArea.STACK, unit="llm"), "<category>/<service>"),
        (BlueprintTarget(area=BlueprintArea.INFRA, unit="ci"), "no infra unit ci"),
    ],
    ids=[
        "skill-ref",
        "no-entity",
        "no-id",
        "id-in-name",
        "wrong-part",
        "no-name",
        "stack",
        "project",
        "unknown-project",
        "new-project",
        "bad-layer",
        "stack-service",
        "bad-category",
        "stack-flat",
        "infra",
    ],
)
async def test_distill_target_problems(target: HarnessTarget | BlueprintTarget, problem: str) -> None:
    found = target.problems()
    assert (problem in found[0]) if problem else found == ()


@pytest.mark.parametrize(
    ("target", "plane"),
    [
        (HarnessTarget(entity=Entity.SKILL, id="a", part=HarnessPart.LIB), Plane.LIBRARY),
        (HarnessTarget(entity=Entity.SKILL, id="a"), Plane.DOCTRINE),
        (HarnessTarget(entity=Entity.PERSONA, id="persona"), Plane.DOCTRINE),
        (HarnessTarget(entity=Entity.CONFIG, id="config"), Plane.TOOLING),
        (HarnessTarget(kind=HarnessKind.STACK), Plane.TOOLING),
        (HarnessTarget(entity=Entity.AGENT, id="a"), Plane.PROCESS),
        (HarnessTarget(kind=HarnessKind.SPEC, name="x"), Plane.TOOLING),
        (BlueprintTarget(area=BlueprintArea.PROJECT, unit="core", layer="common"), Plane.COMMON),
        (BlueprintTarget(area=BlueprintArea.PROJECT, unit="core", layer="ops"), Plane.MODULE),
        (BlueprintTarget(area=BlueprintArea.PROJECT, unit="api"), Plane.PROJECT),
        (BlueprintTarget(area=BlueprintArea.STACK, unit="llm/vllm"), Plane.SERVICE),
        (BlueprintTarget(area=BlueprintArea.TOOLS, unit="x"), Plane.OPS),
    ],
)
async def test_distill_plane_follows_the_place(target: HarnessTarget | BlueprintTarget, plane: Plane) -> None:
    assert target.plane is plane


async def test_distill_blueprint_target_root() -> None:
    assert BlueprintTarget(area=BlueprintArea.STACK, unit="llm/vllm").root == "stack/llm/vllm"
    assert BlueprintTarget(area=BlueprintArea.PROJECT, unit="api").root == "projects/python/api"
    assert BlueprintTarget(area=BlueprintArea.TOOLS, unit="x").root == "tools"


@pytest.mark.parametrize(
    ("targets", "expected"),
    [
        ((HarnessTarget(entity=Entity.SKILL, id="a"),), Reach.ONE),
        ((HarnessTarget(entity=Entity.SKILL, id="a"), HarnessTarget(entity=Entity.AGENT, id="b")), Reach.SEVERAL),
        ((BlueprintTarget(area=BlueprintArea.PROJECT, unit="core", layer="ops"),), Reach.ALL_PROJECTS),
        (
            (HarnessTarget(entity=Entity.SKILL, id="a"), BlueprintTarget(area=BlueprintArea.PROJECT, unit="api")),
            Reach.CROSS,
        ),
    ],
    ids=["one", "several", "all-projects", "cross"],
)
async def test_distill_reach(targets: tuple[Any, ...], expected: Reach) -> None:
    assert Candidate(id="c", claims=(), targets=targets, relation=Relation.ADDS, sketch="s").reach is expected


@pytest.mark.parametrize(
    ("ident", "relation", "replaces", "problems"),
    [
        ("c1", Relation.IMPROVES, (), ()),
        ("c1", Relation.CONTRADICTS, ("awa",), ()),
        ("c1", Relation.CONTRADICTS, (" ",), ("a contradiction names the term it replaces in `replaces`",)),
        ("../x", Relation.ADDS, (), ("id '../x' is not one safe word (letters, digits, . _ -)",)),
    ],
    ids=["plain", "contradiction", "blank-term", "unsafe-id"],
)
async def test_distill_candidate_problems(
    ident: str, relation: Relation, replaces: tuple[str, ...], problems: tuple[str, ...]
) -> None:
    assert (
        Candidate(id=ident, claims=(), targets=(), relation=relation, sketch="s", replaces=replaces).problems()
        == problems
    )


async def test_distill_candidate_round_trips_its_unions() -> None:
    raw = {
        "id": "c1",
        "claims": ["k1"],
        "relation": "contradicts",
        "sketch": "s",
        "replaces": ["awa"],
        "targets": [
            {"type": "harness", "entity": "skill", "id": "api-py-server", "part": "instructions"},
            {"type": "blueprint", "area": "project", "unit": "api", "layer": "src"},
        ],
        "evidence": [{"type": "commit", "sha": "abc", "message": "m"}, {"type": "drift", "path": "p", "template": "t"}],
    }
    candidate = msgspec.convert(raw, Candidate)
    assert msgspec.convert(msgspec.to_builtins(candidate), Candidate) == candidate
    assert isinstance(candidate.targets[1], BlueprintTarget)


async def test_distill_candidate_refuses_an_unknown_field() -> None:
    raw = {"id": "c1", "claims": [], "targets": [], "relation": "improves", "sketch": "s", "change": "update"}
    with pytest.raises(msgspec.ValidationError, match="change"):
        msgspec.convert(raw, Candidate)
