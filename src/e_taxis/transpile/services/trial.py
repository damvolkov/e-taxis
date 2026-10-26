"""services.trial: the render proven in the harness itself — a phantom raised on a sandboxed home, asked what it loaded.

The fence proves it holds (canary) before anything runs inside it. The core is projected into `<home>/<tree>`, the
spec's `trial` plants an established install's state, a fake model listens, and every probe runs fenced: a `capture`
probe reads the requests the harness sent its model, a `command` probe what it printed. Both are reduced to text
(JSON walked for its strings, whitespace folded: a harness may rewrap, it may not reword). Evidence comes from the
render, never from a list: a persona shows every non-empty slot it renders, an instanced entity every id. Nothing
outside the sandbox is written, and only the fake model's port can be reached."""

import json
import os
import shutil
import tempfile
from functools import partial
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING, Any

import anyio

from e_taxis.transpile.models.error import TranspileError
from e_taxis.transpile.models.trial import TrialReport, TrialRun, TrialSight
from e_taxis.transpile.transforms.claudecode import reaches

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from e_taxis.transpile.models.nous import NousTree
    from e_taxis.transpile.models.ports import CapturePort, FencePort, NousPort
    from e_taxis.transpile.models.projection import Projection
    from e_taxis.transpile.services.run import RunService

##### DEFAULTS #####
CAPTURE: str = "capture"
PERSONA: str = "persona"
PROFILE: str = "ghost"
TURN: str = "1"
TIMEOUT: float = 120.0
KEPT: int = 2000


