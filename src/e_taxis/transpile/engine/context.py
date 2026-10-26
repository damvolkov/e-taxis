"""engine.context: what a row's transforms may read beside its value — read-only, the same for every row of a run.

`config` is the facet's modules as data, `native` the spec's own tables, `bindings` the placeholders (`out`,
`profile`, and per instance `id`), `instance` the manifest a row of an instanced section reads from."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import reduce
from typing import Any

##### DEFAULTS #####
MISSING: object = object()


##### TYPES #####
@dataclass(frozen=True, slots=True)
class RowContext:
    config: Mapping[str, Any]
    native: Mapping[str, Any]
    bindings: Mapping[str, str]
    instance: Mapping[str, Any] | None = None

    def bind(self, text: str) -> str:
        """Every `{name}` of a binding replaced; an unknown `{…}` is left as it is (JSON braces, other grammars)."""
        return reduce(lambda acc, item: acc.replace(f"{{{item[0]}}}", item[1]), self.bindings.items(), text)

    def path(self, path: str) -> Any:
        """A dotted path into the config modules (`models.tiers`), or into `native.` — MISSING when absent."""
        head, _, rest = path.partition(".")
        root = self.native if head == "native" else self.config
        keys = rest.split(".") if head == "native" else path.split(".")
        return reduce(lambda node, key: node.get(key, MISSING) if isinstance(node, Mapping) else MISSING, keys, root)

    def per(self, instance: Mapping[str, Any], ident: str) -> RowContext:
        """The same context for one instance: its manifest, and `id` bound."""
        return replace(self, instance=instance, bindings={**self.bindings, "id": ident})
