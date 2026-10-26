"""tests/unit/e_taxis/workflow/distill/store: artifacts as models — written, read back, refused when they misfit."""

from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.workflow.distill.store import DistillStore
from e_taxis.workflow.models.distill import Candidate, Judgement, Verdict
from e_taxis.workflow.models.error import DistillError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


async def test_store_round_trips_an_artifact(rundir: Path, candidate: Callable[..., Candidate], skill_ref) -> None:
    store = DistillStore(rundir)
    await store.put("candidates", (candidate("c1", skill_ref),))
    assert (await store.get("candidates", tuple[Candidate, ...]))[0].id == "c1"
    assert store.rundir == rundir


async def test_store_reads_an_agent_answer(rundir: Path, answer: Callable[[str, Any], None]) -> None:
    answer("worth", [{"candidate": "c1", "verdict": "must", "generality": 0.8, "rationale": "r"}])
    assert (await DistillStore(rundir).agent("worth", tuple[Judgement, ...]))[0].verdict is Verdict.MUST


async def test_store_reads_a_bare_answer(rundir: Path) -> None:
    out = rundir / "nodes" / "worth" / "out.md"
    out.parent.mkdir(parents=True)
    out.write_text('[{"candidate": "c1", "verdict": "case", "generality": 0.1, "rationale": "r"}]\n')
    assert (await DistillStore(rundir).agent("worth", tuple[Judgement, ...]))[0].verdict is Verdict.CASE


@pytest.mark.parametrize(
    ("value", "match"), [(None, "left no answer"), ([{"candidate": "c1"}], "does not fit")], ids=["missing", "misfit"]
)
async def test_store_agent_refuses(rundir: Path, answer: Callable[[str, Any], None], value: Any, match: str) -> None:
    _ = value is not None and answer("worth", value)
    with pytest.raises(DistillError, match=match):
        await DistillStore(rundir).agent("worth", tuple[Judgement, ...])


async def test_store_get_refuses_a_missing_or_misfit_artifact(rundir: Path) -> None:
    store = DistillStore(rundir)
    with pytest.raises(DistillError, match="its step has not run"):
        await store.get("scope", Candidate)
    await store.put("scope", {"id": 1})
    with pytest.raises(DistillError, match="does not fit its model"):
        await store.get("scope", Candidate)
