"""assess.bench: every arm of the plan installed fresh in its own fenced sandbox, then measured, interleaved.

**The sandbox.** One temp root per bench; under it, per arm, a throwaway HOME (XDG dirs inside it), a work dir and a
TMPDIR. Every process runs through the lab (Landlock): read and execute everywhere, write only inside its arm's
sandbox, the network open — installs need it. The environment is set whole: the sandbox's paths, `PATH` with the
sandbox's `~/.local/bin` first, `CASE` while measuring; nothing else is inherited. The canary proves the fence holds
before anything runs: one that does not hold refuses the bench.

**The runs.** An arm's `install` lines run as one `set -e` script; a failure is the arm's result (installed false,
the error kept), never a crash. Then the rounds: for every repetition and case, each installed arm once, in an order
drawn from the plan's seed — interleaved, so drift cancels instead of biasing; the first `warmup` repetitions of every
case are run and discarded. A run's `run` lines are one `set -e` script with `CASE` set; its last stdout line is a
JSON number or {"metric": n, …secondary}. When the plan's metric is `seconds`, taxis measures the wall time itself
(around the fenced process, so the fence's start-up is in every arm alike) and the line, when it is an object, gives
only the secondaries. A run that fails is kept, its metric null and its error said."""

import os
import platform
import random
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, Final

import anyio
import msgspec

from e_taxis.workflow.models.assess import (
    SECONDS,
    Arm,
    ArmSamples,
    Machine,
    Overlap,
    Plan,
    Sample,
    Samples,
)
from e_taxis.workflow.models.error import AssessError

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Mapping, Sequence

    from e_taxis.transpile.models.trial import TrialRun
    from e_taxis.workflow.models.ports import LabPort

##### DEFAULTS #####
PREFIX: str = "e-taxis-bench-"
SHELL: Final[tuple[str, ...]] = ("bash", "-c")
STRICT: str = "set -e\n"
TAIL: int = 400
CPUINFO: str = "/proc/cpuinfo"
XDG: Final[Mapping[str, str]] = {
    "XDG_CACHE_HOME": ".cache",
    "XDG_CONFIG_HOME": ".config",
    "XDG_DATA_HOME": ".local/share",
    "XDG_STATE_HOME": ".local/state",
}

type Reading = tuple[float | None, dict[str, float], str]


