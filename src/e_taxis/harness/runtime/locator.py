"""runtime.locator: where a command finds the brain — `--nous` when given, else one ladder, the same from any shell.

A valid e-nous checkout holds both `core/schema.yaml` and `specs/base.yaml`. The first rung that yields one wins:
the explicit `--nous` (an invalid one is an error, never a fall-through); TAXIS_NOUS; the nearest ancestor of the
cwd; `<git toplevel of the cwd, or the cwd>/../e-nous`, so e-arkhetypo and e-taxis find the checkout beside them.
None → `NousLocatorError`, naming every rung. What leaves is absolute: a relative `--nous` once broke a sandbox's
symlinks (#20).

Commands declare the parameter as `Nous` (always located) or `ProfileNous` (located only when `--profile` is not
the source); the launcher fills it before the command runs — one place, never a copy per command."""

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Final

import anyio
from cyclopts import Parameter

from e_taxis.harness.models.error import NousLocatorError

##### DEFAULTS #####
MARKERS: Final[tuple[str, ...]] = ("core/schema.yaml", "specs/base.yaml")
SIBLING: Final[str] = "e-nous"
### only makes the flag optional: the launcher fills an absent `--nous` before the call, so no body ever sees it.
UNSET: Final[Path] = Path()

Nous = Annotated[Path, Parameter(name="--nous", show_default=False)]
ProfileNous = Annotated[Path | None, Parameter(name="--nous", show_default=False)]
### the declared annotation → the flag that, given, is the source instead; "" names none: always located.
LOCATED: Final[Mapping[object, str]] = MappingProxyType({Nous: "", ProfileNous: "profile"})


##### TYPES #####
class NousLocator:
    """The ladder over one cwd and the TAXIS_NOUS setting."""

    __slots__ = ("_cwd", "_env")

    def __init__(self, *, env: Path | None, cwd: Path) -> None:
        self._env = env
        self._cwd = cwd

    ##### PRIVATE METHODS #####

    async def _locate_absolute(self, path: Path) -> Path:
        return Path(await anyio.Path(self._cwd).joinpath(await anyio.Path(path).expanduser()).resolve())

    @staticmethod
    async def _locate_valid(root: Path) -> bool:
        return all([await anyio.Path(root, marker).is_file() for marker in MARKERS])

    async def _locate_explicit(self, given: Path) -> Path:
        root = await self._locate_absolute(given)
        match await self._locate_valid(root):
            case True:
                return root
            case _:
                msg = f"--nous {given}: not an e-nous checkout — {root} lacks {' or '.join(MARKERS)}"
                raise NousLocatorError(msg)

    async def _locate_ladder(self) -> Path:
        """TAXIS_NOUS, the cwd and its ancestors nearest first, then the sibling of the git toplevel (or the cwd)."""
        cwd = await self._locate_absolute(Path())
        ### the toplevel is the nearest ancestor holding `.git` (a dir, or a worktree's file): no git process to ask.
        top = await anext((path for path in (cwd, *cwd.parents) if await anyio.Path(path, ".git").exists()), cwd)
        env = () if self._env is None else (await self._locate_absolute(self._env),)
        sibling = top.parent / SIBLING
        rungs = (*env, cwd, *cwd.parents, sibling)
        match await anext((root for root in rungs if await self._locate_valid(root)), None):
            case Path() as found:
                return found
            case _:
                msg = (
                    f"no e-nous checkout: --nous not given · TAXIS_NOUS {self._env or 'unset'}"
                    f" · no ancestor of {cwd} · no sibling {sibling} — pass --nous PATH or set TAXIS_NOUS"
                )
                raise NousLocatorError(msg)

    ############################################################

    ##### PUBLIC #####

    async def locate(self, given: Path | None) -> Path:
        """The checkout, absolute: `given` checked, or the ladder's first valid rung."""
        match given:
            case Path():
                return await self._locate_explicit(given)
            case _:
                return await self._locate_ladder()
