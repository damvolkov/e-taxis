"""adapters.primitives.file: one marked block in a text file — `<!-- e-taxis:<block> -->` … `<!-- /e-taxis:<block> -->`.

The block is the only text this primitive owns: inserted at the end (after a blank line) when absent, its
body replaced in place when present, removed with the blank line it brought. Nothing outside the markers
is ever rewritten, and an unchanged body writes nothing."""

import re
from pathlib import Path
from typing import TYPE_CHECKING

from e_taxis.adapters.disk import read_file, remove_file, write_file
from e_taxis.models.journal import JournalBlock
from e_taxis.models.primitive import PrimitiveStep
from e_taxis.models.recipe import RecipeBlock, RecipeFile

if TYPE_CHECKING:
    from e_taxis.models.catalog import CatalogEntry, CatalogRecipe
    from e_taxis.models.primitive import PrimitiveContext


##### TYPES #####
class FilePrimitive:
    """Satisfies PrimitivePort over text files; `revert` undoes one JournalBlock."""

    __slots__ = ()

    ##### PRIVATE METHODS #####

    @staticmethod
    def _common_match(text: str, block: str) -> re.Match[str] | None:
        name = re.escape(block)
        return re.search(rf"\n?<!-- e-taxis:{name} -->\n(?P<body>.*?)\n<!-- /e-taxis:{name} -->\n?", text, re.DOTALL)

    @classmethod
    def _common_put(cls, text: str, block: str, body: str | None) -> str:
        """`text` with the block's body set to `body`, or the block removed when `body` is None."""
        match cls._common_match(text, block):
            case None if body is None:
                return text
            case None:
                rendered = f"<!-- e-taxis:{block} -->\n{body}\n<!-- /e-taxis:{block} -->\n"
                return f"{text.rstrip('\n')}\n\n{rendered}" if text else rendered
            case found if body is None:
                ### a block between other text leaves one blank line behind, never the two paragraphs glued.
                glue = "\n" if found.start() and found.end() < len(text) else ""
                return text[: found.start()] + glue + text[found.end() :]
            case found:
                return text[: found.start("body")] + (body or "") + text[found.end("body") :]

    @staticmethod
    async def _common_load(file: Path) -> tuple[str, bool]:
        """The text and whether the file is missing (then empty)."""
        match await read_file(file):
            case None:
                return ("", True)
            case found:
                return (found[0].decode(), False)

    @classmethod
    async def _common_write(cls, file: Path, text: str, block: str, body: str | None) -> str | None:
        """Set the block and write when the text changes; the body it held before, None when it was absent."""
        found = cls._common_match(text, block)
        before = found and found.group("body")
        updated = cls._common_put(text, block, body)
        match updated == text:
            case False:
                await write_file(file, updated.encode())
            case _:
                pass
        return before

    ############################################################

    ##### PUBLIC #####

    async def install(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:  # noqa: ARG002 — the port's shape
        args = recipe.args(RecipeFile)
        file = ctx.expand(args.file)
        text, missing = await self._common_load(file)
        body = args.text.rstrip("\n")
        match self._common_match(text, args.block):
            case found if found and found.group("body") == body:
                return PrimitiveStep(detail=f"block {args.block} already in {file}")
            case _:
                before = await self._common_write(file, text, args.block, body)
                effect = JournalBlock(file=str(file), block=args.block, before=before, fresh=missing)
                return PrimitiveStep(effects=(effect,), detail=f"block {args.block} in {file}")

    async def uninstall(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:  # noqa: ARG002 — the port's shape
        args = recipe.args(RecipeBlock)
        file = ctx.expand(args.file)
        text, _ = await self._common_load(file)
        match await self._common_write(file, text, args.block, None):
            case None:
                return PrimitiveStep(detail=f"no block {args.block} in {file}")
            case before:
                effect = JournalBlock(file=str(file), block=args.block, before=before)
                return PrimitiveStep(effects=(effect,), detail=f"block {args.block} removed from {file}")

    async def revert(self, effect: JournalBlock) -> None:
        file = Path(effect.file)
        text, _ = await self._common_load(file)
        match (effect.fresh, self._common_put(text, effect.block, effect.before)):
            case (True, ""):
                await remove_file(file)
            case (_, updated) if updated != text:
                await write_file(file, updated.encode())
            case _:
                pass
