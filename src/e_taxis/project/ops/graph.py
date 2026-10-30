"""ops.graph: the dependency analysis of a system — Rust-parsed imports, discovered unit catalog, and the pure graph algebra over them.

Three stages, each a named total: ``imports_of`` reads one file's concrete syntax tree; ``catalog`` walks a project's
``src/`` into units — every module file under an area, at any depth, keyed by its path without ``.py``; ``resolve`` turns unit edges into levels, dependents and lock state. The transitive machinery
lives in ``ops.deps`` and is shared with the stack parser; this module is what is specific to a *system*: the AST
import extraction and the unit catalog.
"""

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

import libcst as cst

from e_taxis.project.models.graph import Unit
from e_taxis.project.ops.deps import closure, levels, reverse

if TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Mapping
    from pathlib import Path

    from e_taxis.project.models.manifest import Common

INIT_NAME: str = "__init__.py"


##### PARSING #####
def _dotted(node: cst.BaseExpression | None) -> str | None:
    match node:
        case None:
            return None
        case cst.Name(value=single):
            return single
        case cst.Attribute(value=inner, attr=cst.Name(value=tail)):
            return None if (prefix := _dotted(inner)) is None else f"{prefix}.{tail}"
        case _:
            return None


def _unit(dotted: str, keys: frozenset[str]) -> str | None:
    """``providers.drivers.store.redis.RedisDriver`` → ``providers/drivers/store/redis``: the longest unit key that prefixes the name."""
    parts = dotted.split(".")
    return next((key for size in range(len(parts), 0, -1) if (key := "/".join(parts[:size])) in keys), None)


def _from_dots(node: cst.ImportFrom) -> tuple[str, ...]:
    base = _dotted(node.module)
    if not base:
        return ()
    match node.names:
        case None | cst.ImportStar():
            return (base,)
        case aliases:
            return (base, *(f"{base}.{name}" for alias in aliases if (name := _dotted(alias.name))))


def _import_dots(node: cst.Import) -> tuple[str, ...]:
    match node.names:
        case None | cst.ImportStar():
            return ()
        case aliases:
            return tuple(name for alias in aliases if (name := _dotted(alias.name)))


class _Refs(cst.CSTVisitor):
    """A libcst dispatch hook — collects the dotted names every import statement mentions."""

    def __init__(self) -> None:
        self.dots: list[str] = []

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:  # noqa: N802 — libcst dispatches by node class name
        self.dots.extend(_from_dots(node))

    def visit_Import(self, node: cst.Import) -> None:  # noqa: N802 — libcst dispatches by node class name
        self.dots.extend(_import_dots(node))


def imports_of(text: str, keys: frozenset[str]) -> frozenset[str]:
    """Every unit of ``keys`` a source file references, read from its concrete syntax tree."""
    visitor = _Refs()
    cst.parse_module(text).visit(visitor)
    return frozenset(unit for dot in visitor.dots if (unit := _unit(dot, keys)))


##### DISCOVERY #####
def _modules(base: Path) -> Iterator[Path]:
    """Every module file under ``base`` at any depth: namespace packages carry no ``__init__``, and one that does is no unit."""
    return (p for p in sorted(base.rglob("*.py")) if "__pycache__" not in p.parts and p.name != INIT_NAME)


def areas_of(src: Path, package: str) -> tuple[str, ...]:
    """The top-level ``src`` directories that are not the app package and hold a module at any depth."""
    return tuple(
        sorted(
            p.name for p in src.iterdir() if p.is_dir() and p.name != package and next(_modules(p), None) is not None
        )
    )


def catalog(src: Path, areas: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    """The unit catalog: each module's key (its path under ``src`` without ``.py``) and the project-relative file it owns."""
    system = src.parent
    return {
        module.relative_to(src).with_suffix("").as_posix(): (module.relative_to(system).as_posix(),)
        for area in areas
        for module in _modules(src / area)
    }


def core_tests(common: Common, common_dir: Path, keys: Collection[str]) -> dict[str, tuple[str, ...]]:
    """The core tests each unit owns, spelled as the destination paths they materialize to in a generated project.

    A unit ``a/b/c`` owns ``test_c*.py`` beside the mirrored path ``tests/unit/<package>/a/b``."""
    root = common_dir / "tests" / "unit" / common.package
    return {key: _owned_tests(root, PurePosixPath(key)) for key in keys}


def _owned_tests(root: Path, key: PurePosixPath) -> tuple[str, ...]:
    return tuple(
        f"tests/unit/{key.parent.as_posix()}/{test.name}"
        for test in sorted((root / key.parent).glob(f"test_{key.name}*.py"))
    )


##### SYSTEM ALGEBRA #####
def forward(
    keys: Collection[str],
    files_of: Mapping[str, Collection[str]],
    imports_of_map: Mapping[str, Collection[str]],
    skip: frozenset[str],
) -> dict[str, frozenset[str]]:
    """Unit→unit imports: what a unit's files reference that is a live unit, never the unit itself."""
    valid = set(keys) - skip
    return {
        key: frozenset(unit for src in files_of[key] for unit in imports_of_map[src] if unit in valid) - {key}
        for key in valid
    }


def pinned(
    root_files: Collection[str],
    imports_map: Mapping[str, Collection[str]],
    deps: Mapping[str, frozenset[str]],
    detach: frozenset[str],
) -> frozenset[str]:
    """Units the service pins: imported by the app root, minus those a detach rule releases, closed forward."""
    direct = {unit for src in root_files for unit in imports_map[src] if unit in deps}
    return closure(direct - detach, deps)


def resolve(
    *,
    keys: Collection[str],
    files_of: Mapping[str, tuple[str, ...]],
    tests_of: Mapping[str, tuple[str, ...]],
    imports_map: Mapping[str, frozenset[str]],
    root_files: Collection[str],
    detach: frozenset[str],
    skip: frozenset[str],
) -> tuple[Unit, ...]:
    """The whole classification: every live unit with its edges, closures, level and lock state, sorted by key."""
    deps = forward(keys, files_of, imports_map, skip)
    back = reverse(deps)
    rank = levels(deps)
    locked = pinned(root_files, imports_map, deps, detach)
    return tuple(
        Unit(
            key=key,
            area=key.partition("/")[0],
            name=key.partition("/")[2],
            files=files_of[key],
            tests=tests_of.get(key, ()),
            deps=tuple(sorted(deps[key])),
            dependents=tuple(sorted(back[key])),
            closure=tuple(sorted(closure(deps[key], deps))),
            level=rank[key],
            locked=key in locked,
            detachable=key in detach,
        )
        for key in sorted(deps)
    )
