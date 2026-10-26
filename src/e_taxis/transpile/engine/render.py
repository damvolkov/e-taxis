"""engine.render: one spec over one core → placements, in declaration order — the generic row engine.

No backend is named here. A persona row reads a slot of the facet's layers, an instanced row a field of each
instance (sorted by id), a config row a dotted path of the facet's modules, `native.` or a constant. Its `via`
runs left to right through the combinators and the backend's named transforms; `each` fans a mapping out into
one placement per child. `to` binds `{id}`, `{name}` (the `each` variable), every binding and any `{a.b}` core path.
An absent value places nothing; a present one — null included — runs its `via` (so `falsy` can stand in for it) and
places nothing only when it ends as None. A `required` row with an empty value refuses the render.
Pure: no I/O, the same inputs give the same placements."""

import re
from collections.abc import Callable, Iterator, Mapping
from functools import partial, reduce
from pathlib import PurePosixPath
from typing import Any, Final

from e_taxis.transpile.engine.combinators import COMBINATORS
from e_taxis.transpile.engine.context import MISSING, RowContext
from e_taxis.transpile.models.error import RenderError
from e_taxis.transpile.models.placement import GLUE, Placement

##### DEFAULTS #####
HOLE: Final = re.compile(r"\{([A-Za-z_][\w.-]*)\}")
EMPTY: tuple[Any, ...] = (None, "", [], {})
COPY: str = "copy"
### the key of `folders` under which the facet's config folder sits (assets are read from it).
CONFIG: str = "config"

type Transforms = Mapping[str, Callable[[Any, RowContext], Any]]


