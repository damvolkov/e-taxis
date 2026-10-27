"""adapters.evals: the evaluator's ledgers, read from the e-nous checkout — brain data, never e-taxis's own.

One Markdown per skill, its cases in the first fenced `toml` block: `core/tekton/evals/queries/<skill>.md` (routing)
and `core/tekton/evals/tasks/<skill>.md` (effect). Until e-nous moves them there (docs/workflow.md §8), a checkout
that has no `core/tekton/evals/` is read at the legacy `ops/evaluator/ledgers/` — the transition, and the only
fallback: a checkout with the new folder is never read at the old one. A skill without a set reads as None; the
place each set was read (or would be) travels with it, so a report says which ledger it judged."""

import re
from pathlib import Path
from typing import Any, Final

import anyio
import eserde
import msgspec

from e_taxis.workflow.models.case import QueryCase, QuerySet, TaskCase, TaskSet
from e_taxis.workflow.models.error import PlaneError

##### DEFAULTS #####
HOME: Final[Path] = Path("core/tekton/evals")
LEGACY: Final[Path] = Path("ops/evaluator/ledgers")
BLOCK: Final[re.Pattern[str]] = re.compile(r"^```toml\n(.*?)^```", re.MULTILINE | re.DOTALL)
QUERIES: str = "queries"
TASKS: str = "tasks"


##### TYPES #####
class NousEvals:
    """Satisfies EvalsPort over the checkout's files."""

    __slots__ = ()

    ##### PRIVATE METHODS #####

    @staticmethod
    async def _common_root(nous: Path) -> Path:
        """`core/tekton/evals/` when the checkout has it, else the legacy ledgers folder."""
        return nous / (HOME if await anyio.Path(nous / HOME).is_dir() else LEGACY)

    @staticmethod
    async def _common_block(path: Path) -> dict[str, Any] | None:
        """The file's first `toml` block, or None when the file is not there."""
        try:
            text = await anyio.Path(path).read_text()
        except FileNotFoundError:
            return None
        match BLOCK.search(text):
            case re.Match() as found:
                return eserde.loads(found.group(1), format=eserde.Format.TOML)
            case _:
                msg = f"{path}: no ```toml block"
                raise PlaneError(msg)

    ############################################################

    ##### PUBLIC #####

    async def queries(self, nous: Path, skill: str) -> tuple[QuerySet | None, str]:
        path = await self._common_root(nous) / QUERIES / f"{skill}.md"
        match await self._common_block(path):
            case None:
                return None, str(path.relative_to(nous))
            case block:
                cases = msgspec.convert(block.get("case", ()), tuple[QueryCase, ...], strict=False)
                return QuerySet(skill=skill, cases=cases), str(path.relative_to(nous))

    async def tasks(self, nous: Path, skill: str) -> tuple[TaskSet | None, str]:
        path = await self._common_root(nous) / TASKS / f"{skill}.md"
        match await self._common_block(path):
            case None:
                return None, str(path.relative_to(nous))
            case block:
                tasks = msgspec.convert(block.get("task", ()), tuple[TaskCase, ...], strict=False)
                return TaskSet(skill=skill, tasks=tasks), str(path.relative_to(nous))
