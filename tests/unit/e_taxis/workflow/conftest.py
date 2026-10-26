"""tests/unit/e_taxis/workflow: an e-nous copy with test workflows, typed builders, fakes for the agent side, and
the real git repos reverse-distill reads (a project with a feature branch, the two cores).

`nous` is the transpiler's mini checkout (copied per test) with its `converge` replaced by the workflows under
`tests/resources/workflow/workflows`: `demo` (every kind of step), `looped` (a bounded loop) and `broken` (an unknown
agent). Commands run for real (bash, git); agents never do — `FakeAgent` answers, `FakeFence` decides the canary."""

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
from e_taxis.transpile.adapters.nous import GitNous
from e_taxis.workflow.adapters.agent import OpencodeAgent
from e_taxis.workflow.adapters.command import ShellCommand
from e_taxis.workflow.adapters.ledger import JsonlLedger
from e_taxis.workflow.adapters.lock import FlockLock
from e_taxis.workflow.distill.grade import DistillGrade
from e_taxis.workflow.distill.matrix import VersionMatrix
from e_taxis.workflow.engine.reader import WorkflowReader
from e_taxis.workflow.models.distill import Candidate, Change, HarnessPart, HarnessTarget, Relation, Target
from e_taxis.workflow.models.entity import Entity
from e_taxis.workflow.models.error import AgentError, CommandError
from e_taxis.workflow.models.graph import GraphSpec, StepSpec
from e_taxis.workflow.models.ports import AgentPort, NodeContext, RunState
from e_taxis.workflow.models.run import NodeRun, Outcome, Reply, RunManifest, RunPaths, Status
from e_taxis.workflow.models.workflow import Workflow
from e_taxis.workflow.services.run import WorkflowRun
from e_taxis.workflow.services.step import WorkflowStep

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Mapping

    from pytest_resources import Resources

    from e_taxis.transpile.models.nous import NousTree


class FakeAgent:
    """AgentPort that drives nothing: every session is recorded; an agent in `failing` raises AgentError."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.failing: set[str] = set()
        self.answer = "the agent's answer"

    async def drive(
        self, agent: str, prompt: str, *, cwd: Path, limit: float, readonly: bool = False, steps: int = 0
    ) -> Reply:
        self.calls.append({"agent": agent, "prompt": prompt, "cwd": cwd, "readonly": readonly, "steps": steps})
        if agent in self.failing:
            msg = f"agent {agent!r} refused"
            raise AgentError(msg)
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
        return msgspec.convert({"id": "w", "description": "d", "nodes": list(nodes), **extra}, Workflow)

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
    """A live OpenCode tree: `builder` drivable (mode all), `scout` a subagent; global asks in the v2 list form."""
    root = tmp_path / "opencode"
    (root / "agents").mkdir(parents=True)
    (root / "agents" / "builder.md").write_text(
        '---\nmode: all\npermission:\n  edit: allow\n  bash:\n    "*": ask\n    "ls*": allow\n---\nbody\n'
    )
    (root / "agents" / "scout.md").write_text("---\nmode: subagent\n---\nbody\n")
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
    "projects/python/core/src/e_core/adapters/http.py": "x = 1\n",
    "projects/python/core/src/e_core/adapters/ports.py": "p = 1\n",
    "projects/python/core/src/e_core/adapters/thing.py": "class Thing:\n    pass\n",
    "projects/python/core/src/e_core/ops/file.py": "f = 1\n",
    "projects/python/core/src/e_core/ops/same.py": "s = 1\n",
    "projects/python/core/common/prek.toml": "a = 1\n",
    "projects/python/core/common/gitattributes": "* text\n",
    "projects/python/api/Makefile": "lint:\n\t@true\ncore-check:\n\t@true\ncommon-check:\n\t@true\n",
    "projects/python/api/pyproject.toml": '[project]\nname = "e-api"\ndependencies = ["psqlpy>=0.1"]\n[tool.ruff]\nline-length = 120\n',
    "projects/python/api/src/e_api/router/x.py": "",
    "projects/python/api/tests/unit/test_x.py": "",
    "stack/rdb/paradedb/compose.yml": "services: {}\n",
    "scripts/release.sh": "",
    "projects/templates.yml": (
        "templates:\n  api:\n    source: projects/python/api\n    package: e_api\n    brand: e-api\n    materials:\n"
        "      - {src: projects/python/core/common/prek.toml, dst: prek.toml}\n"
        "      - {src: projects/python/core/common/gitattributes, dst: .gitattributes}\n"
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
            "projects/python/core/src/e_core/adapters/ports.py": "p = 2\n",
            "projects/python/core/src/e_core/ops/file.py": "f = 2\n",
        },
    )
    await commit(templates, "v2")
    tree(
        harness,
        {
            "core/tekton/skills/lang-py-datamodel/references/lib.md": "| x | msgspec |\n",
            "core/tekton/config/mcp.yaml": "serena: {}\n",
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
