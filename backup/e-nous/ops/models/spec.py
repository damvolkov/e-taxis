"""models.spec — the data model of a backend spec: the shapes the transpiler obeys.

One msgspec struct per section of `specs/<harness>/<backend>/*.yaml`, plus the regexes those
shapes lean on. Pure vocabulary: no filesystem, no render, no CLI — which is why the
classifier and the transpiler can both stand on it without either owning the other.
"""

from __future__ import annotations

import re
from typing import Any, Final, Literal

import msgspec

#: The frontmatter block of a flat markdown file: name, description, and the slots beside them.
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
#: A fold of a list slot into one line above the body.
JOIN_RE = re.compile(r"\{join(?:: (.+?))?\}")
#: A `${name}` in a command template, resolved to its positional argument.
NAME_RE = re.compile(r"\$\{?([a-z_][a-z0-9_-]*)\}?(?!\w)")


#: How a slot's value is turned into its key's value — each kind is one function in the render.
type Resolve = Literal["tier", "names", "hint", "denied"]


class FmField(msgspec.Struct, frozen=True):
    """One frontmatter key: which structured slot feeds it, under which name, through which resolver.

    `table` is the resolver's data, when it needs some: for `denied`, house permission key →
    the backend's tool names.
    """

    slot: str
    key: str
    required: bool = False
    resolve: Resolve | None = None
    table: dict[str, list[str]] = {}


class Preload(msgspec.Struct, frozen=True):
    """A list slot folded into one line above the body."""

    slot: str
    line: str


class Flat(msgspec.Struct, frozen=True):
    """How one structured instance becomes one flat file."""

    path: str
    body_slot: str
    body_title: str | None = None
    body_preload: Preload | None = None
    positional: str = ""
    #: What each declared input becomes in the body: `{n}` its 1-based position, `{name}` its name.
    placeholder: str = "${n}"
    frontmatter: list[FmField] = []
    house_only: list[str] = []


class Refs(msgspec.Struct, frozen=True):
    """Auxiliary files carried verbatim beside the flat file."""

    slot: str = ""
    dir: str = ""


class Block(msgspec.Struct, frozen=True):
    """One typeset block of a document: the slots it joins, in order, under one form.

    `h1`, `para` and `quote` are the preamble, at most one of each, before the first `h2`.
    An `h2` carries its `heading`. Slots are joined by `join` — a blank line between
    paragraphs, a bare newline when the slots are fragments of one list. An empty slot is
    skipped; a block whose slots are all empty is not rendered at all.
    """

    type: Literal["h1", "para", "quote", "h2"]
    slots: list[str]
    heading: str = ""
    join: str = "\n\n"

    @property
    def key(self) -> str:
        """How the block is told apart when a document is read back: its heading, or its form."""
        return self.heading if self.type == "h2" else self.type


class Region(msgspec.Struct, frozen=True):
    """A part of a target document the harness owns: never drift, carried over on write, never absorbed.

    `heading`: an `## {match}` section up to the next `## `. `marker`: from a `start` regex
    to an `end` regex; `end` may back-reference the groups of `start`. `sample` is one
    instance as the harness writes it, `${nonce}` inside: what a trial plants to prove the
    region survives an export and is never absorbed.
    """

    kind: Literal["heading", "marker"]
    match: str = ""
    start: str = ""
    end: str = ""
    sample: str = ""


class Document(msgspec.Struct, frozen=True):
    """One markdown file the persona renders into: which slots land where, and what the harness keeps for itself.

    `limit` is the harness's own cap in characters (0: none): a render above it is refused,
    never truncated downstream. `audience` is who loads the file — information, not behaviour.
    """

    target: str
    blocks: list[Block]
    limit: int = 0
    audience: str = ""
    regions: list[Region] = []


