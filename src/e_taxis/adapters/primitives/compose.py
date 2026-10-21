"""adapters.primitives.compose: a container service — P3. Until then a typed answer, and nothing touched."""

from typing import TYPE_CHECKING

from e_taxis.harness.models.catalog import Primitive
from e_taxis.harness.models.primitive import NotSupportedYet

if TYPE_CHECKING:
    from e_taxis.harness.models.catalog import CatalogEntry, CatalogRecipe
    from e_taxis.harness.models.primitive import PrimitiveContext

##### DEFAULTS #####
LATER: NotSupportedYet = NotSupportedYet(primitive=Primitive.COMPOSE, detail="compose lands in P3")


##### TYPES #####
class ComposePrimitive:
    """Satisfies PrimitivePort; answers NotSupportedYet to both calls."""

    __slots__ = ()

    async def install(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> NotSupportedYet:  # noqa: ARG002 — the port's shape
        return LATER

    async def uninstall(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> NotSupportedYet:  # noqa: ARG002 — the port's shape
        return LATER
