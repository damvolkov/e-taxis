"""transpiler.history.view — the history models rendered: one `Plan`, as many faces as the reader needs.

`table` for eyes — rich, ordered, every entity named even at zero; `text` for logs
and narrow pipes; `json` for machines — the changelog persists that same payload.
The model stays pure: nothing here writes knowledge back into `plan.py`, and the
dispatch is a frozen mapping, not a chain of branches.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from difflib import unified_diff
from io import StringIO
from typing import Final, Literal

import msgspec
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from ops.models.entity import Entity
from ops.transpiler.history.plan import Direction, Move, Plan

#: How a report may be rendered: for eyes, for logs, for machines.
type View = Literal["table", "text", "json"]

#: The banner: what you are looking at, before any number scrolls past it.
TITLE: Final = "TRANSPILE PLAN"

#: The sections, in reading order — safe first, the ones needing a human last.
#: The prose lives here and nowhere else: the model carries the verdict, not its meaning.
SECTIONS: Final[tuple[tuple[Direction, str], ...]] = (
    ("core", "core moved · export applies it"),
    ("harness", "harness moved · export would destroy it"),
    ("diverged", "diverged · decide file by file"),
    ("unbased", "unbased · no snapshot to attribute the move to"),
)


def _identity(move: Move) -> str:
    """Who the move is about: entity and instance, one cell."""
    return f"{move.change.entity.value}:{move.change.subentity or move.change.id or '—'}"


def _cells(move: Move) -> tuple[str, ...]:
    return (
        move.direction,
        move.change.kind[0].upper(),
        _identity(move),
        ", ".join(pointer.lstrip("/") for pointer in move.change.pointers) or "—",
        move.change.grade,
        move.change.target,
    )


def _summary(plan: Plan) -> str:
    return (
        f"bump {plan.bump} · {len(plan.moves)} to apply · "
        f"{plan.settled} settled · {len(plan.destructive)} would lose work"
    )


def _specs_effect(plan: Plan) -> str:
    """What the spec moves did to the render, said once for all of them."""
    return (
        "not sealed at this base — the next apply seals them"
        if not plan.sealed
        else "none since the base"
        if not plan.specs
        else "render unchanged · apply only seals them"
        if plan.empty
        else f"render moves {len(plan.moves)} paths (above)"
    )


def _ordered(plan: Plan) -> tuple[Move, ...]:
    return tuple(sorted(plan.moves, key=lambda m: (m.direction, m.change.target)))


def file_diff(left_label: str, right_label: str, left: str, right: str, context: int = 3) -> str:
    """One unified diff between two texts, shared by `plan --diff` and `show --diff`."""
    return "\n".join(
        unified_diff(left.splitlines(), right.splitlines(), left_label, right_label, lineterm="", n=context)
    )


def summary(plans: Mapping[str, Plan]) -> str:
    """Every target in one table — entity rows, a column per harness, `moves · lose` cells — so the
    question an apply asks is read over the whole export, never over the last harness printed."""
    console = Console(record=True, file=StringIO(), color_system=None, width=110)
    grid = Table(title="every target", title_justify="left")
    grid.add_column("entity")
    for name in plans:
        grid.add_column(name, justify="right")
    for entity in Entity:
        cells = [
            (len(touched), sum(1 for m in touched if m.destructive))
            for plan in plans.values()
            for touched in (tuple(m for m in plan.moves if m.change.entity is entity),)
        ]
        any(moves for moves, _ in cells) and grid.add_row(
            entity.value, *(f"{moves} · {lost} lose" if lost else str(moves or "·") for moves, lost in cells)
        )
    grid.row_count or grid.add_row("nothing to apply", *("·" for _ in plans))
    console.print(grid)
    return console.export_text().rstrip()


def table(plan: Plan, content: bool = False) -> str:
    """The form: provenance, every move in a row, every entity counted.

    `content` adds the diff of each move under the tables — the stat first, the
    substance after, the way `git diff --stat` and then hunks read.
    """
    console = Console(record=True, file=StringIO(), color_system=None, width=110)
    console.print(Panel(Text(TITLE, style="bold"), border_style="bold"))
    origin = Table.grid(padding=(0, 2))
    origin.add_column(justify="right")
    origin.add_column()
    origin.add_row("base", str(plan.base or "none — run `op transpiler init`"))
    origin.add_row("live", plan.live)
    origin.add_row("core", plan.core)
    console.print(origin, "\n")

    moves = Table(title="moves", title_justify="left", caption=_summary(plan), caption_style="")
    for column in ("side", "kind", "entity", "slots", "grade", "path"):
        moves.add_column(column)
    for move in _ordered(plan):
        style = "red" if move.destructive else ""
        moves.add_row(*_cells(move), style=style)
    if plan.empty:
        moves.add_row("—", "·", "nothing to apply", "·", "·", "·")
    console.print(moves)

    specs = Table(title="specs", title_justify="left")
    specs.add_column("kind")
    specs.add_column("path")
    for change in plan.specs:
        specs.add_row(change.kind[0].upper(), change.path)
    plan.specs or specs.add_row("·", "no spec moved" if plan.sealed else "—")
    console.print("\n", specs, _specs_effect(plan))

    counts = Table(title="per entity", title_justify="left")
    counts.add_column("entity")
    counts.add_column("moves", justify="right")
    counts.add_column("would lose work", justify="right")
    for entity in Entity:
        touched = tuple(move for move in plan.moves if move.change.entity is entity)
        counts.add_row(entity.value, str(len(touched)), str(sum(1 for m in touched if m.destructive)))
    console.print("\n", counts)

    if content:
        for move in _ordered(plan):
            left, right = move.sides
            hunks = "\n".join(move.diff().splitlines()[2:]) or "(no text change)"
            console.print(f"\n── {left} → {right} · {move.change.target}", style="bold")
            console.print(Syntax(hunks, "diff", background_color="default", word_wrap=True))
    return console.export_text().rstrip()


def text(plan: Plan, content: bool = False) -> str:
    """The same form, plain: no tty, no framework, logs and scripts."""
    lines = [TITLE, ""]
    for line in (
        f"base    {plan.base or 'none — run `op transpiler init`'}",
        f"live    {plan.live}",
        f"core    {plan.core}",
        "",
    ):
        lines.append(line)
    for key, title in SECTIONS:
        moves = plan.section(key)
        lines.append(f"{title}  ({len(moves)})")
        lines += [f"  {move}" for move in moves] or ["  —"]
    lines.append(f"settled  ({plan.settled})")
    lines.append(f"specs  ({len(plan.specs)}) · {_specs_effect(plan)}")
    lines += [f"  {change.kind[0].upper()} {change.path}" for change in plan.specs]
    lines.append(
        "per entity  "
        + " · ".join(
            f"{entity.value} {sum(1 for move in plan.moves if move.change.entity is entity)}" for entity in Entity
        )
    )
    lines.append(_summary(plan))
    if content:
        for move in _ordered(plan):
            lines += [
                "",
                f"── {move.sides[0]} → {move.sides[1]} · {move.change.target}",
                move.diff() or "(no text change)",
            ]
    return "\n".join(lines)


def json(plan: Plan, content: bool = False) -> str:
    """The payload itself — what the changelog will hold, byte for byte.

    No prose, no hunks: the before/after already ride in the model, so a machine can
    diff them itself. `content` is deliberately ignored here.
    """
    return msgspec.json.format(msgspec.json.encode(plan), indent=2).decode()


#: The dispatch: the renderer is chosen, never branched.
RENDERS: Final[Mapping[View, Callable[[Plan, bool], str]]] = {"table": table, "text": text, "json": json}


def render(plan: Plan, view: View = "table", content: bool = False) -> str:
    """One model, the chosen face; `content` asks it to show its work."""
    return RENDERS[view](plan, content)
