"""transpiler.render — spec-driven, deterministic corpus conversion: structured core/ → flat tree.

Everything the transpiler knows about a backend lives in specs/<harness>/<backend>/ and
specs/<harness>/common/ (data, maintained by the speckeeper through the enhancer). The render is
pure: core/ + specs/ in, files out. It never reads its own output, and it only ever
touches the paths it produces — runtime state living beside them (sessions, projects,
autolearn memory, runtime-owned skill trees) is not its business. The commands that
drive it live in `ops/cli/commands/transpiler.py`.
"""

from __future__ import annotations

import functools
import shlex
from collections import Counter
from collections.abc import Callable, Mapping
from functools import cached_property
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Literal

import eserde
import msgspec

from ops.core.dotted import dotted_drop, dotted_get, dotted_set
from ops.core.settings import settings
from ops.models.entity import FACETS, HARNESS, INSTANCED, Backend, Entity
from ops.models.graph import LoopDecl
from ops.models.mcp import McpServer, McpServers
from ops.models.spec import (
    JOIN_RE,
    NAME_RE,
    ConfigFile,
    Document,
    Flat,
    FmField,
    Graph,
    Spec,
)
from ops.transpiler.typeset import Typeset

SCHEMA_URL: Final[Mapping[Backend, str]] = {
    Backend.OPENCODE: "https://opencode.ai/config.json",
    Backend.CLAUDECODE: "https://json.schemastore.org/claude-code-settings.json",
}

#: What an export does with flat files the render no longer produces.
type Capability = Literal["replace", "reset"]
#: Why a flat file fails the replication gate.
type Kind = Literal["missing", "drift", "stale", "symlink"]


# ------------------------------------------------------------------ verdict
class Drift(msgspec.Struct, frozen=True):
    """One flat file that does not replicate the render."""

    path: str
    kind: Kind

    def __str__(self) -> str:
        return f"{self.path}: {self.kind}"


class Report(msgspec.Struct, frozen=True):
    """What one export did."""

    written: tuple[str, ...] = ()
    pruned: tuple[str, ...] = ()
    faithful: int = 0

    def __str__(self) -> str:
        pruned = f" · {len(self.pruned)} pruned" if self.pruned else ""
        return "\n".join(
            (
                *self.written,
                *(f"- {p}" for p in self.pruned),
                f"{len(self.written)} written · {self.faithful} already faithful{pruned}",
            )
        )


def _parse_json(text: str) -> object:
    return eserde.loads(text, format=eserde.Format.JSONC)


def _parse_env(text: str) -> dict[str, str]:
    """The KEY=VALUE lines of a dotenv file; comments, blanks and lines without `=` carry no key."""
    return {
        key.strip().removeprefix("export ").strip(): value.strip().strip('"').strip("'")
        for line in text.splitlines()
        if (stripped := line.strip()) and not stripped.startswith("#") and "=" in stripped
        for key, _, value in (stripped.partition("="),)
    }


#: How each structured config format is read back.
PARSE: Final[Mapping[str, Callable[[str], object]]] = {
    "json": _parse_json,
    "toml": lambda text: eserde.loads(text, format=eserde.Format.TOML),
    "yaml": lambda text: eserde.loads(text, format=eserde.Format.YAML) or {},
    "env": _parse_env,
}


def _dump_toml(data: dict) -> str:
    return eserde.dumps(data, format=eserde.Format.TOML).decode()


def _dump_yaml(data: dict) -> str:
    return eserde.dumps(data, format=eserde.Format.YAML).decode()


def _dump_env(data: Mapping[str, object]) -> str:
    return "".join(f"{key}={value}\n" for key, value in data.items())


#: How a dotted-path format is written back from its nested tables.
DUMP: Final[Mapping[str, Callable[[dict], str]]] = {"toml": _dump_toml, "yaml": _dump_yaml}


def _merge_env(live: str, owned: Mapping[str, object], omitted: frozenset[str]) -> str:
    """The live dotenv with each owned key set in place (appended when new) and each omitted key dropped.

    Every other line — comments, blanks, the harness's secrets — is kept byte for byte: a secret is never
    parsed into the render, only stepped over.
    """
    keyed = [(line, next(iter(_parse_env(line)), None)) for line in live.splitlines()]
    kept = [f"{key}={owned[key]}" if key and key in owned else line for line, key in keyed if key not in omitted]
    present = {key for _, key in keyed if key}
    return "\n".join([*kept, *(f"{key}={value}" for key, value in owned.items() if key not in present)]) + "\n"


def _dump_json(obj: object) -> str:
    """Indented JSON: a generated file is read by humans, but never edited by them."""
    return msgspec.json.format(eserde.dumps(obj, format=eserde.Format.JSON), indent=2).decode() + "\n"


