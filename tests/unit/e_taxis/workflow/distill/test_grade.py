"""tests/unit/e_taxis/workflow/distill/grade: candidates merged, contradictions propagated, each one weighed.

Defect 3: a candidate that contradicts the core only reached the places its miner named. The real case — awa replaced
by PgQueuer, named in sys-gen-scaling and arch-py-events — left `test-py-tdd/references/lib.md:12` stating awa. Grade
now greps the replaced term across the harness scope and adds every place that still states it."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.distill.grade import DistillGrade
from e_taxis.workflow.distill.matrix import VersionMatrix
from e_taxis.workflow.models.distill import (
    BlueprintArea,
    BlueprintTarget,
    Change,
    CodeEvidence,
    HarnessFacet,
    HarnessKind,
    HarnessPart,
    HarnessTarget,
    Reach,
    Relation,
)
from e_taxis.workflow.models.entity import Entity
from e_taxis.workflow.models.error import DistillError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.models.distill import Candidate

SCALING = HarnessTarget(entity=Entity.SKILL, id="sys-gen-scaling", part=HarnessPart.LIB)
EVENTS = HarnessTarget(entity=Entity.SKILL, id="arch-py-events", part=HarnessPart.INSTRUCTIONS)


@pytest.fixture
def blueprint(tmp_path: Path) -> Path:
    root = tmp_path / "e-arkhetypo"
    (root / "projects" / "python" / "api").mkdir(parents=True)
    return root


async def test_grade_propagates_a_contradiction_to_every_place_that_states_it(
    harness: Path, blueprint: Path, grader_for: Callable[..., DistillGrade], candidate: Callable[..., Candidate]
) -> None:
    grader = grader_for(harness, blueprint)
    awa = candidate("c1", SCALING, EVENTS, relation=Relation.CONTRADICTS, replaces=("awa",))
    (amended,), spread = await grader.propagate((awa,))
    (grade,) = await grader.grade((amended,), spread=spread)
    added = set(amended.targets) - {SCALING, EVENTS}
    assert added == {
        HarnessTarget(entity=Entity.SKILL, id="test-py-tdd", part=HarnessPart.LIB),
        HarnessTarget(kind=HarnessKind.SPEC, name="tekton/legacy.yaml"),
        HarnessTarget(kind=HarnessKind.STACK),
        HarnessTarget(
            facet=HarnessFacet.TEKTON, entity=Entity.CONFIG, id="config", part=HarnessPart.MODULE, name="queue"
        ),
    }
    assert (
        CodeEvidence(path="core/tekton/skills/test-py-tdd/references/lib.md", lines=(12, 12), symbol="awa")
        in amended.evidence
    )
    assert (
        CodeEvidence(path="core/tekton/skills/test-py-tdd/evals/case.md", lines=(1, 1), symbol="awa")
        in amended.evidence
    )
    assert not any(
        "conc-py-async" in getattr(e, "path", "") or "docs/" in getattr(e, "path", "") for e in amended.evidence
    )
    assert "core/tekton/skills/test-py-tdd/references/lib.md" in grade.propagated
    assert (grade.stop, grade.reach) == ((), Reach.SEVERAL)


async def test_grade_contradiction_of_nothing_stops(
    harness: Path, blueprint: Path, grader_for: Callable[..., DistillGrade], candidate: Callable[..., Candidate]
) -> None:
    grader = grader_for(harness, blueprint)
    ghost = candidate("c1", SCALING, relation=Relation.CONTRADICTS, replaces=("celery", "awa"))
    bare = candidate("c2", SCALING, relation=Relation.CONTRADICTS)
    amended, spread = await grader.propagate((ghost, bare))
    by = {g.candidate: g for g in await grader.grade(amended, spread=spread)}
    assert any("`celery` appears nowhere in core, specs/tekton" in stop for stop in by["c1"].stop)
    assert by["c2"].stop == ("a contradiction names the term it replaces in `replaces`",)


async def test_grade_unreadable_harness_is_a_distill_error(
    nous: Path, blueprint: Path, grader_for: Callable[..., DistillGrade], candidate: Callable[..., Candidate]
) -> None:
    with pytest.raises(DistillError, match="cannot grep"):
        await grader_for(nous, blueprint).propagate(
            (candidate("c1", SCALING, relation=Relation.CONTRADICTS, replaces=("awa",)),)
        )


async def test_grade_weighs_against_the_matrix_and_the_trees(
    harness: Path,
    blueprint: Path,
    grader_for: Callable[..., DistillGrade],
    candidate: Callable[..., Candidate],
    skill_ref,
) -> None:
    grades = await grader_for(harness, blueprint).grade(
        (
            candidate("c1", skill_ref),
            candidate("c2", BlueprintTarget(area=BlueprintArea.PROJECT, unit="api", layer="src")),
            candidate("c3", HarnessTarget(entity=Entity.SKILL, id="ghost-skill", part=HarnessPart.INSTRUCTIONS)),
            candidate(
                "c4",
                HarnessTarget(entity=Entity.SKILL, id="algo-py-core", part=HarnessPart.INSTRUCTIONS),
                change=Change.CREATE,
            ),
            candidate("c5", HarnessTarget(id="x")),
            candidate(
                "c6",
                BlueprintTarget(area=BlueprintArea.PROJECT, unit="api", path="projects/python/api/deploy.py"),
                change=Change.CREATE,
            ),
            candidate(
                "c7",
                HarnessTarget(
                    entity=Entity.SKILL, id="algo-py-core", part=HarnessPart.REFERENCE, name="references/algorithms.md"
                ),
            ),
            candidate("c8", HarnessTarget(kind=HarnessKind.STACK)),
            candidate("c9", HarnessTarget(kind=HarnessKind.MATRIX)),
            candidate("d1", HarnessTarget(entity=Entity.PERSONA, id="persona", part=HarnessPart.SLOT, name="voice")),
            candidate("d2", HarnessTarget(entity=Entity.CONFIG, id="config", part=HarnessPart.MODULE, name="main")),
            candidate("d3", BlueprintTarget(area=BlueprintArea.TOOLS, unit="x", new=True)),
            candidate("bad id/../x", skill_ref),
        )
    )
    by = {g.candidate: g for g in grades}
    assert (by["c1"].matrix, by["c1"].stop, by["c1"].reach) == ("deepening", (), Reach.ONE)
    assert (by["c2"].stop, by["c2"].matrix) == ((), "")
    assert any("does not exist" in s for s in by["c3"].stop)
    assert any("already exists" in s for s in by["c4"].stop)
    assert by["c4"].matrix == "surface"
    assert any("needs `entity`" in s for s in by["c5"].stop)
    assert (by["c6"].stop, by["c7"].stop) == ((), ())
    assert by["c8"].stop == ()
    assert by["c9"].stop == ("core/versioning/matrix.yaml does not exist",)
    assert (by["d1"].matrix, by["d1"].stop) == ("guidance", ())
    assert by["d2"].stop == ()
    assert by["d3"].stop == ()
    assert any("not one safe word" in s for s in by["bad id/../x"].stop)


async def test_grade_stops_a_slot_the_matrix_does_not_judge(
    harness: Path, blueprint: Path, command, layout, candidate: Callable[..., Candidate], skill_ref
) -> None:
    table = {
        "grades": [{"name": "a", "level": 0, "bump": "patch", "description": "d"}],
        "lifecycle": {},
        "slots": {"skill": {}},
    }
    grader = DistillGrade(
        command, VersionMatrix(table), harness=harness, blueprint=blueprint, layout=layout, scope=("core",)
    )
    (grade,) = await grader.grade((candidate("c1", skill_ref),))
    assert grade.stop == ("the matrix does not judge skill:references/x.md: no row of matrix.yaml judges this slot",)


async def test_grade_stops_what_is_past_the_cap(
    harness: Path,
    blueprint: Path,
    grader_for: Callable[..., DistillGrade],
    candidate: Callable[..., Candidate],
    skill_ref,
) -> None:
    grades = await grader_for(harness, blueprint).grade(
        (candidate("c1", skill_ref), candidate("c2", skill_ref)), frozenset({"c2"})
    )
    assert [g.stop for g in grades] == [(), ("past its miner's cap",)]


async def test_grade_merge_folds_by_targets_and_keeps_the_miners_ids(
    candidate: Callable[..., Candidate], skill_ref
) -> None:
    merged = DistillGrade.merge(
        (candidate("x", skill_ref, facts=("f1",), replaces=("a",)),),
        (
            candidate("y", skill_ref, facts=("f2",), replaces=("a", "b")),
            candidate("z", BlueprintTarget(area=BlueprintArea.INFRA, unit="jobs")),
        ),
    )
    assert [c.id for c in merged] == ["x", "z"]
    assert merged[0].sketch == "(x) sketch x\n\n(y) sketch y"
    assert (merged[0].facts, merged[0].replaces) == (("f1", "f2"), ("a", "b"))


async def test_grade_merge_suffixes_a_clash(candidate: Callable[..., Candidate], skill_ref) -> None:
    merged = DistillGrade.merge(
        (candidate("c1", skill_ref),), (candidate("c1", BlueprintTarget(area=BlueprintArea.INFRA, unit="jobs")),)
    )
    assert [c.id for c in merged] == ["c1-1", "c1-2"]


async def test_grade_recent_ignores_a_pure_move(
    tmp_path: Path,
    harness: Path,
    grader_for: Callable[..., DistillGrade],
    candidate: Callable[..., Candidate],
    git,
    tree,
    commit,
) -> None:
    templates = tmp_path / "e-arkhetypo"
    await git(tmp_path, "init", "-q", "-b", "main", str(templates))
    tree(templates, {"projects/python/api/a.py": "x = 1\n" * 20})
    await commit(templates, "feat: add a")
    await git(templates, "mv", "projects/python/api/a.py", "projects/python/api/b.py")
    await commit(templates, "refactor: move a to b")
    moved = candidate("t1", BlueprintTarget(area=BlueprintArea.PROJECT, unit="api", path="projects/python/api/b.py"))
    assert (await grader_for(harness, templates).grade((moved,)))[0].duplicate_of == ""
    tree(templates, {"projects/python/api/b.py": "x = 2\n"})
    await commit(templates, "fix: b")
    assert (await grader_for(harness, templates).grade((moved,)))[0].duplicate_of.endswith("fix: b")
    await git(templates, "switch", "-q", "--detach", "HEAD~2")
    assert (await grader_for(harness, templates, "main").grade((moved,)))[0].stop == ()
    assert (await grader_for(harness, templates).grade((moved,)))[0].stop == (
        "projects/python/api/b.py does not exist",
    )
