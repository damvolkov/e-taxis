"""tests/unit/e_taxis/workflow/assess: hand-written API answers for the shapes no recording has, a lab whose fence
leaks, and typed builders for a plan and its samples. The recorded API and the lab live one level up (the commands
use them too)."""

import base64
import datetime as dt
from typing import TYPE_CHECKING, Any

import msgspec
import pytest

from e_taxis.workflow.models.assess import (
    Arm,
    ArmSamples,
    Cache,
    Candidate,
    Fetched,
    Overlap,
    Plan,
    Registry,
    Role,
    Sample,
    Samples,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence


##### DEFAULTS #####
MISSING = b'{"message": "Not Found"}'


##### FAKES #####
class StubApi:
    """ApiPort answering hand-written bodies by URL, 404 otherwise: the shapes no recorded answer has."""

    def __init__(self, answers: Mapping[str, Any]) -> None:
        self._answers = dict(answers)

    async def get(self, url: str) -> Fetched:
        match self._answers.get(url):
            case None:
                return Fetched(url=url, status=404, body=MISSING)
            case (int() as status, body):
                return Fetched(url=url, status=status, body=msgspec.json.encode(body))
            case body:
                return Fetched(url=url, status=200, body=msgspec.json.encode(body))


##### FIXTURES #####
@pytest.fixture
def stub() -> Callable[[Mapping[str, Any]], StubApi]:
    return StubApi


@pytest.fixture
def rtk() -> Candidate:
    return Candidate(tech="https://github.com/rtk-ai/rtk", name="rtk", repo="rtk-ai/rtk")


@pytest.fixture
def msgspec_candidate() -> Candidate:
    return Candidate(tech="msgspec", name="msgspec", repo="msgspec/msgspec", package="msgspec", registry=Registry.PYPI)


@pytest.fixture
def arm() -> Callable[..., Arm]:
    def build(name: str, role: Role, run: Sequence[str] = ("echo 1",), install: Sequence[str] = ()) -> Arm:
        return Arm(name=name, role=role, install=tuple(install), run=tuple(run))

    return build


@pytest.fixture
def plan(arm: Callable[..., Arm]) -> Callable[..., Plan]:
    """A plan of two arms (`fast` the candidate, `slow` the incumbent) over the given knobs."""

    def build(*arms: Arm, **knobs: Any) -> Plan:
        frame: dict[str, Any] = {
            "incumbent": "slow",
            "overlap": Overlap.REPLACES,
            "hypothesis": "fast is faster",
            "metric": "ms",
            "threshold": 0.5,
            "higher_is_better": False,
            "cases": ("a",),
            "n": 3,
            "cache": Cache.WARM,
            "arms": arms or (arm("fast", Role.CANDIDATE), arm("slow", Role.INCUMBENT)),
            "landing": "lib.md row",
            "warmup": 0,
        }
        return Plan(**(frame | knobs))

    return build


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
