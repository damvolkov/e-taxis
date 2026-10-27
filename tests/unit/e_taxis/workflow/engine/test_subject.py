"""tests/unit/e_taxis/workflow/engine/subject: a target's subjects and places in one e-nous tree, from its schema."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.models.error import PlaneError
from e_taxis.workflow.models.plane import Target

if TYPE_CHECKING:
    from e_taxis.workflow.engine.subject import NousSubject


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (Target.CORPUS, ()),
        (Target.PERSONA, ("persona",)),
        (Target.CONFIG, ("config",)),
        (Target.SPEC, ("claudecode", "hermes", "opencode", "openhuman")),
        (Target.SKILL, ("algo-py-core",)),
    ],
    ids=["corpus", "persona", "config", "spec", "skill"],
)
async def test_subject_all_declared(subjects: NousSubject, target: Target, expected: tuple[str, ...]) -> None:
    assert subjects.all(target) == expected


async def test_subject_all_named_and_unknown(subjects: NousSubject) -> None:
    assert subjects.all(Target.AGENT, ("builder", "builder")) == ("builder",)
    with pytest.raises(PlaneError, match="agent: unknown subject"):
        subjects.all(Target.AGENT, ("ghost",))


@pytest.mark.parametrize(
    ("target", "subject", "place"),
    [
        (Target.CORPUS, "", "core"),
        (Target.PERSONA, "persona", "core/tekton/persona"),
        (Target.CONFIG, "config", "core/tekton/config"),
        (Target.SPEC, "hermes", "specs/nomos/hermes.yaml"),
        (Target.COMMAND, "ship", "core/tekton/commands/ship"),
    ],
    ids=["corpus", "persona", "config", "spec", "command"],
)
async def test_subject_place(subjects: NousSubject, target: Target, subject: str, place: str) -> None:
    assert subjects.place(target, subject) == place
