"""adapters.primitives.plugin: a Claude Code plugin — its marketplace added, then the plugin installed from it.

Each of the two CLI calls is its own effect: a failing install still leaves the marketplace recorded, so
undo removes it. Uninstall removes the plugin and leaves the marketplace, which other plugins may use."""

from typing import TYPE_CHECKING

from e_taxis.harness.models.error import RunnerError
from e_taxis.harness.models.journal import JournalCommand
from e_taxis.harness.models.primitive import PrimitiveStep
from e_taxis.harness.models.recipe import RecipePlugin, RecipePluginSource

if TYPE_CHECKING:
    from e_taxis.harness.models.catalog import CatalogEntry, CatalogRecipe
    from e_taxis.harness.models.ports import RunnerPort
    from e_taxis.harness.models.primitive import PrimitiveContext


##### TYPES #####
class PluginPrimitive:
    """Satisfies PrimitivePort over `claude plugin`."""

    __slots__ = ("_runner",)

    def __init__(self, runner: RunnerPort) -> None:
        self._runner = runner

    ##### PRIVATE METHODS #####

    @staticmethod
    def _common_argv(args: RecipePlugin) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(install, uninstall) for the plugin."""
        plugin = f"{args.name}@{args.marketplace}"
        return (("claude", "plugin", "install", plugin), ("claude", "plugin", "uninstall", plugin))

    ############################################################

    ##### PUBLIC #####

    async def install(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:  # noqa: ARG002 — the port's shape
        args = recipe.args(RecipePluginSource)
        market = JournalCommand(
            argv=("claude", "plugin", "marketplace", "add", args.source),
            undo=("claude", "plugin", "marketplace", "remove", args.marketplace),
        )
        install, uninstall = self._common_argv(args)
        await self._runner.run(market.argv)
        try:
            await self._runner.run(install)
        except RunnerError as exc:
            raise RunnerError(exc.message, effects=(market,)) from exc
        return PrimitiveStep(effects=(market, JournalCommand(argv=install, undo=uninstall)), detail=install[-1])

    async def uninstall(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:  # noqa: ARG002 — the port's shape
        install, uninstall = self._common_argv(recipe.args(RecipePlugin))
        await self._runner.run(uninstall)
        return PrimitiveStep(effects=(JournalCommand(argv=uninstall, undo=install),), detail=uninstall[-1])
