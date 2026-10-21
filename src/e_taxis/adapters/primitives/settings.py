"""adapters.primitives.settings: owned keys merged into a JSON config — Claude Code's settings.json, OpenCode's opencode.json.

A recipe writes either `env: {K: V}` (each under `env`) or one `key: a.b.c` with its `value`. Every key it
writes must be listed in the entry's `owns`, or nothing is written: one owner per key is the contract with
the transpiler. The file is created when missing, rewritten atomically, and only when a value changes. A
file that is not plain JSON (JSONC comments, trailing commas) is refused: rewriting it would destroy them.

Each key written is one effect holding its prior value, or how many trailing segments the write created,
so undo puts back exactly that key and leaves every key others wrote since alone."""

from functools import reduce
from itertools import accumulate, islice, takewhile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import msgspec

from e_taxis.adapters.disk import read_file, remove_file, write_file
from e_taxis.harness.models.error import JsoncError, OwnsError, RecipeError, SettingsError
from e_taxis.harness.models.journal import JournalKey
from e_taxis.harness.models.primitive import PrimitiveStep
from e_taxis.harness.models.recipe import RecipeSettings

if TYPE_CHECKING:
    from e_taxis.harness.models.catalog import CatalogEntry, CatalogRecipe
    from e_taxis.harness.models.primitive import PrimitiveContext

##### DEFAULTS #####
MISSING: Final = object()
INDENT: int = 2

type Document = dict[str, Any]
type KeyPath = tuple[str, ...]


##### TYPES #####
class SettingsPrimitive:
    """Satisfies PrimitivePort over JSON files; `revert` undoes one JournalKey."""

    __slots__ = ()

    ##### PRIVATE METHODS #####

    @staticmethod
    def _install_pairs(args: RecipeSettings) -> tuple[tuple[KeyPath, Any], ...]:
        match (args.env, args.key):
            case (dict() as env, None):
                return tuple((("env", name), value) for name, value in env.items())
            case (None, str() as key):
                return ((tuple(key.split(".")), args.value),)
            case _:
                msg = f"settings recipe for {args.file}: give `env` or `key`, exactly one"
                raise RecipeError(msg)

    @staticmethod
    def _install_owned(entry: CatalogEntry, pairs: tuple[tuple[KeyPath, Any], ...]) -> None:
        match [".".join(path) for path, _ in pairs if ".".join(path) not in entry.owns]:
            case []:
                pass
            case unowned:
                msg = f"{entry.id} writes {', '.join(unowned)} without owning them: list them in `owns`"
                raise OwnsError(msg)

    @staticmethod
    def _common_walk(doc: Document, path: KeyPath) -> list[Any]:
        """The values along `path`, one per leading segment that exists."""
        nodes = accumulate(
            path, lambda node, key: node.get(key, MISSING) if isinstance(node, dict) else MISSING, initial=doc
        )
        return list(takewhile(lambda node: node is not MISSING, islice(nodes, 1, None)))

    @classmethod
    def _common_set(cls, file: Path, doc: Document, path: KeyPath, value: Any) -> JournalKey | None:
        """Set `path` to `value` in place; the effect that reverses it, or None when it already held `value`."""
        found = cls._common_walk(doc, path)
        deepest = found[-1] if found else doc
        match (len(found) == len(path), deepest):
            case (True, before) if before == value:
                return None
            case (True, before):
                created = 0
            case (False, dict()):
                before, created = None, len(path) - len(found)
            case _:
                msg = f"{file}: {'.'.join(path[: len(found)])} is not a JSON object"
                raise SettingsError(msg)
        reduce(lambda node, key: node.setdefault(key, {}), path[:-1], doc)[path[-1]] = value
        return JournalKey(file=str(file), path=path, before=before, created=created)

    @classmethod
    def _common_drop(cls, file: Path, doc: Document, path: KeyPath) -> JournalKey | None:
        """Remove `path` in place; the effect that puts it back, or None when it was not there."""
        found = cls._common_walk(doc, path)
        match len(found) == len(path):
            case True:
                parent = found[-2] if len(path) > 1 else doc
                return JournalKey(file=str(file), path=path, before=parent.pop(path[-1]))
            case _:
                return None

    @staticmethod
    async def _common_load(file: Path) -> tuple[Document, bool]:
        """The document and whether the file is missing (then an empty document)."""
        match await read_file(file):
            case None:
                return ({}, True)
            case found:
                try:
                    doc = msgspec.json.decode(found[0])
                except msgspec.DecodeError as exc:
                    msg = f"{file} is not plain JSON ({exc}) — comments or trailing commas would be lost; refusing to rewrite it"
                    raise JsoncError(msg) from exc
                match doc:
                    case dict():
                        return (doc, False)
                    case _:
                        msg = f"{file}: the root is not a JSON object"
                        raise SettingsError(msg)

    @staticmethod
    async def _common_dump(file: Path, doc: Document) -> None:
        await write_file(file, msgspec.json.format(msgspec.json.encode(doc), indent=INDENT) + b"\n")

    ############################################################

    ##### PUBLIC #####

    async def read(self, file: Path) -> Document:
        """The document as it stands; an empty one where the file is missing."""
        doc, _ = await self._common_load(file)
        return doc

    async def merge(self, file: Path, pairs: tuple[tuple[KeyPath, Any], ...]) -> tuple[JournalKey, ...]:
        """Each key set to its value, the file rewritten once and only if one moved; the effects that reverse it."""
        doc, missing = await self._common_load(file)
        effects = [effect for path, value in pairs if (effect := self._common_set(file, doc, path, value))]
        match effects:
            case [first, *rest]:
                await self._common_dump(file, doc)
                ### the file's creation rides on the first key: reverted last, it removes the file once it is empty.
                return (msgspec.structs.replace(first, fresh=missing), *rest)
            case _:
                return ()

    async def install(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:
        args = recipe.args(RecipeSettings)
        pairs = self._install_pairs(args)
        self._install_owned(entry, pairs)
        file = ctx.expand(args.file)
        match await self.merge(file, pairs):
            case ():
                return PrimitiveStep(detail=f"{file} already holds every key")
            case effects:
                return PrimitiveStep(effects=effects, detail=f"{len(effects)} key(s) in {file}")

    async def uninstall(self, entry: CatalogEntry, recipe: CatalogRecipe, ctx: PrimitiveContext) -> PrimitiveStep:
        file = ctx.expand(recipe.args(RecipeSettings).file)
        doc, missing = await self._common_load(file)
        effects = (
            ()
            if missing
            else tuple(effect for key in entry.owns if (effect := self._common_drop(file, doc, tuple(key.split(".")))))
        )
        match effects:
            case ():
                return PrimitiveStep(detail=f"{file} holds none of {entry.id}'s keys")
            case _:
                await self._common_dump(file, doc)
                return PrimitiveStep(effects=effects, detail=f"{len(effects)} key(s) dropped from {file}")

    async def revert(self, effect: JournalKey) -> None:
        file = Path(effect.file)
        doc, missing = await self._common_load(file)
        top = effect.path[: len(effect.path) - effect.created + 1]
        changed = (
            self._common_set(file, doc, effect.path, effect.before)
            if effect.created == 0
            else self._common_drop(file, doc, top)
        )
        match (effect.fresh and not doc, changed is not None and not missing):
            case (True, _):
                await remove_file(file)
            case (False, True):
                await self._common_dump(file, doc)
            case _:
                pass
