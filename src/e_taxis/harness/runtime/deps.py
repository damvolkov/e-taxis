"""runtime.deps: injection by declared type — the one place ports meet adapters, built on demand, once per run.

This is the composition root of the hexagon: `SQLiteAdapter`, `FileCatalog`, `ShellProbe`, the runner, the
downloader and every primitive adapter are named here and nowhere else; the store is wrapped in the undo
journal and handed on as a bare `StorePort` (and as the services' recorder), the catalog and the probe reach
the services as their ports, the primitives as one frozen table Primitive → adapter. The run's home, Claude's
config dir and the environment (gate secrets are named by the catalog, so they are read here, once) are resolved
here too. `Inject[T]` marks a parameter cyclopts must not parse (and `--help` must not show); the launcher resolves
each one from its type through `Deps.PROVIDERS`, a frozen table type → builder. A builder runs at most once
per run, and every resource it opens enters the run's exit stack, so edges close in reverse on the way out.
A command that never asks for the store never opens sqlite. Adding an injectable is one builder and one row in the table."""

import os
import sys
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AsyncExitStack
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, ClassVar, TypeVar, cast

import anyio
from cyclopts import Parameter
from rich.console import Console

from e_taxis.adapters.catalog import FileCatalog
from e_taxis.adapters.downloader import WreqDownloader
from e_taxis.adapters.ports import StorePort
from e_taxis.adapters.primitives.binary import BinaryPrimitive
from e_taxis.adapters.primitives.compose import ComposePrimitive
from e_taxis.adapters.primitives.file import FilePrimitive
from e_taxis.adapters.primitives.mcp import McpPrimitive
from e_taxis.adapters.primitives.npm import NpmPrimitive
from e_taxis.adapters.primitives.plugin import PluginPrimitive
from e_taxis.adapters.primitives.settings import SettingsPrimitive
from e_taxis.adapters.primitives.uv import UvPrimitive
from e_taxis.adapters.probe import ShellProbe
from e_taxis.adapters.runner import ProcessRunner
from e_taxis.adapters.sqlite import SQLiteAdapter
from e_taxis.adapters.undo import EffectUndo
from e_taxis.harness.models.catalog import Primitive
from e_taxis.harness.models.ports import (
    CatalogPort,
    DownloaderPort,
    PrimitivePort,
    ProbePort,
    RunnerPort,
    UndoPort,
)
from e_taxis.harness.runtime.journal import StoreJournal
from e_taxis.harness.runtime.locator import NousLocator
from e_taxis.harness.runtime.settings import TaxisSettings
from e_taxis.harness.services.apply import ApplyService
from e_taxis.harness.services.doctor import DoctorService
from e_taxis.harness.services.plan import PlanService
from e_taxis.harness.services.resolver import ResolverService
from e_taxis.harness.services.uninstall import UninstallService
from e_taxis.harness.services.verify import VerifyService
from e_taxis.infra.settings import settings as st
from e_taxis.infra.state import State
from e_taxis.schedule.adapters.systemd import UserSystemd
from e_taxis.schedule.services.schedule import ScheduleService
from e_taxis.transpile.adapters.capture import HttpCapture
from e_taxis.transpile.adapters.fence import LandrunFence
from e_taxis.transpile.models.ports import CapturePort
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.land import LandService
from e_taxis.transpile.services.reverse import ReverseService
from e_taxis.transpile.services.run import RunService
from e_taxis.transpile.services.trial import TrialService
from e_taxis.workflow.adapters.agent import ClaudeAgent, ModeAgent, OpencodeAgent
from e_taxis.workflow.adapters.api import WreqApi
from e_taxis.workflow.adapters.chat import WreqChat
from e_taxis.workflow.adapters.coder import ClaudeCoder, OpencodeCoder
from e_taxis.workflow.adapters.command import ShellCommand
from e_taxis.workflow.adapters.evals import NousEvals
from e_taxis.workflow.adapters.harness import ClaudeHarness, Harness, HarnessTable, OpencodeHarness
from e_taxis.workflow.adapters.ledger import JsonlLedger
from e_taxis.workflow.adapters.lock import FlockLock
from e_taxis.workflow.adapters.provider import HouseProvider
from e_taxis.workflow.adapters.runner import AnthropicRunner
from e_taxis.workflow.adapters.sandbox import GitSandbox
from e_taxis.workflow.adapters.scanner import SkillspectorScanner
from e_taxis.workflow.adapters.web import WreqWeb
from e_taxis.workflow.assess.bench import AssessBench
from e_taxis.workflow.models.ports import (
    AgentPort,
    ApiPort,
    CommandPort,
    LabPort,
    PlaneNodePort,
    SandboxPort,
    WebPort,
)
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

