"""tests/unit/e_taxis/workflow/models/plane: the planes' data — a node's cadence, the ledgers' law, every reading's one
line, a report's breakage, an acceptance's reach."""

import pytest

from e_taxis.workflow.models.case import QueryCase, QuerySet, TaskCase, TaskCheck, TaskOp, TaskSet, TaskSplit
from e_taxis.workflow.models.metrics import (
    BriefMetrics,
    CandidateMetrics,
    DecisionMetrics,
    Finding,
    GradeMetrics,
    LawMetrics,
    LedgerMetrics,
    LoadingMetrics,
    LoopMetrics,
    LoopState,
    Metrics,
    Need,
    NeedsMetrics,
    Owner,
    PatchMetrics,
    ProposalMetrics,
    RenderMetrics,
    SandboxMetrics,
    SecurityMetrics,
    SessionMetrics,
    SignalMetrics,
    SignalRow,
    SnapshotMetrics,
)
from e_taxis.workflow.models.plane import Cadence, NodeCard, NodeSpec, Role
from e_taxis.workflow.models.security import Acceptance
from e_taxis.workflow.models.verdict import Decision

FINDING = Finding("E1", "HIGH", "core/tekton/skills/x/instructions.md", 3, "curl", "abcdef0123456789")


@pytest.mark.parametrize(
    ("cadence", "declared", "due"),
    [
        (Cadence.COMMIT, (), True),
        (Cadence.COMMIT, (Cadence.WEEKLY,), False),
        (Cadence.WEEKLY, (Cadence.WEEKLY,), True),
        (Cadence.MANUAL, (Cadence.WEEKLY,), True),
    ],
    ids=["always", "not-due", "due", "manual-runs-all"],
)
async def test_plane_node_due(cadence: Cadence, declared: tuple[Cadence, ...], due: bool) -> None:
    spec = NodeSpec(id="n", use="n", card=NodeCard(role=Role.GATE, summary="s", cadence=declared))
    assert spec.due(cadence) is due


@pytest.mark.parametrize(
    ("role", "only", "selected"),
    [
        (Role.MEASURE, (), True),
        (Role.MEASURE, ("n",), True),
        (Role.MEASURE, ("other",), False),
        (Role.GATE, ("other",), True),
    ],
    ids=["no-selection", "named", "not-named", "gates-always-run"],
)
async def test_plane_node_selected(role: Role, only: tuple[str, ...], selected: bool) -> None:
    spec = NodeSpec(id="n", use="n", card=NodeCard(role=role, summary="s"))
    assert spec.selected(only) is selected


