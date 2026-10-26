"""distill.drift: where the project departs from the blueprint it materialized, as its own checks say.

No diff of our own: a project born from e-arkhetypo carries `make core-check` and `make common-check`. This runs them
read-only and turns their verdict into evidence; a project without them is simply not checked."""

import re
from typing import TYPE_CHECKING, Final

import anyio

from e_taxis.workflow.models.distill import Drift, DriftEvidence
from e_taxis.workflow.models.error import CommandError

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.models.ports import CommandPort

##### DEFAULTS #####
ISSUE: Final[re.Pattern[str]] = re.compile(r"^\s{2}(\S+): (.+)$")
TARGETS: Final[tuple[str, ...]] = ("core-check", "common-check")
MAKE: float = 300.0
SAID: int = 300


##### TYPES #####
class DistillDrift:
    """The project's own drift checks, run and read."""

    __slots__ = ("_command",)

    def __init__(self, command: CommandPort) -> None:
        self._command = command

    ##### PRIVATE METHODS #####

    async def _check_one(self, project: Path, target: str) -> tuple[DriftEvidence, ...]:
        try:
            await self._command.run("make", "-s", "-C", str(project), target, limit=MAKE)
        except CommandError as drifted:
            said = drifted.stdout or str(drifted)
            issues = tuple(
                DriftEvidence(path=found.group(1), template=f"projects/python/core: {found.group(2)}")
                for line in said.splitlines()
                if (found := ISSUE.match(line))
            )
            return issues or (DriftEvidence(path=target, template=" ".join(said.split())[:SAID]),)
        return ()

    ############################################################

    ##### PUBLIC #####

    async def check(self, project: Path) -> Drift:
        makefile = anyio.Path(project / "Makefile")
        text = await makefile.read_text() if await makefile.is_file() else ""
        present = [target for target in TARGETS if re.search(rf"^{target}:", text, re.MULTILINE)]
        found = [issue for target in present for issue in await self._check_one(project, target)]
        return Drift(checked=bool(present), files=tuple(found))
