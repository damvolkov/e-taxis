"""services.trial: the render proven in the harness itself — a phantom raised on a sandboxed home, asked what it loaded.

The fence proves it holds (canary) before anything runs inside it. The core is projected into `<home>/<tree>`, the
spec's `trial` plants an established install's state, a fake model listens, and every probe runs fenced: a `capture`
probe reads the requests the harness sent its model, a `command` probe what it printed. Both are reduced to text
(JSON walked for its strings, whitespace folded: a harness may rewrap, it may not reword). Evidence comes from the
render, never from a list: a persona shows every non-empty slot it renders, an instanced entity every id. Nothing
outside the sandbox is written, and only the fake model's port can be reached. A probe that declares `reply` gets a
turn answered instead of a 400, so the hooks of a turn fire; a config module's sight (hooks) expects every `command`
its rows render, shown by an exec trace one probe writes and another reads."""

import json
import os
import shutil
import socket
import tempfile
from collections.abc import Mapping
from functools import partial
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING, Any

import anyio

from e_taxis.transpile.engine.plan import STRUCTURED
from e_taxis.transpile.models.error import TranspileError
from e_taxis.transpile.models.placement import Placement
from e_taxis.transpile.models.trial import TrialReport, TrialRun, TrialSight
from e_taxis.transpile.transforms.backends import reaches

if TYPE_CHECKING:
    from collections.abc import Iterator

    from e_taxis.transpile.models.nous import NousTree
    from e_taxis.transpile.models.ports import CapturePort, FencePort, NousPort
    from e_taxis.transpile.models.projection import Projection
    from e_taxis.transpile.services.run import RunService

##### DEFAULTS #####
CAPTURE: str = "capture"
COMMAND: str = "command"
PERSONA: str = "persona"
PROFILE: str = "ghost"
TURN: str = "1"
TIMEOUT: float = 120.0
KEPT: int = 2000
POLL: float = 0.25


##### UTILITIES #####
def values_trial(node: Any, path: list[str]) -> list[str]:
    """Every string a core path names, `*` walking every key of a mapping."""
    match (path, node):
        case ([], str()):
            return [node]
        case ([], _):
            return []
        case (["*", *rest], Mapping()):
            return [found for child in node.values() for found in values_trial(child, rest)]
        case ([head, *rest], Mapping()) if head in node:
            return values_trial(node[head], rest)
        case _:
            return []


def swap_trial(node: Any, swaps: Mapping[str, str]) -> Any:
    """`node` with every string equal to a swap key replaced, at any depth."""
    match node:
        case str() if node in swaps:
            return swaps[node]
        case Mapping():
            return {key: swap_trial(value, swaps) for key, value in node.items()}
        case list():
            return [swap_trial(value, swaps) for value in node]
        case _:
            return node


def bind_trial(node: Any, bindings: Mapping[str, str]) -> Any:
    """Every `${name}` in every string of `node` bound; values that are not strings stay."""
    match node:
        case str():
            return Template(node).safe_substitute(bindings)
        case Mapping():
            return {key: bind_trial(value, bindings) for key, value in node.items()}
        case list():
            return [bind_trial(value, bindings) for value in node]
        case _:
            return node


