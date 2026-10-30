"""scripts/materialize: the hardened sed — copy arkhetypo's `e_infra` sections into the project package with a structural rewrite.

libcst parses each source file as real 3.14 syntax (PEP 695 included, verified against the whole
`e_infra` tree) and rewrites *only* the import nodes: `e_infra.<section> → e_taxis.<section>`; every
result is re-parsed with `ast.parse` and scanned for leftovers before it is written. Sections land
under their upstream names — `src/e_taxis/{infra,ops,adapters,processors}` — because materialized code
is part of the project and the wheel ships one root, never a global `infra` or `adapters`. `ops` and
`adapters` are shared homes — the project keeps code beside generated files there — so the write is
never destructive: each run lands what the sections expect, prunes only what its own manifest lists
and the new run does not, and records the rest in `src/e_taxis/.materialized.json` — the generator's
memory, because untracked project code is never its to touch. `make common` materializes into `src/`;
`make common-check` materializes into a throwaway tree under `/tmp` and diffs, so both modes run the
exact same generation path and the drift-check cannot lie about a second one.
"""

import argparse
import ast
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

import libcst as cst

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

ROOT: Path = Path(__file__).resolve().parents[1]
PACKAGE: Final[str] = "e_taxis"
### a standalone repo: the common blueprint lives in the e-arkhetypo checkout beside it; E_COMMON_SRC points elsewhere.
COMMON_SRC: Path = Path(
    os.environ.get("E_COMMON_SRC", ROOT.parent / "e-arkhetypo" / "projects" / "python" / "common" / "src" / "e_infra")
)
SECTIONS: tuple[str, ...] = ("adapters", "infra", "ops", "processors")
DEST: Final[Mapping[str, str]] = MappingProxyType({section: f"{PACKAGE}/{section}" for section in SECTIONS})
### the TUI header belongs to the boilerplate wizard, not to a running service: same topology as the old sed.
### the compose tool belongs to the stack, not to a running service.
EXCLUDES: frozenset[str] = frozenset({"ops/tui.py", "ops/snap.py", "ops/compose.py"})
### `ops` and `adapters` are shared homes: only the manifest owns there — committed code is the project's.
### `infra` and `processors` are dedicated: anything tracked inside is a violation the gate must flag.
SHARED: Final[frozenset[str]] = frozenset({"ops", "adapters"})


##### REWRITE #####
def _parts(name: cst.BaseExpression) -> list[str] | None:
    """A dotted name as its segments; None when the node is not a plain dotted expression."""
    match name:
        case cst.Name(value=only):
            return [only]
        case cst.Attribute(value=inner, attr=cst.Name(value=tail)):
            return None if (prefix := _parts(inner)) is None else [*prefix, tail]
        case _:
            return None


def _dotted(parts: Sequence[str]) -> cst.BaseExpression:
    """The left-nested libcst attribute chain spelling `parts`."""
    match parts:
        case []:
            msg = "empty dotted name"
            raise ValueError(msg)
        case [only]:
            return cst.Name(only)
        case [*init, last]:
            return cst.Attribute(value=_dotted(init), attr=cst.Name(last))


def _reroot_e_infra(name: cst.BaseExpression) -> cst.BaseExpression:
    """`e_infra.infra.x` → `e_taxis.infra.x`; anything outside a materialized section untouched."""
    parts = _parts(name)
    hit = parts is not None and parts[0] == "e_infra" and len(parts) > 1 and parts[1] in SECTIONS
    return _dotted([*DEST[parts[1]].split("/"), *parts[2:]]) if hit else name


def _strip_alias(alias: object) -> object:
    """One `import a.b [as c]` alias, rerooted whatever its wrapper shape; anything else passes through."""
    match alias:
        case cst.ImportAlias(name=name):
            return alias.with_changes(name=_reroot_e_infra(name))
        case cst.Element(node=cst.ImportAlias() as inner):
            return alias.with_changes(node=_strip_alias(inner))
        case _:
            return alias


