"""models.nous: one read of an e-nous checkout, raw — the two schemas, the specs and the core as plain data.

Nothing here is typed by e-taxis: the shapes live in the checkout itself (`core/schema.yaml`, `specs/base.yaml`) and
are compiled on the fly by `engine.model`. Every `{source: file}` envelope of a persona slot or a manifest is
already resolved (Markdown as text, YAML parsed); config modules are data and keep any `source` key they hold."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


##### TYPES #####
@dataclass(frozen=True, slots=True)
class NousTree:
    """`commit` is the sha the ref resolved to, or `worktree` when the checkout was read as it stands.

    `specs` is keyed `<harness>/<backend>`; `persona` by layer; `entities` entity → id → manifest; `config`
    facet → module → content; `assets` facet → every file under the facet's config asset folders; `blobs` the bytes
    of every file a render may copy as it is (entity folders, config assets), keyed by path from the checkout root."""

    root: str
    commit: str
    schema: Mapping[str, Any]
    base: Mapping[str, Any]
    specs: Mapping[str, Mapping[str, Any]]
    persona: Mapping[str, Mapping[str, Any]]
    entities: Mapping[str, Mapping[str, Mapping[str, Any]]]
    config: Mapping[str, Mapping[str, Any]]
    assets: Mapping[str, tuple[str, ...]]
    blobs: Mapping[str, bytes]