def port_trial() -> int:
    """A loopback port nothing listens on now: the one a served phantom binds."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


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

    @classmethod
    def _run_commands(cls, node: object) -> Iterator[str]:
        """Every string held under a `command` key, at any depth."""
        match node:
            case dict():
                yield from (
                    text
                    for key, value in node.items()
                    for text in ([value] if key == COMMAND and isinstance(value, str) else cls._run_commands(value))
                )
            case list():
                yield from (text for value in node for text in cls._run_commands(value))
            case _:
                return

    @classmethod
    def _run_expected(
        cls, tree: NousTree, spec: Mapping[str, Any], projection: Projection, entity: str
    ) -> tuple[str, ...]:
        """What an entity must show: every non-empty persona text it renders, every `command` a config module's rows
        render, or every id of its instances."""
        placements = [placement for found in projection.placements.values() for placement in found]
        match entity:
            case "persona":
                return tuple(
                    text
                    for placement in placements
                    if placement.section == PERSONA and (text := str(placement.value).strip())
                )
            case module if module in tree.config.get(spec["harness"], {}):
                return tuple(
                    dict.fromkeys(
                        command
                        for placement in placements
                        if any(source.partition(".")[0] == module for source in placement.sources)
                        for command in cls._run_commands(placement.value)
                    )
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
        capture.clear()
        capture.answer(probe.get("reply"))
        argv = [self._run_bind(arg, bindings) for arg in probe["argv"]]
        limit = float(probe.get("timeout") or TIMEOUT)
        ports = [capture.port, int(bindings["port"])]
        match probe.get("serve"):
            case None:
                run = await self._fence.run(
                    argv, env=env, cwd=Path(bindings["home"]), writable=[root], ports=ports, limit=limit
                )
            case serve:
                served = [self._run_bind(arg, bindings) for arg in serve]
                async with self._fence.serve(
                    served,
                    env=env,
                    cwd=Path(bindings["home"]),
                    writable=[root],
                    ports=ports,
                    binds=[int(bindings["port"])],
                ):
                    ready = [self._run_bind(arg, bindings) for arg in probe.get("ready") or ["true"]]
                    await self._run_ready(
                        ready, env=env, root=root, home=Path(bindings["home"]), ports=ports, left=limit
                    )
                    run = await self._fence.run(
                        argv, env=env, cwd=Path(bindings["home"]), writable=[root], ports=ports, limit=limit
                    )
                    await self._run_settle(capture, float(probe.get("wait") or 0))
                    await anyio.sleep(float(probe.get("linger") or 0))
        shown = (
            "\n".join(self._run_text(body.decode(errors="replace")) for body in capture.bodies())
            if probe["kind"] == CAPTURE
            else self._run_text(run.stdout)
        )
        return TrialRun(
            argv=run.argv, code=run.code, seconds=run.seconds, stdout=run.stdout[-KEPT:], stderr=run.stderr
        ), shown

    async def _run_ready(
        self, argv: list[str], *, env: Mapping[str, str], root: Path, home: Path, ports: list[int], left: float
    ) -> None:
        """Poll a served probe's `ready` command until it succeeds, or the probe's limit runs out."""
        done = await self._fence.run(argv, env=env, cwd=home, writable=[root], ports=ports, limit=10.0)
        match (done.code == 0, left <= 0):
            case (True, _) | (_, True):
                return
            case _:
                await anyio.sleep(POLL)
                await self._run_ready(argv, env=env, root=root, home=home, ports=ports, left=left - POLL - done.seconds)

    async def _run_settle(self, capture: CapturePort, left: float) -> None:
        """Wait for the served harness to reach the fake model, up to `left` seconds."""
        match bool(capture.bodies()) or left <= 0:
            case True:
                return
            case _:
                await anyio.sleep(POLL)
                await self._run_settle(capture, left - POLL)

    async def _run_plant(
        self,
        tree: NousTree,
        spec: Mapping[str, Any],
        *,
        bindings: Mapping[str, str],
        env: Mapping[str, str],
        root: Path,
        capture: CapturePort,
    ) -> None:
        """An established install's state, the setup commands, then every overlay bending the render to the fake model."""
        trial = spec["trial"]
        _ = [
            await self._run_write(
                Path(self._run_bind(state["path"], bindings)), self._run_bind(state["text"], bindings)
            )
            for state in trial.get("state", [])
        ]
        _ = [
            await self._fence.run(
                [self._run_bind(arg, bindings) for arg in argv],
                env=env,
                cwd=Path(bindings["home"]),
                writable=[root],
                ports=[capture.port],
                limit=TIMEOUT,
            )
            for argv in trial.get("setup", [])
        ]
        _ = [await self._run_overlay(tree, spec, overlay, bindings) for overlay in trial.get("overlays", [])]

    async def _run_overlay(
        self, tree: NousTree, spec: Mapping[str, Any], overlay: Mapping[str, Any], bindings: Mapping[str, str]
    ) -> None:
        """One file bent to the fake model: core values swapped wherever they sit, keys set, lists extended."""
        path = anyio.Path(self._run_bind(overlay["path"], bindings))
        read, encode = STRUCTURED[overlay["format"]]
        data = read(await path.read_bytes()) if await path.is_file() else {}
        config = tree.config.get(spec["harness"], {})
        bind = partial(bind_trial, bindings=bindings)
        swaps = {
            old: bind(new)
            for key, new in (overlay.get("swap") or {}).items()
            for old in (values_trial(config, key[1:].split(".")) if key.startswith("@") else [key])
        }
        swapped = swap_trial(data, swaps)
        extended = {
            key: [*(swapped.get(key) or []), *bind(items)] for key, items in (overlay.get("extend") or {}).items()
        }
        placements = [
            *(Placement("", key, value, "trial", -1) for key, value in {**swapped, **extended}.items()),
            *(Placement("", key, bind(value), "trial", -1) for key, value in (overlay.get("set") or {}).items()),
        ]
        await path.write_bytes(encode("", {}, placements))

    @staticmethod
    async def _run_write(path: Path, text: str) -> None:
        await anyio.Path(path.parent).mkdir(parents=True, exist_ok=True)
        await anyio.Path(path).write_text(text)

    async def _run_inside(
        self, nous: NousPort, tree: NousTree, spec: Mapping[str, Any], root: Path, capture: CapturePort
    ) -> TrialReport:
        trial = spec["trial"]
        home = root / "home"
        projection = await self._runner.run(
            nous, spec["backend"], home / spec["tree"], dict.fromkeys(spec.get("bindings", {}), PROFILE)
        )
        async with capture.serve():
            bindings = {
                "home": str(home),
                "tree": str(home / spec["tree"]),
                "llm": capture.url,
                "path": self._path,
                "profile": PROFILE,
                "turn": TURN,
                "mcp": self._run_servers(tree, spec),
                "port": str(port_trial()),
            }
            env = {name: self._run_bind(value, bindings) for name, value in trial.get("env", {}).items()}
            await self._run_plant(tree, spec, bindings=bindings, env=env, root=root, capture=capture)
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
