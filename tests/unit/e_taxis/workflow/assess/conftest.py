"""tests/unit/e_taxis/workflow/assess: hand-written API answers for the shapes no recording has, a lab whose fence
leaks, and typed builders for a plan and its samples. The recorded API and the lab live one level up (the commands
use them too)."""

import base64
import datetime as dt
from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.workflow.models.assess import (
    ArmSamples,
    Candidate,
    Registry,
    Role,
    Sample,
    Samples,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


##### DEFAULTS #####
MISSING = b'{"message": "Not Found"}'


##### FAKES #####
##### FIXTURES #####
@pytest.fixture
def rtk() -> Candidate:
    return Candidate(tech="https://github.com/rtk-ai/rtk", name="rtk", repo="rtk-ai/rtk")


@pytest.fixture
def msgspec_candidate() -> Candidate:
    return Candidate(tech="msgspec", name="msgspec", repo="msgspec/msgspec", package="msgspec", registry=Registry.PYPI)


@pytest.fixture
def samples() -> Callable[..., Samples]:
    """Samples of `fast` and `slow` from per-arm metric lists, one case `a`, repetitions in order."""

    def build(fast: Sequence[float | None], slow: Sequence[float | None], **extra: Any) -> Samples:
        def side(name: str, role: Role, values: Sequence[float | None]) -> ArmSamples:
            runs = tuple(Sample(case="a", rep=rep, at=rep, metric=value) for rep, value in enumerate(values))
            return ArmSamples(name=name, role=role, installed=True, samples=runs)

        arms = (side("fast", Role.CANDIDATE, fast), side("slow", Role.INCUMBENT, slow))
        return Samples(arms=arms, warmup=0, **extra)

    return build


@pytest.fixture
def encoded() -> Callable[[str], dict[str, str]]:
    """A file as GitHub's contents API answers it."""

    def build(text: str) -> dict[str, str]:
        return {"content": base64.b64encode(text.encode()).decode(), "encoding": "base64"}

    return build


@pytest.fixture
def releases(now: dt.datetime) -> Callable[..., list[dict[str, Any]]]:
    """`count` GitHub releases, one every `every` days back from `now`, the first `pre` of them pre-releases."""

    def build(count: int, every: float = 1.0, pre: int = 0, start: int = 0) -> list[dict[str, Any]]:
        stamps = [(now - dt.timedelta(days=every * (start + k))).isoformat() for k in range(count)]
        return [
            {"created_at": stamp, "published_at": stamp, "prerelease": k < pre, "draft": False}
            for k, stamp in enumerate(stamps)
        ]

    return build
