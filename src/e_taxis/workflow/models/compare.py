"""models.compare: soa-compare's data — what a repository runs, against what could replace it, measured, judged.

**The chain.** `Stack` (intake: every declared dependency, its version, its manifest, where it is imported) →
`Rivals` (the agent: the incumbents the query names, at most three rivals each) → `Healths` (assess's `Health` per
subject, plus whether its hot path is Rust or C) → `Shortlist` (one rubric; per incumbent the best rival that beats
it) → `Plans` (the agent: one assess `Plan` per pair, with its migration) → `PairSamples` → `PairStats` → `Verdicts`
→ `Reviews` (the adversary) → `Report` (what stood, per incumbent).

**Pairs.** A compare pair *is* an assess plan: `Plan`, `Samples`, `Stats` and `Health` are soa-assess's own, reused
as they are; each port here is a list of them keyed by the pair (`incumbent`, `rival`) — the names the rivals'
answer gave, the join key of every step after it.

**Answers.** `Rivals`, `Plans`, `Verdicts` and `Reviews` are agent answers: they forbid unknown fields, so a block
that does not fit fails its reader's step with msgspec's message."""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final

import msgspec

from e_taxis.workflow.models.assess import Health, Objection, Plan, Registry, Samples, Stats

##### DEFAULTS #####
RIVALS: int = 3


##### ENUMS #####
class Ecosystem(StrEnum):
    """Where a dependency is declared: its manifest's world."""

    PYTHON = "python"
    RUST = "rust"
    JS = "js"
    CONTAINER = "container"


class Decision(StrEnum):
    """replace.md's verdicts, per incumbent."""

    REPLACE = "replace"
    TRIAL = "trial"
    KEEP = "keep"


class Destination(StrEnum):
    """Where the lesson lands, by the Triad — or the repository alone."""

    NOUS = "e-nous"
    ARKHETYPO = "e-arkhetypo"
    TAXIS = "e-taxis"
    PROJECT = "project"
    NONE = "none"


