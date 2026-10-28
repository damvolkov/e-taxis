"""adapters.nous: an e-nous checkout read whole — core and specs at one ref, so a stamp versions them together.

At a ref (the default HEAD) `git archive` exports `core/` and `specs/` into a temporary directory: what another
hand left uncommitted never reaches a render. `ref=None` reads the working tree as it stands. Where things live
is not known here: `core/schema.yaml` says it (`persona.file`, each entity's `path`, the config layout), so a new
entity or module needs no code. Every `{source: file}` envelope of a persona slot or a manifest is resolved —
Markdown as text, YAML parsed and resolved in turn — confined to the folder that declares it. Config modules are
data: a `source` key there means what it says. Parsing is blocking file work, done in one worker thread."""

import io
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any

import anyio
import eserde

from e_taxis.transpile.adapters.ontology import WorkflowOntology
from e_taxis.transpile.models.error import NousError
from e_taxis.transpile.models.nous import NousTree

if TYPE_CHECKING:
    from collections.abc import Mapping

##### DEFAULTS #####
SCHEMA: str = "core/schema.yaml"
BASE: str = "specs/base.yaml"
SPECS: str = "specs"
CORE: str = "core"
WORKTREE: str = "worktree"
MARKDOWN: str = ".md"
YAML: frozenset[str] = frozenset({".yaml", ".yml"})
### the entity a facet's `workflows` config module makes whole at load (adapters.ontology).
WORKFLOW: str = "workflow"
WORKFLOWS: str = "workflows"


##### TYPES #####
class GitNous:
    """Satisfies NousPort over a checkout: `ref` names the commit, None the working tree."""

    __slots__ = ("_ref", "_root")

    def __init__(self, root: Path, ref: str | None = "HEAD") -> None:
        self._root = root
        self._ref = ref

    ##### PRIVATE METHODS #####

    async def _load_git(self, *args: str) -> bytes:
        done = await anyio.run_process(("git", "-C", str(self._root), *args), check=False)
        match done.returncode:
            case 0:
                return done.stdout
            case code:
                msg = f"`git {' '.join(args)}` in {self._root} exited {code}: {done.stderr.decode().strip()}"
                raise NousError(msg)

    @staticmethod
    def _load_yaml(path: Path) -> Any:
        try:
            return eserde.load(path)
        except (OSError, eserde.LoadError) as exc:
            msg = f"{path}: {exc}"
            raise NousError(msg) from exc

    @classmethod
    def _load_source(cls, rel: str, base: Path) -> Any:
        """One envelope's content: the file must sit under `base`, the folder that declares it."""
        target = (base / rel).resolve()
        match target.is_relative_to(base.resolve()) and target.is_file():
            case False:
                msg = f"{base}: `source: {rel}` is missing or escapes its folder"
                raise NousError(msg)
            case _ if target.suffix == MARKDOWN:
                return target.read_text()
            case _ if target.suffix in YAML:
                return cls._load_resolve(cls._load_yaml(target), target.parent)
            case _:
                msg = f"{target}: a source is Markdown or YAML"
                raise NousError(msg)

    @classmethod
    def _load_resolve(cls, node: Any, base: Path) -> Any:
        match node:
            case {"source": str() as rel} if len(node) == 1:
                return cls._load_source(rel, base)
            case dict():
                return {key: cls._load_resolve(value, base) for key, value in node.items()}
            case list():
                return [cls._load_resolve(value, base) for value in node]
            case _:
                return node

    @classmethod
    def _load_manifest(cls, path: Path) -> Any:
        return cls._load_resolve(cls._load_yaml(path), path.parent)

    @classmethod
    def _load_entities(cls, root: Path, schema: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        """Each entity's instances by id: the `{id}` segment of its declared path is the folder name."""
        return {
            name: {
                manifest.parent.name: cls._load_manifest(manifest)
                for manifest in sorted(root.glob(spec["path"].replace("{id}", "*")))
            }
            for name, spec in schema.get("entities", {}).items()
        }

    @classmethod
    def _load_config(cls, root: Path, schema: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            facet: {path.stem: cls._load_yaml(path) for path in sorted((root / CORE / facet / "config").glob("*.yaml"))}
            for facet in schema["facets"]
        }

    @staticmethod
    def _load_assets(root: Path, schema: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
        return {
            facet: tuple(
                str(path.relative_to(root / CORE / facet / "config"))
                for folder in schema["config"].get(facet, {}).get("assets", ())
                for path in sorted((root / CORE / facet / "config" / folder).rglob("*"))
                if path.is_file()
            )
            for facet in schema["facets"]
        }

    @staticmethod
    def _load_blobs(root: Path, schema: Mapping[str, Any]) -> dict[str, bytes]:
        """Every file under an entity instance folder or a config asset folder, by path from the root."""
        folders = [
            *(
                folder
                for spec in schema.get("entities", {}).values()
                for folder in sorted(root.glob(str(Path(spec["path"]).parent).replace("{id}", "*")))
            ),
            *(
                root / CORE / facet / "config" / name
                for facet in schema["facets"]
                for name in schema["config"].get(facet, {}).get("assets", ())
            ),
        ]
        return {
            str(path.relative_to(root)): path.read_bytes()
            for folder in folders
            for path in sorted(folder.rglob("*"))
            if path.is_file()
        }

    @classmethod
    def _load_tree(cls, root: Path, commit: str, origin: str) -> NousTree:
        schema = cls._load_yaml(root / SCHEMA)
        layers = {layer for chain in schema["facets"].values() for layer in chain}
        config = cls._load_config(root, schema)
        entities = cls._load_entities(root, schema)
        facet = schema.get("entities", {}).get(WORKFLOW, {}).get("facet", "")
        ontology = WorkflowOntology(config.get(facet, {}).get(WORKFLOWS) or {})
        workflows = {ident: ontology.expand(ident, raw) for ident, raw in entities.get(WORKFLOW, {}).items()}
        return NousTree(
            root=origin,
            commit=commit,
            schema=schema,
            base=cls._load_yaml(root / BASE),
            specs={
                str(path.relative_to(root / SPECS).with_suffix("")): cls._load_yaml(path)
                for path in sorted((root / SPECS).glob("*/*.yaml"))
            },
            persona={
                layer: cls._load_manifest(root / schema["persona"]["file"].replace("<layer>", layer))
                for layer in sorted(layers)
            },
            entities={**entities, **({WORKFLOW: workflows} if WORKFLOW in entities else {})},
            config=config,
            assets=cls._load_assets(root, schema),
            blobs=cls._load_blobs(root, schema),
        )

    async def _load_archive(self, dest: Path) -> str:
        commit = (await self._load_git("rev-parse", "--verify", f"{self._ref}^{{commit}}")).decode().strip()
        with tarfile.open(
            fileobj=io.BytesIO(await self._load_git("archive", "--format=tar", commit, CORE, SPECS))
        ) as tar:
            tar.extractall(dest, filter="data")
        return commit

    ############################################################

    ##### PUBLIC #####

    async def load(self) -> NousTree:
        """The checkout read at the ref (or as it stands): schemas, specs and core, envelopes resolved."""
        match self._ref:
            case None:
                return await anyio.to_thread.run_sync(self._load_tree, self._root, WORKTREE, str(self._root))
            case _:
                with TemporaryDirectory(prefix="e-taxis-nous-") as scratch:
                    commit = await self._load_archive(Path(scratch))
                    return await anyio.to_thread.run_sync(self._load_tree, Path(scratch), commit, str(self._root))
