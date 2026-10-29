"""assess.store: radar-tech's typed artifacts in a run's folder — written and read as models, never as prose.

Deterministic steps write `<rundir>/radar/<name>.json` and read their parents' the same way; the report is
`radar/assess.json`. An agent step answers with a JSON block in its `out.md`; the step after it reads that block back
through its model — a block that does not fit fails the reading step with msgspec's message. Which step answered a
model is the workflow's to say (its output ports), never a step id written here."""

from typing import TYPE_CHECKING, Any

import anyio
import msgspec

from e_taxis.workflow.distill.store import FENCE
from e_taxis.workflow.models.error import AssessError
from e_taxis.workflow.models.run import RunPaths

if TYPE_CHECKING:
    from pathlib import Path

##### DEFAULTS #####
FOLDER: str = "radar"


##### TYPES #####
class AssessStore:
    """The run's artifacts, by name, as models."""

    __slots__ = ("_folder", "_paths")

    def __init__(self, rundir: Path) -> None:
        self._paths = RunPaths(rundir)
        self._folder = rundir / FOLDER

    ##### PUBLIC #####

    @property
    def rundir(self) -> Path:
        return self._paths.root

    async def put(self, name: str, value: object) -> Path:
        await anyio.Path(self._folder).mkdir(parents=True, exist_ok=True)
        path = self._folder / f"{name}.json"
        await anyio.Path(path).write_bytes(msgspec.json.format(msgspec.json.encode(value), indent=2))
        return path

    async def get(self, name: str, kind: Any) -> Any:
        """An artifact read through `kind`."""
        try:
            raw = await anyio.Path(self._folder / f"{name}.json").read_bytes()
        except FileNotFoundError as missing:
            msg = f"no artifact {name}: its step has not run"
            raise AssessError(msg) from missing
        try:
            return msgspec.json.decode(raw, type=kind)
        except msgspec.ValidationError as bad:
            msg = f"artifact {name} does not fit its model: {bad}"
            raise AssessError(msg) from bad

    async def agent(self, node: str, kind: Any) -> Any:
        """An agent step's answer: the last JSON block of its out.md, read through `kind`."""
        try:
            text = await anyio.Path(self._paths.out(node)).read_text()
        except FileNotFoundError as missing:
            msg = f"step {node} left no answer"
            raise AssessError(msg) from missing
        blocks = FENCE.findall(text)
        try:
            return msgspec.json.decode(blocks[-1] if blocks else text.strip(), type=kind)
        except (msgspec.ValidationError, msgspec.DecodeError) as bad:
            msg = f"step {node}'s answer does not fit {getattr(kind, '__name__', kind)}: {bad}"
            raise AssessError(msg) from bad
