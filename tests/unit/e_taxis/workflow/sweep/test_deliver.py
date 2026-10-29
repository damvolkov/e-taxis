"""tests/unit/e_taxis/workflow/sweep/deliver: the summary to a Discord webhook read from a file, report.md attached."""

import json
from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.models.error import SweepError
from e_taxis.workflow.models.sweep import FindingStatus, Frame, Report, VoiceRow, VoiceStatus
from e_taxis.workflow.sweep.deliver import SweepDeliver

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from e_taxis.workflow.models.sweep import Finding

HOOK = "https://discord.com/api/webhooks/1/x"
FRAME = Frame(brief="b", topic="", keywords=(), since="2026-10-26", until="2026-10-28", voices=())


@pytest.fixture
def report(finding: Callable[..., Finding]) -> Report:
    return Report(
        path="/r/report.md",
        voices=(
            VoiceRow(id="ada", status=VoiceStatus.OK, parsed=3, in_window=2, new=1, findings=1),
            VoiceRow(id="down", status=VoiceStatus.ERROR, error="404"),
        ),
        findings=(finding("Spanline", relevance=5, status=FindingStatus.NEW), finding("B", relevance=2)),
        assess=("taxis workflow run soa-assess tech=https://github.com/spanline/spanline",),
    )


@pytest.mark.parametrize("where", ["absolute", "relative"])
async def test_deliver_posts_the_summary_and_the_report(web, tmp_path: Path, report: Report, where: str) -> None:
    (tmp_path / "hook").write_text(f"{HOOK}\n")
    named = str(tmp_path / "hook") if where == "absolute" else "hook"
    said = await SweepDeliver(web).deliver(webhook=named, base=tmp_path, frame=FRAME, report=report, markdown="# R\n")
    ((url, fields, files),) = web.posted
    payload = json.loads(fields["payload_json"])
    assert url == HOOK
    assert payload["content"] == said
    assert payload["attachments"] == [{"id": 0, "filename": "report.md"}]
    assert files == {"files[0]": ("report.md", b"# R\n")}
    assert said.splitlines() == [
        "**soa-sweep** · the whole plane · 2026-10-26 → 2026-10-28",
        "ok **ada** — 3 parsed · 2 in window · 1 new · 1 findings",
        "error **down** — 404",
        "2 findings · 1 to assess",
        "- Spanline (5/5, new)",
        "- B (2/5, unfit)",
        "Full report attached.",
    ]


@pytest.mark.parametrize(
    ("webhook", "text", "said"),
    [("", None, "names no webhook file"), ("hook", None, "no webhook file at"), ("hook", "  \n", "is empty")],
    ids=["unset", "missing", "empty"],
)
async def test_deliver_refuses(web, tmp_path: Path, report: Report, webhook: str, text: str | None, said: str) -> None:
    _ = text is not None and (tmp_path / "hook").write_text(text)
    with pytest.raises(SweepError, match=said):
        await SweepDeliver(web).deliver(webhook=webhook, base=tmp_path, frame=FRAME, report=report, markdown="")
