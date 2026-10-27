"""plane.security: SkillSpector over one rendered skill, its findings traced back to core/, the accepted ones dropped.

The scanner is the one the e-nous stack pins (`core/common/stack.yaml`, part `skillspector`: `git+<link>@<pin>`),
static and zero tokens. A finding is placed in core/ where its line reads back: a reference is copied byte for byte,
so its line is the core file's; a SKILL.md line is found, verbatim, in the skill's own core files — the v2 render
keeps no line map, and this is the sound equivalent of v1's origin tracing (a line it cannot find stays at its
rendered place). The findings a human accepted in `core/tekton/config/security.yaml` are dropped by fingerprint and
file; the gate fails on one left at or above `fail`, and every one left is a need."""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import anyio
import eserde

from e_taxis.workflow.models.error import PlaneError
from e_taxis.workflow.models.metrics import Finding, SecurityMetrics
from e_taxis.workflow.models.plane import NodeCard, Role
from e_taxis.workflow.models.run import Outcome, Status
from e_taxis.workflow.models.security import SEVERITY, SecurityBaseline

if TYPE_CHECKING:
    from e_taxis.workflow.models.ports import PlaneContext, ScannerPort

##### DEFAULTS #####
CANDIDATE: str = "candidate"
BASE: str = "base"
STACK: str = "core/common/stack.yaml"
BASELINE: str = "core/tekton/config/security.yaml"
PART: str = "skillspector"
REFERENCES: str = "references/"
SOURCES: tuple[str, ...] = ("*.md", "*.yaml")


##### TYPES #####
class PlaneSecurity:
    """Satisfies PlaneNodePort over a scanner; `fail` is the lowest severity that turns the gate red."""

    __slots__ = ("_fail", "_scanner")

    card: ClassVar[NodeCard] = NodeCard(
        role=Role.GATE, summary="SkillSpector over the base or candidate render, findings placed in core/"
    )

    def __init__(self, scanner: ScannerPort, fail: str) -> None:
        self._scanner = scanner
        self._fail = SEVERITY[fail]

    ##### PRIVATE METHODS #####

    @staticmethod
    async def _run_source(source: Path) -> str:
        """The scanner's install source, as the stack pins it."""
        stack = eserde.loads(await anyio.Path(source / STACK).read_text(), format=eserde.Format.YAML)
        match (stack.get("parts") or {}).get(PART):
            case {"link": str() as link, "pin": str() as pin}:
                return f"git+{link}@{pin}"
            case _:
                msg = f"{source / STACK}: no pinned {PART} part"
                raise PlaneError(msg)

    @staticmethod
    async def _run_accepted(source: Path) -> SecurityBaseline:
        path = anyio.Path(source / BASELINE)
        match await path.is_file():
            case True:
                return eserde.loads(await path.read_text(), format=eserde.Format.YAML, type=SecurityBaseline)
            case _:
                return SecurityBaseline()

    @staticmethod
    async def _run_lines(core: Path) -> dict[str, list[str]]:
        """Every core file of the skill, by its path inside the skill's folder, as lines."""
        found = [path for pattern in SOURCES async for path in anyio.Path(core).glob(pattern)]
        return {path.name: (await path.read_text()).splitlines() for path in sorted(found)}

    @staticmethod
    def _run_place(finding: Finding, flat: list[str], core: dict[str, list[str]], prefix: str) -> Finding:
        """The finding at its core file and line; at its rendered place when the line does not read back."""
        match finding.path.startswith(REFERENCES):
            case True:
                return Finding(
                    finding.rule,
                    finding.severity,
                    f"{prefix}/{finding.path}",
                    finding.line,
                    finding.detail,
                    finding.fingerprint,
                )
            case _:
                said = flat[finding.line - 1].strip() if 0 < finding.line <= len(flat) else ""
                spot = next(
                    (
                        (name, number)
                        for name, lines in core.items()
                        for number, line in enumerate(lines, 1)
                        if said and line.strip() == said
                    ),
                    None,
                )
                path, line = (f"{prefix}/{spot[0]}", spot[1]) if spot else (finding.path, finding.line)
                return Finding(finding.rule, finding.severity, path, line, finding.detail, finding.fingerprint)

    ############################################################

    ##### PUBLIC #####

    async def run(self, context: PlaneContext) -> Outcome:
        state, tree = context.state, context.param("tree", BASE)
        candidate = tree == CANDIDATE
        folder = (
            (state.paths.candidate(context.subject) if candidate else state.paths.base) / "skills" / context.subject
        )
        match await anyio.Path(folder / "SKILL.md").is_file():
            case False:
                return Outcome(status=Status.SKIP, reason=f"no {tree} render of {context.subject}")
            case _:
                flat = (await anyio.Path(folder / "SKILL.md").read_text()).splitlines()
        source = state.paths.tree(context.subject) if candidate else Path(state.manifest.tree)
        prefix = state.manifest.place(context.subject)
        result = await self._scanner.scan(folder, await self._run_source(source))
        core = await self._run_lines(source / prefix)
        accepted = (await self._run_accepted(source)).accepted.get(context.subject, ())
        placed = tuple(self._run_place(finding, flat, core, prefix) for finding in result.findings)
        findings = tuple(f for f in placed if not any(a.covers(f, prefix) for a in accepted))
        blocking = any(SEVERITY.get(f.severity, 0) >= self._fail for f in findings)
        return Outcome(
            status=Status.FAIL if blocking else Status.OK,
            metrics=SecurityMetrics(
                tree=tree,
                scanner=result.scanner,
                score=result.score,
                findings=findings,
                accepted=len(placed) - len(findings),
            ),
        )
