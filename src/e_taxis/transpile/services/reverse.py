"""services.reverse: the live tree read back toward the core — who moved each fragment since the last landing.

The base is the landing record (`transpile:<backend>`: a digest per fragment). Each target the projection names is
read under `<home>/<tree>` and classified fragment by fragment (`engine.reverse`): the core moved, the harness
moved (and whether it can fold back, into which core path), or both. Report only: nothing is written, the core
included — absorbing is the next step, on the owner's word."""

from typing import TYPE_CHECKING

import msgspec

from e_taxis.adapters.disk import read_file
from e_taxis.transpile.engine.encode import match_target
from e_taxis.transpile.engine.model import SpecModel
from e_taxis.transpile.engine.reverse import classify_reverse
from e_taxis.transpile.models.report import Report
from e_taxis.transpile.services.check import CheckService
from e_taxis.transpile.services.land import PREFIX
from e_taxis.transpile.services.run import RunService

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.ports.store import StorePort
    from e_taxis.transpile.models.ports import NousPort


##### TYPES #####
class ReverseService:
    """The render it reads the tree against, and the store holding the last landing."""

    __slots__ = ("_runner", "_store")

    def __init__(self, runner: RunService, store: StorePort) -> None:
        self._runner = runner
        self._store = store

    ##### PUBLIC #####

    async def run(self, nous: NousPort, backend: str, home: Path) -> Report:
        tree = await nous.load()
        root = home / RunService.spec(tree, backend)["tree"]
        checked, projection = await self._runner.project(nous, backend, root)
        spec = RunService.spec(checked, backend)
        raw = await self._store.get(f"{PREFIX}{backend}")
        base = None if raw is None else msgspec.json.decode(raw).get("fragments", {})
        findings = [
            finding
            for path in projection.files
            for found in (await read_file(root / path),)
            for finding in classify_reverse(
                spec,
                path,
                match_target(path, spec["targets"]),
                projection.placements[path],
                live=None if found is None else found[0],
                base=base,
            )
        ]
        return Report(stamp=CheckService.stamp(checked, SpecModel(checked.base).version), findings=tuple(findings))
