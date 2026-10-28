"""models.assess: soa-assess's data — one technology weighed against what we already run, measured, judged.

**The chain.** `Candidate` (intake: what the technology resolves to) → `Inventory` (what lives here in its domain) →
`Upstream` (the scout: what its own sources claim) → `Health` (dated KPIs from no-auth sources) → `Plan` (the
pre-registered benchmark: incumbent, overlap, metric, threshold, arms) → `Samples` (every fenced run, raw) → `Stats`
(the paired interval against the threshold) → `Verdict` → `Review` (the adversary) → `Report` (what stood).

**Answers.** `Upstream`, `Plan`, `Verdict` and `Review` are agent answers: they forbid unknown fields, so a block that
does not fit fails its reader's step with msgspec's message. A `Plan` names exactly one candidate arm and exactly one
baseline (the incumbent, or the empty arm when nothing does the job): the difference is measured between those two."""

from collections import Counter
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final

import msgspec

##### DEFAULTS #####
### the metric taxis measures itself: the wall time of a run, never what the run prints.
SECONDS: str = "seconds"
SUCCESS: Final[range] = range(200, 300)


##### ENUMS #####
class Registry(StrEnum):
    """Where a package is published: the downloads and the dependents are read from there."""

    PYPI = "pypi"
    NPM = "npm"
    CRATES = "crates"


class Overlap(StrEnum):
    """flow-gen-research's fit: what the candidate does to the inventory."""

    REPLACES = "replaces"
    COMPLEMENTS = "complements"
    OVERLAPS = "overlaps"
    NONE = "none"


class Cache(StrEnum):
    COLD = "cold"
    WARM = "warm"


class Role(StrEnum):
    """One side of the benchmark: the candidate, and the baseline it is weighed against."""

    CANDIDATE = "candidate"
    INCUMBENT = "incumbent"
    EMPTY = "empty"


class Outcome(StrEnum):
    BETTER = "better"
    WORSE = "worse"
    SAME = "no difference"
    UNMEASURED = "not measured"


class Ring(StrEnum):
    """The radar's rings: what a machine can act on."""

    ADOPT = "adopt"
    TRIAL = "trial"
    HOLD = "hold"
    REJECT = "reject"


class Landing(StrEnum):
    """Where the lesson lands, by the Triad."""

    NOUS = "e-nous"
    ARKHETYPO = "e-arkhetypo"
    TAXIS = "e-taxis"
    NONE = "none"


##### INTAKE #####
class Candidate(msgspec.Struct, frozen=True, kw_only=True):
    """intake: the technology resolved to what can be fetched and installed; `notes` say what was refused and why."""

    tech: str
    name: str
    repo: str = ""
    package: str = ""
    registry: Registry | None = None
    topic: str = ""
    notes: tuple[str, ...] = ()


class Row(msgspec.Struct, frozen=True, kw_only=True):
    """One thing that lives here: where it is written, its name, the job it does there."""

    where: str
    name: str
    role: str = ""


class Inventory(msgspec.Struct, frozen=True, kw_only=True):
    """inventory: what lives here today in the candidate's domain, and every past assessment."""

    rows: tuple[Row, ...]
    assessed: tuple[str, ...]


