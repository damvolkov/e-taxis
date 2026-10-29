"""tests/unit/e_taxis/workflow/compare: the sample repository soa-compare reads, and the typed artifacts its steps pass."""

from typing import TYPE_CHECKING, Any

import pytest

from e_taxis.workflow.models.assess import Health, Plan, Registry, Samples
from e_taxis.workflow.models.compare import Rivalry, Rivals, Subject, Vital

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Callable
    from pathlib import Path

    from pytest_resources import Resources


@pytest.fixture
def project(resources: Resources) -> Path:
    """A repository declaring Python, Rust, JS and container dependencies, with lockfiles and sources importing them."""
    return resources.path / "compare" / "project"


@pytest.fixture
def rivals() -> Rivals:
    """msgspec against orjson and pydantic-core; wreq against nothing."""
    pypi = Registry.PYPI
    return Rivals(
        incumbents=(
            Rivalry(
                incumbent=Subject(name="msgspec", repo="msgspec/msgspec", package="msgspec", registry=pypi),
                role="serialization",
                rivals=(
                    Subject(name="orjson", repo="ijl/orjson", package="orjson", registry=pypi),
                    Subject(name="pydantic-core", repo="pydantic/pydantic-core"),
                ),
            ),
            Rivalry(incumbent=Subject(name="wreq"), role="http", rivals=()),
        )
    )


@pytest.fixture
def vital() -> Callable[..., Vital]:
    def build(name: str, *, rust: bool = False, stars: int | None = None, **kpis: Any) -> Vital:
        health = Health(measured_at="2026-10-29T00:00:00+00:00", **kpis)
        return Vital(name=name, health=health, rust=rust, basis=(), stars=stars)

    return build


class SkippingBench:
    """AssessBench's shape: every plan answered with nothing measured, the skip flag recorded."""

    def __init__(self) -> None:
        self.skips: list[bool] = []

    async def run(self, plan: Plan, *, skip: bool, now: dt.datetime) -> Samples:
        self.skips.append(skip)
        return Samples(arms=(), warmup=plan.warmup, reason="bench=false: judged on desk evidence")


@pytest.fixture
def skipping() -> SkippingBench:
    return SkippingBench()