##### TYPES #####
class AssessBench:
    """Runs a plan through the lab (LabPort); `path` is the PATH every sandbox starts from, `limit` bounds each process
    (seconds), `temp` is where the sandboxes' root is made (None: the system's temp dir)."""

    __slots__ = ("_lab", "_limit", "_path", "_temp")

    def __init__(self, lab: LabPort, *, path: str, limit: float, temp: Path | None = None) -> None:
        self._lab = lab
        self._path = path
        self._limit = limit
        self._temp = temp

    ##### PRIVATE METHODS #####

    def _run_env(self, sandbox: Path, case: str = "") -> dict[str, str]:
        home = sandbox / "home"
        return {
            "HOME": str(home),
            "PATH": os.pathsep.join((str(home / ".local" / "bin"), self._path)),
            "TMPDIR": str(sandbox / "tmp"),
            "LANG": "C.UTF-8",
            **{name: str(home / leaf) for name, leaf in XDG.items()},
            **({"CASE": case} if case else {}),
        }

    async def _run_script(self, sandbox: Path, lines: Sequence[str], case: str = "") -> TrialRun:
        return await self._lab.run(
            [*SHELL, STRICT + "\n".join(lines)],
            env=self._run_env(sandbox, case),
            cwd=sandbox / "work",
            writable=[sandbox],
            ports=[],
            limit=self._limit,
            network=True,
        )

    @staticmethod
    def _run_failure(run: TrialRun, limit: float) -> str:
        """Why a run did not end clean, from its exit and its stderr's tail; empty when it did."""
        match run.code:
            case 0:
                return ""
            case None:
                return f"timed out after {limit:g}s"
            case code:
                return f"exit {code}: {run.stderr[-TAIL:].strip()}"

    @staticmethod
    def _run_reading(stdout: str) -> Reading:
        """(metric, secondaries, error) off the last stdout line: a JSON number, or {"metric": n, …}."""
        line = next((text for text in reversed(stdout.splitlines()) if text.strip()), "")
        try:
            value: Any = msgspec.json.decode(line)
        except msgspec.DecodeError:
            return None, {}, f"the last stdout line is not JSON: {line[:80]!r}"
        match value:
            case bool():
                return None, {}, f"the last stdout line is not a number: {line[:80]!r}"
            case int() | float():
                return float(value), {}, ""
            case {"metric": bool()}:
                return None, {}, f"the metric is not a number: {line[:80]!r}"
            case {"metric": int() | float() as metric, **rest}:
                numbers = {key: float(v) for key, v in rest.items() if type(v) in {int, float}}
                return float(metric), numbers, ""
            case _:
                return None, {}, f"the last stdout line is no metric: {line[:80]!r}"

    async def _run_install(self, root: Path, arm: Arm) -> ArmSamples:
        sandbox = root / arm.name
        _ = [await anyio.Path(sandbox / leaf).mkdir(parents=True) for leaf in ("home", "work", "tmp")]
        run = await self._run_script(sandbox, arm.install) if arm.install else None
        error = self._run_failure(run, self._limit) if run else ""
        return ArmSamples(name=arm.name, role=arm.role, installed=not error, error=error, version=arm.version)

    async def _run_measure(self, root: Path, plan: Plan, slot: tuple[int, int], arm: Arm, case: str) -> Sample:
        """One run of `arm` on `case`; `slot` is (repetition, position in the whole schedule)."""
        rep, at = slot
        started = time.perf_counter()
        run = await self._run_script(root / arm.name, arm.run, case)
        wall = time.perf_counter() - started
        failure = self._run_failure(run, self._limit)
        metric, secondary, unread = self._run_reading(run.stdout)
        timed = plan.metric == SECONDS
        match (failure, timed):
            case ("", True):
                return Sample(case=case, rep=rep, at=at, metric=round(wall, 6), secondary=secondary)
            case ("", False):
                return Sample(case=case, rep=rep, at=at, metric=metric, secondary=secondary, error=unread)
            case _:
                return Sample(case=case, rep=rep, at=at, error=failure)

    @staticmethod
    def _run_rounds(plan: Plan, arms: Sequence[Arm]) -> list[tuple[int, str, Arm]]:
        """(repetition, case, arm) in run order: every round is each arm once, in an order the seed fixes."""
        rng = random.Random(plan.seed)  # noqa: S311 — a reproducible order, not a secret
        rounds = [(rep, case) for rep in range(plan.warmup + plan.n) for case in plan.cases]
        return [(rep, case, arm) for rep, case in rounds for arm in rng.sample(list(arms), k=len(arms))]

    @staticmethod
    async def _run_machine() -> Machine:
        info = await anyio.Path(CPUINFO).read_text() if await anyio.Path(CPUINFO).is_file() else ""
        model = next((line.split(":", 1)[1].strip() for line in info.splitlines() if line.startswith("model name")), "")
        return Machine(
            cpu=model or platform.processor() or platform.machine(),
            cores=os.cpu_count() or 0,
            ram=os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
            load=round(os.getloadavg()[0], 2),
            kernel=platform.platform(),
        )

    async def _run_fenced(self, plan: Plan, now: dt.datetime) -> Samples:
        with TemporaryDirectory(prefix=PREFIX, dir=self._temp) as tmp:
            root = Path(tmp)
            match await self._lab.canary(root / "canary" / "in", root.with_name(f"{root.name}-outside")):
                case False:
                    msg = "the bench's fence does not hold: refusing to install anything unfenced"
                    raise AssessError(msg)
                case _:
                    machine = await self._run_machine()
            installed = [await self._run_install(root, arm) for arm in plan.arms]
            live = [arm for arm, result in zip(plan.arms, installed, strict=True) if result.installed]
            schedule = self._run_rounds(plan, live)
            measured = [
                (arm.name, rep, await self._run_measure(root, plan, (rep, at), arm, case))
                for at, (rep, case, arm) in enumerate(schedule)
            ]
        kept = [(name, sample) for name, rep, sample in measured if rep >= plan.warmup]
        return Samples(
            arms=tuple(
                msgspec.structs.replace(result, samples=tuple(s for name, s in kept if name == result.name))
                for result in installed
            ),
            warmup=plan.warmup,
            machine=machine,
            seed=plan.seed,
            measured_at=now.isoformat(),
        )

    ############################################################

    ##### PUBLIC #####

    async def run(self, plan: Plan, *, skip: bool, now: dt.datetime) -> Samples:
        """The plan measured, or — `skip` (bench=false) or an overlap of none — nothing installed and why."""
        match (skip, plan.overlap):
            case (True, _):
                return Samples(
                    arms=(), warmup=plan.warmup, seed=plan.seed, reason="bench=false: judged on desk evidence"
                )
            case (_, Overlap.NONE):
                return Samples(
                    arms=(), warmup=plan.warmup, seed=plan.seed, reason="overlap none: nothing to weigh it against"
                )
            case _ if not plan.arms:
                return Samples(arms=(), warmup=plan.warmup, seed=plan.seed, reason="the plan has no arms: desk only")
            case _:
                return await self._run_fenced(plan, now)
