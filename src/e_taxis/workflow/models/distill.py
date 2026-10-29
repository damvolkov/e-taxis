"""models.distill: reverse-distill's data — where a change can land, and the chain from a claim to a proposal.

**Targets.** A proposal lands in one of the two cores, on a place that exists — or that it creates on purpose.
e-nous (`HarnessTarget`): a facet, an entity, its id and the part of its anatomy, or a place that is no entity (the
stack, a spec, a matrix row). e-arkhetypo (`BlueprintTarget`): an area, the unit in it and the layer. The enums are
closed and mirror the repos: a new system or stack category is a deliberate change here, never a path a model invents.

**The chain.** `Claim` (what the human and the commits say) → `Candidate` (a concrete change against targets) →
`Grade` (deterministic: matrix, existence, duplicates, reach, and the places a contradiction must also reach) →
`Judgement` (must · should · case · reject) → `Review` (adversarial) → `Proposal` (what survives, with the `Handoff`
that applies it). The `Report` gathers the run.

**Contradictions.** A candidate that `contradicts` the core replaces a fact the core states: it names the replaced
term(s) in `replaces`, and grade greps them across the harness scope so every place that still states the old fact
becomes a target — the miner's recall is not trusted to find them all."""

import re
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

import msgspec

from e_taxis.workflow.models.entity import Entity


