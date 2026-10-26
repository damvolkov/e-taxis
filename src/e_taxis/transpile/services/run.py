"""services.run: an e-nous core projected for one backend — checked first, rendered, encoded, written to `out`.

A render never runs on a checkout its own law refuses: the check runs first and its blocking findings for the core
or this backend stop the run. Then the spec's rows render against the facet's persona, entities and config, the
placements are encoded per target, and — with `out` — every file lands under it (a pure export: never a live
tree; the live path, with ownership and the journal, is `transpile run --yes`)."""

import tomllib
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

import anyio
import msgspec

from e_taxis.transpile.engine.context import RowContext
from e_taxis.transpile.engine.encode import encode_projection, match_target
from e_taxis.transpile.engine.model import CoreModel
from e_taxis.transpile.engine.plan import land_plan
from e_taxis.transpile.engine.render import CONFIG, SpecRender
from e_taxis.transpile.models.error import CheckError, RenderError
from e_taxis.transpile.models.report import CORE
from e_taxis.transpile.transforms.catalog import CATALOG

if TYPE_CHECKING:
    from collections.abc import Mapping

    from e_taxis.transpile.models.nous import NousTree
    from e_taxis.transpile.models.ports import NousPort
    from e_taxis.transpile.models.projection import Projection
    from e_taxis.transpile.services.check import CheckService


##### TYPES #####
class RunService:
    """The check it passes through, and the backends' transform tables."""

    __slots__ = ("_checker",)

    def __init__(self, checker: CheckService) -> None:
        self._checker = checker

    ##### PRIVATE METHODS #####

    @staticmethod
    def spec(tree: NousTree, backend: str) -> Mapping[str, Any]:
        found = [spec for key, spec in tree.specs.items() if key.rpartition("/")[2] == backend]
        match found:
            case [spec]:
                return spec
            case _:
                msg = f"no spec for backend `{backend}` in {tree.root}: {', '.join(sorted(tree.specs))}"
                raise RenderError(msg)

    @staticmethod
    async def _run_binding(name: str, read: str, root: Path) -> tuple[str, str]:
        """One binding read from the harness's own file under `root`: `<file>#<key>`, TOML or JSON."""
        file, _, key = read.partition("#")
        path = anyio.Path(root / file)
        match await path.is_file():
            case False:
                msg = f"binding `{name}`: {root / file} is not there — the harness has not created it yet"
                raise RenderError(msg)
            case _:
                data = await path.read_bytes()
        tree = tomllib.loads(data.decode()) if file.endswith(".toml") else msgspec.json.decode(data)
        return (name, str(tree[key]))

    @classmethod
    async def bindings(cls, spec: Mapping[str, Any], root: Path) -> dict[str, str]:
        """Every binding the spec declares, read from the harness under `root`."""
        return dict(
            [await cls._run_binding(name, binding["read"], root) for name, binding in spec.get("bindings", {}).items()]
        )

    @staticmethod
    def _run_project(tree: NousTree, spec: Mapping[str, Any], out: str, bindings: Mapping[str, str]) -> Projection:
        core = CoreModel(tree.schema)
        facet = spec["harness"]
        slots = {
            slot: text for layer in core.facets[facet] for slot, text in tree.persona[layer].get("slots", {}).items()
        }
        folders = {
            **{
                name: str(PurePosixPath(entity["path"]).parent)
                for name, entity in tree.schema.get("entities", {}).items()
            },
            CONFIG: f"core/{facet}/config",
        }
        ctx = RowContext(
            config=tree.config.get(facet, {}), native=spec.get("native", {}), bindings={"out": out, **bindings}
        )
        transforms = CATALOG.get(spec["backend"], {})
        placements = SpecRender(
            spec,
            slots=slots,
            ctx=ctx,
            transforms=transforms,
            entities={name: found for name, found in tree.entities.items() if core.entities.get(name) == facet},
            folders=folders,
            blobs=tree.blobs,
        ).run()
        return encode_projection(spec["backend"], out, spec, placements, ctx.bindings)

    @staticmethod
    async def _run_file(target: anyio.Path, data: bytes) -> None:
        await target.parent.mkdir(parents=True, exist_ok=True)
        await target.write_bytes(data)

    @classmethod
    async def _run_write(cls, projection: Projection, out: Path) -> None:
        _ = [await cls._run_file(anyio.Path(out / path), data) for path, data in projection.files.items()]

    ############################################################

    ##### PUBLIC #####

    async def project(
        self,
        nous: NousPort,
        backend: str,
        out: Path,
        bindings: Mapping[str, str] | None = None,
        *,
        live: Path | None = None,
    ) -> tuple[NousTree, Projection]:
        """The checked checkout and its projection for `backend`, `{out}` bound to `out`; the spec's bindings are
        given, or read from the harness's tree (`live`, by default `out` itself). Writes nothing."""
        report = await self._checker.run(nous)
        blocking = [finding for finding in report.blocking if finding.backend in (CORE, backend)]
        match blocking:
            case []:
                pass
            case _:
                msg = f"{len(blocking)} blocking finding(s) for {backend}: run `taxis transpile check` first"
                raise CheckError(msg)
        tree = await nous.load()
        spec = self.spec(tree, backend)
        bound = await self.bindings(spec, live or out) if bindings is None else bindings
        return (tree, self._run_project(tree, spec, str(out), bound))

    async def run(
        self,
        nous: NousPort,
        backend: str,
        out: Path,
        bindings: Mapping[str, str] | None = None,
        *,
        live: Path | None = None,
    ) -> Projection:
        """The projection of `backend` into `out`, written there: a pure export, never a live tree. Bindings are
        given, or read from the harness's live tree (`live`), never from `out`."""
        tree, projection = await self.project(nous, backend, out, bindings, live=live)
        spec = self.spec(tree, backend)
        exported = {
            path: land_plan(
                target.get("format", "file"), data, None, target.get("foreign", []), projection.placements[path]
            )
            for path, data in projection.files.items()
            for target in (match_target(path, spec["targets"]),)
        }
        await self._run_write(replace(projection, files=exported), out)
        return replace(projection, files=exported)
