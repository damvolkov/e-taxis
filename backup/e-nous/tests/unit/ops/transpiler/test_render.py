"""Unit tests for the transpiler's split manifests: e-serde embeds, the transpiler lifts the envelope."""

from __future__ import annotations

import json
from pathlib import Path

import eserde
import pytest

from ops.core.settings import settings
from ops.models.entity import Backend
from ops.models.spec import Graph
from ops.transpiler.render import Transpiler


@pytest.fixture
def transpiler(tmp_path: Path) -> Transpiler:
    """A transpiler over the real corpus, rendering nowhere it matters."""
    return Transpiler(settings.ROOT, Backend.OPENCODE, tmp_path / "out")


@pytest.fixture
def split(tmp_path: Path) -> Path:
    """A manifest split into node files plus a markdown body, the way workflows are laid out."""
    (tmp_path / "nodes").mkdir()
    (tmp_path / "nodes" / "a.yaml").write_text("id: a\ndepends: []\n")
    (tmp_path / "nodes" / "b.yaml").write_text("id: b\ndepends: [a]\n")
    (tmp_path / "body.md").write_text("# body\n")
    manifest = tmp_path / "workflow.yaml"
    manifest.write_text("nodes:\n  - {source: nodes/a.yaml}\n  - {source: nodes/b.yaml}\nbody: {source: body.md}\n")
    return manifest


def test_unwrap_lifts_sub_documents_in_order(transpiler: Transpiler, split: Path) -> None:
    """Each embedded file takes its reference's place, in declaration order."""
    data = transpiler.unwrap(eserde.load(split, embed=True))
    assert data["nodes"] == [{"id": "a", "depends": []}, {"id": "b", "depends": ["a"]}]


def test_unwrap_keeps_markdown_as_a_body_slot(transpiler: Transpiler, split: Path) -> None:
    """A markdown source stays in its envelope, as text: `_body` reads it."""
    data = transpiler.unwrap(eserde.load(split, embed=True))
    assert data["body"] == {"source": "# body\n"}
    assert transpiler._body(data["body"], split.parent) == "# body\n"


def test_embed_refuses_escaping_the_instance_dir(tmp_path: Path) -> None:
    """Confinement is e-serde's: a reference never reaches outside the manifest's folder."""
    (tmp_path / "inner").mkdir()
    (tmp_path / "x.yaml").write_text("id: x\n")
    (tmp_path / "inner" / "m.yaml").write_text("n: {source: ../x.yaml}\n")
    with pytest.raises(eserde.LoadError, match="escapes"):
        eserde.load(tmp_path / "inner" / "m.yaml", embed=True)


def test_split_workflow_renders_every_node(transpiler: Transpiler) -> None:
    """The real split workflow renders a step for each node file."""
    rendered = next(text for path, text in transpiler.files.items() if path.name == "emaintenance.md")
    nodes = sorted(p.stem for p in (settings.ROOT / "core/tekton/workflows/emaintenance/nodes").glob("*.yaml"))
    assert all(f"### {node} (depends:" in rendered for node in nodes)


##### GRAPH PROJECTION #####
def _nodes() -> list[dict]:
    return [
        {"id": "a", "depends": [], "actor": None, "instruction": "validate"},
        {"id": "b", "depends": ["a"], "actor": "builder", "instruction": "make it"},
        {"id": "c", "depends": ["a"], "actor": "scout", "instruction": "look up"},
        {"id": "d", "depends": ["b", "c"], "actor": "verifier", "instruction": "check"},
    ]


def _graph(data: dict) -> str:
    return Transpiler()._graph(Graph(), data)


def test_edges_follow_declaration_order_and_close_terminals() -> None:
    body = _graph({"nodes": _nodes(), "output": {"type": "report", "path": "session"}})
    assert [line.strip() for line in body.splitlines() if "-->" in line] == [
        "start --> a",
        "a --> b",
        "a --> c",
        "b --> d",
        "c --> d",
        "d --> done",
    ]


def test_steps_carry_dependencies_and_actor() -> None:
    body = _graph({"nodes": _nodes()})
    assert "### d (depends: b, c)" in body
    assert "@builder make it" in body and "@scout look up" in body
    assert "validate" in body and "@None" not in body and "@null" not in body


def test_only_sinks_reach_done() -> None:
    body = _graph({"nodes": _nodes()})
    assert body.count("--> done") == 1
    assert "b --> done" not in body and "c --> done" not in body


def test_output_section_declared_or_absent() -> None:
    data = {"nodes": _nodes(), "output": {"type": "report", "path": "core/x.md"}}
    assert "## output\n\ntype: report\npath: core/x.md" in _graph(data)
    assert "## output" not in _graph({"nodes": _nodes()})


@pytest.mark.parametrize(
    "data",
    [
        {"nodes": []},
        {"nodes": [{"id": "start", "instruction": "x"}]},
        {"nodes": [{"id": "a", "depends": ["ghost"], "instruction": "x"}]},
    ],
    ids=["empty", "terminal-collision", "dangling-edge"],
)
def test_a_malformed_graph_fails_loudly(data: dict) -> None:
    with pytest.raises(ValueError):
        _graph(data)


