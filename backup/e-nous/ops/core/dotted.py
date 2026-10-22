"""core.dotted — read, set and drop a value at a dotted path of nested tables: `search.roles` inside a parsed TOML.

Config files a harness co-owns are owned leaf by leaf, not table by table; the transpiler
projects and merges them through these functions, the trial overlays them the same way.
"""

from __future__ import annotations

from typing import Any


def dotted_get(data: object, dotted: str) -> tuple[bool, Any]:
    """(found, value) at a dotted path; (False, None) the moment a table is missing."""
    head, _, rest = dotted.partition(".")
    match data:
        case dict() if head in data:
            return (True, data[head]) if not rest else dotted_get(data[head], rest)
        case _:
            return False, None


def dotted_set(data: dict, dotted: str, value: object) -> dict:
    """`data` with `value` at a dotted path, the tables on the way created — a new dict, never in place."""
    head, _, rest = dotted.partition(".")
    inner = data.get(head)
    table: dict = dict(inner) if isinstance(inner, dict) else {}
    return data | {head: dotted_set(table, rest, value) if rest else value}


def dotted_drop(data: dict, dotted: str) -> dict:
    """`data` without the leaf at a dotted path — a new dict, never in place; an absent path changes nothing."""
    head, _, rest = dotted.partition(".")
    match data.get(head):
        case _ if head not in data:
            return data
        case dict() as inner if rest:
            return data | {head: dotted_drop(inner, rest)}
        case _ if rest:
            return data
        case _:
            return {key: value for key, value in data.items() if key != head}