class ConfigFile(msgspec.Struct, frozen=True):
    """One emitted config file: JSON or TOML with its keys in canonical order, or text that carries one slot.

    A JSON file owns root keys. A TOML file owns dotted paths (`search.roles`): a harness keeps its
    own leaves inside the same tables — a key it stores there is never ours to render or overwrite.
    `within` names tables only the harness creates (a channel it connects, with its secret): an
    owned key under one is written only where the live file already holds that table.
    `items` narrows an owned list to the items matching a filter (`memory_sources: {kind: folder}`):
    the core owns those, every other item is the harness's and is kept.
    """

    out: str
    keys: list[str] = []
    within: list[str] = []
    items: dict[str, dict[str, str]] = {}
    format: Literal["json", "toml", "yaml", "env", "text"] = "json"
    slot: str = ""


class Asset(msgspec.Struct, frozen=True):
    """A file of core/tekton/config carried verbatim into the tree at the same relative path, and the slot it moves."""

    out: str
    slot: str


class Config(msgspec.Struct, frozen=True):
    """How core/tekton/config modules become the backend's config files, and which of its files travel as they are."""

    #: byte · semantic (same JSON) · keys (same JSON on the keys the spec declares; the coder's own keys are kept)
    exactness: Literal["byte", "semantic", "keys"] = "byte"
    modules: list[str] = []
    files: list[ConfigFile] = []
    assets: list[Asset] = []
    #: What only this harness has, so the core never names it: its ids, its own providers, its words for the core's.
    native: dict[str, Any] = {}


class Graph(msgspec.Struct, frozen=True):
    """A derived flat body: the graph of an instance rendered, never copied."""

    nodes_slot: str = "nodes"
    output_slot: str = "output"
    loop_slot: str = "loop"
    start: str = "start"
    done: str = "done"


class Spec(msgspec.Struct, frozen=True):
    """A backend's model for one entity: data the transpiler obeys, never code."""

    entity: str
    release: str
    verified: str = ""
    sources: list[str] = []
    status: str = "ready"
    structured_manifest: str = ""
    flat: Flat | None = None
    references: Refs = Refs()
    documents: list[Document] = []
    config: Config | None = None
    graph: Graph | None = None


class GhostProbe(msgspec.Struct, frozen=True):
    """One way a phantom instance shows what it loaded.

    `capture`: run `argv` and read what reached the fake LLM the sandbox serves at `${llm}`.
    `command`: read what `argv` itself prints. A harness that only runs a turn as a service
    declares `serve` (kept up for the probe, on `${port}`), `ready` (polled until it exits 0)
    and `wait` (seconds to wait for the capture to receive the turn); `argv` then triggers it.
    """

    name: str
    kind: Literal["capture", "command"]
    argv: list[str]
    timeout: float = 120.0
    serve: list[str] = []
    ready: list[str] = []
    wait: float = 0.0


class GhostLink(msgspec.Struct, frozen=True):
    """A symlink the harness's real topology has: `path` → `to`; `${document}` repeats it per persona document,
    `only` (a glob on the document's target) narrows which ones."""

    path: str
    to: str
    only: str = "*"


class GhostOverlay(msgspec.Struct, frozen=True):
    """Keys imposed on a harness file while a phantom loads — routing its model calls to the fake LLM.

    Applied after every apply and before the probes, so the render is what placement judges and
    the overlay only what the phantom runs on. `swap` rewrites every equal string value first (a
    rendered endpoint pointed at the fake, wherever the render placed it); `set` is keyed by dotted
    path; `extend` appends to the list at a dotted path, keeping what the render put there.
    Strings bind placeholders.
    """

    path: str
    format: Literal["toml", "json", "yaml"]
    swap: dict[str, str] = {}
    set: dict[str, Any] = {}
    extend: dict[str, list[Any]] = {}


class GhostSeed(msgspec.Struct, frozen=True):
    """A tree copied read-only from the real home into the sandbox: `path` (`~` expands) → `to`."""

    path: str
    to: str


