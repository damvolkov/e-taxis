"""tests/unit/e_taxis/workflow/sweep/frame: radar.yaml and a run's extras fixed into the sweep's frame."""

import datetime as dt
from typing import TYPE_CHECKING

import pytest

from e_taxis.workflow.models.error import SweepError
from e_taxis.workflow.models.sweep import VoiceKind
from e_taxis.workflow.sweep.frame import SweepFrame

if TYPE_CHECKING:
    from pathlib import Path

TODAY = dt.date(2026, 10, 28)


async def test_frame_topic_narrows_keywords_voices_and_links(radar_nous: Path) -> None:
    frame = (await SweepFrame.load(radar_nous)).fix(topic="observability", today=TODAY)
    assert (frame.brief, frame.topic) == ("Agentic systems, watched.", "observability")
    assert frame.keywords == ("agent tracing", "OpenTelemetry")
    assert (frame.since, frame.until) == ("2026-10-26", "2026-10-28")
    assert [voice.id for voice in frame.voices] == ["ada"]
    assert frame.links == ("https://opentelemetry.io/docs/specs/semconv/gen-ai/", "https://example.org/agents")


async def test_frame_empty_topic_is_the_whole_plane(radar_nous: Path) -> None:
    frame = (await SweepFrame.load(radar_nous)).fix(today=TODAY)
    assert frame.keywords == ("agent memory", "knowledge graph", "agent tracing", "OpenTelemetry")
    assert [voice.id for voice in frame.voices] == ["ada", "blog"]
    assert len(frame.links) == 2


async def test_frame_extras_join_for_the_run(radar_nous: Path) -> None:
    extras = "https://www.linkedin.com/in/bo/ https://news.example/atom.xml https://site.example/x https://www.linkedin.com/in/adavoice"
    frame = (await SweepFrame.load(radar_nous)).fix(
        topic="memory", window="7", authors=extras, links="https://l.example https://l.example", today=TODAY
    )
    assert frame.since == "2026-10-21"
    assert [(voice.id, voice.kind) for voice in frame.voices] == [
        ("ada", VoiceKind.LINKEDIN_PROFILE),
        ("blog", VoiceKind.ATOM_FEED),
        ("www.linkedin.com/in/bo", VoiceKind.LINKEDIN_PROFILE),
        ("news.example/atom.xml", VoiceKind.ATOM_FEED),
        ("site.example/x", VoiceKind.WEB),
    ]
    assert frame.voices[-1].topics == ("memory",)
    assert frame.links == ("https://example.org/agents", "https://l.example")


@pytest.mark.parametrize(
    ("kwargs", "said"),
    [
        ({"topic": "cooking"}, "unknown topic 'cooking'"),
        ({"window": "two"}, "window 'two'"),
        ({"window": "-1"}, "window '-1'"),
    ],
    ids=["topic", "word", "negative"],
)
async def test_frame_refuses(radar_nous: Path, kwargs: dict[str, str], said: str) -> None:
    with pytest.raises(SweepError, match=said):
        (await SweepFrame.load(radar_nous)).fix(today=TODAY, **kwargs)


@pytest.mark.parametrize(
    ("text", "said"),
    [(None, "no radar.yaml"), ("brief: x\n", "radar.yaml does not fit"), ("a: [", "radar.yaml does not fit")],
    ids=["missing", "shape", "yaml"],
)
async def test_frame_load_refuses(tmp_path: Path, text: str | None, said: str) -> None:
    config = tmp_path / "core" / "tekton" / "config"
    config.mkdir(parents=True)
    _ = text and (config / "radar.yaml").write_text(text)
    with pytest.raises(SweepError, match=said):
        await SweepFrame.load(tmp_path)


async def test_frame_load_keeps_the_config(radar_nous: Path) -> None:
    assert (await SweepFrame.load(radar_nous)).config.discord.webhook == ""
