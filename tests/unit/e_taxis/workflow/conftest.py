"""tests/unit/e_taxis/workflow: an e-nous copy with test workflows, typed builders, fakes for the agent side, and
the real git repos reverse-distill reads (a project with a feature branch, the two cores).

`nous` is the transpiler's mini checkout (copied per test) with its `converge` replaced by the workflows under
`tests/resources/workflow/workflows`: `demo` (every kind of step), `looped` (a bounded loop) and `broken` (an unknown
agent). Commands run for real (bash, git); agents never do — `FakeAgent` answers, `FakeFence` decides the canary.
soa-sweep never leaves the machine: `FakeWeb` serves the recorded pages under `tests/resources/sweep`.

soa-assess: `RecordedApi` answers every URL of `tests/resources/assess/http/index.json` with the body recorded there
(trimmed to the fields read; GitHub's numeric repository ids in `Link` replaced by `x/y`) and a 404 for every other —
the contract `WreqApi` keeps: it never raises; `outage` turns chosen URLs into transport failures (status 0).
`FakeLab` runs for real through the stand-in landrun, its canary saying what `holds` says."""

import asyncio
import datetime as dt
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import anyio
import eserde
import msgspec
import pytest

from e_taxis.harness.runtime.deps import Deps
from e_taxis.transpile.adapters.capture import HttpCapture
from e_taxis.transpile.adapters.fence import LandrunFence
from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.transpile.models.trial import TrialReport, TrialSight
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.run import RunService
from e_taxis.workflow.adapters.agent import ClaudeAgent, ModeAgent, OpencodeAgent
from e_taxis.workflow.adapters.command import ShellCommand
from e_taxis.workflow.adapters.evals import NousEvals
from e_taxis.workflow.adapters.ledger import JsonlLedger
from e_taxis.workflow.adapters.lock import FlockLock
from e_taxis.workflow.adapters.sandbox import GitSandbox
from e_taxis.workflow.distill.grade import DistillGrade
from e_taxis.workflow.distill.matrix import VersionMatrix
from e_taxis.workflow.engine.reader import WorkflowReader
from e_taxis.workflow.models.assess import Arm, Cache, Fetched, Overlap, Plan, Role
from e_taxis.workflow.models.case import ProbeMode, ProbeResult
from e_taxis.workflow.models.distill import Candidate, Change, HarnessPart, HarnessTarget, Relation, Target
from e_taxis.workflow.models.endpoint import Endpoint
from e_taxis.workflow.models.entity import Entity
from e_taxis.workflow.models.error import AgentError, CommandError, ProviderError, SweepError
from e_taxis.workflow.models.graph import GraphSpec, StepSpec
from e_taxis.workflow.models.plane import Cadence, NodeCard, NodeSpec, Plane, PlaneGraph, PlaneManifest, PlanePaths
from e_taxis.workflow.models.plane import Target as PlaneTarget
from e_taxis.workflow.models.ports import AgentPort, NodeContext, PlaneContext, PlaneState, RunState, WebPort
from e_taxis.workflow.models.run import NodeRun, Outcome, Reply, RunManifest, RunPaths, Status
from e_taxis.workflow.models.security import ScanResult
from e_taxis.workflow.models.sweep import Finding as SweepFinding
from e_taxis.workflow.models.sweep import FindingKind
from e_taxis.workflow.models.workflow import Workflow
from e_taxis.workflow.plane.activation import PlaneActivation
from e_taxis.workflow.plane.brief import PlaneBrief
from e_taxis.workflow.plane.candidate import PlaneCandidate
from e_taxis.workflow.plane.decide import PlaneDecide
from e_taxis.workflow.plane.effect import PlaneEffect
from e_taxis.workflow.plane.grade import PlaneGrade
from e_taxis.workflow.plane.intake import PlaneIntake
from e_taxis.workflow.plane.integrate import PlaneIntegrate
from e_taxis.workflow.plane.law import PlaneLaw
from e_taxis.workflow.plane.loading import PlaneLoading
from e_taxis.workflow.plane.manual import PlaneManual
from e_taxis.workflow.plane.needs import PlaneNeeds
from e_taxis.workflow.plane.patch import PlanePatch
from e_taxis.workflow.plane.queries import PlaneQueries
from e_taxis.workflow.plane.render import PlaneRender
from e_taxis.workflow.plane.sandbox import PlaneSandbox
from e_taxis.workflow.plane.security import PlaneSecurity
from e_taxis.workflow.plane.semantic import PlaneSemantic
from e_taxis.workflow.plane.signals import PlaneSignals
from e_taxis.workflow.plane.snapshot import PlaneSnapshot
from e_taxis.workflow.plane.speckeeper import PlaneSpeckeeper
from e_taxis.workflow.plane.tasks import PlaneTasks
from e_taxis.workflow.services.kwargs import WorkflowKwargs
from e_taxis.workflow.services.plane import PlaneRun
from e_taxis.workflow.services.promote import PlanePromote
from e_taxis.workflow.services.run import WorkflowRun
from e_taxis.workflow.services.step import WorkflowStep

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence

    from pytest_resources import Resources

    from e_taxis.transpile.models.nous import NousTree
    from e_taxis.transpile.models.trial import TrialRun
    from e_taxis.workflow.models.metrics import Finding