@pytest.mark.parametrize(
    ("metrics", "expected"),
    [
        (SessionMetrics(agent="a", narrative=("x", "last")), "a: last"),
        (SessionMetrics(agent="a", narrative=()), "a: —"),
        (LoopMetrics(iteration=2, state=LoopState.OPEN, open=1, digest="d"), "iteration 2: open"),
        (
            SnapshotMetrics(base_sha="abcdef0123456", dirty=("a",), tools={"git": "2"}),
            "base abcdef0123 · 1 dirty · git 2",
        ),
        (SandboxMetrics(path="/s", base_sha="b"), "/s"),
        (RenderMetrics(out="/o", backend="b", files=3, tree="working"), "3 files · b · working → /o"),
        (
            LawMetrics(tree="base", violations=("v",), lines=4, rules=2),
            "base: 1 violations · 4 lines · 2 rules\n      - v",
        ),
        (
            SecurityMetrics(tree="base", scanner="s@1", score=5, findings=(FINDING,), accepted=1),
            (
                "base s@1: score 5 · 1 findings · 1 accepted\n      ! abcdef012345  HIGH    E1    "
                "core/tekton/skills/x/instructions.md:3  curl"
            ),
        ),
        (
            LedgerMetrics(kind="tasks", cases=2, problems=("p",), where="w", splits={"test": 1}),
            "tasks: 2 cases test=1 · w\n      - p",
        ),
        (LoadingMetrics(backend="b", declared=3, invisible=("skill:x",)), "b: 3 declared · 1 invisible"),
        (
            SignalMetrics(backend="b", signals=(SignalRow("upstream", "1.0", "moved"),)),
            "1 signals\n      ⚠ upstream/1.0: moved",
        ),
        (NeedsMetrics(needs=(Need("law", "law", "v"),)), "1 needs\n      → law      law                 v"),
        (BriefMetrics(source="", needs=(), directive="do", manual=True), "from — · 0 needs · directive: do · manual"),
        (ProposalMetrics(proposer="p", files=("f",), lessons=("l",)), "p: 1 files · 1 lessons\n      + l"),
        (
            CandidateMetrics(out="/c", changed=("a",), fixpoint=False, unread=("a",)),
            "1 changed · fixpoint ✗\n      ~ a\n      ✗ a",
        ),
        (GradeMetrics(changes=(), grade="", bump=""), "— · bump —"),
        (DecisionMetrics(decision="hold", reasons=("r",)), "hold\n      · r"),
        (PatchMetrics(path="/p", files=("f",), added=2, removed=1, sha256="s"), "+2 -1 · 1 files · /p"),
    ],
    ids=lambda value: None if isinstance(value, str) else type(value).__name__,
)
async def test_plane_metrics_summary(metrics: Metrics, expected: str) -> None:
    assert metrics.summary == expected


async def test_plane_need_owner() -> None:
    assert Need("law", "n", "d").owner is Owner.AGENT
    assert Need("routing", "n", "d").owner is Owner.HUMAN


async def test_plane_decision_promotable() -> None:
    assert {d for d in Decision if d.promotable} == {Decision.ADOPT, Decision.PROPOSE}


async def test_plane_query_set_problems() -> None:
    cases = (
        QueryCase(prompt="p", expect=frozenset({"a-py-x"}), reads=frozenset({"lib.md", "b-py-y/ref.md"})),
        QueryCase(prompt="q", owner=frozenset({"ghost-py-z"})),
    )
    problems = QuerySet(skill="a-py-x", cases=cases).problems(frozenset({"a-py-x"}), frozenset({"a-py-x/lib.md"}))
    assert problems == ("unknown skill cited: ghost-py-z", "unknown reference: b-py-y/ref.md")


async def test_plane_task_set_problems() -> None:
    tasks = (
        TaskCase(id="t", split=TaskSplit.TRAIN, prompt="p", checks=(TaskCheck(TaskOp.MAX_CHARS, "9"),)),
        TaskCase(id="t", split=TaskSplit.TRAIN, prompt="p", checks=(TaskCheck(TaskOp.REGEX, "("),)),
        TaskCase(id="u", split=TaskSplit.VAL, prompt="p", checks=()),
    )
    assert TaskSet(skill="s", tasks=tasks).problems == (
        "duplicate task id t",
        "t: shape-only judge — won by reformatting",
        "t: bad regex '('",
        "u: no checks",
        "no test tasks",
    )
    assert TaskSet(skill="s", tasks=()).problems == ()


@pytest.mark.parametrize(
    ("acceptance", "covers"),
    [
        (Acceptance(fingerprint="abcdef012345", file="instructions.md", why="w"), True),
        (Acceptance(fingerprint="abcdef", file="core/tekton/skills/x/instructions.md", why="w"), True),
        (Acceptance(fingerprint="abcdef012345", file="references/lib.md", why="w"), False),
        (Acceptance(fingerprint="ffff", file="instructions.md", why="w"), False),
    ],
    ids=["by-name", "by-path", "other-file", "other-text"],
)
async def test_plane_acceptance_covers(acceptance: Acceptance, covers: bool) -> None:
    assert acceptance.covers(FINDING, "core/tekton/skills/x") is covers