class Transpiler:
    """One transpiler per backend+out. It only knows what the specs say.

    Without `out` it lands on the backend's own live tree (`settings.transpiler.targets`):
    every backend owns one, so no backend ever compares against another's files.
    """

    def __init__(
        self,
        root: Path | None = None,
        backend: Backend = Backend.OPENCODE,
        out: Path | None = None,
        profile: str | None = None,
    ) -> None:
        """`profile` binds `{profile}` in spec paths; the backend's from settings when not given."""
        self.root = (root or settings.ROOT).resolve()
        self.backend = backend
        self.profile = settings.transpiler.profiles.get(backend, "") if profile is None else profile
        self.out = out.expanduser().resolve() if out else settings.transpiler.live(backend)
        self.specs = self.root / settings.layout.harness(backend)

    @cached_property
    def config_dir(self) -> Path:
        """Where this backend's config modules live: the config of the first facet its harness renders."""
        return self.root / settings.layout.core(FACETS[HARNESS[self.backend]][0])[Entity.CONFIG]

    @cached_property
    def model_tiers(self) -> dict[str, str]:
        """House tiers (builder, scout…) → provider/model ids, from core/tekton/config/models.yaml alone.

        A tier names a provider alias plus a model; the alias carries the vendor id. Reading
        the rendered config back would make the render depend on its own output.
        """
        models = eserde.load(self.config_dir / "models.yaml")
        vendor = {alias: data["id"] for alias, data in models["providers"].items()}
        return {
            tier: f"{vendor[alias]}/{model}"
            for tier, data in models["tiers"].items()
            for alias, model in (data["model"].split("/", 1),)
        }

    # ---------------------------------------------------------------- public
    def spec(self, entity: Entity) -> Spec | None:
        """The live spec for an entity, or None while the backend's model is pending."""
        return self.find(entity.value, "flat")

    def ids(self, entity: Entity, spec: Spec) -> list[str]:
        """Every structured instance of an entity, by directory name."""
        root = self.root / settings.layout.core()[entity]
        return sorted(p.parent.name for p in root.glob(f"*/{spec.structured_manifest}")) if root.is_dir() else []

    @cached_property
    def files(self) -> Mapping[Path, str]:
        """The whole flat corpus this backend should hold: entities, persona, config."""
        entities = {
            path: text
            for entity in INSTANCED
            if (spec := self.spec(entity))
            for ident in self.ids(entity, spec)
            for path, text in self._entity(spec, ident).items()
        }
        return entities | self._persona() | self._config()

    @cached_property
    def config_names(self) -> frozenset[str]:
        """The structured files the config spec emits (JSON, TOML) — the only ones a spec may compare loosely."""
        spec = self.find("config", "config")
        return frozenset(f.out for f in spec.config.files if f.format in PARSE) if spec and spec.config else frozenset()

    @cached_property
    def mcp(self) -> McpServers:
        """The facet's mcp.yaml with `{out}` bound to this tree: every backend's MCP servers, one declaration; none without one."""
        source = self.config_dir / "mcp.yaml"
        raw = source.read_text().replace("{out}", str(self.out)) if source.is_file() else "servers: {}"
        return eserde.loads(raw, format=eserde.Format.YAML, type=McpServers)

    def mcp_registrations(self) -> dict[str, dict[str, Any]]:
        """Claude Code's user-scope servers in the shape `claude mcp add-json` takes: not a file the tree holds."""
        return {
            name: self._mcp_claudecode(server) for name, server in self.mcp.of(self.backend).items() if server.enabled
        }

    def export(self, capability: Capability = "replace", dry: bool = False) -> Report:
        """Write the corpus into out/. `replace` leaves strangers alone; `reset` prunes them."""
        files = self.files
        doomed = {"replace": tuple, "reset": lambda: self._stale(files)}[capability]()
        claimed = self._links(files)
        written = [
            path
            for path, text in files.items()
            if not self._faithful(path, text) or any(path.is_relative_to(link) for link in claimed)
        ]
        if not dry:
            for link in claimed:
                link.unlink()
            for path in written:
                self._write(path, self.merged(path, files[path]))
            self._prune(doomed)
        return Report(tuple(map(self._rel, written)), tuple(map(self._rel, doomed)), len(files) - len(written))

    def check(self) -> tuple[Drift, ...]:
        """The replication gate: every way out/ fails to mirror the render. Never writes."""
        files = self.files
        return (
            *(
                Drift(self._rel(p), "drift" if p.is_file() else "missing")
                for p, text in files.items()
                if not self._faithful(p, text)
            ),
            *(Drift(self._rel(p), "stale") for p in self._stale(files)),
            *(Drift(self._rel(link), "symlink") for link in self._links(files)),
        )

    # ------------------------------------------------------------------ spec
    def emitted(self, entity: Entity) -> frozenset[str]:
        """Every slot the render can put in the flat form of an entity: what the matrix must judge."""
        match entity:
            case Entity.PERSONA:
                spec = self.find("persona", "documents")
                return frozenset(
                    slot for doc in (spec.documents if spec else ()) for block in doc.blocks for slot in block.slots
                )
            case Entity.CONFIG:
                cfg = self.find("config", "config")
                return (
                    frozenset(
                        {key for file in cfg.config.files for key in file.keys}
                        | {file.slot for file in cfg.config.files if file.slot}
                        | {asset.slot for asset in cfg.config.assets}
                    )
                    if cfg and cfg.config
                    else frozenset()
                )
            case _:
                spec = self.spec(entity)
                return (
                    frozenset({field.key for field in spec.flat.frontmatter} | {spec.flat.body_slot})
                    if spec and spec.flat
                    else frozenset()
                )

    def find(self, name: str, needs: str) -> Spec | None:
        """The newest ready spec for a name, backend before common; `{profile}` bound to this backend's profile."""
        found = [
            eserde.loads(p.read_text().replace("{profile}", self.profile), format=eserde.Format.YAML, type=Spec)
            for p in (self.specs / self.backend.value / f"{name}.yaml", self.specs / "common" / f"{name}.yaml")
            if p.is_file()
        ]
        ok = [s for s in found if s.status == "ready" and getattr(s, needs)]
        return max(ok, key=lambda s: (s.release, s.verified)) if ok else None

    # -------------------------------------------------------------- entities
    def _entity(self, spec: Spec, ident: str) -> dict[Path, str]:
        """One structured instance → its flat file plus every reference it carries."""
        assert spec.flat
        sdir = self.root / settings.layout.core()[Entity(spec.entity)] / ident
        data = self.unwrap(eserde.load(sdir / spec.structured_manifest, embed=True))
        target = self.out / spec.flat.path.format(id=ident)
        refs = data.get(spec.references.slot, []) if spec.references.slot else []
        return {target: self._compose(spec.flat, ident, data, sdir, spec.graph)} | {
            target.parent / ref: (sdir / ref).read_text() for ref in refs
        }

    @classmethod
    def unwrap(cls, node: Any) -> Any:
        """Lift every embedded sub-document out of its `source` envelope.

        e-serde (`embed=True`) resolves each `source:` reference against the document that
        holds it — markdown as text, structured files as trees, recursively, confined to the
        instance dir, cycles refused — and keeps the envelope: `{source: <tree>}`. A manifest
        split into files (`nodes: [{source: nodes/intake.yaml}, …]`) means the tree itself, so
        a lone envelope around a mapping or a list is lifted; `{source: <text>}` stays, it is a
        body slot `_body` reads. Declaration order is kept: the render equals the one-file one.
        """
        match node:
            case {"source": dict() | list() as tree} if len(node) == 1:
                return cls.unwrap(tree)
            case dict():
                return {key: cls.unwrap(value) for key, value in node.items()}
            case list():
                return [cls.unwrap(value) for value in node]
            case _:
                return node

    def _compose(self, flat: Flat, ident: str, data: dict, sdir: Path, graph: Graph | None = None) -> str:
        """Frontmatter + body, in the order the spec declares — a graph body is derived, never copied."""
        body = (self._graph(graph, data) if graph else self._body(data.get(flat.body_slot, ""), sdir)).rstrip()
        if (pre := flat.body_preload) and (items := data.get(pre.slot)):
            body = f"{JOIN_RE.sub(lambda m: (m.group(1) or ', ').strip(chr(39)).join(items), pre.line)}\n\n{body}"
        if flat.positional and (names := list(data.get(flat.positional, {}))):
            body = NAME_RE.sub(
                lambda m: (
                    flat.placeholder.format(n=names.index(m.group(1)) + 1, name=m.group(1))
                    if m.group(1) in names
                    else m.group(0)
                ),
                body,
            )
        title = f"# {ident}\n\n" if flat.body_title == "id" else ""
        return f"{self._frontmatter(flat, data)}\n\n{title}{body}\n"

    def _graph(self, graph: Graph, data: dict) -> str:
        """An instance of the graph rendered: mermaid over the edges, steps over the nodes, output declared.

        The declaration order of the nodes is the canonical order of the render: same graph in,
        same bytes out — the replication gate demands it and the interpreter reads it.
        """
        nodes = data.get(graph.nodes_slot, [])
        if not nodes:
            raise ValueError(f"{graph.nodes_slot}: an empty graph is not a workflow")
        ids = [node["id"] for node in nodes]
        if clash := set(ids) & {graph.start, graph.done}:
            raise ValueError(f"node ids collide with the terminals: {sorted(clash)}")
        depends = {node["id"]: list(node.get("depends") or []) for node in nodes}
        if bad := {p for ps in depends.values() for p in ps if p not in ids or p in {graph.start, graph.done}}:
            raise ValueError(f"edges to undeclared or terminal nodes: {sorted(bad)}")
        parents = {node_id: ps or [graph.start] for node_id, ps in depends.items()}
        depended = {p for ps in parents.values() for p in ps}
        edges = [f"    {parent} --> {node['id']}" for node in nodes for parent in parents[node["id"]]]
        edges += [f"    {node['id']} --> {graph.done}" for node in nodes if node["id"] not in depended]
        steps = "\n\n".join(
            f"### {node['id']} (depends: {', '.join(parents[node['id']])})\n\n" + self._graph_step(node)
            for node in nodes
        )
        loop = msgspec.convert(raw, LoopDecl) if (raw := data.get(graph.loop_slot)) else None
        if loop and (problems := loop.problems(ids)):
            raise ValueError("; ".join(problems))
        edges += [f'    {loop.nodes[-1]} -.->|"until {loop.until} · max {loop.max}"| {loop.nodes[0]}'] if loop else []
        blocks = ["```mermaid\nflowchart TD\n" + "\n".join(edges) + "\n```", f"## steps\n\n{steps}"]
        blocks += [self._graph_loop(loop)] if loop else []
        if out := data.get(graph.output_slot):
            blocks.append("## output\n\n" + "\n".join(f"{k}: {v}" for k, v in out.items()))
        return "\n\n".join(blocks)

    @staticmethod
    def _graph_loop(loop: LoopDecl) -> str:
        """The loop as the lead reads it: which steps repeat, how many times at most, and what ends it."""
        return (
            f"## loop\n\nRepeat {' → '.join(f'`{n}`' for n in loop.nodes)} at most {loop.max} times. "
            f"`{loop.until}` ends it: its command exits 0 (closed), or prints the same open set as the "
            "previous iteration (stalled). After an ending check every remaining step of the loop is skipped "
            "and the run continues past it. `{{iteration}}` is the current pass, from 1."
        )

    @staticmethod
    def _graph_step(node: dict) -> str:
        """One step's body: its condition, then a command to run or an instruction for its actor.

        `when: {op: [create, retire]}` renders as a condition line; `run:` as the exact command,
        which both executors run as is — `op workflow run` itself, `/workflow` through the lead.
        """
        when = "".join(
            f"*only when `{key}` is {' or '.join(f'`{v}`' for v in ([values] if isinstance(values, str) else values))}*\n\n"
            for key, values in (node.get("when") or {}).items()
        )
        match node:
            case {"run": str(command)}:
                note = f"\n\n{node['instruction']}" if node.get("instruction") else ""
                return f"{when}run: `{command}`{note}"
            case {"instruction": str(text)}:
                return when + (f"@{node['actor']} " if node.get("actor") else "") + text
            case _:
                raise ValueError(f"step {node.get('id')!r}: needs `run` or `instruction`")

    @staticmethod
    def _body(value: object, sdir: Path) -> str:
        """A body slot is inline markdown, a file e-serde already embedded, or a bare `.md` name beside the manifest."""
        match value:
            case {"source": str(text)}:
                return text
            case str() if value.endswith(".md"):
                return (sdir / value).read_text()
            case _:
                return str(value or "")

    def _frontmatter(self, flat: Flat, data: dict) -> str:
        fields = {
            field.key: resolved
            for field in flat.frontmatter
            if (value := self._slot(flat, field, data)) not in (None, "", [], {})
            and (resolved := self._resolve(field, value)) not in (None, "", [], {})
        }
        return "---\n" + eserde.dumps(fields, format=eserde.Format.YAML).decode().rstrip() + "\n---"

    @staticmethod
    def _slot(flat: Flat, field: FmField, data: dict) -> object:
        if (value := data.get(field.slot)) in (None, "", [], {}) and field.required:
            raise ValueError(f"{flat.path}: required slot '{field.slot}' is empty")
        return value

    def _resolve(self, field: FmField, value: Any) -> object:
        return self._RESOLVE[field.resolve](self, field, value)

    def _resolve_as_is(self, _: FmField, value: Any) -> object:
        return value

    def _resolve_tier(self, _: FmField, value: Any) -> object:
        """A house tier → the provider/model id it names; anything else passes through."""
        return self.model_tiers.get(value, value)

    def _resolve_names(self, _: FmField, value: Any) -> list[str]:
        """A mapping of declared inputs → their names, in declaration order."""
        return list(value)

    def _resolve_hint(self, _: FmField, value: Any) -> str:
        """A mapping of declared inputs → the `[a] [b]` hint a coder shows while typing."""
        return " ".join(f"[{name}]" for name in value)

    def _resolve_denied(self, field: FmField, value: Any) -> list[str]:
        """A house permission map → the backend tools it denies outright, in the table's order.

        Only a flat `deny` (or `"*": deny` with nothing allowed beside it) is a denied tool;
        a pattern-scoped grant has no tool-level equivalent and stays to the coder's own rules.
        """
        return [
            tool
            for key, tools in field.table.items()
            if (rule := value.get(key)) == "deny" or (isinstance(rule, dict) and set(rule.values()) == {"deny"})
            for tool in tools
        ]

    #: One resolver per kind a spec may name; no kind is the slot's value as it stands.
    _RESOLVE: Final[Mapping[str | None, Callable[[Transpiler, FmField, Any], object]]] = {
        None: _resolve_as_is,
        "tier": _resolve_tier,
        "names": _resolve_names,
        "hint": _resolve_hint,
        "denied": _resolve_denied,
    }

    # --------------------------------------------------------------- persona
    @cached_property
    def persona(self) -> Mapping[str, str]:
        """Every persona slot this backend's harness may render: core/base, then its facets. A slot lives in one layer."""
        found = [
            (slot, value["source"] if isinstance(value, dict) else str(value))
            for layer in self._persona_layers
            for slot, value in eserde.load(layer / "persona.yaml", embed=True)["slots"].items()
        ]
        if twice := sorted(slot for slot, count in Counter(slot for slot, _ in found).items() if count > 1):
            raise ValueError(f"persona slots declared by more than one layer: {twice}")
        return MappingProxyType(dict(found))

    @cached_property
    def sources(self) -> Mapping[str, Path | None]:
        """Where each persona slot's text lives: its `.md` file, or None when it is inline in its layer's manifest."""
        return MappingProxyType(
            {
                slot: layer / value["source"] if isinstance(value, dict) else None
                for layer in self._persona_layers
                for slot, value in eserde.load(layer / "persona.yaml")["slots"].items()
            }
        )

    @cached_property
    def documents(self) -> tuple[Document, ...]:
        """The persona documents this backend's spec declares; none while it is pending."""
        spec = self.find("persona", "documents")
        return tuple(spec.documents) if spec else ()

    @cached_property
    def _persona_layers(self) -> tuple[Path, ...]:
        return (
            self.root / settings.layout.base,
            *(self.root / settings.layout.core(facet)[Entity.PERSONA] for facet in FACETS[HARNESS[self.backend]]),
        )

    def _persona(self) -> dict[Path, str]:
        """The persona documents: one registry of slots, one markdown file per document the spec declares."""
        return {self.out / doc.target: Typeset(doc).render(self.persona) for doc in self.documents}

    @cached_property
    def _documents(self) -> Mapping[Path, Document]:
        return {self.out / doc.target: doc for doc in self.documents}

    # ---------------------------------------------------------------- config
    def _config(self) -> dict[Path, str]:
        """The facet's config modules → the backend's config files, keys in the order the spec fixes."""
        if (spec := self.find("config", "config")) is None or not spec.config:
            return {}
        mods = {name: eserde.load(self.config_dir / f"{name}.yaml") for name in spec.config.modules}
        built = self._CONFIG[self.backend](self, mods)
        files = {self.out / f.out: self._config_text(f, built[f.out]) for f in spec.config.files}
        return files | {self.out / asset.out: (self.config_dir / asset.out).read_text() for asset in spec.config.assets}

    def _config_text(self, file: ConfigFile, built: Any) -> str:
        """JSON keyed by root; TOML and YAML keyed by dotted path, nested back into their tables; dotenv flat; text as built."""
        match file.format:
            case "json":
                return _dump_json(self._ordered(file, built))
            case "toml" | "yaml":
                ordered = self._ordered(file, built)
                return DUMP[file.format](functools.reduce(lambda acc, kv: dotted_set(acc, *kv), ordered.items(), {}))
            case "env":
                return _dump_env(self._ordered(file, built))
            case _:
                return built

    @staticmethod
    def _ordered(file: ConfigFile, data: Mapping[str, object]) -> dict[str, object]:
        """The built keys in the spec's order; a `prefix.*` spec key takes every built child of prefix, in build order."""
        keys = file.keys or list(data)
        ordered = [
            built
            for key in keys
            for built in (
                [k for k in data if k.startswith(key[:-1]) and "." not in k[len(key) - 1 :]]
                if key.endswith(".*")
                else [key]
            )
            if built in data
        ]
        if extra := set(data) - set(ordered):
            raise ValueError(f"{file.out}: keys absent from the spec: {sorted(extra)}")
        return {key: data[key] for key in ordered}

    def _config_opencode(self, mods: Mapping[str, dict]) -> dict[str, Any]:
        main, models, agents, perms, plugins = (mods[k] for k in ("main", "models", "agents", "permissions", "plugins"))
        model = {k: self.model_tiers.get(v, v) for k, v in main["model"].items() if isinstance(v, str)}
        return {
            "opencode.jsonc": {
                "$schema": SCHEMA_URL[Backend.OPENCODE],
                "username": main["user"],
                "model": model["default"],
                "small_model": model["small"],
                "agent": self._agents(agents),
                "plugin": plugins["opencode"],
                "instructions": [path.format(out=self.out) for path in main["instructions"]],
                "mcp": {name: self._mcp_opencode(server) for name, server in self.mcp.of(Backend.OPENCODE).items()},
                "permission": perms["granular"],
                "enabled_providers": [data["id"] for data in models["providers"].values()],
                "provider": self._providers(models),
            },
            "tui.json": {"plugin": plugins["tui"]},
            "package.json": {"dependencies": dict((plugins["sdk"].rsplit("@", 1),))},
        }

    def _config_claudecode(self, mods: Mapping[str, dict]) -> dict[str, Any]:
        """User settings: the session's model and effort, the permission policy, the hooks."""
        main, perms, hooks = (mods[k] for k in ("main", "permissions", "hooks"))
        return {
            "rules/instructions.md": "".join(f"@{path.format(out=self.out)}\n" for path in main["instructions"]),
            "settings.json": {
                "$schema": SCHEMA_URL[Backend.CLAUDECODE],
                "model": main["model"]["alias"][Backend.CLAUDECODE],
                "effortLevel": main["effort"],
                "tui": main["display"]["tui"],
                "permissions": {
                    "allow": perms["rules"]["allow"],
                    "defaultMode": perms["default_mode"],
                    "additionalDirectories": perms["external_dirs"],
                },
                "hooks": self._hooks(hooks),
            },
        }

    def _config_openhuman(self, mods: Mapping[str, dict]) -> dict[str, Any]:
        """config.toml by dotted path: the agnostic core in OpenHuman's words (spec `native`) — the app keeps the rest."""
        main, models, memory, sources, voice, search, channels, tools, permissions, mcp = (
            mods[k]
            for k in (
                "main",
                "models",
                "memory",
                "sources",
                "voice",
                "search",
                "channels",
                "tools",
                "permissions",
                "mcp",
            )
        )
        spec = self.find("config", "config")
        native = spec.config.native if spec and spec.config else {}
        route = lambda role: models["roles"][native["roles"][role]].replace("/", ":", 1)  # noqa: E731
        stt, tts = f"evoice-stt:{voice['stt']['model']}", f"evoice-tts:{voice['tts']['voice']}"
        embedder = memory["embedder"]
        vault = self.out / "memory"
        voices = [
            {
                "id": "vp_evoice_stt",
                "slug": "evoice-stt",
                "label": "e-voice STT",
                "endpoint": voice["stt"]["endpoint"],
                "auth_style": "bearer",
                "capability": "stt",
                "stt_api_style": "openaiaudio",
                "tts_api_style": "openaiaudio",
                "default_stt_model": voice["stt"]["model"],
            },
            {
                "id": "vp_evoice_tts",
                "slug": "evoice-tts",
                "label": "e-voice TTS",
                "endpoint": voice["tts"]["endpoint"],
                "auth_style": "bearer",
                "capability": "tts",
                "stt_api_style": "openaiaudio",
                "tts_api_style": "openaiaudio",
                "default_tts_voice": voice["tts"]["voice"],
            },
        ]
        engines = search["engines"]
        rows = {
            "default_model": route("default"),
            "primary_cloud": native["ids"][models["primary"]],
            **{
                f"{role}_provider": route(role)
                for role in ("chat", "reasoning", "agentic", "coding", "memory", "vision")
            },
            ### The core reads a BYOK model as image-capable only from its registry flag.
            "model_registry": [
                {"id": model, "provider": provider, "vision": True}
                for provider, model in (route("vision").split(":", 1),)
            ],
            "stt_provider": stt,
            "tts_provider": tts,
            ### The memory host finds a custom embedder only by slug among cloud providers (openhuman#6984).
            "cloud_providers": [
                *(
                    {
                        "id": native["ids"][slug],
                        "slug": slug,
                        "label": p["label"],
                        "endpoint": p["endpoint"],
                        "auth_style": native["auth"][p["api"]],
                    }
                    for slug, p in models["providers"].items()
                ),
                *(
                    {
                        "id": p["id"],
                        "slug": slug,
                        "label": p["label"],
                        "endpoint": p["endpoint"],
                        "auth_style": p["auth"],
                    }
                    for slug, p in native["providers"].items()
                ),
                {
                    "id": "p_custom_embedder",
                    "slug": "custom",
                    "label": "Embedder (memory host)",
                    "endpoint": embedder["endpoint"],
                    "auth_style": "bearer",
                },
            ],
            "voice_providers": voices,
            "memory.embedding_provider": f"custom:{embedder['endpoint']}",
            "memory.embedding_model": embedder["model"],
            "memory.embedding_dimensions": embedder["dimensions"],
            "custom_embeddings": {k: embedder[k] for k in ("endpoint", "model", "dimensions")},
            "memory.engine": memory["engine"]["kind"],
            f"memory.engines.{memory['engine']['kind']}.endpoint": memory["engine"]["endpoint"],
            "memory.sources": [
                {
                    "id": src["id"],
                    "kind": "folder",
                    "target": str(vault / src["path"]),
                    "label": src["label"],
                    "schedule_mins": memory["sync"],
                }
                for src in sources.values()
                if not src.get("off", False)
            ],
            "searxng.base_url": engines["searxng"]["url"],
            "search.roles": {"search": search["order"]},
            "search.providers": {
                name: {"enabled": not engine.get("off", False), "route": native["routes"][engine["via"]]}
                for name, engine in engines.items()
            },
            "search.max_results": tools["search"]["results"],
            "search.timeout_secs": tools["search"]["timeout"],
            "web_search.max_results": tools["search"]["results"],
            "web_search.timeout_secs": tools["search"]["timeout"],
            "agent.max_tool_iterations": tools["steps"] or native["unbounded"],
            "agent.agent_timeout_secs": tools["timeout"],
            "agent.parallel_tools": tools["parallel"],
            "agent.tool_dispatcher": tools["calls"],
            "agent.max_parallel_tools": tools["fanout"],
            "agent.tool_result_budget_bytes": tools["output"],
            "context.tool_result_budget_bytes": tools["output"],
            "http_request.max_response_size": tools["fetch"]["size"],
            "http_request.timeout_secs": tools["fetch"]["timeout"],
            "curl.max_download_bytes": tools["download"]["size"],
            "curl.timeout_secs": tools["download"]["timeout"],
            "multimodal.allow_remote_fetch": tools["remote"],
            "multimodal_files.allow_remote_fetch": tools["remote"],
            "agent.agents_md_enabled": main["instructions"],
            "autonomy.enabled": permissions["guard"],
            "autonomy.level": native["levels"][permissions["mode"]],
            "autonomy.workspace_only": permissions["scope"] == "workspace",
            "autonomy.trusted_roots": [
                *({"access": "read", "path": str(vault / d)} for d in permissions["vault"]["read"]),
                *({"access": "readwrite", "path": str(vault / d)} for d in permissions["vault"]["write"]),
            ],
            "runtime.local_jail.extra_read_only": [
                *(str(vault / d) for d in permissions["vault"]["read"]),
                *permissions.get("toolchains", []),
            ],
            "runtime.local_jail.extra_read_write": [str(vault / d) for d in permissions["vault"]["write"]],
            "update.enabled": main["updates"],
            "channels_config.message_timeout_secs": channels["reply"],
            "mcp_client.servers": [self._config_openhuman_server(name, srv) for name, srv in mcp["servers"].items()],
            "mcp_client.direct_servers": [n for n, srv in mcp["servers"].items() if srv.get("pinned")],
            "channels_config.discord.allowed_users": channels["discord"]["users"],
            "multimodal_files.trusted_channel_senders": [f"discord:{u}" for u in channels["discord"]["files"]],
            **(
                {"channels_config.discord.channel_id": channels["discord"]["channel"]}
                if channels["discord"]["channel"]
                else {}
            ),
            "local_ai.stt_provider": stt,
            "local_ai.tts_provider": tts,
        }
        return {spec.config.files[0].out: rows} if spec and spec.config else {}

    def _config_hermes(self, mods: Mapping[str, dict]) -> dict[str, Any]:
        """config.yaml by dotted path and .env by key: the agnostic core in Hermes's words (spec `native`)."""
        main, models, search, channels, tools, permissions, mcp = (
            mods[k] for k in ("main", "models", "search", "channels", "tools", "permissions", "mcp")
        )
        spec = self.find("config", "config")
        native = spec.config.native if spec and spec.config else {}
        route = functools.partial(self._config_hermes_route, native["names"])
        pick = lambda role: route(models["roles"][role])  # noqa: E731
        engines = search["engines"]
        backend = next(name for name in search["order"] if not engines[name].get("off", False))
        discord = channels["discord"]
        config = {
            "model.provider": pick("main")["provider"],
            "model.default": pick("main")["model"],
            **{
                f"providers.{native['names'][alias]}": {
                    "base_url": p["endpoint"],
                    "api_mode": native["api"][p["api"]],
                    "key_env": p["key"],
                }
                for alias, p in models["providers"].items()
            },
            "fallback_providers": [route(entry) for entry in models["fallback"]],
            **{
                f"auxiliary.{task}.{field}": pick(role)[field]
                for task, role in native["auxiliary"].items()
                for field in ("provider", "model")
            },
            "delegation.provider": pick("act")["provider"],
            "delegation.model": pick("act")["model"],
            "agent.max_turns": tools["steps"] or "none",
            "terminal.cwd": str(self.out / "workspace"),
            "terminal.timeout": tools["timeout"],
            "tool_output.max_bytes": tools["output"],
            "web.search_backend": native["search"][backend],
            "approvals.mode": native["levels"][permissions["mode"]] if permissions["guard"] else "off",
            "timezone": main["timezone"],
            "context_file_max_chars": native["context"],
            "discord.require_mention": discord["mention"],
            "discord.allowed_channels": discord["channel"] or "",
            **{f"mcp_servers.{name}": self._config_hermes_server(srv) for name, srv in mcp["servers"].items()},
        }
        env = {
            "DISCORD_ALLOWED_USERS": ",".join(discord["users"]),
            "SEARXNG_URL": engines["searxng"]["url"],
        }
        return {"config.yaml": config, ".env": env} if spec and spec.config else {}

    @staticmethod
    def _config_hermes_route(names: Mapping[str, str], value: str) -> dict[str, str]:
        """`alias/model` from the core as Hermes's `{provider, model}`, the alias under its Hermes name."""
        alias, model = value.split("/", 1)
        return {"provider": names[alias], "model": model}

    @staticmethod
    def _config_openhuman_server(name: str, server: Mapping[str, Any]) -> dict[str, Any]:
        """A core MCP server as an OpenHuman `mcp_client.servers` entry: remote endpoint, or stdio argv.

        This static set cannot sign a client in: an `oauth` server is written disabled (an update, never a removal)
        and reaches OpenHuman through its MCP registry instead (`make mcp`), which holds the sign-in."""
        enabled = not server.get("oauth", False)
        match server:
            case {"command": [command, *args]}:
                return {
                    "name": name,
                    "enabled": enabled,
                    "endpoint": "",
                    "command": command,
                    "args": args,
                    "env": server.get("env", {}),
                }
            case _:
                return {"name": name, "enabled": enabled, "endpoint": server["url"]}

    @staticmethod
    def _config_hermes_server(server: Mapping[str, Any]) -> dict[str, Any]:
        """A core MCP server as a Hermes `mcp_servers` entry: argv split into command and args, or url and headers."""
        match server:
            case {"command": [command, *args]}:
                return {"command": command, "args": args, "env": server.get("env", {})}
            case _:
                return {"url": server["url"], "headers": server.get("headers", {})}

    #: One config builder per backend: the files each coder reads diverge as the coders do.
    _CONFIG: Final[Mapping[Backend, Callable[[Transpiler, Mapping[str, dict]], dict[str, Any]]]] = {
        Backend.OPENCODE: _config_opencode,
        Backend.CLAUDECODE: _config_claudecode,
        Backend.OPENHUMAN: _config_openhuman,
        Backend.HERMES: _config_hermes,
    }

    def _hooks(self, hooks: Mapping[str, list[dict]]) -> dict[str, list[dict]]:
        """One entry per event and matcher (none when the event takes no matcher); `{out}` bound to this tree."""
        return {
            event: [
                ({"matcher": matcher} if matcher else {})
                | {
                    "hooks": [
                        {"type": "command", "command": shlex.join(arg.format(out=self.out) for arg in entry["run"])}
                    ]
                }
                for entry in entries
                for matcher in entry.get("matchers") or [""]
            ]
            for event, entries in hooks.items()
        }

    def _agents(self, agents: Mapping[str, dict]) -> dict[str, dict]:
        """System agents and per-agent overrides, with house tiers resolved to model ids."""
        return {
            name: cfg | {"model": self.model_tiers[cfg["model"]]} if cfg.get("model") in self.model_tiers else cfg
            for name, cfg in {**agents["overrides"], **agents["system"]}.items()
        }

    @staticmethod
    def _mcp_opencode(server: McpServer) -> dict[str, Any]:
        """opencode.jsonc · mcp: `local` with the argv whole, or `remote`."""
        shape = (
            {"type": "local", "command": server.command, "environment": server.env}
            if server.command
            else {"type": "remote", "url": server.url, "headers": server.headers}
        )
        return {key: value for key, value in shape.items() if value} | {"enabled": server.enabled}

    @staticmethod
    def _mcp_claudecode(server: McpServer) -> dict[str, Any]:
        """`claude mcp add-json`, in the shape Claude stores it: `stdio` always carries `args`, env and headers only when set."""
        shape = (
            {"type": "stdio", "command": server.command[0], "args": server.command[1:], "env": server.env}
            if server.command
            else {"type": "http", "url": server.url, "headers": server.headers}
        )
        return {key: value for key, value in shape.items() if value or key == "args"}

    @staticmethod
    def _providers(models: Mapping[str, dict]) -> dict[str, dict]:
        """One entry per vendor, each carrying the tiers that name it."""
        return {
            data["id"]: {
                "npm": data["sdk"],
                "name": data["display"],
                "options": {
                    k: v for k, v in {"baseURL": data.get("base_url"), "apiKey": data.get("api_key")}.items() if v
                },
                "models": {
                    tier_data["model"].split("/")[1]: {
                        k: v
                        for k, v in {
                            "name": tier,
                            "reasoning": tier_data.get("reasoning"),
                            "limit": tier_data.get("limits"),
                            "modalities": tier_data.get("modalities"),
                            "options": tier_data.get("options"),
                        }.items()
                        if v
                    }
                    for tier, tier_data in models["tiers"].items()
                    if tier_data["model"].split("/")[0] == alias
                },
            }
            for alias, data in models["providers"].items()
        }

    # ------------------------------------------------------------ filesystem
    def _rel(self, path: Path) -> str:
        return str(path.relative_to(self.out))

    def _faithful(self, path: Path, text: str) -> bool:
        """Byte files and documents against the render as written; structured files on what each side owns."""
        live = path.read_text() if path.is_file() else None
        loose = self._exactness(path) != "byte"
        return live is not None and (
            self.owned(path, live) == self.owned(path, self.merged(path, text)) if loose else live == text
        )

    @cached_property
    def _config_files(self) -> Mapping[Path, ConfigFile]:
        spec = self.find("config", "config")
        return {self.out / f.out: f for f in spec.config.files} if spec and spec.config else {}

    def owned(self, path: Path, text: str) -> str:
        """What of a file's text the render owns, in the form the plan compares.

        A persona document is its text without the harness's regions. A `keys` file is projected onto the keys its spec declares: Claude Code writes its own
        into settings.json (statusLine, outputStyle, enabledPlugins…), they are the coder's, so
        they never count as drift and are never overwritten. A `keys` or `semantic` file is
        compared as JSON, so its text is canonical (keys sorted): a coder that only reorders
        what it rewrites has moved nothing. Every other file is its bytes.
        """
        if (doc := self._documents.get(path)) is not None:
            return Typeset(doc).strip(text)
        file = self._config_files.get(path)
        exactness = self._exactness(path)
        if not text.strip() or file is None or exactness == "byte":
            return text
        data = PARSE[file.format](text)
        keyed = exactness == "keys" and isinstance(data, dict)
        dormant = self._dormant(path)
        projected = (
            {
                key: self._items(file, key, value, mine=True)
                for key in self._keys(path)
                if key not in dormant and (dug := dotted_get(data, key))[0]
                for value in (dug[1],)
            }
            if keyed
            else data
        )
        return msgspec.json.format(msgspec.json.encode(projected, order="sorted"), indent=2).decode() + "\n"

    def merged(self, path: Path, text: str) -> str:
        """What an export writes: the render over what is there — it updates and adds, never drops what is live.

        A `keys` file keeps the harness's keys, and every `items` element: the core's by id are updated,
        the rest stay. A document keeps its regions and every heading no block declares.

        An owned key the render omits is dropped from the file: absence is a value the core can own.
        A dormant key (under a table the harness has not created) is neither written nor dropped.
        """
        if (doc := self._documents.get(path)) is not None:
            return Typeset(doc).merge(text, path.read_text()) if path.is_file() else text
        if self._exactness(path) != "keys":
            return text
        file = self._config_files[path]
        live = path.read_text() if path.is_file() else ""
        awake = [key for key in self._keys(path) if key not in self._dormant(path)]
        if file.format == "env":
            rendered_env = _parse_env(text)
            return _merge_env(
                live,
                {key: rendered_env[key] for key in awake if key in rendered_env},
                frozenset(key for key in awake if key not in rendered_env),
            )
        if file.format in DUMP:
            rendered = PARSE[file.format](text)
            current = PARSE[file.format](live) if live.strip() else {}
            owned = [
                (key, self._merged_items(file, key, value, dotted_get(current, key)[1]))
                if key in file.items
                else (key, value)
                for key in awake
                if (dug := dotted_get(rendered, key))[0]
                for value in (dug[1],)
            ]
            omitted = [key for key in awake if not dotted_get(rendered, key)[0]]
            base: dict = functools.reduce(dotted_drop, omitted, current if isinstance(current, dict) else {})
            return DUMP[file.format](functools.reduce(lambda acc, kv: dotted_set(acc, *kv), owned, base))
        if not live.strip():
            return text
        own = set(file.keys)
        current = _parse_json(live)
        foreign = {key: value for key, value in current.items() if key not in own} if isinstance(current, dict) else {}
        rendered = _parse_json(text)
        return _dump_json(rendered | foreign) if foreign and isinstance(rendered, dict) else text

    @staticmethod
    def _merged_identity(item: Mapping[str, Any]) -> object:
        """What names a list item across both sides: its `id`, else its `name`, else its `path`."""
        return item.get("id", item.get("name", item.get("path")))

    @classmethod
    def _merged_items(cls, file: ConfigFile, key: str, rendered: list, live: Any) -> list:
        """The core's items over their live twins field by field (the harness's extra fields stay), then each live
        core-kind item the render does not name (by `id`, `name` or `path`), then the harness's."""
        listed = live if isinstance(live, list) else []
        twins = {cls._merged_identity(item): item for item in cls._items(file, key, listed, mine=True)}
        named = {cls._merged_identity(item) for item in rendered if isinstance(item, dict)}
        updated = [
            {**twins.get(cls._merged_identity(item), {}), **item} if isinstance(item, dict) else item
            for item in rendered
        ]
        kept = [item for identity, item in twins.items() if identity not in named]
        return [*updated, *kept, *cls._items(file, key, listed, mine=False)]

    @staticmethod
    def _items(file: ConfigFile, key: str, value: Any, *, mine: bool) -> Any:
        """An `items` list cut to the core's items (`mine`) or to the harness's; any other value as it is."""
        match (file.items.get(key), value):
            case (dict() as rule, list()):
                return [
                    item
                    for item in value
                    if (isinstance(item, dict) and all(item.get(k) == v for k, v in rule.items())) == mine
                ]
            case (dict(), _):
                return [] if not mine else value
            case _:
                return value

    def _dormant(self, path: Path) -> frozenset[str]:
        """Owned keys under a `within` table the live file does not hold: the harness never created it, so it is not ours to write."""
        file = self._config_files.get(path)
        if file is None or not file.within:
            return frozenset()
        live = path.read_text() if path.is_file() else ""
        data = PARSE[file.format](live) if live.strip() else {}
        absent = [table for table in file.within if not dotted_get(data, table)[0]]
        return frozenset(key for key in self._keys(path) for table in absent if key.startswith(f"{table}."))

    def _keys(self, path: Path) -> list[str]:
        """The spec's keys for a file, each `prefix.*` expanded to the children the render puts under prefix.

        The core owns the children it renders; a child the harness adds beside them is the harness's.
        """
        file = self._config_files[path]
        wild = [key.removesuffix(".*") for key in file.keys if key.endswith(".*")]
        rendered = PARSE[file.format](self.files[path]) if wild else {}
        children = {base: dotted_get(rendered, base)[1] for base in wild}
        return [
            expanded
            for key in file.keys
            for expanded in (
                [f"{key[:-2]}.{name}" for name in children[key[:-2]] or {}] if key.endswith(".*") else [key]
            )
        ]

    def _exactness(self, path: Path) -> str:
        spec = self.find("config", "config")
        loose = spec and spec.config and str(path.relative_to(self.out)) in self.config_names
        return spec.config.exactness if loose and spec and spec.config else "byte"

    def governed(self) -> frozenset[Path]:
        """Trees this backend owns under out/; everything else there is runtime state."""
        return frozenset(
            self.out / Path(spec.flat.path).parts[0]
            for entity in INSTANCED
            if (spec := self.spec(entity)) and spec.flat
        )

    def _stale(self, files: Mapping[Path, str]) -> tuple[Path, ...]:
        """Flat files inside the governed trees that the render no longer produces; a linked tree is not ours to sweep."""
        return tuple(
            path
            for root in sorted(self.governed())
            if root.is_dir() and not root.is_symlink()
            for path in sorted(root.rglob("*"))
            if path.is_file() and path not in files and not self._foreign(path)
        )

    def _links(self, files: Mapping[Path, str]) -> tuple[Path, ...]:
        """Paths the render owns that are symlinks — a top-level tree or a file itself: an apply makes them real,
        never touching their target. A harness may refuse to follow a link (OpenHuman opens AGENTS.md O_NOFOLLOW)."""
        roots = {self.out / path.relative_to(self.out).parts[0] for path in files}
        return tuple(sorted(path for path in roots | set(files) if path.is_symlink()))

    def _foreign(self, path: Path) -> bool:
        return bool(settings.layout.third_party & set(path.relative_to(self.out).parts))

    @staticmethod
    def _write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def _prune(self, doomed: tuple[Path, ...]) -> None:
        """Remove what the render dropped, then the directories it emptied — ours only."""
        for path in doomed:
            path.unlink(missing_ok=True)
        for root in sorted(self.governed()) if doomed else ():
            for path in sorted(root.rglob("*") if not root.is_symlink() else (), reverse=True):
                path.is_dir() and not self._foreign(path) and not any(path.iterdir()) and path.rmdir()
