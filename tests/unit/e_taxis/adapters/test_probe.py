"""tests/unit/e_taxis/adapters/probe: real, harmless shell commands — exit code decides, the first line is the version."""

import pytest

from e_taxis.adapters.probe import ShellProbe
from e_taxis.harness.models.plan import Probe
from e_taxis.harness.models.ports import ProbePort


def test_probe_satisfies_the_port() -> None:
    assert isinstance(ShellProbe(timeout=1), ProbePort)


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("echo 1.2.3", Probe(present=True, version="1.2.3", detail="exit 0 · 1.2.3")),
        ("true", Probe(present=True, version=None, detail="exit 0")),
        ("false", Probe(present=False, version=None, detail="exit 1")),
        ("echo oops >&2; exit 3", Probe(present=False, version="oops", detail="exit 3 · oops")),
    ],
    ids=["version", "silent", "absent", "stderr"],
)
async def test_probe_run(command: str, expected: Probe) -> None:
    assert await ShellProbe(timeout=5).run(command) == expected


async def test_probe_run_past_the_timeout_is_absent() -> None:
    probe = await ShellProbe(timeout=0.1).run("sleep 5")
    assert (probe.present, probe.detail) == (False, "timeout after 0.1s")
