"""adapters.primitives.uv: a Python CLI as a uv tool — `uv tool install <source>`, the pin carried in the source."""

from typing import TYPE_CHECKING

from e_taxis.harness.models.journal import JournalCommand
from e_taxis.harness.models.primitive import PrimitiveStep
from e_taxis.harness.models.recipe import RecipeUv, RecipeUvName

if TYPE_CHECKING:
    from e_taxis.harness.models.catalog import CatalogEntry, CatalogRecipe
    from e_taxis.harness.models.ports import RunnerPort
    from e_taxis.harness.models.primitive import PrimitiveContext


##### TYPES #####
class UvPrimitive:
    """Satisfies PrimitivePort over `uv tool`."""

    __slots__ = ("_runner",)

    def __init__(self, runner: RunnerPort) -> None:
        self._runner = runner

    ##### PRIVATE METHODS #####

    @staticmethod
    def _common_argv(args: RecipeUv) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(install, uninstall) for one tool."""
        return (("uv", "tool", "install", args.source), ("uv", "tool", "uninstall", args.name))

    ############################################################

    ##### PUBLIC #####

    async def install(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:  # noqa: ARG002 — the port's shape
        install, uninstall = self._common_argv(recipe.args(RecipeUv))
        await self._runner.run(install)
        return PrimitiveStep(effects=(JournalCommand(argv=install, undo=uninstall),), detail=" ".join(install))

    async def uninstall(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:
        ### undo reinstalls from the install recipe's source: resolved before anything is removed.
        install, _ = self._common_argv((entry.recipe(ctx.target) or recipe).args(RecipeUv))
        uninstall = ("uv", "tool", "uninstall", recipe.args(RecipeUvName).name)
        await self._runner.run(uninstall)
        return PrimitiveStep(effects=(JournalCommand(argv=uninstall, undo=install),), detail=" ".join(uninstall))
