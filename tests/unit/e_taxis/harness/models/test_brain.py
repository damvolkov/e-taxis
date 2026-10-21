"""tests/unit/e_taxis/models/brain: a document keeps every live section it does not declare; a plan counts its moves."""

from e_taxis.harness.models.brain import BrainAction, BrainFile, BrainMove, BrainPlan
from e_taxis.harness.models.catalog import Target

DOC = BrainFile(path="CLAUDE.md", data=b"# T\n\n## Owned\n\nnew", headings=("Owned",))


def test_brain_file_plain_lands_as_rendered() -> None:
    plain = BrainFile(path="a.md", data=b"new")
    assert (plain.merged(None), plain.merged(b"old")) == (b"new", b"new")


def test_brain_document_without_live_lands_as_rendered() -> None:
    assert DOC.merged(None) == DOC.data


def test_brain_document_carries_live_sections_it_does_not_declare() -> None:
    live = b"# T\n\n## Owned\n\nold\n\n## Mine \n\nkept body\n\n## Empty\n"
    assert DOC.merged(live) == b"# T\n\n## Owned\n\nnew\n\n## Mine\n\nkept body\n\n## Empty"


def test_brain_plan_pending_and_count() -> None:
    moves = tuple(BrainMove(path=action, action=action) for action in BrainAction)
    plan = BrainPlan(target=Target.CLAUDECODE, tree="/t", moves=(*moves, BrainMove(path="x", action=BrainAction.ADD)))
    assert [move.action for move in plan.pending] == [
        BrainAction.ADD,
        BrainAction.UPDATE,
        BrainAction.OVERWRITE,
        BrainAction.ADD,
    ]
    assert (plan.count(BrainAction.ADD), plan.count(BrainAction.ORPHAN)) == (2, 1)
