"""models.metrics: the typed evidence a step or a node leaves in the ledger — a tagged union, one tag per kind.

A workflow step leaves a session's narrative or a loop check; a plane node its own reading (a law, a scan, a
ledger, a render, a verdict). The tag is the kind of evidence, so the ledger decodes without guessing and readers
dispatch on the type, never on a string. Every plane reading says itself in one line (`summary`): the report row a
reader needs without opening the ledger."""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from msgspec import Struct

##### DEFAULTS #####
SHOWN: int = 12


##### TYPES #####
class SessionMetrics(Struct, frozen=True, tag="session"):
    """A step's run: who ran it (`run` for a command) and the last lines it said."""

    agent: str
    narrative: tuple[str, ...]

    @property
    def summary(self) -> str:
        return f"{self.agent}: {self.narrative[-1] if self.narrative else '—'}"


class LoopState(StrEnum):
    """What one `until` check of a bounded loop concluded."""

    CLOSED = "closed"
    OPEN = "open"
    STALLED = "stalled"

    @property
    def ends(self) -> bool:
        """Whether the loop stops here: done, or the same open set as the check before."""
        return self is not LoopState.OPEN


class LoopMetrics(Struct, frozen=True, tag="loop"):
    """One `until` check: its iteration, its conclusion, how much stayed open and a digest of it."""

    iteration: int
    state: LoopState
    open: int
    digest: str

    @property
    def summary(self) -> str:
        return f"iteration {self.iteration}: {self.state}"


class Owner(StrEnum):
    """Who acts on a need: the enhancer's agents in a loop, or you."""

    AGENT = "agent"
    HUMAN = "human"


### every need kind and its owner; a kind absent here raises — a new kind is a decision, never a default.
NEED_OWNER: Final[Mapping[str, Owner]] = MappingProxyType(
    {
        "law": Owner.AGENT,
        "security": Owner.AGENT,
        "effect": Owner.AGENT,
        "drift": Owner.AGENT,
        "routing": Owner.HUMAN,
        "coverage": Owner.HUMAN,
        "broken": Owner.HUMAN,
    }
)


class Need(Struct, frozen=True, array_like=True):
    """One reason to act on a subject: what kind, which node saw it, the detail."""

    kind: str
    node: str
    detail: str

    @property
    def owner(self) -> Owner:
        return NEED_OWNER[self.kind]


class Finding(Struct, frozen=True, array_like=True):
    """One scanner finding, placed in core/ when its line traces back: rule, severity, where, what, its fingerprint."""

    rule: str
    severity: str
    path: str
    line: int
    detail: str
    fingerprint: str


class GradedChange(Struct, frozen=True, array_like=True):
    """One rendered path, weighed by the versioning matrix: its kind of change, its grade, the slots it moved."""

    path: str
    kind: str
    grade: str
    slots: tuple[str, ...]


class SignalRow(Struct, frozen=True, array_like=True):
    """One upstream drift signal: where it came from and what moved."""

    category: str
    source: str
    detail: str


class SnapshotMetrics(Struct, frozen=True, tag="snapshot"):
    """The world the run started from: the base, the checkout's dirty paths, every tool a verdict leans on."""

    base_sha: str
    dirty: tuple[str, ...]
    tools: dict[str, str]

    @property
    def summary(self) -> str:
        tools = " · ".join(f"{name} {version}" for name, version in sorted(self.tools.items()))
        return f"base {self.base_sha[:10]} · {len(self.dirty)} dirty · {tools}"


class SandboxMetrics(Struct, frozen=True, tag="sandbox"):
    """The clone every write of the run lands in."""

    path: str
    base_sha: str

    @property
    def summary(self) -> str:
        return self.path


class RenderMetrics(Struct, frozen=True, tag="render"):
    """One v2 render of a tree for one backend."""

    out: str
    backend: str
    files: int
    tree: str

    @property
    def summary(self) -> str:
        return f"{self.files} files · {self.backend} · {self.tree} → {self.out}"


class LawMetrics(Struct, frozen=True, tag="law"):
    """House law over one subject, in the tree the node was pointed at."""

    tree: str
    violations: tuple[str, ...]
    lines: int = 0
    rules: int = 0
    description: int = 0

    @property
    def summary(self) -> str:
        shape = f" · {self.lines} lines · {self.rules} rules" if self.lines else ""
        listed = "".join(f"\n      - {violation}" for violation in self.violations[:SHOWN])
        return f"{self.tree}: {len(self.violations)} violations{shape}{listed}"


class SecurityMetrics(Struct, frozen=True, tag="security"):
    """A scan of one rendered subject: its findings (accepted ones dropped) and the scanner's risk score."""

    tree: str
    scanner: str
    score: int
    findings: tuple[Finding, ...]
    accepted: int = 0

    @property
    def summary(self) -> str:
        listed = "".join(
            f"\n      ! {f.fingerprint[:12]}  {f.severity:<8}{f.rule:<6}{f.path}:{f.line}  {f.detail[:80]}"
            for f in self.findings[:SHOWN]
        )
        head = f"{self.tree} {self.scanner}: score {self.score} · {len(self.findings)} findings"
        return f"{head} · {self.accepted} accepted{listed}"