class FakeAgent:
    """AgentPort that drives nothing: every session is recorded; an agent in `failing` raises AgentError; `effect`,
    when set, is what the session does to its working directory."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.failing: set[str] = set()
        self.answer = "the agent's answer"
        self.effect: Callable[[Path], object] | None = None

    async def drive(
        self, agent: str, prompt: str, *, cwd: Path, limit: float, readonly: bool = False, steps: int = 0
    ) -> Reply:
        self.calls.append({"agent": agent, "prompt": prompt, "cwd": cwd, "readonly": readonly, "steps": steps})
        if agent in self.failing:
            msg = f"agent {agent!r} refused"
            raise AgentError(msg)
        _ = self.effect and self.effect(cwd)
        return Reply(text=self.answer, tokens=7, cached=3)


class FakeCommand:
    """CommandPort over a table argv-prefix → stdout or exit code: every call recorded; an unmatched argv answers ''."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], dict[str, str]]] = []
        self.answers: dict[tuple[str, ...], str | int] = {}

    async def run(
        self,
        *argv: str,
        limit: float,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        echo: str = "",
    ) -> str:
        self.calls.append((argv, dict(env or {})))
        found = next((answer for prefix, answer in self.answers.items() if argv[: len(prefix)] == prefix), "")
        if isinstance(found, int):
            msg = f"{argv[0]} exited {found}"
            raise CommandError(msg, found, "said before failing")
        return found


class ScriptedNode:
    """NodePort answering a status per step id; `boom` raises; `order` records starts, `peak` the concurrency seen."""

    def __init__(self, statuses: dict[str, Status]) -> None:
        self.statuses = statuses
        self.order: list[str] = []
        self.running = 0
        self.peak = 0

    async def run(self, context: NodeContext) -> Outcome:
        self.order.append(context.spec.id)
        self.running += 1
        self.peak = max(self.peak, self.running)
        await asyncio.sleep(0.01)
        self.running -= 1
        if context.spec.id == "boom":
            msg = "kaput"
            raise RuntimeError(msg)
        return Outcome(status=self.statuses.get(context.spec.id, Status.OK), reason=context.spec.id)


class FakeFence:
    """FencePort whose canary says what `holds` says."""

    def __init__(self) -> None:
        self.holds = True

    async def canary(self, inside: Path, outside: Path) -> bool:
        return self.holds


@pytest.fixture
def nous(resources: Resources, tmp_path: Path) -> Path:
    root = tmp_path / "nous"
    shutil.copytree(resources.path / "transpile", root)
    workflows = root / "core" / "tekton" / "workflows"
    shutil.rmtree(workflows / "converge")
    shutil.copytree(resources.path / "workflow" / "workflows", workflows, dirs_exist_ok=True)
    return root


@pytest.fixture
async def nous_tree(nous: Path) -> NousTree:
    return await GitNous(nous, None).load()


@pytest.fixture
def reader(nous_tree: NousTree) -> WorkflowReader:
    return WorkflowReader(nous_tree)


@pytest.fixture
def flow() -> Callable[..., Workflow]:
    """A workflow from node dicts, as the manifest would declare it."""

    def build(*nodes: dict[str, Any], **extra: Any) -> Workflow:
        return msgspec.convert(
            {"id": "w", "description": "d", "domains": ["tekton"], "nodes": list(nodes), **extra}, Workflow
        )

    return build


@pytest.fixture
def agent() -> FakeAgent:
    return FakeAgent()


@pytest.fixture
def fake_command() -> FakeCommand:
    return FakeCommand()


@pytest.fixture
def fence() -> FakeFence:
    return FakeFence()


@pytest.fixture
def command() -> ShellCommand:
    return ShellCommand({"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"})


@pytest.fixture
def step(command: ShellCommand, agent: FakeAgent) -> WorkflowStep:
    return WorkflowStep(command, agent, limit=30.0, env={"TAXIS_LOCK": "token"})


@pytest.fixture
def state(tmp_path: Path) -> Callable[..., Any]:
    """A run state over `steps` with its own folder and ledger, ready for an executor or a step."""

    async def build(*steps: StepSpec, params: dict[str, str] | None = None, nous: str = "") -> RunState:
        root = tmp_path / "run"
        manifest = RunManifest(
            run_id="r1",
            workflow="w",
            nous=nous or str(tmp_path),
            base_sha="abc1234def",
            started=dt.datetime(2026, 10, 26, tzinfo=dt.UTC),
            graph=GraphSpec(summary="s", steps=steps),
            params=params or {},
        )
        return RunState(manifest=manifest, paths=RunPaths(root), ledger=await JsonlLedger.open(root / "ledger.jsonl"))

    return build


@pytest.fixture
def context() -> Callable[[RunState, str], NodeContext]:
    def build(run: RunState, step: str) -> NodeContext:
        return NodeContext(state=run, spec=run.manifest.graph[step])

    return build


@pytest.fixture
def scripted() -> Callable[[dict[str, Status]], ScriptedNode]:
    return ScriptedNode


@pytest.fixture
def record() -> Callable[..., Any]:
    """Append what a step returned to its run's ledger, as the executor would."""

    async def append(run: RunState, node: str, outcome: Outcome) -> None:
        stamp = run.manifest.started
        await run.ledger.append(
            NodeRun(
                run_id=run.manifest.run_id,
                node=node,
                status=outcome.status,
                started=stamp,
                ended=stamp,
                input_hash="",
                output_hash="",
                metrics=outcome.metrics,
                reason=outcome.reason,
            )
        )

    return append


@pytest.fixture
def lock() -> FlockLock:
    return FlockLock(wait=0.2, poll=0.05)


@pytest.fixture
def workflow_run(command: ShellCommand, agent: FakeAgent, lock: FlockLock) -> WorkflowRun:
    return WorkflowRun(command, agent, lock, JsonlLedger.open, concurrency=4, limit=30.0, reports=Path(".reports"))


