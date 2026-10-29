"""tests/unit/e_taxis/workflow/assess/store: artifacts under radar/ as models; agent answers read back or refused."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.assess.store import AssessStore
from e_taxis.workflow.models.assess import Candidate, Review, Ring
from e_taxis.workflow.models.error import AssessError

if TYPE_CHECKING:
    from pathlib import Path


async def test_store_round_trips_an_artifact(tmp_path: Path) -> None:
    store = AssessStore(tmp_path)
    path = await store.put("candidate", Candidate(tech="t", name="n"))
    assert path == tmp_path / "radar" / "candidate.json"
    assert (await store.get("candidate", Candidate)).name == "n"
    assert store.rundir == tmp_path


@pytest.mark.parametrize(
    ("text", "verdict"),
    [
        ('Thinking\n```json\n{"stands": true, "objections": [], "verdict": "hold"}\n```\n', Ring.HOLD),
        ('{"stands": false, "objections": [], "verdict": "reject"}\n', Ring.REJECT),
    ],
    ids=["fenced", "bare"],
)
async def test_store_agent_reads_an_answer(tmp_path: Path, text: str, verdict: Ring) -> None:
    out = tmp_path / "nodes" / "adversary" / "out.md"
    out.parent.mkdir(parents=True)
    out.write_text(text)
    assert (await AssessStore(tmp_path).agent("adversary", Review)).verdict is verdict


@pytest.mark.parametrize(
    ("text", "match"),
    [(None, "left no answer"), ('{"stands": true, "extra": 1}', "does not fit Review"), ("prose only", "does not fit")],
    ids=["missing", "misfit", "not-json"],
)
async def test_store_agent_refuses(tmp_path: Path, text: str | None, match: str) -> None:
    out = tmp_path / "nodes" / "adversary" / "out.md"
    out.parent.mkdir(parents=True)
    _ = text is not None and out.write_text(text)
    with pytest.raises(AssessError, match=match):
        await AssessStore(tmp_path).agent("adversary", Review)


async def test_store_get_refuses_a_missing_or_misfit_artifact(tmp_path: Path) -> None:
    store = AssessStore(tmp_path)
    with pytest.raises(AssessError, match="its step has not run"):
        await store.get("candidate", Candidate)
    await store.put("candidate", {"tech": 1})
    with pytest.raises(AssessError, match="does not fit its model"):
        await store.get("candidate", Candidate)