class LedgerMetrics(Struct, frozen=True, tag="ledger"):
    """A declared case set (routing queries or effect tasks), where it was read and what is wrong with it."""

    kind: str
    cases: int
    problems: tuple[str, ...]
    where: str = ""
    splits: dict[str, int] = {}

    @property
    def summary(self) -> str:
        splits = "".join(f" {split}={count}" for split, count in sorted(self.splits.items()))
        listed = "".join(f"\n      - {problem}" for problem in self.problems)
        return f"{self.kind}: {self.cases} cases{splits} · {self.where}{listed}"


class LoadingMetrics(Struct, frozen=True, tag="loading"):
    """What the real harness, raised fenced on the render, showed of what the core declares."""

    backend: str
    declared: int
    invisible: tuple[str, ...]

    @property
    def summary(self) -> str:
        return f"{self.backend}: {self.declared} declared · {len(self.invisible)} invisible"


class SignalMetrics(Struct, frozen=True, tag="signals"):
    """Upstream drift the spec check saw for one backend."""

    backend: str
    signals: tuple[SignalRow, ...]

    @property
    def summary(self) -> str:
        listed = "".join(f"\n      ⚠ {s.category}/{s.source}: {s.detail}" for s in self.signals)
        return f"{len(self.signals)} signals{listed}"


class NeedsMetrics(Struct, frozen=True, tag="needs"):
    """The evaluator's conclusion for one subject: every reason to enhance it, or none."""

    needs: tuple[Need, ...]

    @property
    def summary(self) -> str:
        listed = "".join(f"\n      → {n.kind:<9}{n.node:<20}{n.detail[:120]}" for n in self.needs)
        return f"{len(self.needs)} needs{listed}"


class BriefMetrics(Struct, frozen=True, tag="brief"):
    """What an enhancement acts on: the evaluation it came from, its needs, your directive."""

    source: str
    needs: tuple[Need, ...]
    directive: str = ""
    manual: bool = False

    @property
    def summary(self) -> str:
        directive = f" · directive: {self.directive[:100]}" if self.directive else ""
        return f"from {self.source or '—'} · {len(self.needs)} needs{directive}{' · manual' if self.manual else ''}"


class ProposalMetrics(Struct, frozen=True, tag="proposal"):
    """What a proposer changed (git measured it) and the lessons it acted on."""

    proposer: str
    files: tuple[str, ...]
    lessons: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        listed = "".join(f"\n      + {lesson[:140]}" for lesson in self.lessons)
        return f"{self.proposer}: {len(self.files)} files · {len(self.lessons)} lessons{listed}"


class CandidateMetrics(Struct, frozen=True, tag="candidate"):
    """One subject's candidate render, the paths it moved against the base, and whether it reads back unchanged."""

    out: str
    changed: tuple[str, ...]
    fixpoint: bool
    unread: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        listed = "".join(f"\n      ~ {path}" for path in self.changed)
        unread = "".join(f"\n      ✗ {path}" for path in self.unread)
        return f"{len(self.changed)} changed · fixpoint {'✓' if self.fixpoint else '✗'}{listed}{unread}"


class GradeMetrics(Struct, frozen=True, tag="grade"):
    """How much the candidate weighs, by the table and never by a model."""

    changes: tuple[GradedChange, ...]
    grade: str
    bump: str

    @property
    def summary(self) -> str:
        return f"{self.grade or '—'} · bump {self.bump or '—'}"


class DecisionMetrics(Struct, frozen=True, tag="decision"):
    """The verdict and every reason behind it."""

    decision: str
    reasons: tuple[str, ...]
    grade: str = ""
    bump: str = ""

    @property
    def summary(self) -> str:
        return self.decision + "".join(f"\n      · {reason}" for reason in self.reasons)


class PatchMetrics(Struct, frozen=True, tag="patch"):
    """The diff a promotion would apply to the checkout."""

    path: str
    files: tuple[str, ...]
    added: int
    removed: int
    sha256: str

    @property
    def summary(self) -> str:
        return f"+{self.added} -{self.removed} · {len(self.files)} files · {self.path}"


type Metrics = (
    SessionMetrics
    | LoopMetrics
    | SnapshotMetrics
    | SandboxMetrics
    | RenderMetrics
    | LawMetrics
    | SecurityMetrics
    | LedgerMetrics
    | LoadingMetrics
    | SignalMetrics
    | NeedsMetrics
    | BriefMetrics
    | ProposalMetrics
    | CandidateMetrics
    | GradeMetrics
    | DecisionMetrics
    | PatchMetrics
)