@pytest.fixture
def fake_agent_deps(monkeypatch: pytest.MonkeyPatch, agent: FakeAgent) -> FakeAgent:
    """Every `taxis` run drives the fake agent in place of OpenCode."""

    async def fake(deps: Deps) -> FakeAgent:
        return agent

    monkeypatch.setattr(Deps, "PROVIDERS", MappingProxyType({**Deps.PROVIDERS, AgentPort: fake}))
    return agent


@pytest.fixture
def opencode_tree(tmp_path: Path) -> Path:
    """A live OpenCode tree: `builder` drivable (mode all), `scout` a subagent, `orchestrator` the lead; global asks in
    the v2 list form."""
    root = tmp_path / "opencode"
    (root / "agents").mkdir(parents=True)
    (root / "agents" / "builder.md").write_text(
        '---\nmode: all\npermission:\n  edit: allow\n  bash:\n    "*": ask\n    "ls*": allow\n---\nbody\n'
    )
    (root / "agents" / "scout.md").write_text("---\nmode: subagent\n---\nbody\n")
    (root / "agents" / "orchestrator.md").write_text(
        '---\nmode: primary\npermission:\n  bash:\n    "*": ask\n---\nlead\n'
    )
    (root / "opencode.jsonc").write_text(
        '{\n  // global\n  "permissions": [\n'
        '    {"action": "edit", "resource": "*", "effect": "allow"},\n'
        '    {"action": "edit", "resource": ".env*", "effect": "ask"},\n'
        '    {"action": "shell", "resource": "sudo *", "effect": "ask"}\n  ]\n}\n'
    )
    return root


