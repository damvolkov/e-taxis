"""engine.subject: what a target's subjects are in one e-nous tree, and where each lives — read from its schema.

An instanced kind fans out over its ids (the `{id}` folders its schema path names); `persona` and `config` are one
subject each, the tekton facet's (`core/tekton/persona/`, `core/tekton/config/`); a spec is one per backend
(`specs/<harness>/<backend>.yaml`); the corpus has none. The place is what a manual proposal overlays, what a patch
is cut from and what a promotion touches — one path, so a promotion changes exactly what the run measured."""

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from e_taxis.workflow.models.error import PlaneError
from e_taxis.workflow.models.plane import Target

if TYPE_CHECKING:
    from e_taxis.transpile.models.nous import NousTree

##### DEFAULTS #####
FACET: str = "tekton"
CORPUS: str = "core"


##### TYPES #####
class NousSubject:
    """The subjects and places of one tree."""

    __slots__ = ("_tree",)

    def __init__(self, tree: NousTree) -> None:
        self._tree = tree

    ##### PRIVATE METHODS #####

    def _all_declared(self, target: Target) -> tuple[str, ...]:
        match target:
            case Target.CORPUS:
                return ()
            case Target.PERSONA | Target.CONFIG:
                return (target.value,)
            case Target.SPEC:
                return tuple(sorted(key.rpartition("/")[2] for key in self._tree.specs))
            case _:
                return tuple(sorted(self._tree.entities.get(target.value, {})))

    ############################################################

    ##### PUBLIC #####

    def all(self, target: Target, ids: tuple[str, ...] = ()) -> tuple[str, ...]:
        """Every subject of a target, or the named ones — each of which must exist."""
        declared = self._all_declared(target)
        match sorted(set(ids) - set(declared)):
            case []:
                return tuple(sorted(set(ids))) if ids else declared
            case unknown:
                msg = f"{target}: unknown subject(s) {', '.join(unknown)}"
                raise PlaneError(msg)

    def place(self, target: Target, subject: str) -> str:
        """Where one subject lives, repo-relative."""
        match target:
            case Target.CORPUS:
                return CORPUS
            case Target.PERSONA | Target.CONFIG:
                return f"{CORPUS}/{FACET}/{target.value}"
            case Target.SPEC:
                key = next(key for key in self._tree.specs if key.rpartition("/")[2] == subject)
                return f"specs/{key}.yaml"
            case _:
                path = self._tree.schema["entities"][target.value]["path"].replace("{id}", subject)
                return str(PurePosixPath(path).parent)