class GhostMemory(msgspec.Struct, frozen=True):
    """The memory pipeline end to end in a phantom: a note fed to a rendered source, embedded, sealed into a tree.

    `seed` brings what the harness would download (the fence keeps the network local). `serve`
    keeps the harness up on `${port}`; `rpc` is its JSON-RPC URL and `token` the bearer `env`
    gives it. `source` names a rendered memory source: the note lands in its folder, the source
    is synced, the tree flushed. Done when the queue drains or `timeout` runs out. Then `store`,
    the harness's own SQLite, is read: `counts` maps every `Memory` count to the query giving it,
    `errors` is the query listing what failed.
    """

    serve: list[str]
    rpc: str
    token: str
    source: str
    store: str
    counts: dict[str, str]
    errors: str
    seed: list[GhostSeed] = []
    timeout: float = 180.0


class GhostState(msgspec.Struct, frozen=True):
    """Runtime state an established harness already holds, written into the sandbox before anything runs.

    A fresh home makes a harness run its first-start migrations, and those rewrite files
    the render owns. The trial raises an established harness, not a new install: `text`
    is written to `path` — never a secret, only the markers that tell the harness it has
    already been set up.
    """

    path: str
    text: str


class Ghost(msgspec.Struct, frozen=True):
    """`specs/<harness>/<backend>/ghost.yaml` — how a phantom instance of the harness is raised in a sandbox, and what it must see.

    A new backend is a new file: where its live tree sits under a home (`tree`), the
    environment that points the real binary at the sandbox and nowhere else (`env`), the
    links its topology needs, the probes that read what it loaded, and which entities each
    probe must show (`sees`). `llm` names the protocol the fake endpoint speaks; `network`
    whether the fence lets the binary reach anything but that endpoint. `stage` lists the
    specs promoted to ready inside the sandbox only, so a pending model is tested before
    it ships. `setup` runs once a phantom is about to load (a local credential, say);
    `overlays` route it to the fake endpoint. `blind` names the documents no probe can show:
    their slots are not asked for as evidence, and a mutation in one is judged on the live file.
    `memory`, when declared, runs the harness's memory pipeline over the applied tree.
    """

    backend: str
    release: str
    verified: str = ""
    status: str = "ready"
    sources: list[str] = []
    tree: str = ""
    llm: Literal["anthropic", "openai", "none"] = "none"
    network: Literal["local", "open"] = "local"
    env: dict[str, str] = {}
    links: list[GhostLink] = []
    state: list[GhostState] = []
    stage: list[str] = []
    setup: list[list[str]] = []
    overlays: list[GhostOverlay] = []
    probes: list[GhostProbe] = []
    sees: dict[str, list[str]] = {}
    blind: list[str] = []
    memory: GhostMemory | None = None
    notes: str = ""


class Source(msgspec.Struct, frozen=True):
    """One upstream place a change becomes visible: a feed, a schema, a page, a registry."""

    name: str
    kind: Literal["atom", "api", "npm", "json", "markdown", "html", "git"]
    url: str
    note: str = ""


class SourceCategory(msgspec.Struct, frozen=True):
    """One kind of change the harness can undergo, and the sources that prove it."""

    watch: str = ""
    sources: list[Source] = []
    specs: dict[str, dict[str, Any]] = {}


class Sources(msgspec.Struct, frozen=True):
    """`specs/<harness>/<backend>/sources.yml` — the maintenance contract: what to watch, where, as what kind."""

    backend: str
    product: str = ""
    verified: str = ""
    repo: str = ""
    entities_index: list[Source] = []
    categories: dict[str, SourceCategory] = {}


#: The change categories every backend must declare, identical across backends — the shared maintenance surface.
SOURCE_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "core",
        "changelog",
        "config",
        "entities",
        "tools",
        "extensions",
        "cli",
        "deprecations",
        "community",
    }
)
#: Categories that inform but never act on their own (flow-gen-specs, signals.md): the clock and the chatter.
CONTEXT_CATEGORIES: Final[frozenset[str]] = frozenset({"core", "community"})


class Probe(msgspec.Struct, frozen=True):
    """What one source returned at the last look: the machine-readable unit of memory."""

    version: str = ""
    facts: tuple[str, ...] = ()


class Signal(msgspec.Struct, frozen=True):
    """One drift: backend, category, source and what moved — the only input a maintainer trusts."""

    backend: str
    category: str
    source: str
    detail: str