##### TYPES #####
class TrialService:
    """The render it proves, the fence its phantoms run under, and the PATH they find their binaries on."""

    __slots__ = ("_fence", "_path", "_runner")

    def __init__(self, runner: RunService, fence: FencePort, *, path: str) -> None:
        self._runner = runner
        self._fence = fence
        self._path = path

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_bind(text: str, bindings: Mapping[str, str]) -> str:
        """A trial string with every `${name}` bound; an unknown one refuses the trial."""
        try:
            return Template(text).substitute(bindings)
        except (KeyError, ValueError) as exc:
            msg = f"trial placeholder {exc} is bound by no sandbox"
            raise TranspileError(msg) from exc

    @staticmethod
    def _run_servers(tree: NousTree, spec: Mapping[str, Any]) -> str:
        """`${mcp}`: every MCP server the core declares for this backend, switched off — a phantom loads, never serves."""
        servers = tree.config.get(spec["harness"], {}).get("mcp", {}).get("servers", {})
        return json.dumps(
            {name: {"enabled": False} for name, server in servers.items() if reaches(server, spec["backend"])}
        )

    @classmethod
    def _run_walk(cls, node: object) -> Iterator[str]:
        match node:
            case str():
                yield node
            case dict():
                yield from (text for key, value in node.items() for text in (str(key), *cls._run_walk(value)))
            case list():
                yield from (text for value in node for text in cls._run_walk(value))
            case _:
                return

    @classmethod
    def _run_text(cls, raw: str) -> str:
        """Every string a JSON document holds, joined; a text that is not JSON as it is."""
        try:
            return "\n".join(cls._run_walk(json.loads(raw)))
        except ValueError:
            return raw

    @staticmethod
    def _run_fold(text: str) -> str:
        return " ".join(text.split())

    @staticmethod
    def _run_expected(tree: NousTree, spec: Mapping[str, Any], projection: Projection, entity: str) -> tuple[str, ...]:
        """What an entity must show: every non-empty persona text it renders, or every id of its instances."""
        match entity:
            case "persona":
                return tuple(
                    text
                    for placements in projection.placements.values()
                    for placement in placements
                    if placement.section == PERSONA and (text := str(placement.value).strip())
                )
            case _:
                return tuple(sorted(tree.entities.get(entity, {}))) if entity in spec["map"] else ()

    async def _run_probe(
        self,
        probe: Mapping[str, Any],
        *,
        bindings: Mapping[str, str],
        env: Mapping[str, str],
        root: Path,
        capture: CapturePort,
    ) -> tuple[TrialRun, str]:
        """One probe fenced, and the text it showed: the captured requests, or its stdout."""
        match probe.get("serve"):
            case None:
                pass
            case _:
                msg = f"probe `{probe['name']}` serves a process: served probes arrive with the nomos backends"
                raise TranspileError(msg)
        capture.clear()
        run = await self._fence.run(
            [self._run_bind(arg, bindings) for arg in probe["argv"]],
            env=env,
            cwd=Path(bindings["home"]),
            writable=[root],
            ports=[capture.port],
            limit=float(probe.get("timeout") or TIMEOUT),
        )
        shown = (
            "\n".join(self._run_text(body.decode(errors="replace")) for body in capture.bodies())
            if probe["kind"] == CAPTURE
            else self._run_text(run.stdout)
        )
        return TrialRun(
            argv=run.argv, code=run.code, seconds=run.seconds, stdout=run.stdout[-KEPT:], stderr=run.stderr
        ), shown

    async def _run_plant(self, trial: Mapping[str, Any], bindings: Mapping[str, str]) -> None:
        """The established install's state, then the setup commands; overlays arrive with the nomos backends."""
        match trial.get("overlays") or trial.get("setup"):
            case None | []:
                pass
            case _:
                msg = "trial overlays and setup arrive with the nomos backends"
                raise TranspileError(msg)
        _ = [
            await self._run_write(
                Path(self._run_bind(state["path"], bindings)), self._run_bind(state["text"], bindings)
            )
            for state in trial.get("state", [])
        ]

    @staticmethod
    async def _run_write(path: Path, text: str) -> None:
        await anyio.Path(path.parent).mkdir(parents=True, exist_ok=True)
        await anyio.Path(path).write_text(text)

    async def _run_inside(
        self, nous: NousPort, tree: NousTree, spec: Mapping[str, Any], root: Path, capture: CapturePort
    ) -> TrialReport:
        trial = spec["trial"]
        home = root / "home"
        projection = await self._runner.run(nous, spec["backend"], home / spec["tree"])
        async with capture.serve():
            bindings = {
                "home": str(home),
                "tree": str(home / spec["tree"]),
                "llm": capture.url,
                "path": self._path,
                "profile": PROFILE,
                "turn": TURN,
                "mcp": self._run_servers(tree, spec),
            }
            env = {name: self._run_bind(value, bindings) for name, value in trial.get("env", {}).items()}
            await self._run_plant(trial, bindings)
            results = [
                await self._run_probe(probe, bindings=bindings, env=env, root=root, capture=capture)
                for probe in trial["probes"]
            ]
        shown = {probe["name"]: text for probe, (_, text) in zip(trial["probes"], results, strict=True)}
        sights = tuple(
            TrialSight(
                entity=entity,
                probes=tuple(probes),
                expected=len(expected := self._run_expected(tree, spec, projection, entity)),
                missing=tuple(
                    token[:120]
                    for token in expected
                    if self._run_fold(token) not in self._run_fold("\n".join(shown[name] for name in probes))
                ),
            )
            for entity, probes in trial["sees"].items()
        )
        captured = sum(bool(shown[probe["name"]]) for probe in trial["probes"] if probe["kind"] == CAPTURE)
        return TrialReport(
            backend=spec["backend"], runs=tuple(run for run, _ in results), sights=sights, captured=captured
        )

    ############################################################

    ##### PUBLIC #####

    async def run(self, nous: NousPort, backend: str, capture: CapturePort) -> TrialReport:
        """One phantom of `backend`: a fresh sandbox, a proven fence, the render loaded and read back."""
        tree = await nous.load()
        spec = self._runner.spec(tree, backend)
        match spec.get("trial"):
            case None:
                msg = f"{backend}: its spec declares no trial"
                raise TranspileError(msg)
            case _:
                pass
        root = Path(await anyio.to_thread.run_sync(partial(tempfile.mkdtemp, prefix="taxis-trial-")))
        try:
            outside = Path(tempfile.gettempdir()) / f"taxis-canary-{os.getpid()}"
            match await self._fence.canary(root / "canary", outside):
                case False:
                    msg = "the fence does not hold: a write outside the sandbox landed, so no harness is raised"
                    raise TranspileError(msg)
                case _:
                    return await self._run_inside(nous, tree, spec, root, capture)
        finally:
            await anyio.to_thread.run_sync(partial(shutil.rmtree, root, ignore_errors=True))
