"""adapters.ontology: a workflow manifest made whole from the facet's `workflows` config — at load, once.

`kwargs` is the one typed vocabulary of parameters: a workflow names the ones it takes (`parameters: [project, query]`)
and may refine an entry (`{query: {doc: …}}`); a name the vocabulary lacks must be declared in full where it is used.
`families` groups workflows that share a philosophy: the family's kwargs join every member's, its output stands for
a member that declares none (`{name}` is the member's id), and its nodes are written once and used as
`{use: <node>, depends: …, inputs: …, outputs: …}` — the family's definition with the member's wiring over it. Every
reader downstream — the engine, the Claude workflow, the OpenCode walk, the law — sees the expanded manifest only."""

from typing import TYPE_CHECKING, Any

from e_taxis.transpile.models.error import NousError

if TYPE_CHECKING:
    from collections.abc import Mapping


class WorkflowOntology:
    """The facet's `workflows` config: `kwargs` and `families`."""

    __slots__ = ("_families", "_kwargs")

    def __init__(self, config: Mapping[str, Any]) -> None:
        self._kwargs: Mapping[str, Any] = config.get("kwargs") or {}
        self._families: Mapping[str, Any] = config.get("families") or {}

    ##### PRIVATE #####

    def _expand_kwarg(self, ident: str, name: str, refined: Any) -> dict[str, Any]:
        """One parameter: the vocabulary's entry, a string refining its doc, or a mapping over it."""
        base = self._kwargs.get(name)
        match (base, refined):
            case (None, None):
                msg = f"workflow {ident}: kwarg {name!r} is in no vocabulary and declared nowhere"
                raise NousError(msg)
            case (dict() as entry, None):
                return dict(entry)
            case (_, str() as doc):
                return {**(base or {}), "doc": doc}
            case _:
                return {**(base or {}), **refined}

    def _expand_params(self, ident: str, declared: Any, family: Mapping[str, Any]) -> dict[str, Any]:
        named = dict.fromkeys(declared) if isinstance(declared, list) else dict(declared or {})
        wanted = {**dict.fromkeys(family.get("kwargs") or ()), **named}
        return {name: self._expand_kwarg(ident, name, refined) for name, refined in wanted.items()}

    @staticmethod
    def _expand_node(ident: str, node: Any, shared: Mapping[str, Any]) -> Any:
        """A family node used by name, the member's wiring over the family's definition; any other node as written."""
        match node:
            case {"use": str() as name, **wiring} if name in shared:
                return {**shared[name], "id": wiring.pop("id", name), **wiring}
            case {"use": str() as name}:
                msg = f"workflow {ident}: uses {name!r}, which its family does not define"
                raise NousError(msg)
            case _:
                return node

    def _expand_family(self, ident: str, manifest: Mapping[str, Any]) -> Mapping[str, Any]:
        match manifest.get("family"):
            case None | "":
                return {}
            case str() as name if name in self._families:
                return self._families[name]
            case name:
                msg = f"workflow {ident}: family {name!r} is not in the workflows config"
                raise NousError(msg)

    ############################################################

    ##### PUBLIC #####

    def expand(self, ident: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
        """The manifest with its kwargs and family nodes written out; its own fields win over the family's."""
        family = self._expand_family(ident, manifest)
        shared = family.get("nodes") or {}
        output = manifest.get("output") or (
            {key: str(value).replace("{name}", ident) for key, value in family["output"].items()}
            if family.get("output")
            else None
        )
        return {
            **manifest,
            "parameters": self._expand_params(ident, manifest.get("parameters"), family),
            "nodes": [self._expand_node(ident, node, shared) for node in manifest.get("nodes") or ()],
            **({"output": output} if output else {}),
        }
