"""engine.chart: a workflow drawn for a terminal — exact by construction, one line per chain.

A node whose only parent has it as its only child continues that parent's line (`→`); every other node opens a line
and names its parents (`←`). `D` a command runs, `S` an agent reasons; `↻n` marks a loop's body, `?k=v` a condition.
Drawn from the declaration, not the unrolled graph: a loop is one box, never `max` copies. The heading is the
description's first clause. No box-drawing library measured draws these DAGs without a false edge (docs/decisions.md)."""

import re
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from e_taxis.workflow.models.workflow import Node, Workflow

##### DEFAULTS #####
WIDTH: Final[int] = 100
CLAUSE: Final[re.Pattern[str]] = re.compile(r" — |: |\. ")


class WorkflowChart:
    """One declaration as text: its heading, its parameters, its chains."""

    __slots__ = ("_children", "_decl", "_nodes")

    def __init__(self, decl: Workflow) -> None:
        self._decl = decl
        self._nodes = {node.id: node for node in decl.nodes}
        self._children = {
            ident: tuple(node.id for node in decl.nodes if ident in node.depends) for ident in self._nodes
        }

    ##### PRIVATE #####

    def _render_label(self, node: Node) -> str:
        looped = self._decl.loop is not None and node.id in self._decl.loop.nodes
        loop = f" ↻{self._decl.loop.max}" if self._decl.loop is not None and looped else ""
        when = ",".join(f"{key}={'|'.join(values)}" for key, values in node.conditions.items())
        return f"{'D' if node.run else 'S'} {node.id}{loop}{f' ?{when}' if when else ''}"

    def _render_continues(self, ident: str) -> bool:
        """Whether a node rides its parent's line: one parent, and that parent's only child."""
        match self._nodes[ident].depends:
            case (parent,):
                return self._children.get(parent, ()) == (ident,)
            case _:
                return False

    def _render_chain(self, ident: str) -> tuple[str, ...]:
        match self._children[ident]:
            case (child,) if self._render_continues(child):
                return (ident, *self._render_chain(child))
            case _:
                return (ident,)

    def _render_line(self, ident: str) -> str:
        chain = " → ".join(self._render_label(self._nodes[step]) for step in self._render_chain(ident))
        parents = " · ".join(self._nodes[ident].depends)
        return f"  {chain}{f'   ← {parents}' if parents else ''}"

    def _render_heading(self) -> str:
        first = CLAUSE.split(" ".join(self._decl.description.split()), maxsplit=1)[0]
        return first if len(first) <= WIDTH else f"{first[:WIDTH].rsplit(' ', 1)[0]}…"

    ############################################################

    ##### PUBLIC #####

    def render(self) -> str:
        """The heading, the parameters and every chain, in declaration order."""
        params = [f"  params {' · '.join(self._decl.parameters)}"] if self._decl.parameters else []
        lines = [self._render_line(ident) for ident in self._nodes if not self._render_continues(ident)]
        return "\n".join([f"{self._decl.id} — {self._render_heading()}", *params, *lines])