def test_the_maintenance_graph_renders_into_the_corpus() -> None:
    tp = Transpiler()
    text = tp.files[tp.out / "workflows" / "emaintenance.md"]
    assert text.startswith("---\nid: emaintenance")
    assert "```mermaid" in text and "flowchart TD" in text
    assert "start --> intake" in text and "report --> done" in text
    assert "### enhance (depends: intake)" in text
    assert "*only when `op` is `update`*" in text and "run: `uv run op enhance run" in text


##### LIVE TREES #####
@pytest.mark.parametrize("backend", list(Backend))
def test_every_backend_lands_on_its_own_live_tree_by_default(backend: Backend) -> None:
    assert Transpiler(backend=backend).out == settings.transpiler.live(backend)


def test_the_live_trees_are_distinct() -> None:
    assert len({settings.transpiler.live(backend) for backend in Backend}) == len(Backend)


def test_an_explicit_out_wins(tmp_path: Path) -> None:
    assert Transpiler(backend=Backend.CLAUDECODE, out=tmp_path).out == tmp_path.resolve()


##### CLAUDECODE #####
@pytest.fixture(scope="module")
def claude(tmp_path_factory: pytest.TempPathFactory) -> Transpiler:
    return Transpiler(settings.ROOT, Backend.CLAUDECODE, tmp_path_factory.mktemp("claude"))


def _front(text: str) -> dict:
    return eserde.loads(text.split("---\n")[1], format=eserde.Format.YAML)


def test_claude_agents_carry_the_name_claude_requires(claude: Transpiler) -> None:
    """Without `name` Claude Code reads the file as documentation and never loads the agent."""
    agents = {path.stem: text for path, text in claude.files.items() if path.parent.name == "agents"}
    assert agents and all(_front(text)["name"] == stem for stem, text in agents.items())


def test_claude_agents_preload_natively_and_deny_by_table(claude: Transpiler) -> None:
    front = _front(claude.files[claude.out / "agents" / "architect.md"])
    assert "arch-py-hexagonal" in front["skills"]
    assert {"Bash", "Agent", "AskUserQuestion"} <= set(front["disallowedTools"])
    assert "Edit" not in front["disallowedTools"]  # a pattern-scoped grant is not a denied tool
    assert not {"mode", "model", "permission"} & set(front)


def test_claude_commands_take_named_arguments(claude: Transpiler) -> None:
    """Claude counts arguments from $0: a positional $1 would land on the second one."""
    text = claude.files[claude.out / "commands" / "maintenance.md"]
    front = _front(text)
    assert front["arguments"] == ["entity", "op", "id", "details", "publish"]
    assert front["argument-hint"] == "[entity] [op] [id] [details] [publish]"
    assert "entity: $entity\n" in text and "$1" not in text


def test_opencode_commands_stay_positional(transpiler: Transpiler) -> None:
    text = transpiler.files[transpiler.out / "commands" / "maintenance.md"]
    assert "entity: $1\n" in text and "arguments" not in _front(text)


##### NO LINKS #####
@pytest.mark.parametrize(("backend", "persona"), [(Backend.OPENCODE, "AGENTS.md"), (Backend.CLAUDECODE, "CLAUDE.md")])
def test_each_backend_writes_its_own_persona_file_and_no_other(tmp_path: Path, backend: Backend, persona: str) -> None:
    files = Transpiler(settings.ROOT, backend, tmp_path).files
    assert tmp_path.resolve() / persona in files
    assert {"AGENTS.md", "CLAUDE.md"} - {persona} not in {path.name for path in files}


def test_a_symlinked_tree_becomes_real_and_its_target_is_untouched(tmp_path: Path) -> None:
    """The old wiring: ~/.claude/agents → another tree. An export writes real files; the target keeps its own."""
    foreign = tmp_path / "foreign"
    (foreign / "agents").mkdir(parents=True)
    (foreign / "agents" / "theirs.md").write_text("not ours")
    out = tmp_path / "out"
    out.mkdir()
    (out / "agents").symlink_to(foreign / "agents")
    tp = Transpiler(settings.ROOT, Backend.CLAUDECODE, out)
    assert "agents: symlink" in map(str, tp.check())
    tp.export("reset")
    assert not (out / "agents").is_symlink() and (out / "agents" / "builder.md").is_file()
    assert (foreign / "agents" / "theirs.md").read_text() == "not ours"
    assert sorted(p.name for p in (foreign / "agents").iterdir()) == ["theirs.md"]


