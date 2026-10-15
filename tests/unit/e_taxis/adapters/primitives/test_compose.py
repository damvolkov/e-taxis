"""tests/unit/e_taxis/adapters/primitives/compose: not in P2 — a typed answer, nothing touched."""

from e_taxis.adapters.ports import PrimitivePort
from e_taxis.adapters.primitives.compose import ComposePrimitive
from e_taxis.models.catalog import Primitive
from e_taxis.models.primitive import NotSupportedYet


async def test_compose_is_not_supported_yet(entry, ctx) -> None:
    compose = ComposePrimitive()
    part = entry("compose", {"path": "~/.config/compose/x"}, uninstall={"path": "~/.config/compose/x"})
    expected = NotSupportedYet(primitive=Primitive.COMPOSE, detail="compose lands in P3")
    assert isinstance(compose, PrimitivePort)
    assert await compose.install(part, part.recipe(ctx.target), ctx) == expected
    assert await compose.uninstall(part, part.uninstall, ctx) == expected
