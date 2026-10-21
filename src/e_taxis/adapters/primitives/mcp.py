"""adapters.primitives.mcp: an MCP server registered with Claude Code through its own CLI — `claude mcp add-json`.

stdio servers carry `command`, `args`, `env` (a `~/` command resolved against the run's home: Claude does
not expand it); http servers carry their `url`. Claude refuses to add over an existing name, so an update
removes first — the prior registration is not recorded, and undo of an update removes the server."""

from typing import TYPE_CHECKING, Any

import msgspec

from e_taxis.harness.models.error import RecipeError
from e_taxis.harness.models.journal import JournalCommand
from e_taxis.harness.models.primitive import PrimitiveStep
from e_taxis.harness.models.recipe import RecipeMcp

if TYPE_CHECKING:
    from e_taxis.harness.models.catalog import CatalogEntry, CatalogRecipe
    from e_taxis.harness.models.ports import RunnerPort
    from e_taxis.harness.models.primitive import PrimitiveContext


##### TYPES #####
class McpPrimitive:
    """Satisfies PrimitivePort over `claude mcp`."""

    __slots__ = ("_runner",)

    def __init__(self, runner: RunnerPort) -> None:
        self._runner = runner

    ##### PRIVATE METHODS #####

    @staticmethod
    def _common_config(args: RecipeMcp, ctx: PrimitiveContext) -> dict[str, Any]:
        match (args.transport, args.command, args.url):
            case ("http", _, str() as url):
                return {"type": "http", "url": url}
            case ("stdio", str() as command, _):
                env = {"env": args.env} if args.env else {}
                return {"type": "stdio", "command": str(ctx.expand(command)), "args": list(args.args), **env}
            case _:
                msg = f"claude-mcp recipe {args.name}: stdio needs `command`, http needs `url`"
                raise RecipeError(msg)

    @classmethod
    def _common_add(cls, args: RecipeMcp, ctx: PrimitiveContext) -> tuple[str, ...]:
        config = msgspec.json.encode(cls._common_config(args, ctx)).decode()
        return ("claude", "mcp", "add-json", "--scope", args.scope, args.name, config)

    @staticmethod
    def _common_remove(args: RecipeMcp) -> tuple[str, ...]:
        ### `claude mcp remove` takes no --scope (verified on Claude Code 2.1.296): the name alone.
        return ("claude", "mcp", "remove", args.name)

    ############################################################

    ##### PUBLIC #####

    async def install(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:  # noqa: ARG002 — the port's shape
        args = recipe.args(RecipeMcp)
        add, remove = self._common_add(args, ctx), self._common_remove(args)
        match ctx.update:
            case True:
                await self._runner.run(remove)
            case _:
                pass
        await self._runner.run(add)
        return PrimitiveStep(effects=(JournalCommand(argv=add, undo=remove),), detail=f"{args.name} ({args.scope})")

    async def uninstall(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:
        add = self._common_add((entry.recipe(ctx.target) or recipe).args(RecipeMcp), ctx)
        remove = self._common_remove(recipe.args(RecipeMcp))
        await self._runner.run(remove)
        return PrimitiveStep(effects=(JournalCommand(argv=remove, undo=add),), detail=" ".join(remove[:-1]))
