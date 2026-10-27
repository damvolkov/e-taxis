"""engine.law: the house law of a skill, an agent and a command — deterministic, zero tokens, no I/O.

A skill is judged on its render (the SKILL.md that reaches the context window, and its references); an agent and a
command on their core manifests, against what the corpus holds (skills, agents, MCP servers, model tiers). Each law
is a tuple of violations, empty when the subject holds. Ported from e-nous `ops/evaluator/law/{skill,agent,command}`;
the model tiers are read from the facet's `models.tiers` (the schema's definition of a tier) instead of a fixed list."""

import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any, Final

##### DEFAULTS #####
NAME: Final[re.Pattern[str]] = re.compile(r"^[a-z]+-[a-z]+-[a-z0-9]+$")
KEBAB: Final[re.Pattern[str]] = re.compile(r"^[a-z]+(-[a-z0-9]+)*$")
FRONT: Final[re.Pattern[str]] = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
RULE: Final[re.Pattern[str]] = re.compile(r"^\d+\.\s+\*\*", re.MULTILINE)
ABSOLUTE: Final[re.Pattern[str]] = re.compile(r"\b(MUST|NEVER|ALWAYS|FORBIDDEN|MANDATORY)\b")
OMITTED: Final[re.Pattern[str]] = re.compile(r"No\s+`lib\.md`")
LINKED: Final[re.Pattern[str]] = re.compile(r"`references/([a-z_]+\.md)`")
SUBSTITUTION: Final[re.Pattern[str]] = re.compile(r"\$\{?([a-zA-Z_][\w-]*|ARGUMENTS)\}?")
POSITIONAL: Final[re.Pattern[str]] = re.compile(r"\$[0-9]")
SCOPES: Final[frozenset[str]] = frozenset({"gen", "py", "rs", "sh", "sql", "en", "es"})
PERMISSIONS: Final[frozenset[str]] = frozenset(
    {
        "read",
        "edit",
        "glob",
        "grep",
        "list",
        "bash",
        "task",
        "external_directory",
        "todowrite",
        "webfetch",
        "websearch",
        "lsp",
        "skill",
        "question",
        "doom_loop",
    }
)
MODES: Final[frozenset[str]] = frozenset({"primary", "subagent", "all"})
DESTRUCTIVE: Final[tuple[str, ...]] = ("git push", "rm -rf", "sudo")
DESCRIPTION: int = 200
LINES: int = 60
RULES: int = 7
ABSOLUTES: int = 8
TEMPLATE: str = "template.md"
### a sample is one fence opened and closed.
FENCES: int = 2


##### UTILITIES #####
def front_law(text: str) -> dict[str, str]:
    """A Markdown file's frontmatter, top-level keys only, values as written."""
    match FRONT.match(text):
        case re.Match() as found:
            pairs = (line.partition(":") for line in found.group(1).splitlines() if ":" in line)
            return {key.strip(): value.strip() for key, _, value in pairs if not key.startswith(" ")}
        case _:
            return {}