class Upstream(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """upstream: the candidate as its own sources describe it — claims, not evidence."""

    what: str
    install: tuple[str, ...]
    requires: tuple[str, ...]
    claims: tuple[str, ...]
    docs: tuple[str, ...]


class Health(msgspec.Struct, frozen=True, kw_only=True):
    """health: dated KPIs from no-auth sources. A field a source could not give is null and its source is in
    `failed`; `sources` names where every field that has a value was read."""

    measured_at: str
    last_release: str | None = None
    releases_per_year: float | None = None
    downloads_month: int | None = None
    dependents: int | None = None
    scorecard: float | None = None
    license: str | None = None
    open_issue_ratio: float | None = None
    contributors: int | None = None
    sources: dict[str, str] = {}
    failed: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


##### PLAN #####
class Arm(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """One side of the benchmark, installed fresh in its own sandbox. `run` is one script per case and repetition
    (its lines in order, `CASE` in the environment): its last stdout line is a JSON number or {"metric": n, …}."""

    name: Annotated[str, msgspec.Meta(pattern=r"^[A-Za-z0-9._-]+$")]
    role: Role
    install: tuple[str, ...]
    run: Annotated[tuple[str, ...], msgspec.Meta(min_length=1)]
    version: str = ""


class Plan(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """weigh: the incumbent, the overlap and the pre-registered benchmark. `threshold` is in the metric's own units;
    `warmup` runs per arm and case are discarded; `seed` fixes the order the arms take in every round."""

    incumbent: str
    overlap: Overlap
    hypothesis: str
    metric: str
    threshold: Annotated[float, msgspec.Meta(ge=0)]
    higher_is_better: bool
    cases: Annotated[tuple[str, ...], msgspec.Meta(min_length=1)]
    n: Annotated[int, msgspec.Meta(ge=1)]
    cache: Cache
    arms: tuple[Arm, ...]
    landing: str
    secondary: tuple[str, ...] = ()
    warmup: Annotated[int, msgspec.Meta(ge=0)] = 1
    seed: int = 0

    def __post_init__(self) -> None:
        roles = Counter(Role.EMPTY if arm.role is Role.INCUMBENT else arm.role for arm in self.arms)
        names = Counter(arm.name for arm in self.arms)
        match (roles[Role.CANDIDATE], roles[Role.EMPTY], max(names.values(), default=0)):
            case (1, 1, 1):
                return
            case (_, _, twice) if twice > 1:
                msg = f"arm names repeat: {sorted(name for name, seen in names.items() if seen > 1)}"
                raise ValueError(msg)
            case _:
                msg = "a plan runs exactly one candidate arm and one baseline (incumbent or empty)"
                raise ValueError(msg)

    @property
    def candidate(self) -> Arm:
        return next(arm for arm in self.arms if arm.role is Role.CANDIDATE)

    @property
    def baseline(self) -> Arm:
        return next(arm for arm in self.arms if arm.role is not Role.CANDIDATE)


##### BENCH #####
class Sample(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """One measured run: its repetition, its position in the whole interleaved schedule (`at`, warm-ups counted);
    `metric` null when the run failed, `error` saying how."""

    case: str
    rep: int
    at: int
    metric: float | None = None
    secondary: dict[str, float] = {}
    error: str = ""


class ArmSamples(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """One arm as it ran: installed or not (the install's failure is the arm's result), its measured runs."""

    name: str
    role: Role
    installed: bool
    samples: tuple[Sample, ...] = ()
    error: str = ""
    version: str = ""


class Machine(msgspec.Struct, frozen=True, kw_only=True):
    """Where the arms ran, read at the start: a busy machine is not comparable to an idle one."""

    cpu: str
    cores: int
    ram: int
    load: float
    kernel: str


class Samples(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """bench: raw samples per arm and case, interleaved; install failures recorded. No arm ran → `reason` says why."""

    arms: tuple[ArmSamples, ...]
    warmup: int
    machine: Machine | None = None
    seed: int = 0
    measured_at: str = ""
    reason: str = ""


##### STATS #####
class Stats(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """stats: the interval of the paired difference (candidate - baseline, in the metric's units) against the
    threshold; `secondary` describes, never decides."""

    metric: str
    outcome: Outcome
    candidate: str = ""
    baseline: str = ""
    pairs: int = 0
    mean: float | None = None
    low: float | None = None
    high: float | None = None
    threshold: float = 0.0
    higher_is_better: bool = True
    resamples: int = 0
    confidence: float = 0.0
    secondary: dict[str, str] = {}
    reason: str = ""


##### VERDICT #####
class Verdict(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """verdict: adopt, trial, hold or reject, with its evidence and its landing."""

    verdict: Ring
    evidence: tuple[str, ...]
    landing: Landing
    command: str
    target: str = ""


class Objection(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    claim: str
    refuted: bool
    evidence: str = ""


class Review(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """adversary: what tried to sink the verdict, and whether it stands; `verdict` is the reviewer's own."""

    stands: bool
    objections: tuple[Objection, ...]
    verdict: Ring


##### REPORT #####
class Report(msgspec.Struct, frozen=True, kw_only=True):
    """report: the assessment as written — `verdict` is what stood after the adversary; `proposed` the verdict
    step's own, which differs only when the review does not stand."""

    name: str
    date: str
    path: str
    verdict: Ring
    proposed: Ring
    stands: bool
    landing: Landing
    command: str
    candidate: Candidate
    incumbent: str
    overlap: Overlap
    health: Health
    stats: Stats
    evidence: tuple[str, ...] = ()
    objections: tuple[Objection, ...] = ()


class Assessed(msgspec.Struct, frozen=True, kw_only=True):
    """One row of the state's index (`assessed.json`, name → row): where soa-sweep's fit finds a past assessment."""

    verdict: Ring
    date: str
    report: str


##### TRANSPORT #####
class Fetched(msgspec.Struct, frozen=True, kw_only=True):
    """One GET as it came back: `status` 0 when it never arrived (`error` says why), `link` the pagination header."""

    url: str
    status: int
    body: bytes = b""
    link: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status in SUCCESS


##### THE PORTS #####
### Every artifact passed between soa-assess's steps, by the model name its ports declare: one JSON Schema each.
PORTS: Final[Mapping[str, object]] = MappingProxyType(
    {
        "Candidate": Candidate,
        "Inventory": Inventory,
        "Upstream": Upstream,
        "Health": Health,
        "Plan": Plan,
        "Samples": Samples,
        "Stats": Stats,
        "Verdict": Verdict,
        "Review": Review,
        "Report": Report,
    }
)
