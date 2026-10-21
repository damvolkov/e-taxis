"""adapters.source: where the wanted parts come from — a profile shipped with the catalog, or an e-nous checkout.

A profile wants every part it does not leave `out`, for any target: the resolver filters by target. An
e-nous checkout wants, per target, the parts whose `used` lists that backend, across
`core/common/stack.yaml` and every `core/<facet>/stack.yaml`."""

from typing import TYPE_CHECKING

import anyio
import msgspec
import yaml

from e_taxis.harness.models.catalog import Rollout, Target
from e_taxis.harness.models.error import CatalogError, SourceError
from e_taxis.harness.models.profile import Profile
from e_taxis.harness.models.stack import Stack
from e_taxis.harness.models.wanted import WantedPart

if TYPE_CHECKING:
    from pathlib import Path


##### DEFAULTS #####
COMMON: str = "core/common/stack.yaml"
FACETS: str = "core/*/stack.yaml"


##### TYPES #####
class ProfileSource:
    """Satisfies SourcePort with `profiles/<id>.yaml` under the catalog root."""

    __slots__ = ("_id", "_root")

    def __init__(self, root: Path, profile: str) -> None:
        self._root = root
        self._id = profile

    ##### PRIVATE METHODS #####

    async def _wanted_profile(self) -> Profile:
        path = anyio.Path(self._root / "profiles" / f"{self._id}.yaml")
        try:
            raw = await path.read_bytes()
        except FileNotFoundError:
            shipped = sorted([found.stem async for found in path.parent.glob("*.yaml")])
            msg = f"no profile {self._id!r}: shipped are {', '.join(shipped) or 'none'}"
            raise SourceError(msg) from None
        try:
            return msgspec.yaml.decode(raw, type=Profile)
        except msgspec.DecodeError as exc:
            msg = f"profile {path.name}: {exc}"
            raise CatalogError(msg) from exc

    ############################################################

    ##### PUBLIC #####

    async def wanted(self, target: Target) -> tuple[WantedPart, ...]:  # noqa: ARG002 — a profile is target-agnostic; the resolver filters
        profile = await self._wanted_profile()
        return tuple(
            WantedPart(id=part, source=f"profile:{profile.id}")
            for part, rollout in profile.parts.items()
            if rollout is not Rollout.OUT
        )


class NousSource:
    """Satisfies SourcePort with an e-nous checkout's stack registry."""

    __slots__ = ("_root",)

    def __init__(self, root: Path) -> None:
        self._root = root

    ##### PRIVATE METHODS #####

    async def _wanted_files(self) -> list[str]:
        """Common first, then each facet in name order: the order the registry reads in."""
        match await anyio.Path(self._root / COMMON).is_file():
            case False:
                msg = f"not an e-nous checkout: {self._root / COMMON} is missing"
                raise SourceError(msg)
            case _:
                facets = sorted(
                    [str(path.relative_to(self._root)) async for path in anyio.Path(self._root).glob(FACETS)]
                )
                return [COMMON, *(facet for facet in facets if facet != COMMON)]

    async def _wanted_stack(self, relative: str) -> Stack:
        ### BaseLoader keeps every scalar a string: a pin like `1.10` must not become the float 1.1.
        raw = await anyio.Path(self._root / relative).read_text()
        try:
            return msgspec.convert(yaml.load(raw, Loader=yaml.CBaseLoader), Stack)  # noqa: S506 — BaseLoader builds no objects
        except msgspec.ValidationError as exc:
            msg = f"e-nous {relative}: {exc}"
            raise SourceError(msg) from exc

    ############################################################

    ##### PUBLIC #####

    async def wanted(self, target: Target) -> tuple[WantedPart, ...]:
        stacks = [(relative, await self._wanted_stack(relative)) for relative in await self._wanted_files()]
        return tuple(
            WantedPart(id=part_id, source=f"nous:{relative}", pin=part.pin or None)
            for relative, stack in stacks
            for part_id, part in stack.parts.items()
            if target.value in part.used
        )