def test_claude_settings_come_from_core_config(claude: Transpiler) -> None:
    settings_json = eserde.loads(claude.files[claude.out / "settings.json"], format=eserde.Format.JSON)
    assert settings_json["model"] == "opus[1m]" and settings_json["permissions"]["defaultMode"]
    command = settings_json["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert command == f"bash {claude.out / 'hooks' / 'cbm-session-reminder'}"
    assert "matcher" not in settings_json["hooks"]["Stop"][0]  # an event without matchers takes none
    assert (claude.out / "hooks" / "autolearn.mjs") in claude.files


def test_claude_reads_the_instructions_opencode_reads(claude: Transpiler, transpiler: Transpiler) -> None:
    """rules/instructions.md imports what opencode.jsonc lists, each bound to its own tree."""
    rules = claude.files[claude.out / "rules" / "instructions.md"].splitlines()
    config = eserde.loads(transpiler.files[transpiler.out / "opencode.jsonc"], format=eserde.Format.JSON)
    assert [line.removeprefix("@") for line in rules] == [
        path.replace(str(transpiler.out), str(claude.out)) for path in config["instructions"]
    ]


##### MCP #####
def test_one_declaration_two_syntaxes(claude: Transpiler, transpiler: Transpiler) -> None:
    """core/tekton/config/mcp.yaml → opencode `local` argv whole; Claude `stdio` argv split. Shared servers, same env; a server listing one backend reaches only it."""
    opencode = eserde.loads(transpiler.files[transpiler.out / "opencode.jsonc"], format=eserde.Format.JSON)["mcp"]
    registered = claude.mcp_registrations()
    assert [name for name in registered if name in opencode] == list(opencode) and "playwright" in registered
    assert "e-gnosis" in registered and "e-gnosis" not in opencode
    assert opencode["searxng"]["type"] == "local" and registered["searxng"]["type"] == "stdio"
    assert [registered["searxng"]["command"], *registered["searxng"]["args"]] == opencode["searxng"]["command"]
    assert opencode["searxng"]["environment"] == registered["searxng"]["env"]


def test_an_mcp_config_file_travels_with_the_tree_that_names_it(claude: Transpiler) -> None:
    pointer = claude.mcp_registrations()["playwright"]["env"]["PLAYWRIGHT_MCP_CONFIG"]
    assert Path(pointer) == claude.out / "mcp" / "playwright.json" and Path(pointer) in claude.files


def test_opencode_instructions_point_inside_the_tree_they_land_in(transpiler: Transpiler) -> None:
    config = eserde.loads(transpiler.files[transpiler.out / "opencode.jsonc"], format=eserde.Format.JSON)
    assert str(transpiler.out / "skills" / "tax-py-naming" / "SKILL.md") in config["instructions"]
    assert not any("{out}" in path or "ecoder" in path for path in config["instructions"])


##### OWNED KEYS #####
def test_claudes_own_settings_keys_are_never_drift_nor_overwritten(tmp_path: Path) -> None:
    """statusLine, outputStyle, enabledPlugins: Claude writes them into the file the render shares."""
    tp = Transpiler(settings.ROOT, Backend.CLAUDECODE, tmp_path)
    tp.export()
    path = tmp_path.resolve() / "settings.json"
    live = eserde.loads(path.read_text(), format=eserde.Format.JSON)
    path.write_text(json.dumps(live | {"statusLine": {"type": "command", "command": "x"}, "outputStyle": "terse"}))
    assert not Transpiler(settings.ROOT, Backend.CLAUDECODE, tmp_path).check()
    live["model"] = "haiku"
    path.write_text(json.dumps(live | {"statusLine": {"type": "command", "command": "x"}}))
    assert "settings.json: drift" in map(str, Transpiler(settings.ROOT, Backend.CLAUDECODE, tmp_path).check())
    Transpiler(settings.ROOT, Backend.CLAUDECODE, tmp_path).export()
    healed = eserde.loads(path.read_text(), format=eserde.Format.JSON)
    assert healed["model"] == "opus[1m]" and healed["statusLine"] == {"type": "command", "command": "x"}


def test_a_reordered_rewrite_is_the_same_settings(tmp_path: Path) -> None:
    """Claude rewrites settings.json in its own key order: the owned form does not move."""
    tp = Transpiler(settings.ROOT, Backend.CLAUDECODE, tmp_path)
    path = tmp_path.resolve() / "settings.json"
    rendered = eserde.loads(tp.files[path], format=eserde.Format.JSON)
    shuffled = {key: rendered[key] for key in reversed(list(rendered))}
    shuffled["hooks"] = {event: rendered["hooks"][event] for event in reversed(list(rendered["hooks"]))}
    assert tp.owned(path, json.dumps(shuffled)) == tp.owned(path, tp.files[path])


async def test_render_workflow_draws_its_loop(tmp_path: Path) -> None:
    data = {
        "nodes": [{"id": "a", "run": "x"}, {"id": "b", "depends": ["a"], "run": "y"}],
        "loop": {"nodes": ["a", "b"], "max": 3, "until": "b"},
    }
    body = Transpiler(settings.ROOT, Backend.OPENCODE, tmp_path)._graph(Graph(), data)
    assert '    b -.->|"until b · max 3"| a' in body and "## loop" in body and "at most 3 times" in body
    with pytest.raises(ValueError, match="unknown step c"):
        Transpiler(settings.ROOT, Backend.OPENCODE, tmp_path)._graph(
            Graph(), data | {"loop": {"nodes": ["c"], "max": 1, "until": "c"}}
        )