T = TypeVar("T")
### cyclopts reads `Annotated` metadata but does not unwrap PEP 695 `type` aliases: the classic generic alias is what it sees.
Inject = Annotated[T, Parameter(parse=False)]

type Builder = Callable[[Deps], Awaitable[object]]

### the variable a terminal-started taxis hands its children: the human's mandate (TaxisSettings.taxis_human).
MANDATE: str = "TAXIS_HUMAN"


##### TYPES #####
class Deps:
    """The run's provider: builds what a command declares, caches it for the run, owns nothing past the stack."""

    __slots__ = ("_built", "_stack", "_state")

    def __init__(self, stack: AsyncExitStack, state: State) -> None:
        self._stack = stack
        self._state = state
        self._built: dict[Builder, object] = {}

    ##### PRIVATE METHODS #####

    async def _resolve_state(self) -> State:
        return self._state

    async def _resolve_console(self) -> Console:
        return Console()

    async def _resolve_store(self) -> StoreJournal:
        """The local store behind the undo journal: every command write is revertible by construction."""
        store = await self._stack.enter_async_context(SQLiteAdapter())
        world = await self.resolve(UndoPort)
        journal = StoreJournal(store, world=world, command=self._state.session.command, depth=st.cli.cli_history)
        return await self._stack.enter_async_context(journal)

    async def _resolve_settings(self) -> TaxisSettings:
        return TaxisSettings()

    async def _resolve_locator(self) -> NousLocator:
        return NousLocator(env=(await self.resolve(TaxisSettings)).taxis_nous, cwd=Path.cwd())

    async def _resolve_catalog(self) -> FileCatalog:
        return FileCatalog((await self.resolve(TaxisSettings)).taxis_catalog)

    async def _resolve_probe(self) -> ShellProbe:
        return ShellProbe(timeout=(await self.resolve(TaxisSettings)).taxis_timeout)

    async def _resolve_resolver(self) -> ResolverService:
        return ResolverService(await self.resolve(CatalogPort))

    async def _resolve_plan(self) -> PlanService:
        return PlanService(await self.resolve(ResolverService), await self.resolve(ProbePort))

    async def _resolve_verify(self) -> VerifyService:
        return VerifyService(await self.resolve(ResolverService), await self.resolve(ProbePort))

    async def _resolve_doctor(self) -> DoctorService:
        return DoctorService(await self.resolve(CatalogPort))

    async def _resolve_runner(self) -> ProcessRunner:
        return ProcessRunner()

    async def _resolve_downloader(self) -> WreqDownloader:
        return WreqDownloader(timeout=(await self.resolve(TaxisSettings)).taxis_download_timeout)

    async def _resolve_undo(self) -> EffectUndo:
        return EffectUndo(await self.resolve(RunnerPort), SettingsPrimitive(), FilePrimitive())

    async def _common_primitives(self) -> Mapping[Primitive, PrimitivePort]:
        """One adapter per primitive; `env` is the settings primitive's env merge under its own name."""
        settings, runner = await self.resolve(TaxisSettings), await self.resolve(RunnerPort)
        merge = SettingsPrimitive()
        return MappingProxyType(
            {
                Primitive.BINARY: BinaryPrimitive(await self.resolve(DownloaderPort), runner, settings.taxis_temp),
                Primitive.UV_TOOL: UvPrimitive(runner),
                Primitive.NPM: NpmPrimitive(runner, settings.taxis_npm_prefix),
                Primitive.SETTINGS: merge,
                Primitive.ENV: merge,
                Primitive.FILE: FilePrimitive(),
                Primitive.CLAUDE_MCP: McpPrimitive(runner),
                Primitive.CLAUDE_PLUGIN: PluginPrimitive(runner),
                Primitive.COMPOSE: ComposePrimitive(),
            }
        )

    async def _common_homes(self) -> tuple[Path, Path]:
        """(home, Claude's config dir): `~` and `~/.claude` as this run resolves them."""
        home = Path.home()
        return (home, (await self.resolve(TaxisSettings)).claude_config_dir or home / ".claude")

    async def _resolve_apply(self) -> ApplyService:
        home, claude = await self._common_homes()
        return ApplyService(
            await self.resolve(ResolverService),
            await self.resolve(PlanService),
            await self.resolve(ProbePort),
            await self._common_primitives(),
            await self.resolve(StoreJournal),
            home=home,
            claude=claude,
            environ=os.environ,
        )

    async def _resolve_check(self) -> CheckService:
        return CheckService()

    async def _resolve_run(self) -> RunService:
        return RunService(await self.resolve(CheckService))

    async def _resolve_trial(self) -> TrialService:
        """The fence over the configured landrun; phantoms find their binaries on this process's PATH."""
        landrun = (await self.resolve(TaxisSettings)).taxis_landrun.expanduser()
        return TrialService(await self.resolve(RunService), LandrunFence(landrun), path=os.environ.get("PATH", ""))

    async def _resolve_land(self) -> LandService:
        """The run's store is both the record and the recorder: a landing is one undoable journal entry."""
        journal = await self.resolve(StoreJournal)
        return LandService(await self.resolve(RunService), await self.resolve(RunnerPort), journal, journal)

    async def _resolve_reverse(self) -> ReverseService:
        return ReverseService(await self.resolve(RunService), await self.resolve(StorePort))

    async def _resolve_capture(self) -> HttpCapture:
        return HttpCapture()

    async def _resolve_uninstall(self) -> UninstallService:
        home, claude = await self._common_homes()
        return UninstallService(
            await self.resolve(ResolverService),
            await self.resolve(ProbePort),
            await self._common_primitives(),
            await self.resolve(StoreJournal),
            home=home,
            claude=claude,
        )

    async def _resolve_command(self) -> ShellCommand:
        """Children inherit the environment; from a terminal, outside an agent's session, the human's mandate too
        (`TAXIS_HUMAN`): a workflow you start may run the human commands its steps name."""
        settings = await self.resolve(TaxisSettings)
        human = sys.stdin.isatty() and not settings.taxis_headless
        return ShellCommand({**os.environ, **({MANDATE: "1"} if human else {})})

    async def _resolve_agent(self) -> ModeAgent:
        """Agents routed by their live OpenCode mode: a subagent to Claude Code (`~/.claude`), the rest to OpenCode;
        a read-only one fenced by the trial's own landrun."""
        settings, (_, claude) = await self.resolve(TaxisSettings), await self._common_homes()
        command, landrun = await self.resolve(CommandPort), settings.taxis_landrun.expanduser()
        writable = tuple(path.expanduser() for path in settings.taxis_workflow_writable)
        opencode = OpencodeAgent(
            command,
            LandrunFence(landrun),
            config=settings.taxis_workflow_opencode.expanduser(),
            landrun=landrun,
            writable=writable,
            environ=os.environ,
            model=settings.taxis_workflow_model,
        )
        return ModeAgent(
            opencode,
            ClaudeAgent(
                command, LandrunFence(landrun), config=claude, landrun=landrun, writable=writable, environ=os.environ
            ),
        )

    async def _resolve_harnesses(self) -> HarnessTable:
        """The coders that walk a whole workflow: Claude Code from `~/.claude`, OpenCode from its live tree."""
        settings, (_, claude) = await self.resolve(TaxisSettings), await self._common_homes()
        command, landrun = await self.resolve(CommandPort), settings.taxis_landrun.expanduser()
        writable = tuple(path.expanduser() for path in settings.taxis_workflow_writable)
        fence, limit = LandrunFence(landrun), settings.taxis_workflow_harness_limit
        opencode = OpencodeAgent(
            command,
            fence,
            config=settings.taxis_workflow_opencode.expanduser(),
            landrun=landrun,
            writable=writable,
            environ=os.environ,
            model=settings.taxis_workflow_model,
        )
        agent = ClaudeAgent(command, fence, config=claude, landrun=landrun, writable=writable, environ=os.environ)
        return HarnessTable(
            MappingProxyType(
                {
                    Harness.CLAUDE: ClaudeHarness(command, agent, limit),
                    Harness.OPENCODE: OpencodeHarness(command, opencode, limit),
                }
            )
        )

    async def _resolve_workflow(self) -> WorkflowRun:
        """A run waits for the checkout's lock, saying once on stderr whom it waits for."""
        settings = await self.resolve(TaxisSettings)
        lock = FlockLock(
            settings.taxis_workflow_lock_wait, settings.taxis_lock, say=lambda line: sys.stderr.write(f"{line}\n")
        )
        return WorkflowRun(
            await self.resolve(CommandPort),
            await self.resolve(AgentPort),
            lock,
            JsonlLedger.open,
            concurrency=settings.taxis_workflow_concurrency,
            limit=settings.taxis_workflow_timeout,
            reports=settings.taxis_workflow_reports,
            kwargs=WorkflowKwargs(
                WreqChat(settings.taxis_workflow_kwargs_limit),
                HouseProvider(os.environ),
                settings.taxis_workflow_kwargs_tiers,
            ),
        )

    async def _resolve_web(self) -> WreqWeb:
        return WreqWeb()

    async def _resolve_sandbox(self) -> GitSandbox:
        return GitSandbox(await self.resolve(CommandPort))

    async def _common_measures(self, command: CommandPort, evals: NousEvals) -> dict[str, PlaneNodePort]:
        """The weekly heuristic measures: SkillSpector's LLM stage and the effect A/B on the house tiers, the routing
        probe through the coders, each pointed at a sandbox around the render."""
        settings, (home, claude) = await self.resolve(TaxisSettings), await self._common_homes()
        provider, scanner = HouseProvider(os.environ), SkillspectorScanner(command, settings.taxis_eval_scan_timeout)
        coders = MappingProxyType(
            {"opencode": OpencodeCoder(command, home / ".config"), "claudecode": ClaudeCoder(command, claude)}
        )
        return {
            "semantic": PlaneSemantic(
                scanner, settings.taxis_eval_scan_fail, provider, settings.taxis_eval_semantic_tier
            ),
            "activation": PlaneActivation(
                evals,
                coders,
                runs=settings.taxis_eval_probe_runs,
                concurrency=settings.taxis_eval_probe_concurrency,
                limit=settings.taxis_eval_probe_timeout,
            ),
            "effect": PlaneEffect(
                evals,
                provider,
                AnthropicRunner(tokens=settings.taxis_eval_tokens, limit=settings.taxis_eval_runner_timeout),
                tier=settings.taxis_eval_tier,
                seeds=settings.taxis_eval_effect_seeds,
                split=settings.taxis_eval_effect_split,
                concurrency=settings.taxis_eval_probe_concurrency,
            ),
        }

    async def _common_nodes(self) -> Mapping[str, PlaneNodePort]:
        """Every plane node by the `use` a graph names it with: the planes' one table use → node."""
        settings, command = await self.resolve(TaxisSettings), await self.resolve(CommandPort)
        sandbox, evals, agent = await self.resolve(SandboxPort), NousEvals(), await self.resolve(AgentPort)
        render = PlaneRender(await self.resolve(RunService), Path.home())
        return MappingProxyType(
            {
                "snapshot": PlaneSnapshot(command, sandbox),
                "render": render,
                "law": PlaneLaw(await self.resolve(CheckService)),
                "security": PlaneSecurity(
                    SkillspectorScanner(command, settings.taxis_eval_scan_timeout), settings.taxis_eval_scan_fail
                ),
                "queries": PlaneQueries(evals),
                "tasks": PlaneTasks(evals),
                **(await self._common_measures(command, evals)),
                "needs": PlaneNeeds(),
                "signals": PlaneSignals(await self.resolve(CheckService)),
                "loading": PlaneLoading(await self.resolve(TrialService), await self.resolve(CapturePort)),
                "sandbox": PlaneSandbox(sandbox),
                "intake": PlaneIntake(JsonlLedger.open),
                "manual": PlaneManual(sandbox),
                "brief": PlaneBrief(),
                "integrate": PlaneIntegrate(agent, sandbox, settings.taxis_eval_agent_timeout),
                "speckeeper": PlaneSpeckeeper(agent, sandbox, JsonlLedger.open, settings.taxis_eval_agent_timeout),
                "candidate": PlaneCandidate(render, sandbox),
                "grade": PlaneGrade(render, sandbox),
                "decide": PlaneDecide(settings.taxis_eval_promote),
                "patch": PlanePatch(sandbox),
            }
        )

    async def _common_lock(self) -> FlockLock:
        """The checkout's run lock: waited for, re-entered with the token a parent run handed down."""
        settings = await self.resolve(TaxisSettings)
        return FlockLock(
            settings.taxis_workflow_lock_wait, settings.taxis_lock, say=lambda line: sys.stderr.write(f"{line}\n")
        )

    async def _resolve_plane(self) -> PlaneRun:
        """Plane runs share the workflows' reports root and lock: a nested run re-enters its parent's."""
        settings = await self.resolve(TaxisSettings)
        return PlaneRun(
            await self._common_nodes(),
            await self.resolve(SandboxPort),
            await self._common_lock(),
            JsonlLedger.open,
            concurrency=settings.taxis_eval_concurrency,
            reports=settings.taxis_workflow_reports,
            backend=settings.taxis_eval_backend,
        )

    async def _resolve_promote(self) -> PlanePromote:
        return PlanePromote(await self.resolve(PlaneRun), await self.resolve(SandboxPort), await self._common_lock())

    async def _resolve_schedule(self) -> ScheduleService:
        """The units dir from the settings; the binary the one this process was started as — absolute, not resolved
        through symlinks, so a unit keeps pointing at the stable entrypoint (`~/.local/bin/taxis`), never at PATH."""
        units = (await self.resolve(TaxisSettings)).taxis_schedule_units.expanduser()
        return ScheduleService(
            UserSystemd(await self.resolve(RunnerPort), units), Path(await anyio.Path(sys.argv[0]).absolute())
        )

    async def _resolve_api(self) -> WreqApi:
        """soa-assess's public APIs; the GitHub token, when the settings hold one, signs GitHub's requests only."""
        settings = await self.resolve(TaxisSettings)
        token = settings.gh_token.get_secret_value() if settings.gh_token else ""
        return WreqApi(settings.taxis_assess_timeout, token)

    async def _resolve_lab(self) -> LandrunFence:
        return LandrunFence((await self.resolve(TaxisSettings)).taxis_landrun.expanduser())

    async def _resolve_bench(self) -> AssessBench:
        """The bench's sandboxes start from this process's PATH: the arms find the same toolchain."""
        settings = await self.resolve(TaxisSettings)
        return AssessBench(
            await self.resolve(LabPort), path=os.environ.get("PATH", ""), limit=settings.taxis_assess_limit
        )

    ############################################################

    ##### PUBLIC #####

    PROVIDERS: ClassVar[Mapping[type, Builder]] = MappingProxyType(
        {
            State: _resolve_state,
            Console: _resolve_console,
            StorePort: _resolve_store,
            StoreJournal: _resolve_store,
            TaxisSettings: _resolve_settings,
            NousLocator: _resolve_locator,
            CatalogPort: _resolve_catalog,
            ProbePort: _resolve_probe,
            ResolverService: _resolve_resolver,
            PlanService: _resolve_plan,
            VerifyService: _resolve_verify,
            CheckService: _resolve_check,
            RunService: _resolve_run,
            TrialService: _resolve_trial,
            LandService: _resolve_land,
            ReverseService: _resolve_reverse,
            CapturePort: _resolve_capture,
            DoctorService: _resolve_doctor,
            RunnerPort: _resolve_runner,
            DownloaderPort: _resolve_downloader,
            UndoPort: _resolve_undo,
            ApplyService: _resolve_apply,
            UninstallService: _resolve_uninstall,
            CommandPort: _resolve_command,
            AgentPort: _resolve_agent,
            WorkflowRun: _resolve_workflow,
            HarnessTable: _resolve_harnesses,
            SandboxPort: _resolve_sandbox,
            WebPort: _resolve_web,
            PlaneRun: _resolve_plane,
            PlanePromote: _resolve_promote,
            ScheduleService: _resolve_schedule,
            ApiPort: _resolve_api,
            LabPort: _resolve_lab,
            AssessBench: _resolve_bench,
        }
    )

    async def resolve[K](self, kind: type[K]) -> K:
        """The run's single instance of `kind`, built on first ask."""
        try:
            build = self.PROVIDERS[kind]
        except KeyError:
            msg = f"no provider for {kind.__name__}: add a builder to Deps.PROVIDERS"
            raise TypeError(msg) from None
        match build in self._built:
            case False:
                self._built[build] = await build(self)
            case _:
                pass
        return cast("K", self._built[build])

    async def inject(self, wanted: Mapping[str, type]) -> dict[str, object]:
        """Every non-parsed parameter of a command, by name, resolved from its declared type."""
        return {name: await self.resolve(kind) for name, kind in wanted.items()}
