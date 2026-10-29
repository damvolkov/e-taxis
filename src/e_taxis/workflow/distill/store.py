"""distill.store: reverse-distill's typed artifacts in a run's folder — written and read as models, never as prose.

Deterministic steps write `<rundir>/distill/<name>.json` and read their parents' the same way. An agent step answers
with a JSON block in its `out.md`; the step after it reads that block back through its model — a block that does not
fit is a failed step, not data. Which steps answered a model is the workflow's to say (its output ports), never a
step id written here."""

import re
from typing import TYPE_CHECKING, Any, Final

import anyio
import msgspec

from e_taxis.workflow.models.error import DistillError
from e_taxis.workflow.models.run import RunPaths

if TYPE_CHECKING:
    from pathlib import Path

##### DEFAULTS #####
FENCE: Final[re.Pattern[str]] = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)
FOLDER: str = "distill"


##### TYPES #####
class DistillStore:
    """The run's artifacts, by name, as models, in the run's `folder` (another workflow keeps its own: `radar`)."""

    __slots__ = ("_folder", "_paths")

    def __init__(self, rundir: Path, folder: str = FOLDER) -> None:
        self._paths = RunPaths(rundir)
        self._folder = rundir / folder

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
        """An artifact read through `kind` — a model, or a `tuple[Model, ...]`."""
        path = anyio.Path(self._folder / f"{name}.json")
        try:
            raw = await path.read_bytes()
        except FileNotFoundError as missing:
            msg = f"no artifact {name}: its step has not run"
            raise DistillError(msg) from missing
        try:
            return msgspec.json.decode(raw, type=kind)
        except msgspec.ValidationError as bad:
            msg = f"artifact {name} does not fit its model: {bad}"
            raise DistillError(msg) from bad

    async def agent(self, node: str, kind: Any) -> Any:
        """An agent step's answer: the last JSON block of its out.md, read through `kind`."""
        out = anyio.Path(self._paths.out(node))
        match await out.is_file():
            case False:
                msg = f"step {node} left no answer"
                raise DistillError(msg)
            case _:
                text = await out.read_text()
        blocks = FENCE.findall(text)
        try:
            return msgspec.json.decode(blocks[-1] if blocks else text.strip(), type=kind)
        except (msgspec.ValidationError, msgspec.DecodeError) as bad:
            msg = f"step {node}'s answer does not fit {getattr(kind, '__name__', kind)}: {bad}"
            raise DistillError(msg) from bad