##### TYPES #####
class SpecRender:
    """The rows of one spec against one read of the core. `folders` is entity → its instance folder (`{id}` in it),
    `blobs` the copyable bytes by path from the checkout root."""

    __slots__ = ("_blobs", "_ctx", "_entities", "_folders", "_slots", "_spec", "_transforms")

    def __init__(
        self,
        spec: Mapping[str, Any],
        *,
        slots: Mapping[str, str],
        ctx: RowContext,
        transforms: Transforms,
        entities: Mapping[str, Mapping[str, Mapping[str, Any]]],
        folders: Mapping[str, str],
        blobs: Mapping[str, bytes],
    ) -> None:
        self._spec = spec
        self._slots = slots
        self._ctx = ctx
        self._transforms = transforms
        self._entities = entities
        self._folders = folders
        self._blobs = blobs

    ##### PRIVATE METHODS #####

    def _run_via(self, value: Any, via: Any, ctx: RowContext) -> Any:
        """The value through each step in order; a step is a name or `{name: params}`."""
        steps = via if isinstance(via, list) else [via] if via is not None else []
        ### the first step always runs (a `falsy` stands in for a null); a later one stops once a step yields None.
        return reduce(
            lambda acc, indexed: None if acc is None and indexed[0] else self._run_step(acc, indexed[1], ctx),
            enumerate(steps),
            value,
        )

    def _run_step(self, value: Any, step: Any, ctx: RowContext) -> Any:
        """One step: a combinator with its params, or a transform of the backend."""
        name, params = (step, None) if isinstance(step, str) else next(iter(step.items()))
        match (name in COMBINATORS, name in self._transforms):
            case (True, _):
                return COMBINATORS[name](value, params, ctx)
            case (_, True):
                return self._transforms[name](value, ctx)
            case _:
                msg = f"`{name}` is neither a combinator nor a transform of {self._spec['backend']}"
                raise RenderError(msg)

    def _run_to(self, to: str, section: Mapping[str, Any], ctx: RowContext, each: Mapping[str, str]) -> tuple[str, str]:
        """`<target>#<fragment>` with every hole bound: the `each` variable, a binding, else a core path."""
        target, _, fragment = to.partition("#")
        fill = partial(self._run_fill, bound={**ctx.bindings, **each}, ctx=ctx)
        return (HOLE.sub(fill, target or section.get("target", "")), HOLE.sub(fill, fragment))

    @staticmethod
    def _run_fill(found: re.Match[str], *, bound: Mapping[str, str], ctx: RowContext) -> str:
        """One hole: the `each` variable or a binding, else a core path; an unknown hole stays as written."""
        name = found.group(1)
        match (bound.get(name), ctx.path(name)):
            case (str() as value, _):
                return value
            case (None, value) if value is not MISSING:
                return str(value)
            case _:
                return found.group(0)

    def _run_source(self, row: Mapping[str, Any], kind: str, ctx: RowContext) -> Any:
        match (kind, row.get("from"), row.get("value", MISSING)):
            case (_, None, constant) if constant is not MISSING:
                return ctx.bind(constant) if isinstance(constant, str) else constant
            case ("persona", str() as slot, _):
                return self._slots.get(slot, MISSING)
            case ("instanced", str() as field, _):
                return (ctx.instance or {}).get(field, MISSING)
            case (_, str() as path, _):
                return ctx.path(path)
            case _:
                return MISSING

    def _run_row(
        self, name: str, index: int, row: Mapping[str, Any], section: Mapping[str, Any], ctx: RowContext
    ) -> Iterator[Placement]:
        value = self._run_source(row, section["kind"], ctx)
        sources = (row["from"],) if row.get("from") else ()
        glue = row.get("glue", GLUE)
        empty = value is MISSING or value in EMPTY
        match (empty and row.get("required", False), value is MISSING, row.get("each")):
            case (True, _, _):
                msg = f"{self._spec['backend']} · {name}[{index}]: required `{row.get('from')}` is empty"
                raise RenderError(msg)
            case (_, True, _):
                return
            case (_, _, str()) if not value:
                return
            case (_, _, str() as variable):
                yield from (
                    Placement(
                        *self._run_to(row["to"], section, ctx, {variable: child}), shaped, name, index, sources, glue
                    )
                    for child, item in value.items()
                    if (shaped := self._run_via(item, row.get("via"), ctx)) is not None
                )
            case _:
                shaped = self._run_via(value, row.get("via"), ctx)
                at = self._run_to(row["to"], section, ctx, {})
                yield from self._run_place(at, shaped, name=name, index=index, sources=sources, glue=glue, ctx=ctx)

    def _run_place(
        self,
        at: tuple[str, str],
        value: Any,
        *,
        name: str,
        index: int,
        sources: tuple[str, ...],
        glue: str,
        ctx: RowContext,
    ) -> Iterator[Placement]:
        """One placement — or, for `#copy`, one per file the value lists, beside the target, bytes as they are."""
        target, fragment = at
        match (value, fragment):
            case (None, _):
                return
            case (list() as refs, "copy"):
                folder = self._folders[name].replace("{id}", ctx.bindings["id"])
                yield from (
                    Placement(
                        str(PurePosixPath(target).parent / ref),
                        "",
                        self._blobs[f"{folder}/{ref}"],
                        name,
                        index,
                        sources,
                    )
                    for ref in refs
                )
            case _:
                yield Placement(target, fragment, value, name, index, sources, glue)

    def _run_section(self, name: str, section: Mapping[str, Any]) -> Iterator[Placement]:
        rows = list(enumerate(section.get("rows", [])))
        match section["kind"]:
            case "instanced":
                instances = self._entities.get(name, {})
                yield from (
                    placement
                    for ident in sorted(instances)
                    for ctx in (self._ctx.per(instances[ident], ident),)
                    for index, row in rows
                    for placement in self._run_row(name, index, row, section, ctx)
                )
            case "config":
                yield from (
                    placement
                    for index, row in rows
                    for placement in self._run_row(name, index, row, section, self._ctx)
                )
                yield from (
                    Placement(
                        asset["to"],
                        "",
                        self._blobs[f"{self._folders[CONFIG]}/{asset['from']}"],
                        name,
                        len(rows) + index,
                    )
                    for index, asset in enumerate(section.get("assets", []))
                )
            case _:
                yield from (
                    placement
                    for index, row in rows
                    for placement in self._run_row(name, index, row, section, self._ctx)
                )

    ############################################################

    ##### PUBLIC #####

    def run(self) -> tuple[Placement, ...]:
        """Every placement of every ready section, in map order then row order."""
        return tuple(
            placement
            for name, section in self._spec["map"].items()
            if section.get("status", "ready") == "ready"
            for placement in self._run_section(name, section)
        )
