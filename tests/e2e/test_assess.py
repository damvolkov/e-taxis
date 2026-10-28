"""tests/e2e/assess: the bench behind the real landrun — an arm writes its own sandbox, never outside it, and the
network stays open for its installs."""

import datetime as dt
from pathlib import Path

import pytest

from e_taxis.transpile.adapters.fence import LandrunFence
from e_taxis.workflow.assess.bench import AssessBench
from e_taxis.workflow.models.assess import Arm, Cache, Overlap, Plan, Role

pytestmark = pytest.mark.slow

LANDRUN = Path("~/.local/bin/landrun").expanduser()
### an install needs the network: a TCP connection out of the fence must open.
NET = "python3 -c \"import socket; socket.create_connection(('pypi.org', 443), 10).close()\""


async def test_assess_bench_is_fenced_for_real(tmp_path: Path) -> None:
    match LANDRUN.is_file():
        case False:
            pytest.skip("landrun is not installed")
        case _:
            pass
    outside = tmp_path / "outside"
    escape = f"! touch {outside} 2>/dev/null"
    plan = Plan(
        incumbent="none",
        overlap=Overlap.COMPLEMENTS,
        hypothesis="the fence holds",
        metric="seconds",
        threshold=0.0,
        higher_is_better=False,
        cases=("a",),
        n=2,
        cache=Cache.WARM,
        arms=(
            Arm(
                name="cand", role=Role.CANDIDATE, install=("touch $HOME/inside", escape), run=("test -f $HOME/inside",)
            ),
            Arm(name="none", role=Role.EMPTY, install=(NET,), run=("python3 -c 'import socket'",)),
        ),
        landing="none",
        warmup=0,
    )
    found = await AssessBench(LandrunFence(LANDRUN), path="/usr/bin:/bin", limit=60, temp=tmp_path).run(
        plan, skip=False, now=dt.datetime.now(dt.UTC)
    )
    cand, empty = found.arms
    assert (cand.installed, cand.error, empty.installed, empty.error) == (True, "", True, "")
    assert not outside.exists()
    assert all(sample.metric is not None for sample in (*cand.samples, *empty.samples))