##### INTAKE #####
class Dependency(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """One declared dependency: `declared` as the manifest writes it, `resolved` the lockfile's version (empty: no
    lockfile names it); `imports` the first source files that import it, `imported` how many do."""

    name: str
    ecosystem: Ecosystem
    manifest: str
    scope: str = ""
    declared: str = ""
    resolved: str = ""
    imports: tuple[str, ...] = ()
    imported: int = 0


class Stack(msgspec.Struct, frozen=True, kw_only=True):
    """intake: what the repository declares, and the query as written."""

    project: str
    query: str
    manifests: tuple[str, ...]
    dependencies: tuple[Dependency, ...]
    topic: str = ""


##### RIVALS #####
class Subject(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """A technology the health step can read: its GitHub repository (`owner/name`) and its registry entry."""

    name: str
    repo: str = ""
    package: str = ""
    registry: Registry | None = None
    why: str = ""


class Rivalry(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """One incumbent the query is about, the job it does here, and at most three rivals."""

    incumbent: Subject
    role: str
    rivals: Annotated[tuple[Subject, ...], msgspec.Meta(max_length=RIVALS)]


class Rivals(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """rivals: every incumbent the query names, each with its rivals."""

    incumbents: tuple[Rivalry, ...]


##### HEALTH #####
class Vital(msgspec.Struct, frozen=True, kw_only=True):
    """One subject's health (soa-assess's KPIs), its stars, and whether its hot path is Rust or C/C++ — `basis`
    says, reading by reading, how that was decided."""

    name: str
    health: Health
    rust: bool
    basis: tuple[str, ...]
    stars: int | None = None


class Healths(msgspec.Struct, frozen=True, kw_only=True):
    """health: every incumbent and every rival, measured at one instant."""

    measured_at: str
    subjects: tuple[Vital, ...]


##### RANK #####
class Score(msgspec.Struct, frozen=True, kw_only=True):
    """One subject on the rubric: its total, each term's points, the terms no source measured (zero points)."""

    name: str
    total: float
    terms: dict[str, float]
    unmeasured: tuple[str, ...] = ()
    stars: int | None = None


class Contest(msgspec.Struct, frozen=True, kw_only=True):
    """One incumbent against its rivals: every score, the incumbent's first; `rival` the one kept (empty: none
    beat the incumbent by the margin) and why."""

    incumbent: str
    role: str
    scores: tuple[Score, ...]
    reason: str
    rival: str = ""


class Shortlist(msgspec.Struct, frozen=True, kw_only=True):
    """rank: the rubric's weights and margin, and every contest."""

    weights: dict[str, float]
    margin: float
    contests: tuple[Contest, ...]


##### PLANS #####
class Migration(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """The migration sketch: the files it touches and the API changes it takes."""

    files: tuple[str, ...]
    changes: tuple[str, ...]


class Weighed(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """One shortlisted pair's pre-registered benchmark (the incumbent the baseline arm, the rival the candidate)."""

    incumbent: str
    rival: str
    plan: Plan
    migration: Migration


class Plans(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """weigh: one plan per shortlisted pair."""

    pairs: tuple[Weighed, ...]


##### BENCH #####
class Benched(msgspec.Struct, frozen=True, kw_only=True):
    incumbent: str
    rival: str
    samples: Samples


class PairSamples(msgspec.Struct, frozen=True, kw_only=True):
    """bench: every pair's raw samples, as soa-assess's bench keeps them."""

    pairs: tuple[Benched, ...]


##### STATS #####
class Measured(msgspec.Struct, frozen=True, kw_only=True):
    incumbent: str
    rival: str
    stats: Stats


class PairStats(msgspec.Struct, frozen=True, kw_only=True):
    """stats: every pair's paired interval against its threshold, as soa-assess's stats reads it."""

    pairs: tuple[Measured, ...]


##### VERDICT #####
class Ruling(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """One incumbent judged against its rival: replace, trial or keep, with its evidence and its landing."""

    incumbent: str
    rival: str
    decision: Decision
    evidence: tuple[str, ...]
    landing: Destination
    command: str
    target: str = ""


class Verdicts(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """verdict: one ruling per shortlisted pair."""

    verdicts: tuple[Ruling, ...]


class Challenge(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """The adversary on one ruling: what tried to sink it, whether it stands; `decision` is the reviewer's own."""

    incumbent: str
    stands: bool
    objections: tuple[Objection, ...]
    decision: Decision


class Reviews(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """adversary: one challenge per ruling."""

    reviews: tuple[Challenge, ...]


##### REPORT #####
class Settled(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """One incumbent as it stood: `decision` the verdict's when the review stands, the reviewer's when it does not;
    `proposed` the verdict step's own. An incumbent rank kept never reached the verdict: keep, by the rubric."""

    incumbent: str
    decision: Decision
    proposed: Decision
    stands: bool
    scores: tuple[Score, ...]
    declared: tuple[Dependency, ...] = ()
    rival: str = ""
    reason: str = ""
    landing: Destination = Destination.NONE
    command: str = ""
    evidence: tuple[str, ...] = ()
    objections: tuple[Objection, ...] = ()
    migration: Migration | None = None
    stats: Stats | None = None


class Report(msgspec.Struct, frozen=True, kw_only=True):
    """report: the comparison as written, one row per incumbent."""

    project: str
    query: str
    date: str
    path: str
    settled: tuple[Settled, ...]


class Compared(msgspec.Struct, frozen=True, kw_only=True):
    """One row of the state's index (`compared.json`, incumbent → row): the latest verdict on it."""

    verdict: Decision
    date: str
    report: str


##### THE PORTS #####
### Every artifact passed between soa-compare's steps, by the model name its ports declare: one JSON Schema each.
PORTS: Final[Mapping[str, object]] = MappingProxyType(
    {
        "Stack": Stack,
        "Rivals": Rivals,
        "Healths": Healths,
        "Shortlist": Shortlist,
        "Plans": Plans,
        "PairSamples": PairSamples,
        "PairStats": PairStats,
        "Verdicts": Verdicts,
        "Reviews": Reviews,
        "Report": Report,
    }
)