class _RerootEInfra(cst.CSTTransformer):
    """Import statements only: docstrings and comments keep naming the source of truth verbatim."""

    def leave_Import(  # noqa: N802 — libcst dispatches visitor methods by node class name
        self, _original_node: cst.Import, updated_node: cst.Import
    ) -> cst.Import:
        match updated_node.names:
            case cst.ImportStar():
                return updated_node
            case aliases:
                return updated_node.with_changes(names=[_strip_alias(alias) for alias in aliases])

    def leave_ImportFrom(  # noqa: N802 — libcst dispatches by node class name
        self, _original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        match updated_node.module:
            case None:
                return updated_node
            case module:
                return updated_node.with_changes(module=_reroot_e_infra(module))


##### VALIDATION #####
def _is_e_infra_import(node: ast.AST) -> bool:
    match node:
        case ast.ImportFrom(module=module) | ast.Import(names=[ast.alias(name=module), *_]):
            return bool(module) and module.split(".")[0] == "e_infra"
        case _:
            return False


def rewrite_source(text: str, path: str) -> str:
    """One file rewritten structurally, then hard-validated: parseable by `ast`, free of `e_infra` imports."""
    out = cst.parse_module(text).visit(_RerootEInfra()).code
    match [node for node in ast.walk(ast.parse(out, filename=path)) if _is_e_infra_import(node)]:
        case []:
            return out
        case leftovers:
            msg = f"{path}: unresolved e_infra imports survive the rewrite: {[n.lineno for n in leftovers]}"
            raise SystemExit(msg)


##### MATERIALIZATION #####
MANIFEST: Final[Path] = Path("src/e_taxis/.materialized.json")


def _sources(section: str) -> list[Path]:
    """Every .py of one section, in stable order, minus the excluded files."""
    return [
        path
        for path in sorted((COMMON_SRC / section).rglob("*.py"))
        if "__pycache__" not in path.parts and str(path.relative_to(COMMON_SRC)) not in EXCLUDES
    ]


def _target(section: str, rel: Path) -> Path:
    """Where one upstream file lands under `src`: its section's destination root, same tail."""
    return Path(DEST[section]) / rel.relative_to(section)


def _expected() -> dict[Path, str]:
    """Every file the sections must hold, keyed by its path under `src`, rewritten and ready to write."""
    return {
        _target(section, path.relative_to(COMMON_SRC)): rewrite_source(
            path.read_text(), str(path.relative_to(COMMON_SRC))
        )
        for section in SECTIONS
        for path in _sources(section)
    }


def _manifest(dest_root: Path) -> frozenset[Path]:
    """What the last run materialized, relative to `src`. No manifest is a tree that was never generated:
    the previous set is empty, and this run only writes and remembers. The manifest is what keeps a
    project file beside generated code safe between `make common` runs: git knows only what is committed."""
    listing = dest_root / MANIFEST
    return frozenset(map(Path, json.loads(listing.read_text()) if listing.is_file() else []))


def _recorded(dest_root: Path) -> frozenset[Path]:
    """What git tracks under `src`, relative to it: the drift view's second owner — a stray committed
    inside a dedicated section is a violation the gate flags, and outside a repository it finds nothing."""
    found = subprocess.run(
        ("git", "-C", str(dest_root), "ls-files", "--", "src"), capture_output=True, text=True, check=False
    )
    return frozenset(Path(line).relative_to("src") for line in found.stdout.splitlines())


def _under(dest_root: Path, rel: Path) -> Path:
    return dest_root / "src" / rel


def _materialized(dest_root: Path) -> frozenset[Path]:
    """The files under the section roots that the generator owns: what the manifest lists, plus what git
    tracks in the dedicated sections; in a shared folder a tracked file is the project's, never drift."""
    strays = {rel for rel in _recorded(dest_root) if len(rel.parts) > 1 and rel.parts[1] not in SHARED}
    owned = _manifest(dest_root) | strays
    return frozenset(
        rel
        for rel in owned
        if len(rel.parts) > 1
        and rel.parts[0] == PACKAGE
        and rel.parts[1] in SECTIONS
        and _under(dest_root, rel).is_file()
    )


def materialize(dest_root: Path) -> None:
    """Land the rerooted sections under `dest_root/src`, prune what the last run wrote and this one does
    not, and record what remains — the manifest is the generator's memory between runs."""
    previous = _manifest(dest_root)
    expected = _expected()
    for rel, text in expected.items():
        target = _under(dest_root, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    for stale in previous - set(expected):
        _under(dest_root, stale).unlink(missing_ok=True)
    listing = dest_root / MANIFEST
    listing.parent.mkdir(parents=True, exist_ok=True)
    listing.write_text(json.dumps(sorted(map(str, expected)), indent=1))


def check(dest_root: Path) -> int:
    """Regenerate into a throwaway tree under /tmp and diff against `dest_root`: 0 in sync, 1 on drift."""
    tmp = Path(tempfile.mkdtemp(prefix="e-taxis-materialize-"))
    try:
        materialize(tmp)
        expected = set(_expected())
        actual = _materialized(dest_root)
        issues = [
            *(f"{rel}: missing" for rel in sorted(expected - actual)),
            *(f"{rel}: extra" for rel in sorted(actual - expected)),
            *(
                f"{rel}: stale"
                for rel in sorted(expected & actual)
                if not filecmp.cmp(tmp / "src" / rel, dest_root / "src" / rel, shallow=False)
            ),
        ]
        match issues:
            case []:
                print("✓ materialized e_taxis.{infra,ops,adapters,processors} in sync")
                return 0
            case _:
                print("✗ drift from arkhetypo (run make common):")
                print("\n".join(f"  {issue}" for issue in issues))
                return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: default regenerates `src/`; `--check` is the read-only drift gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="regenerate into a tmp tree under /tmp and diff, exit 1 on drift"
    )
    match parser.parse_args(argv).check:
        case True:
            return check(ROOT)
        case _:
            materialize(ROOT)
            print("✓ materialized arkhetypo e-infra into e_taxis.{infra,ops,adapters,processors}")
            return 0


if __name__ == "__main__":
    sys.exit(main())