@pytest.fixture
def opencode_agent(fake_command: FakeCommand, fence: FakeFence, opencode_tree: Path, tmp_path: Path) -> OpencodeAgent:
    return OpencodeAgent(
        fake_command,
        fence,
        config=opencode_tree,
        landrun=Path("/opt/landrun"),
        writable=(tmp_path / "cache",),
        environ={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        model="local/m",
    )


@pytest.fixture
def claude_tree(tmp_path: Path) -> Path:
    """A live Claude Code tree: `scout` denies the shell and the web and reaches two MCP servers (one by name, one
    inline); `builder` names its tools as Claude's comma string."""
    root = tmp_path / "claude"
    (root / "agents").mkdir(parents=True)
    (root / "agents" / "scout.md").write_text(
        "---\nname: scout\nmaxTurns: 20\nmcpServers:\n- graph\n- inline:\n    command: x\n"
        "disallowedTools:\n- Bash\n- WebFetch\n---\nbody\n"
    )
    (root / "agents" / "builder.md").write_text("---\nname: builder\ntools: Read, Edit, Bash\n---\nbody\n")
    return root


@pytest.fixture
def claude_agent(fake_command: FakeCommand, fence: FakeFence, claude_tree: Path, tmp_path: Path) -> ClaudeAgent:
    return ClaudeAgent(
        fake_command,
        fence,
        config=claude_tree,
        landrun=Path("/opt/landrun"),
        writable=(tmp_path / "cache",),
        environ={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
    )


@pytest.fixture
def mode_agent(opencode_agent: OpencodeAgent, claude_agent: ClaudeAgent) -> ModeAgent:
    return ModeAgent(opencode_agent, claude_agent)


@pytest.fixture
def held() -> Callable[[Path], Any]:
    """The lock on `path`, held by a second FlockLock for the block: what another run looks like."""

    @asynccontextmanager
    async def hold(path: Path) -> AsyncIterator[str]:
        async with FlockLock(wait=0.0).hold(path, "another run") as token:
            yield token

    return hold


##### DISTILL #####
IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main")
TEMPLATES_V1 = {
    "projects/python/infra/src/e_infra/adapters/http.py": "x = 1\n",
    "projects/python/infra/src/e_infra/adapters/ports.py": "p = 1\n",
    "projects/python/infra/src/e_infra/adapters/thing.py": "class Thing:\n    pass\n",
    "projects/python/infra/src/e_infra/ops/file.py": "f = 1\n",
    "projects/python/infra/src/e_infra/ops/same.py": "s = 1\n",
    "projects/python/infra/prek.toml": "a = 1\n",
    "projects/python/infra/.gitattributes": "* text\n",
    "projects/python/api/Makefile": "lint:\n\t@true\ninfra-check:\n\t@true\n",
    "projects/python/api/pyproject.toml": '[project]\nname = "e-api"\ndependencies = ["psqlpy>=0.1"]\n[tool.ruff]\nline-length = 120\n',
    "projects/python/api/src/e_api/router/x.py": "",
    "projects/python/api/tests/unit/test_x.py": "",
    "stack/rdb/paradedb/compose.yml": "services: {}\n",
    "scripts/release.sh": "",
    "projects/templates.yml": (
        "templates:\n  api:\n    source: projects/python/api\n    package: e_api\n    brand: e-api\n    materials:\n"
        "      - {src: projects/python/infra/prek.toml, dst: prek.toml}\n"
        "      - {src: projects/python/infra/.gitattributes, dst: .gitattributes}\n"
    ),
}
PROJECT_COPY = {
    "README.md": "x\n",
    "src/e_proj/adapters/http.py": "x = 1\n",
    "src/e_proj/adapters/ports.py": "p = 1\n",
    "src/e_proj/ops/file.py": "f = 1\n",
    "src/e_proj/ops/same.py": "s = 1\n",
    "src/e_proj/adapters/__init__.py": "",
    "prek.toml": "a = 1\n",
    "pyproject.toml": '[project]\nname = "e-proj"\ndependencies = []\n[tool.ruff]\nline-length = 120\n',
}
PROJECT_WORK = {
    "pyproject.toml": '[project]\nname = "e-proj"\ndependencies = ["msgspec>=0.1", "psqlpy>=0.1", 7]\n'
    '[dependency-groups]\ntest = ["pytest-resources[serde]>=0.3"]\n[tool.ruff]\nline-length = 100\n',
    "src/e_proj/adapters/http.py": "x = 1\ny = 2\nclass Thing:\n    pass\ndef novel():\n    pass\n",
    "src/e_proj/adapters/postgres.py": "",
    "src/e_proj/ops/file.py": "f = 1\ng = 1\n",
    "src/e_proj/mcp/tools.py": "",
    "src/e_proj/retrieval/hybrid.py": "",
    "src/e_proj/api/router/q.py": "",
    "prek.toml": "a = 2\n",
    "deploy/systemd/paradedb.service": "",
    "deploy/systemd/tei.service": "",
    "deploy/compose.yaml": "services:\n  e-proj: {}\n  redis: {}\n",
    "Makefile": "lint:\n\t@true\ngolden:\n\t@true\n",
    ".github/workflows/nightly.yml": "on: push\n",
    "scripts/bench.py": "",
    "scripts/release.sh": "",
    "tests/bench/test_speed.py": "",
}


@pytest.fixture
def git() -> Callable[..., Awaitable[str]]:
    """git in a repo, as the tests' own hand (identity pinned, no signing)."""

    async def run(repo: Path, *args: str) -> str:
        done = await anyio.run_process(("git", "-C", str(repo), *IDENTITY, *args))
        return done.stdout.decode()

    return run


@pytest.fixture
def tree() -> Callable[[Path, dict[str, str]], None]:
    def write(root: Path, files: dict[str, str]) -> None:
        _ = [(root / path).parent.mkdir(parents=True, exist_ok=True) for path in files]
        _ = [(root / path).write_text(text) for path, text in files.items()]

    return write


@pytest.fixture
def commit(git: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
    """Stage everything, commit, return the new HEAD."""

    async def run(repo: Path, message: str, *more: str) -> str:
        await git(repo, "add", "-A")
        await git(repo, "commit", "-q", "--allow-empty", "-m", message, *more)
        return (await git(repo, "rev-parse", "HEAD")).strip()

    return run


@pytest.fixture
async def repo(tmp_path: Path, git, tree, commit) -> Path:
    """A project: `main` at a base, `feat/x` two commits past it — one with a body, one without."""
    root = tmp_path / "proj"
    root.mkdir()
    await git(root, "init", "-q", "-b", "main")
    tree(root, {"a.py": "x = 1\n"})
    await commit(root, "base")
    await git(root, "switch", "-qc", "feat/x")
    tree(root, {"a.py": "x = 2\ny = 3\n", "conf.yaml": "k: v\n", "logo.png": ""})
    await commit(root, "feat: faster x", "-m", "measured 2x")
    tree(root, {"docs/notes.md": "n\n"})
    await commit(root, "docs: notes")
    tree(root, {"wip.py": "uncommitted\n"})
    return root


@pytest.fixture
async def cores(tmp_path: Path, git, tree, commit) -> tuple[Path, Path, Path, str]:
    """e-arkhetypo at v1 then v2 (ports and file moved), e-nous's lists, and a project copied from v1."""
    templates, harness, project = tmp_path / "e-arkhetypo", tmp_path / "e-nous", tmp_path / "e-proj"
    tree(templates, TEMPLATES_V1)
    await git(tmp_path, "init", "-q", "-b", "main", str(templates))
    v1 = await commit(templates, "v1")
    tree(
        templates,
        {
            "projects/python/infra/src/e_infra/adapters/ports.py": "p = 2\n",
            "projects/python/infra/src/e_infra/ops/file.py": "f = 2\n",
        },
    )
    await commit(templates, "v2")
    tree(
        harness,
        {
            "core/tekton/skills/lang-py-datamodel/references/lib.md": "| x | msgspec |\n",
            "core/tekton/config/mcp.yaml": "serena: {}\n",
            "core/schema.yaml": "{}\n",
            "specs/base.yaml": "{}\n",
        },
    )
    await git(tmp_path, "init", "-q", "-b", "main", str(project))
    tree(project, PROJECT_COPY)
    await commit(project, "init: generated from v1")
    await git(project, "switch", "-qc", "feat/x")
    tree(project, PROJECT_WORK)
    await commit(project, "feat: everything")
    return templates, harness, project, v1


@pytest.fixture
def candidate() -> Callable[..., Candidate]:
    def build(
        ident: str,
        *targets: Target,
        change: Change = Change.UPDATE,
        facts: tuple[str, ...] = (),
        relation: Relation = Relation.IMPROVES,
        replaces: tuple[str, ...] = (),
    ) -> Candidate:
        return Candidate(
            id=ident,
            claims=("k1",),
            targets=tuple(msgspec.structs.replace(t, change=change) for t in targets),
            relation=relation,
            sketch=f"sketch {ident}",
            facts=facts,
            replaces=replaces,
        )

    return build


@pytest.fixture
def skill_ref() -> HarnessTarget:
    return HarnessTarget(entity=Entity.SKILL, id="algo-py-core", part=HarnessPart.REFERENCE, name="algorithms")


@pytest.fixture
def matrix(resources: Resources) -> VersionMatrix:
    return VersionMatrix(
        eserde.loads((resources.path / "workflow" / "matrix.yaml").read_text(), format=eserde.Format.YAML)
    )


@pytest.fixture
def layout() -> dict[Entity, Path]:
    return {
        Entity.SKILL: Path("core/tekton/skills"),
        Entity.AGENT: Path("core/tekton/agents"),
        Entity.COMMAND: Path("core/tekton/commands"),
        Entity.WORKFLOW: Path("core/tekton/workflows"),
    }


@pytest.fixture
def grader_for(command: ShellCommand, matrix: VersionMatrix, layout: dict[Entity, Path]) -> Callable[..., DistillGrade]:
    def build(harness: Path, blueprint: Path, ref: str = "") -> DistillGrade:
        return DistillGrade(
            command,
            matrix,
            harness=harness,
            blueprint=blueprint,
            layout=layout,
            scope=("core", "specs/tekton"),
            ref=ref,
        )

    return build


@pytest.fixture
async def harness(nous: Path, tree, git, commit) -> Path:
    """The e-nous copy as a git checkout where `awa` is stated in four places — one of them only as `awa-pg` — and
    `await` (no word match) in another; plus a file outside the doctrine scope."""
    tree(
        nous,
        {
            "core/tekton/skills/sys-gen-scaling/references/lib.md": "| queue | awa |\n",
            "core/tekton/skills/arch-py-events/instructions.md": "Durable jobs: Awa.\n",
            "core/tekton/skills/test-py-tdd/references/lib.md": "\n" * 11 + "| jobs | `awa-pg` fixtures |\n",
            "core/tekton/skills/test-py-tdd/evals/case.md": "awa\n",
            "core/tekton/skills/conc-py-async/instructions.md": "always await it\n",
            "core/tekton/config/queue.yaml": "engine: awa\n",
            "core/tekton/stack.yaml": "queue: awa\n",
            "specs/tekton/legacy.yaml": "engine: awa\n",
            "docs/history.md": "awa\n",
        },
    )
    await git(nous, "init", "-q", "-b", "main")
    await commit(nous, "nous")
    return nous


@pytest.fixture
def rundir(tmp_path: Path) -> Path:
    return tmp_path / "run"


@pytest.fixture
def answer(rundir: Path) -> Callable[[str, Any], None]:
    """An agent step's answer in the run's folder, as its out.md would hold it (prose, then a fenced JSON block)."""

    def write(node: str, value: Any) -> None:
        out = rundir / "nodes" / node / "out.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f"Thinking…\n```json\n{msgspec.json.encode(value).decode()}\n```\n")

    return write


##### PLANE #####
class FakeScanner:
    """ScannerPort that scans nothing: every call recorded (the LLM endpoint too); it answers `findings`, score 7."""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, str]] = []
        self.llms: list[Endpoint | None] = []
        self.findings: list[Finding] = []

    async def scan(self, folder: Path, source: str, llm: Endpoint | None = None) -> ScanResult:
        self.calls.append((folder, source))
        self.llms.append(llm)
        return ScanResult(scanner=f"fake@{source.rpartition('@')[2]}", score=7, findings=tuple(self.findings))


class FakeProvider:
    """ProviderPort that resolves every tier to a fake endpoint named after it; `tiers` records the asks."""

    def __init__(self) -> None:
        self.tiers: list[str] = []

    async def endpoint(self, nous: Path, tier: str) -> Endpoint:
        self.tiers.append(tier)
        return Endpoint(base_url="http://fake/v1", key="k", model=tier, openai_url="http://fake/oai")


class EchoRunner:
    """RunnerPort answering its system context then the prompt: a check on the skill's text passes only with it."""

    def __init__(self) -> None:
        self.systems: list[str] = []

    async def complete(self, endpoint: Endpoint, prompt: str, *, system: str = "") -> Reply:
        self.systems.append(system)
        return Reply(text=f"{system}\n{prompt}", tokens=2)


class FakeCoder:
    """CoderPort: `loads` is prompt → the skills a session loads; `refusals` is prompt → the errors its next sessions
    raise, in order. Every sandbox (flat, root) and probe recorded."""

    def __init__(self) -> None:
        self.loads: dict[str, frozenset[str]] = {}
        self.refusals: dict[str, list[str]] = {}
        self.sandboxes: list[tuple[Path, Path]] = []
        self.probes: list[tuple[str, ProbeMode]] = []

    async def sandbox(self, flat: Path, root: Path) -> Mapping[str, str]:
        self.sandboxes.append((flat, root))
        return {"SANDBOX": str(root)}

    async def probe(self, prompt: str, mode: ProbeMode, *, env: Mapping[str, str], limit: float) -> ProbeResult:
        self.probes.append((prompt, mode))
        if self.refusals.get(prompt):
            raise CommandError(self.refusals[prompt].pop(0))
        return ProbeResult(loaded=self.loads.get(prompt, frozenset()), text="done", tokens=5)


class FakeTrial:
    """TrialService stand-in: answers `report`, records the backend it was asked for."""

    def __init__(self) -> None:
        self.backends: list[str] = []
        self.report = TrialReport(
            backend="claudecode",
            runs=(),
            sights=(TrialSight(entity="skill", probes=("capture",), expected=2, missing=("algo-py-core",)),),
            captured=1,
        )

    async def run(self, nous: Any, backend: str, capture: Any) -> TrialReport:
        self.backends.append(backend)
        return self.report


@pytest.fixture
def scanner() -> FakeScanner:
    return FakeScanner()


@pytest.fixture
def trial() -> FakeTrial:
    return FakeTrial()


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def echo() -> EchoRunner:
    return EchoRunner()


@pytest.fixture
def coder() -> FakeCoder:
    return FakeCoder()


@pytest.fixture
async def plane_nous(resources: Resources, tmp_path: Path, git, commit) -> Path:
    """The mini e-nous as a git checkout the planes can read: the transpiler's fixture, plus the stack that pins the
    scanner, the versioning matrix and the evaluator's ledgers at their new home (`core/tekton/evals/`)."""
    root = tmp_path / "plane"
    shutil.copytree(resources.path / "transpile", root)
    plane = resources.path / "plane"
    (root / "core" / "common").mkdir(parents=True)
    (root / "core" / "versioning").mkdir(parents=True)
    shutil.copy(plane / "stack.yaml", root / "core" / "common" / "stack.yaml")
    shutil.copy(resources.path / "workflow" / "matrix.yaml", root / "core" / "versioning" / "matrix.yaml")
    shutil.copytree(plane / "evals", root / "core" / "tekton" / "evals")
    (root / ".gitignore").write_text(".reports/\n")
    await git(root, "init", "-q", "-b", "main")
    await commit(root, "nous")
    return root


@pytest.fixture
def sandbox(command: ShellCommand) -> GitSandbox:
    return GitSandbox(command)


@pytest.fixture
def plane_nodes(
    scanner: FakeScanner,
    agent: FakeAgent,
    sandbox: GitSandbox,
    trial: FakeTrial,
    command: ShellCommand,
    provider: FakeProvider,
    echo: EchoRunner,
    coder: FakeCoder,
    tmp_path: Path,
) -> dict[str, Any]:
    """Every plane node, real but for the scanner, the agent, the trial, the provider, the runner and the coder;
    HOME is a temp dir; a probe never sleeps before a retry."""
    checker = CheckService()
    render = PlaneRender(RunService(checker), tmp_path / "home")
    evals = NousEvals()
    return {
        "snapshot": PlaneSnapshot(command, sandbox),
        "render": render,
        "law": PlaneLaw(checker),
        "security": PlaneSecurity(scanner, "HIGH"),
        "queries": PlaneQueries(evals),
        "tasks": PlaneTasks(evals),
        "semantic": PlaneSemantic(scanner, "HIGH", provider, "builder"),
        "activation": PlaneActivation(evals, {"claudecode": coder}, runs=2, concurrency=4, limit=5.0, backoff=0.0),
        "effect": PlaneEffect(evals, provider, echo, tier="scout", seeds=2, split="test", concurrency=4),
        "needs": PlaneNeeds(),
        "signals": PlaneSignals(checker),
        "loading": PlaneLoading(trial, HttpCapture()),
        "sandbox": PlaneSandbox(sandbox),
        "intake": PlaneIntake(JsonlLedger.open),
        "manual": PlaneManual(sandbox),
        "brief": PlaneBrief(),
        "integrate": PlaneIntegrate(agent, sandbox, 30.0),
        "speckeeper": PlaneSpeckeeper(agent, sandbox, JsonlLedger.open, 30.0),
        "candidate": PlaneCandidate(render, sandbox),
        "grade": PlaneGrade(render, sandbox),
        "decide": PlaneDecide({"skill": "deepening", "agent": "none"}),
        "patch": PlanePatch(sandbox),
    }


@pytest.fixture
def plane_run(plane_nodes: dict[str, Any], sandbox: GitSandbox, lock: FlockLock) -> PlaneRun:
    return PlaneRun(
        plane_nodes, sandbox, lock, JsonlLedger.open, concurrency=4, reports=Path(".reports"), backend="claudecode"
    )


@pytest.fixture
def plane_deps(monkeypatch: pytest.MonkeyPatch, plane_run: PlaneRun, sandbox: GitSandbox, lock: FlockLock) -> PlaneRun:
    """Every `taxis` run gets the test plane (fake scanner, agent and trial) in place of the real one."""

    async def runs(deps: Deps) -> PlaneRun:
        return plane_run

    async def promotes(deps: Deps) -> PlanePromote:
        return PlanePromote(plane_run, sandbox, lock)

    monkeypatch.setattr(Deps, "PROVIDERS", MappingProxyType({**Deps.PROVIDERS, PlaneRun: runs, PlanePromote: promotes}))
    return plane_run


class ScriptedPlaneNode:
    """PlaneNodePort answering a status per (node, subject); `boom` raises; `seen` records every call."""

    def __init__(self, statuses: dict[tuple[str, str], Status], card: NodeCard) -> None:
        self.statuses = statuses
        self.card = card
        self.seen: list[tuple[str, str]] = []

    async def run(self, context: PlaneContext) -> Outcome:
        self.seen.append((context.spec.id, context.subject))
        if context.spec.id == "boom":
            msg = "kaput"
            raise RuntimeError(msg)
        return Outcome(status=self.statuses.get((context.spec.id, context.subject), Status.OK))


@pytest.fixture
def plane_state(tmp_path: Path) -> Callable[..., Any]:
    """A plane run state over `nodes` and `subjects`, with its own folder and ledger; manifest fields overridable."""

    async def build(*nodes: NodeSpec, subjects: tuple[str, ...] = ("s1", "s2"), **manifest: Any) -> PlaneState:
        root = tmp_path / "plane-run"
        fields: dict[str, Any] = {
            "run_id": "20261027T000000Z-evaluator-skill-abc1234",
            "plane": Plane.EVALUATOR,
            "target": PlaneTarget.SKILL,
            "subjects": subjects,
            "cadence": Cadence.COMMIT,
            "nous": str(tmp_path),
            "tree": str(tmp_path),
            "base_sha": "abc1234def",
            "backend": "claudecode",
            "started": dt.datetime(2026, 10, 27, tzinfo=dt.UTC),
            "graph": PlaneGraph(plane=Plane.EVALUATOR, target=PlaneTarget.SKILL, summary="s", nodes=nodes),
            "places": {subject: f"core/tekton/skills/{subject}" for subject in subjects},
        }
        state = PlaneManifest(**(fields | manifest))
        return PlaneState(manifest=state, paths=PlanePaths(root), ledger=await JsonlLedger.open(root / "ledger.jsonl"))

    return build


@pytest.fixture
def plane_record() -> Callable[..., Any]:
    """Append a node run to a plane state's ledger, as the executor would."""

    async def append(state: PlaneState, node: str, subject: str, outcome: Outcome) -> None:
        stamp = state.manifest.started
        await state.ledger.append(
            NodeRun(
                run_id=state.manifest.run_id,
                node=node,
                subject=subject,
                status=outcome.status,
                started=stamp,
                ended=stamp,
                input_hash="",
                output_hash="",
                metrics=outcome.metrics,
                reason=outcome.reason,
            )
        )

    return append


@pytest.fixture
def plane_context() -> Callable[..., PlaneContext]:
    """A node's context in a plane state: its spec found by id, params overridable."""

    def build(state: PlaneState, node: str, subject: str = "s1", **params: str) -> PlaneContext:
        spec = state.manifest.graph[node]
        return PlaneContext(
            state=state, spec=msgspec.structs.replace(spec, params={**spec.params, **params}), subject=subject
        )

    return build


@pytest.fixture
def scripted_plane() -> type[ScriptedPlaneNode]:
    return ScriptedPlaneNode


##### SWEEP #####
FEED = "https://blog.example/feed/"
PROFILE = "https://www.linkedin.com/in/adavoice"
POST = "https://www.linkedin.com/posts/adavoice_tracing-otel-activity-1111111111111111111-AbCd"
REPO = "https://github.com/spanline/spanline"


class FakeWeb:
    """WebPort over a table url → body: an unknown URL raises SweepError, as a page that does not answer; every
    post is kept (url, fields, files)."""

    def __init__(self, pages: Mapping[str, str]) -> None:
        self.pages = dict(pages)
        self.posted: list[tuple[str, dict[str, str], dict[str, tuple[str, bytes]]]] = []

    async def get(self, url: str) -> str:
        if url not in self.pages:
            msg = f"{url}: 404 Not Found"
            raise SweepError(msg)
        return self.pages[url]

    async def post(self, url: str, *, fields: Mapping[str, str], files: Mapping[str, tuple[str, bytes]]) -> None:
        self.posted.append((url, dict(fields), dict(files)))


@pytest.fixture
def soa_nous(resources: Resources, nous: Path) -> Path:
    """The mini checkout with a soa.yaml: two topics, a LinkedIn voice for all of them, a feed for memory only."""
    shutil.copy(resources.path / "sweep" / "soa.yaml", nous / "core" / "tekton" / "config" / "soa.yaml")
    return nous


@pytest.fixture
def web_page(resources: Resources) -> str:
    """A project's page: a title, a publish date, text among a script and a style, links relative and repeated."""
    return (resources.path / "sweep" / "page.html").read_text()


@pytest.fixture
def profile_page(resources: Resources) -> str:
    """A public LinkedIn profile, hand-authored in its real shape: a JSON-LD @graph of the author's posts (two in a
    short window, one older), an article, another author's repost, the page and the person."""
    return (resources.path / "sweep" / "profile.html").read_text()


@pytest.fixture
def post_page(resources: Resources) -> str:
    """A LinkedIn post page, hand-authored in its real shape: its SocialMediaPosting with the body and comments —
    another reader's first, then the author's own first comment (the repo link) listed after a later one."""
    return (resources.path / "sweep" / "post.html").read_text()


@pytest.fixture
def feed_xml(resources: Resources) -> str:
    """A real Atom feed (a Bear blog), cut to three entries: 2026-04-30, 2025-12-19, 2025-03-24."""
    return (resources.path / "sweep" / "feed.xml").read_text()


@pytest.fixture
def web(web_page: str, profile_page: str, post_page: str, feed_xml: str) -> FakeWeb:
    """The recorded world: the feed and its newest entry's page, the profile and its newest post, the repo."""
    return FakeWeb(
        {
            FEED: feed_xml,
            "https://karpathy.bearblog.dev/sequoia-ascent-2026/": web_page,
            PROFILE: profile_page,
            POST: post_page,
            REPO: web_page,
        }
    )


@pytest.fixture
def finding() -> Callable[..., SweepFinding]:
    """A finding as an agent would answer it: grounded by default in the project's page (its repo link)."""

    def build(title: str, **fields: Any) -> SweepFinding:
        told: dict[str, Any] = {
            "title": title,
            "kind": FindingKind.TOOL,
            "description": f"{title} exports agent spans.",
            "why": "Observability of agents.",
            "facts": ("OpenTelemetry exporter",),
            "links": (REPO,),
            "sources": (POST,),
            "published_at": "2026-10-27",
            "relevance": 3,
            "via": "search",
        }
        return SweepFinding(**(told | fields))

    return build


@pytest.fixture
def web_deps(monkeypatch: pytest.MonkeyPatch, web: FakeWeb) -> FakeWeb:
    """Every `taxis` run reads the recorded world in place of the web."""

    async def fake(deps: Deps) -> FakeWeb:
        return web

    monkeypatch.setattr(Deps, "PROVIDERS", MappingProxyType({**Deps.PROVIDERS, WebPort: fake}))
    return web


##### SOA-ASSESS #####
NOW = dt.datetime(2026, 10, 28, 15, 0, tzinfo=dt.UTC)
MISSING = b'{"message": "Not Found"}'


class RecordedApi:
    """ApiPort over recorded answers; `outage` maps a URL to the transport error it fails with."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._index: dict[str, dict[str, Any]] = msgspec.json.decode((root / "index.json").read_bytes())
        self.outage: dict[str, str] = {}

    async def get(self, url: str) -> Fetched:
        match (self.outage.get(url), self._index.get(url)):
            case (str() as error, _):
                return Fetched(url=url, status=0, error=error)
            case (None, {"status": int() as status, "file": str() as file, "link": str() as link}):
                return Fetched(url=url, status=status, body=(self._root / file).read_bytes(), link=link)
            case _:
                return Fetched(url=url, status=404, body=MISSING)


class FakeLab:
    """LabPort: runs for real through the stand-in landrun (no fence), the canary says what `holds` says."""

    def __init__(self, landrun: Path) -> None:
        self._fence = LandrunFence(landrun)
        self.holds = True

    async def run(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str],
        cwd: Path,
        writable: Sequence[Path],
        ports: Sequence[int],
        limit: float,
        network: bool = False,
    ) -> TrialRun:
        return await self._fence.run(
            argv, env=env, cwd=cwd, writable=writable, ports=ports, limit=limit, network=network
        )

    async def canary(self, inside: Path, outside: Path) -> bool:
        return self.holds


@pytest.fixture
def now() -> dt.datetime:
    return NOW


@pytest.fixture
def api(resources: Resources) -> RecordedApi:
    return RecordedApi(resources.path / "assess" / "http")


@pytest.fixture
def outage(api: RecordedApi) -> dict[str, str]:
    """The URLs the recorded API fails to reach, each with its transport error: filled by the test."""
    return api.outage


@pytest.fixture
def landrun(resources: Resources) -> Path:
    return resources.path / "landrun" / "landrun"


@pytest.fixture
def lab(landrun: Path) -> FakeLab:
    return FakeLab(landrun)


@pytest.fixture
def leaky_lab(landrun: Path) -> FakeLab:
    """A lab whose canary says the fence does not hold."""
    leaky = FakeLab(landrun)
    leaky.holds = False
    return leaky


##### HARNESS #####
class WalkingHarness:
    """HarnessPort that walks `demo` the way a coder would: each step through `WorkflowRun.one`, the agent's answer
    kept as given — or, `idle`, walks nothing."""

    def __init__(
        self,
        runner: WorkflowRun,
        nous: Path,
        *,
        idle: bool = False,
        steps: tuple[str, ...] = ("first", "echo", "think", "last"),
    ) -> None:
        self.runner, self.nous, self.idle, self.steps = runner, nous, idle, steps
        self.seen: list[tuple[str, dict[str, str], tuple[str, ...]]] = []

    async def run(self, workflow: str, args: Mapping[str, str], actors: tuple[str, ...], *, cwd: Path) -> str:
        self.seen.append((workflow, dict(args), actors))
        rundir, source = cwd / args["rundir"], GitNous(self.nous, None)
        given = {key: value for key, value in args.items() if key not in {"rundir", "nous"}}
        answer = cwd / "answer.md"
        answer.write_text("thought\n")
        steps = () if self.idle else self.steps
        _ = [
            await self.runner.one(source, workflow, step, given, rundir, answer=answer if step == "think" else None)
            for step in steps
        ]
        return "walked"


@pytest.fixture
def walking(workflow_run: WorkflowRun, nous: Path) -> WalkingHarness:
    return WalkingHarness(workflow_run, nous)


@pytest.fixture
def standing(workflow_run: WorkflowRun, nous: Path) -> WalkingHarness:
    return WalkingHarness(workflow_run, nous, idle=True)


@pytest.fixture
def writing(workflow_run: WorkflowRun, nous: Path) -> WalkingHarness:
    """A harness walking `fanned`: its one command step."""
    return WalkingHarness(workflow_run, nous, steps=("write",))


##### KWARGS #####
class FakeChat:
    """ChatPort: `answers` per tier (the model name); a tier in `down` raises; every request kept."""

    def __init__(self) -> None:
        self.answers: dict[str, dict[str, Any]] = {}
        self.down: set[str] = set()
        self.asked: list[tuple[str, str, str, Mapping[str, Any]]] = []

    async def structured(
        self, endpoint: Endpoint, system: str, user: str, schema: Mapping[str, Any]
    ) -> tuple[dict[str, Any], int]:
        self.asked.append((endpoint.model, system, user, schema))
        if endpoint.model in self.down:
            msg = f"{endpoint.model} is down"
            raise ProviderError(msg)
        return self.answers.get(endpoint.model, {}), 7


@pytest.fixture
def chat() -> FakeChat:
    return FakeChat()


@pytest.fixture
def kwargs_reader(chat: FakeChat, provider: FakeProvider) -> WorkflowKwargs:
    return WorkflowKwargs(chat, provider, ("local", "scout"))


@pytest.fixture
def declare() -> Callable[..., Workflow]:
    """A workflow declaration from its nodes as plain mappings, the way a manifest reads."""
    return lambda nodes, **rest: msgspec.convert(
        {"id": "w", "description": "Draw it: the rest is detail.", "domains": ["tekton"], "nodes": nodes, **rest},
        Workflow,
    )


@pytest.fixture
def reading_run(command: ShellCommand, agent: FakeAgent, lock: FlockLock, kwargs_reader: WorkflowKwargs) -> WorkflowRun:
    """The workflow runner with a small model reading `query` (the fake chat answers per tier)."""
    return WorkflowRun(
        command,
        agent,
        lock,
        JsonlLedger.open,
        concurrency=4,
        limit=30.0,
        reports=Path(".reports"),
        kwargs=kwargs_reader,
    )


##### STUB API #####
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


@pytest.fixture
def stub() -> Callable[[Mapping[str, Any]], StubApi]:
    return StubApi


##### PLANS #####
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
