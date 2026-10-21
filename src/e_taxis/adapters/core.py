"""adapters.core: an e-engineer core read into the content contract — from a git ref, or from the working tree.

By default the core is the committed HEAD: `git archive` exports `core/` into a temporary directory, so
whatever another hand left uncommitted in the checkout never reaches a harness. `ref=None` reads the
working tree as it stands. Manifests are embedded by e-serde (each `{source: file}` resolved beside its
manifest, confined to it) and the envelopes lifted, so the models only hold text. Parsing is blocking
file work and runs in one worker thread."""

import io
import tarfile
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import anyio
import eserde
import msgspec

from e_taxis.harness.models.core import (
    BASE,
    CARRIED,
    CONFIG,
    FACET,
    PERSONA,
    Core,
    CoreAgent,
    CoreCommand,
    CoreEntity,
    CoreHook,
    CoreMain,
    CoreMcp,
    CorePermissions,
    CorePersona,
    CoreSkill,
)
from e_taxis.harness.models.error import CoreError


##### TYPES #####
class GitCore:
    """Satisfies CorePort over an e-engineer checkout."""

    __slots__ = ("_ref", "_root")

    def __init__(self, root: Path, ref: str | None = "HEAD") -> None:
        self._root = root
        self._ref = ref

    ##### PRIVATE METHODS #####

    async def _load_archive(self, dest: Path) -> None:
        argv = ("git", "-C", str(self._root), "archive", "--format=tar", str(self._ref), "core")
        done = await anyio.run_process(argv, check=False)
        match done.returncode:
            case 0:
                with tarfile.open(fileobj=io.BytesIO(done.stdout)) as tar:
                    tar.extractall(dest, filter="data")
            case code:
                msg = f"`git archive {self._ref}` in {self._root} exited {code}: {done.stderr.decode().strip()}"
                raise CoreError(msg)

    @classmethod
    def _load_lift(cls, node: Any) -> Any:
        """Every embedded `{source: text}` envelope replaced by its text."""
        match node:
            case {"source": str() as text} if len(node) == 1:
                return text
            case dict():
                return {key: cls._load_lift(value) for key, value in node.items()}
            case list():
                return [cls._load_lift(value) for value in node]
            case _:
                return node

    @classmethod
    def _load_file[T](cls, path: Path, kind: type[T], *, embed: bool = True) -> T:
        """A manifest, its bodies embedded; config (`embed=False`) is data, where a `source` key means what it says."""
        try:
            return msgspec.convert(cls._load_lift(eserde.load(path, embed=True)) if embed else eserde.load(path), kind)
        except (OSError, eserde.LoadError, msgspec.ValidationError) as exc:
            msg = f"{path}: {exc}"
            raise CoreError(msg) from exc

    @classmethod
    def _load_persona(cls, root: Path) -> dict[str, str]:
        layers = [cls._load_file(layer / PERSONA, CorePersona).slots for layer in (root / BASE, root / FACET)]
        match sorted(slot for slot, seen in Counter(slot for layer in layers for slot in layer).items() if seen > 1):
            case []:
                return {slot: text for layer in layers for slot, text in layer.items()}
            case twice:
                msg = f"persona slots declared by more than one layer: {', '.join(twice)}"
                raise CoreError(msg)

    @classmethod
    def _load_instances[T](cls, root: Path, entity: CoreEntity, kind: type[T]) -> dict[str, T]:
        folder = root / FACET / entity.folder
        return {
            manifest.parent.name: cls._load_file(manifest, kind)
            for manifest in sorted(folder.glob(f"*/{entity.manifest}"))
        }

    @staticmethod
    def _load_carried(config: Path) -> dict[str, bytes]:
        return {
            str(path.relative_to(config)): path.read_bytes()
            for folder in CARRIED
            for path in sorted((config / folder).rglob("*"))
            if path.is_file()
        }

    @classmethod
    def _load_tree(cls, root: Path) -> Core:
        config = root / FACET / CONFIG
        skills = cls._load_instances(root, CoreEntity.SKILL, CoreSkill)
        skill_root = root / FACET / CoreEntity.SKILL.folder
        try:
            references = {
                ident: {ref: (skill_root / ident / ref).read_bytes() for ref in skill.references}
                for ident, skill in skills.items()
            }
        except OSError as exc:
            msg = f"a skill names a reference it does not ship: {exc}"
            raise CoreError(msg) from exc
        return Core(
            persona=cls._load_persona(root),
            skills=skills,
            agents=cls._load_instances(root, CoreEntity.AGENT, CoreAgent),
            commands=cls._load_instances(root, CoreEntity.COMMAND, CoreCommand),
            main=cls._load_file(config / "main.yaml", CoreMain, embed=False),
            permissions=cls._load_file(config / "permissions.yaml", CorePermissions, embed=False),
            hooks=cls._load_file(config / "hooks.yaml", dict[str, tuple[CoreHook, ...]], embed=False),
            mcp=cls._load_file(config / "mcp.yaml", CoreMcp, embed=False),
            carried=cls._load_carried(config),
            references=references,
        )

    ############################################################

    ##### PUBLIC #####

    async def load(self) -> Core:
        match self._ref:
            case None:
                return await anyio.to_thread.run_sync(self._load_tree, self._root)
            case _:
                with TemporaryDirectory(prefix="e-taxis-core-") as scratch:
                    await self._load_archive(Path(scratch))
                    return await anyio.to_thread.run_sync(self._load_tree, Path(scratch))