def rules_law(permission: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """A permission's pattern map, or empty when it is one action."""
    match permission.get(key):
        case Mapping() as patterns:
            return patterns
        case _:
            return {}


def canonical_law(skill: str, skills: frozenset[str]) -> bool:
    """Whether a skill id follows the naming law and exists in the corpus."""
    return bool(NAME.match(skill)) and skill in skills


##### TYPES #####
class SkillLaw:
    """The naming law and the router's budgets over one rendered skill."""

    __slots__ = ()

    @staticmethod
    def check(name: str, text: str, references: Mapping[str, str]) -> tuple[str, ...]:
        """`text` is the rendered SKILL.md, `references` file name → text of `references/`; empty when it holds."""
        front = front_law(text)
        description = front.get("description", "").strip().strip('"')
        scope = name.split("-")[1] if NAME.match(name) else ""
        shouted = len(ABSOLUTE.findall(text))
        lines = len(text.splitlines())
        return (
            *((f"name '{name}' fails {NAME.pattern}",) if not NAME.match(name) else ()),
            *((f"scope '{scope}' not in {sorted(SCOPES)}",) if scope and scope not in SCOPES else ()),
            *((f"frontmatter name '{front.get('name')}' != folder '{name}'",) if front.get("name") != name else ()),
            *((f"description {len(description)} > {DESCRIPTION} chars",) if len(description) > DESCRIPTION else ()),
            *(
                ("description missing 'Use when/before' trigger",)
                if "Use when" not in description and "Use before" not in description
                else ()
            ),
            *(("metadata.family absent",) if "family:" not in text else ()),
            *((f"SKILL.md {lines} > {LINES} lines",) if lines > LINES else ()),
            *((f"more than {RULES} rules",) if len(RULE.findall(text)) > RULES else ()),
            *(("no fenced sample block",) if text.count("```") < FENCES else ()),
            *(
                (f"{shouted} shouted absolutes > {ABSOLUTES} — explain the reason instead",)
                if shouted > ABSOLUTES
                else ()
            ),
            *(
                ("lib.md absent and omission not documented (add '- No `lib.md` — <reason>.')",)
                if "lib.md" not in references and not OMITTED.search(text)
                else ()
            ),
            *(
                f"reference '{ref}' has a hyphen (must be snake_case)"
                for ref in references
                if "-" in PurePosixPath(ref).stem
            ),
            *(
                f"reference '{ref}' links another reference 'references/{hit}'"
                for ref, body in references.items()
                for hit in LINKED.findall(body)
                if hit != ref
            ),
        )


class AgentLaw:
    """Taxonomy, permission coherence and skill scope of one agent manifest."""

    __slots__ = ()

    @staticmethod
    def _check_skills(agent: Mapping[str, Any], skills: frozenset[str]) -> tuple[str, ...]:
        permission = agent["permission"]
        preload, ondemand = agent.get("skills_preload") or [], agent.get("skills_ondemand") or {}
        scope = set(preload) | set(ondemand)
        grants = rules_law(permission, "skill")
        granted = {key for key, action in grants.items() if action in {"allow", "ask"} and key != "*"}
        full = bool(agent.get("skills_full_scope")) and grants.get("*") == "allow" and not scope
        return (
            *(("skill both preloaded and on-demand",) if set(preload) & set(ondemand) else ()),
            *(
                f"skill '{skill}' not canonical or missing in core"
                for skill in sorted(scope)
                if not canonical_law(skill, skills)
            ),
            *(("permission.skill must default deny (role scope)",) if not full and grants.get("*") != "deny" else ()),
            *(
                (f"skill grant ≠ scope: only-granted {sorted(granted - scope)}, only-scoped {sorted(scope - granted)}",)
                if not full and granted != scope
                else ()
            ),
            *(
                f"ondemand trigger for '{skill}' must be a single line"
                for skill, trigger in ondemand.items()
                if not isinstance(trigger, str) or not trigger.strip() or "\n" in trigger
            ),
        )

    @classmethod
    def check(
        cls,
        agent: Mapping[str, Any],
        *,
        agents: frozenset[str],
        skills: frozenset[str],
        servers: frozenset[str],
        tiers: frozenset[str],
    ) -> tuple[str, ...]:
        """One manifest against the corpus: the agents, skills, MCP servers and tiers it may name."""
        ident, permission, mode = agent["id"], agent["permission"], agent["mode"]
        named = list(agent.get("mcp_servers") or [])
        ### OpenCode names an MCP tool `<server>_<tool>`: a permission on one is the agent's own scope of that server.
        tools = {key for key in permission if any(key.startswith(f"{server}_") for server in named)}
        base = ident.split("-", 1)[0]
        task = rules_law(permission, "task")
        delegates = mode == "subagent" and permission.get("task") not in {None, "deny"} and task.get("*") != "deny"
        return (
            *((f"id '{ident}' not kebab-lowercase",) if not KEBAB.match(ident) else ()),
            *((f"specialist '{ident}': no base agent '{base}'",) if "-" in ident and base not in agents else ()),
            *(
                f"mcp server '{server}' not declared in the core's mcp config"
                for server in named
                if server not in servers
            ),
            *((f"mode '{mode}' invalid",) if mode not in MODES else ()),
            *(
                (f"model '{agent['model']}' not a house tier",)
                if "model" in agent and agent["model"] not in tiers
                else ()
            ),
            *(
                (f"description {len(agent['description'])} > {DESCRIPTION} chars",)
                if len(agent["description"]) > DESCRIPTION
                else ()
            ),
            *(
                (f"unknown permission keys {sorted(unknown)}",)
                if (unknown := set(permission) - PERMISSIONS - tools)
                else ()
            ),
            *(("subagent with task delegation",) if delegates else ()),
            *(
                ("question/todowrite allow on non-primary",)
                if mode != "primary" and any(permission.get(key) == "allow" for key in ("question", "todowrite"))
                else ()
            ),
            *(
                f"'{pattern}' is allow — destructive/push must be ask or deny"
                for pattern, action in rules_law(permission, "bash").items()
                if action == "allow" and pattern.startswith(DESTRUCTIVE)
            ),
            *cls._check_skills(agent, skills),
        )


class CommandLaw:
    """Taxonomy, connections and the inputs ↔ substitution contract of one command manifest."""

    __slots__ = ()

    @staticmethod
    def check(
        command: Mapping[str, Any],
        *,
        folder: str,
        template: str,
        agents: frozenset[str],
        skills: frozenset[str],
        tiers: frozenset[str],
    ) -> tuple[str, ...]:
        """`command` is the raw manifest (envelopes unresolved), `template` the body its envelope names."""
        ident = command["id"]
        given = command.get("skills") or {}
        preload, ondemand = given.get("preload") or [], given.get("ondemand") or {}
        envelope = command.get("template")
        source = envelope["source"] if isinstance(envelope, Mapping) else str(envelope)
        declared = set(command.get("inputs") or {})
        used = {name for name in SUBSTITUTION.findall(template) if name != "ARGUMENTS"}
        return (
            *((f"id '{ident}' not kebab-lowercase",) if not KEBAB.match(ident) else ()),
            *((f"id '{ident}' != folder '{folder}'",) if ident != folder else ()),
            *(
                (f"description {len(command['description'])} > {DESCRIPTION} chars",)
                if len(command["description"]) > DESCRIPTION
                else ()
            ),
            *(("subtask must be a boolean",) if not isinstance(command.get("subtask"), bool) else ()),
            *(
                (f"model '{command['model']}' not a house tier",)
                if "model" in command and command["model"] not in tiers
                else ()
            ),
            *((f"agent '{command['agent']}' not in core",) if command["agent"] not in agents else ()),
            *(("skill both preloaded and on-demand",) if set(preload) & set(ondemand) else ()),
            *(
                f"skill '{skill}' not canonical or missing in core"
                for skill in [*preload, *ondemand]
                if not canonical_law(skill, skills)
            ),
            *(
                ("template must export to template.md (structured always exports)",)
                if PurePosixPath(source).name != TEMPLATE
                else ()
            ),
            *(("template.md empty",) if not template.strip() else ()),
            *(
                ("positional $N literal in template — declare an input and use $name",)
                if POSITIONAL.search(template)
                else ()
            ),
            *((f"template uses undeclared $vars: {sorted(used - declared)}",) if used - declared else ()),
            *((f"inputs declared but unused in template: {sorted(declared - used)}",) if declared - used else ()),
            *(f"input name '{name}' not kebab-lowercase" for name in sorted(declared) if not KEBAB.match(name)),
        )