##### ENUMS #####
class Change(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    RETIRE = "retire"


class HarnessFacet(StrEnum):
    """`core/<facet>/`: the two facets, what every facet shares (`base`) and the shared stack (`common`)."""

    TEKTON = "tekton"
    NOMOS = "nomos"
    BASE = "base"
    COMMON = "common"


class HarnessKind(StrEnum):
    """An entity of the corpus, or one of the places that are not entities."""

    ENTITY = "entity"
    STACK = "stack"
    SPEC = "spec"
    MATRIX = "matrix"


class HarnessPart(StrEnum):
    """A piece of an entity's anatomy; which parts an entity has is `PARTS`."""

    MANIFEST = "manifest"
    INSTRUCTIONS = "instructions"
    REFERENCE = "reference"
    LIB = "lib"
    PROMPT = "prompt"
    TEMPLATE = "template"
    NODE = "node"
    SLOT = "slot"
    MODULE = "module"
    ROW = "row"


class BlueprintArea(StrEnum):
    """The top folders of e-arkhetypo that hold doctrine."""

    PROJECT = "project"
    STACK = "stack"
    INFRA = "infra"
    TOOLS = "tools"


class Project(StrEnum):
    """projects/python/: the project blueprints; `infra` is what every project materializes."""

    API = "api"
    CLI = "cli"
    GRAPH = "graph"
    INFRA = "infra"
    MCP = "mcp"
    TUI = "tui"


class InfraLayer(StrEnum):
    """projects/python/infra: the sections materialized into every project, and its shared root files (`common`)."""

    ADAPTERS = "adapters"
    INFRA = "infra"
    OPS = "ops"
    PROCESSORS = "processors"
    COMMON = "common"


class StackCategory(StrEnum):
    """stack/<category>/: one folder per kind of service."""

    AGENT = "agent"
    AUTH = "auth"
    CDB = "cdb"
    DDB = "ddb"
    FRONT = "front"
    GDB = "gdb"
    LLM = "llm"
    MEDIA = "media"
    MEM = "mem"
    PROXY = "proxy"
    QUEUE = "queue"
    RAG = "rag"
    RDB = "rdb"
    SPEECH = "speech"
    STORAGE = "storage"
    TDB = "tdb"
    TOOLS = "tools"
    VDB = "vdb"
    WATCH = "watch"


class Infra(StrEnum):
    FILES = "files"
    JOBS = "jobs"
    SETUP = "setup"
    TRIGGERS = "triggers"
    WORKFLOWS = "workflows"


class Reach(StrEnum):
    """How far a proposal spreads — computed from its targets, never chosen."""

    ONE = "one"
    SEVERAL = "several"
    ALL_PROJECTS = "all_projects"
    CROSS = "cross"


class Plane(StrEnum):
    """Where a lesson can land — every plane is looked at on every run, so an empty one is a finding, not a blind spot."""

    DOCTRINE = "doctrine"
    LIBRARY = "library"
    PROCESS = "process"
    TOOLING = "tooling"
    MODULE = "module"
    COMMON = "common"
    PROJECT = "project"
    SERVICE = "service"
    OPS = "ops"


##### DEFAULTS #####
PARTS: Final[Mapping[Entity, frozenset[HarnessPart]]] = MappingProxyType(
    {
        Entity.SKILL: frozenset(
            {HarnessPart.MANIFEST, HarnessPart.INSTRUCTIONS, HarnessPart.REFERENCE, HarnessPart.LIB}
        ),
        Entity.AGENT: frozenset({HarnessPart.MANIFEST, HarnessPart.PROMPT}),
        Entity.COMMAND: frozenset({HarnessPart.MANIFEST, HarnessPart.TEMPLATE}),
        Entity.WORKFLOW: frozenset({HarnessPart.MANIFEST, HarnessPart.NODE}),
        Entity.PERSONA: frozenset({HarnessPart.SLOT}),
        Entity.CONFIG: frozenset({HarnessPart.MODULE}),
        Entity.TOOL: frozenset({HarnessPart.MANIFEST}),
    }
)
NAMED: Final[frozenset[HarnessPart]] = frozenset(
    {HarnessPart.REFERENCE, HarnessPart.NODE, HarnessPart.SLOT, HarnessPart.MODULE}
)
### a candidate id names its brief file and its branch: one safe word, never a path.
IDENT: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


##### TARGETS #####
class HarnessTarget(
    msgspec.Struct, frozen=True, kw_only=True, tag="harness", omit_defaults=True, forbid_unknown_fields=True
):
    """A place in e-nous. `id` is the entity's id (for a `create`, the id it will have); `name` only the part's own
    bare name (a reference, node, slot or module), never a path or an id."""

    facet: HarnessFacet = HarnessFacet.TEKTON
    kind: HarnessKind = HarnessKind.ENTITY
    entity: Entity | None = None
    id: str = ""
    part: HarnessPart = HarnessPart.MANIFEST
    name: str = ""
    change: Change = Change.UPDATE

    def problems(self) -> tuple[str, ...]:
        """Why this target is not a coherent place; empty when it is (existence on disk is the grade's job)."""
        match self.kind:
            case HarnessKind.ENTITY if self.entity is None:
                return ("an entity target needs `entity`",)
            case HarnessKind.ENTITY if not self.id:
                return ("an entity target needs `id` — for a create, the id the entity will have",)
            case HarnessKind.ENTITY if ":" in self.name:
                return (f"`name` {self.name!r} carries an id: the id goes in `id`, the part's name alone in `name`",)
            case HarnessKind.ENTITY if self.entity is not None and self.part not in PARTS[self.entity]:
                return (f"a {self.entity} has no part {self.part}",)
            case HarnessKind.ENTITY if self.part in NAMED and not self.name:
                return (f"part {self.part} needs `name`",)
            case _:
                return ()

    @property
    def plane(self) -> Plane:
        """The plane this place is — from where it sits, never chosen."""
        match self:
            case HarnessTarget(kind=HarnessKind.ENTITY, entity=Entity.SKILL, part=HarnessPart.LIB):
                return Plane.LIBRARY
            case HarnessTarget(kind=HarnessKind.ENTITY, entity=Entity.SKILL | Entity.PERSONA):
                return Plane.DOCTRINE
            case HarnessTarget(kind=HarnessKind.ENTITY, entity=Entity.CONFIG) | HarnessTarget(kind=HarnessKind.STACK):
                return Plane.TOOLING
            case HarnessTarget(kind=HarnessKind.ENTITY):
                return Plane.PROCESS
            case _:
                return Plane.TOOLING


class BlueprintTarget(
    msgspec.Struct, frozen=True, kw_only=True, tag="blueprint", omit_defaults=True, forbid_unknown_fields=True
):
    """A place in e-arkhetypo: `unit` is the project, `<category>/<service>` of a stack, or the infra unit.

    `new` names a project or a stack service that does not exist yet (the target creates it)."""

    area: BlueprintArea
    unit: str
    new: bool = False
    layer: str = ""
    path: str = ""
    change: Change = Change.UPDATE

    @property
    def root(self) -> str:
        """The folder the unit lives in, repo-relative."""
        folder = {BlueprintArea.PROJECT: "projects/python", BlueprintArea.STACK: "stack"}.get(
            self.area, self.area.value
        )
        return folder if self.area is BlueprintArea.TOOLS else f"{folder}/{self.unit}"

    def problems(self) -> tuple[str, ...]:
        """Why this target names no place the enums know; empty when it does (or when it creates one)."""
        match self.area:
            case BlueprintArea.PROJECT if not self.new and self.unit not in Project.__members__.values():
                return (f"no project {self.unit} (set `new` to create one)",)
            case BlueprintArea.PROJECT if (
                self.unit == Project.INFRA and self.layer and self.layer not in InfraLayer.__members__.values()
            ):
                return (f"project infra has no layer {self.layer}",)
            case BlueprintArea.STACK if self.unit.split("/")[0] not in StackCategory.__members__.values():
                return (f"no stack category {self.unit.split('/')[0]}",)
            case BlueprintArea.STACK if "/" not in self.unit:
                return ("a stack unit is <category>/<service>",)
            case BlueprintArea.INFRA if self.unit not in Infra.__members__.values():
                return (f"no infra unit {self.unit}",)
            case _:
                return ()

    @property
    def plane(self) -> Plane:
        """The plane this place is — from where it sits, never chosen."""
        match self:
            case BlueprintTarget(area=BlueprintArea.PROJECT, unit=Project.INFRA, layer=InfraLayer.COMMON):
                return Plane.COMMON
            case BlueprintTarget(area=BlueprintArea.PROJECT, unit=Project.INFRA):
                return Plane.MODULE
            case BlueprintTarget(area=BlueprintArea.PROJECT):
                return Plane.PROJECT
            case BlueprintTarget(area=BlueprintArea.STACK):
                return Plane.SERVICE
            case _:
                return Plane.OPS

    @property
    def inherited(self) -> bool:
        """Whether every project inherits this place when it materializes its infra."""
        return self.area is BlueprintArea.PROJECT and self.unit == Project.INFRA


type Target = HarnessTarget | BlueprintTarget


##### EVIDENCE #####
class CommitEvidence(msgspec.Struct, frozen=True, kw_only=True, tag="commit", forbid_unknown_fields=True):
    sha: str
    message: str


class CodeEvidence(
    msgspec.Struct, frozen=True, kw_only=True, tag="code", omit_defaults=True, forbid_unknown_fields=True
):
    path: str
    lines: tuple[int, int] = (0, 0)
    symbol: str = ""


class DriftEvidence(msgspec.Struct, frozen=True, kw_only=True, tag="drift", forbid_unknown_fields=True):
    """A file where the project departs from the template it materialized (infra-check)."""

    path: str
    template: str


class BenchEvidence(msgspec.Struct, frozen=True, kw_only=True, tag="bench", forbid_unknown_fields=True):
    metric: str
    before: float
    after: float
    unit: str = ""


class SourceEvidence(msgspec.Struct, frozen=True, kw_only=True, tag="source", forbid_unknown_fields=True):
    url: str
    claim: str


type Evidence = CommitEvidence | CodeEvidence | DriftEvidence | BenchEvidence | SourceEvidence


##### THE CHAIN #####
class ClaimKind(StrEnum):
    DISCOVERY = "discovery"
    IMPROVEMENT = "improvement"
    CONTRADICTION = "contradiction"
    BENCHMARK = "benchmark"
    ONE_OFF = "one_off"


class Claim(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """What the human's words and the commits say was learned: one typed statement, with its evidence."""

    id: str
    kind: ClaimKind
    summary: str
    evidence: tuple[Evidence, ...] = ()


class Relation(StrEnum):
    EXTENDS = "extends"
    IMPROVES = "improves"
    CONTRADICTS = "contradicts"
    ADDS = "adds"
    RETIRES = "retires"


class Candidate(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """A concrete change one claim (or several) asks of the cores.

    `replaces`: for a `contradicts`, the term(s) the core states today that this change replaces (`awa` when the
    lesson is `PgQueuer` over `awa`) — what grade greps the harness for."""

    id: str
    claims: tuple[str, ...]
    targets: tuple[Target, ...]
    relation: Relation
    sketch: str
    evidence: tuple[Evidence, ...] = ()
    facts: tuple[str, ...] = ()
    title: str = ""
    replaces: tuple[str, ...] = ()

    def problems(self) -> tuple[str, ...]:
        """Why this candidate is incoherent as a whole; its targets answer for themselves."""
        return (
            *(() if IDENT.fullmatch(self.id) else (f"id {self.id!r} is not one safe word (letters, digits, . _ -)",)),
            *(
                ("a contradiction names the term it replaces in `replaces`",)
                if self.relation is Relation.CONTRADICTS and not any(term.strip() for term in self.replaces)
                else ()
            ),
        )

    @property
    def reach(self) -> Reach:
        repos = {type(target) for target in self.targets}
        inherited = any(isinstance(target, BlueprintTarget) and target.inherited for target in self.targets)
        match (len(repos), inherited, len(self.targets)):
            case (2, _, _):
                return Reach.CROSS
            case (_, True, _):
                return Reach.ALL_PROJECTS
            case (_, _, 1):
                return Reach.ONE
            case _:
                return Reach.SEVERAL


class Waiver(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """A fact a miner looked at and left: why it teaches the cores nothing."""

    fact: str
    reason: str


class Mining(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """A miner's answer: what it proposes, and every fact of its planes it decided to leave."""

    candidates: tuple[Candidate, ...] = ()
    waived: tuple[Waiver, ...] = ()


class Grade(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """The deterministic weight of a candidate.

    `propagated` lists the places grade added because they still state what a contradiction replaces."""

    candidate: str
    matrix: str = ""
    reach: Reach = Reach.ONE
    exists: bool = True
    duplicate_of: str = ""
    stop: tuple[str, ...] = ()
    propagated: tuple[str, ...] = ()


class Propagation(msgspec.Struct, frozen=True, kw_only=True):
    """What propagating a contradiction did: the places it added, and the replaced terms the core never states."""

    added: tuple[str, ...] = ()
    silent: tuple[str, ...] = ()


class Verdict(StrEnum):
    MUST = "must"
    SHOULD = "should"
    CASE = "case"
    REJECT = "reject"


class Judgement(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    candidate: str
    verdict: Verdict
    generality: float
    rationale: str


class Review(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True, forbid_unknown_fields=True):
    """The adversarial second vote on a must or a should."""

    candidate: str
    upheld: bool
    objection: str = ""
    final: Verdict = Verdict.SHOULD


class Emaintenance(msgspec.Struct, frozen=True, kw_only=True, tag="emaintenance"):
    """A core entity created, updated or retired through `taxis workflow run emaintenance`."""

    entity: Entity
    op: Change
    id: str
    details: str


class Enhance(msgspec.Struct, frozen=True, kw_only=True, tag="enhance"):
    """A core place improved on a directive through `op enhance run` (W2 ports enhance)."""

    entity: Entity
    ids: tuple[str, ...]
    directive: str


class BlueprintChange(msgspec.Struct, frozen=True, kw_only=True, tag="blueprint"):
    """A change to e-arkhetypo: a branch and the brief its builder works from."""

    targets: tuple[BlueprintTarget, ...]
    branch: str
    brief: str


type Handoff = Emaintenance | Enhance | BlueprintChange


class Proposal(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    candidate: Candidate
    grade: Grade
    judgement: Judgement
    handoff: Handoff
    review: Review | None = None


class RunMeta(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    id: str
    project: str
    branches: tuple[str, ...]
    base: str
    work: str = ""
    harness: str = ""
    blueprint: str = ""
    folder: str = ""


class NodeSkip(msgspec.Struct, frozen=True, kw_only=True):
    node: str
    reason: str


class NodeCost(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    node: str
    seconds: float
    tokens: int = 0
    model: str = ""


##### ARTIFACTS OF THE DETERMINISTIC STEPS #####
class Scope(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """guard: the project, the branches, the base they grew from, and what the human said."""

    project: str
    graph: str
    branches: tuple[str, ...]
    base: str
    work: str = ""


class FileKind(StrEnum):
    CODE = "code"
    STRUCTURED = "structured"
    DOCS = "docs"


class FileRow(msgspec.Struct, frozen=True, kw_only=True):
    path: str
    kind: FileKind
    added: int
    removed: int


class CommitRow(msgspec.Struct, frozen=True, kw_only=True):
    sha: str
    subject: str
    body: str = ""


class Manifest(msgspec.Struct, frozen=True, kw_only=True):
    """intake: every commit of the branches since the base, and every file they touched, weighed."""

    scope: Scope
    commits: tuple[CommitRow, ...]
    files: tuple[FileRow, ...]


class Indexes(msgspec.Struct, frozen=True, kw_only=True):
    """index: the code-graph project names the miners query, with the HEAD each was indexed at."""

    harness: str
    blueprint: str
    project: str
    heads: dict[str, str] = {}


class Symbol(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    name: str
    label: str = ""
    file: str = ""


class Deltas(msgspec.Struct, frozen=True, kw_only=True):
    """scan: the files the branches changed in the run's range (git, committed work only) and the symbols the code
    graph says they impact."""

    changed: tuple[str, ...]
    impacted: tuple[Symbol, ...]


class Drift(msgspec.Struct, frozen=True, kw_only=True):
    """drift: where the project departs from the blueprint it materialized; `checked` false when it has no check."""

    checked: bool
    files: tuple[DriftEvidence, ...] = ()


class FactStatus(StrEnum):
    ABSENT = "absent"
    DIVERGED = "diverged"
    MISSING = "missing"


class Direction(StrEnum):
    """Who moved since the base — the template version the project was generated from (three-way, as a merge)."""

    AHEAD = "ahead"
    BEHIND = "behind"
    BOTH = "both"


class Fact(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """inventory: one thing the project has that the cores do not say, found without a model."""

    id: str
    plane: Plane
    subject: str
    status: FactStatus
    detail: str = ""
    where: str = ""
    fresh: bool = True
    direction: Direction | None = None
    base: str = ""


class Inventory(msgspec.Struct, frozen=True, kw_only=True):
    """What the miners weigh (`facts`), and where the project is behind its blueprint (`stale`, for the human)."""

    facts: tuple[Fact, ...]
    stale: tuple[Fact, ...] = ()


class Coverage(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """One plane of the run: what the inventory found, what the miners proposed, what survived, what nobody answered."""

    plane: Plane
    facts: int = 0
    candidates: int = 0
    proposals: int = 0
    open: tuple[Fact, ...] = ()
    waived: tuple[tuple[Fact, str], ...] = ()


class Report(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """The run's whole answer; `report.md` is a view of it, rendered without a model."""

    run: RunMeta
    proposals: tuple[Proposal, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    cases: tuple[Judgement, ...] = ()
    rejected: tuple[Judgement, ...] = ()
    coverage: tuple[Coverage, ...] = ()
    stale: tuple[Fact, ...] = ()
    skipped: tuple[NodeSkip, ...] = ()
    cost: tuple[NodeCost, ...] = ()


##### THE PORTS #####
### Every artifact passed between steps, by the model name its ports declare: one JSON Schema each, written into the
### workflow's `schemas/` — what an agent step is told its answer must fit.
PORTS: Final[Mapping[str, object]] = MappingProxyType(
    {
        "Scope": Scope,
        "Manifest": Manifest,
        "Indexes": Indexes,
        "Deltas": Deltas,
        "Drift": Drift,
        "Inventory": Inventory,
        "Claims": tuple[Claim, ...],
        "Mining": Mining,
        "Candidates": tuple[Candidate, ...],
        "Waivers": tuple[Waiver, ...],
        "Grades": tuple[Grade, ...],
        "Judgements": tuple[Judgement, ...],
        "Reviews": tuple[Review, ...],
        "Report": Report,
    }
)
