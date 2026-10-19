"""adapters.primitives.npm: a Node CLI — `npm install -g <package@version>`, into the configured prefix or npm's own."""

from typing import TYPE_CHECKING

from e_taxis.models.journal import JournalCommand
from e_taxis.models.primitive import PrimitiveStep
from e_taxis.models.recipe import RecipeNpm

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.adapters.ports import RunnerPort
    from e_taxis.models.catalog import CatalogEntry, CatalogRecipe
    from e_taxis.models.primitive import PrimitiveContext


##### TYPES #####
class NpmPrimitive:
    """Satisfies PrimitivePort over `npm -g`; `prefix` None leaves npm on the user's configured prefix."""

    __slots__ = ("_prefix", "_runner")

    def __init__(self, runner: RunnerPort, prefix: Path | None) -> None:
        self._runner = runner
        self._prefix = () if prefix is None else ("--prefix", str(prefix))

    ##### PRIVATE METHODS #####

    def _common_argv(self, verb: str, package: str) -> tuple[str, ...]:
        return ("npm", verb, "-g", *self._prefix, package)

    ############################################################

    ##### PUBLIC #####

    async def install(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:  # noqa: ARG002 — the port's shape
        args = recipe.args(RecipeNpm)
        install = self._common_argv("install", args.package)
        await self._runner.run(install)
        undo = self._common_argv("uninstall", args.name)
        return PrimitiveStep(effects=(JournalCommand(argv=install, undo=undo),), detail=" ".join(install))

    async def uninstall(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:
        undo = self._common_argv("install", (entry.recipe(ctx.target) or recipe).args(RecipeNpm).package)
        uninstall = self._common_argv("uninstall", recipe.args(RecipeNpm).name)
        await self._runner.run(uninstall)
        return PrimitiveStep(effects=(JournalCommand(argv=uninstall, undo=undo),), detail=" ".join(uninstall))
