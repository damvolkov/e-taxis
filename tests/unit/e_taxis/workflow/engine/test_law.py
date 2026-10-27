"""tests/unit/e_taxis/workflow/engine/law: the house law of a skill, an agent and a command — pure, zero tokens."""

from typing import Any

import pytest

from e_taxis.workflow.engine.law import AgentLaw, CommandLaw, SkillLaw, front_law

LAWFUL = (
    "---\nname: algo-py-core\ndescription: Python: things. Use when sorting.\nmetadata:\n  family: design\n---\n"
    "# algo-py-core\n\n1. **One.**\n\n```python\nx = 1\n```\n"
)
AGENT: dict[str, Any] = {
    "id": "builder",
    "description": "d",
    "mode": "primary",
    "model": "builder",
    "permission": {"read": "allow", "bash": {"*": "allow"}, "skill": {"*": "deny", "algo-py-core": "allow"}},
    "skills_preload": ["algo-py-core"],
}
COMMAND: dict[str, Any] = {
    "id": "ship",
    "description": "d",
    "agent": "builder",
    "subtask": True,
    "inputs": {"note": "n"},
    "skills": {"preload": ["algo-py-core"]},
    "template": {"source": "template.md"},
}
CORPUS = {"agents": frozenset({"builder"}), "skills": frozenset({"algo-py-core"}), "tiers": frozenset({"builder"})}


async def test_law_front_without_frontmatter_is_empty() -> None:
    assert front_law("# just a body\n") == {}


async def test_law_skill_lawful_holds() -> None:
    assert SkillLaw.check("algo-py-core", LAWFUL, {"lib.md": "# lib\n"}) == ()


async def test_law_skill_names_every_breach() -> None:
    text = "---\nname: other\ndescription: " + "x" * 210 + "\n---\n" + "1. **r**\n" * 8 + "MUST\n" * 9 + "\n" * 60
    assert SkillLaw.check("Bad_Name", text, {"a-b.md": "see `references/c.md`"}) == (
        "name 'Bad_Name' fails ^[a-z]+-[a-z]+-[a-z0-9]+$",
        "frontmatter name 'other' != folder 'Bad_Name'",
        "description 210 > 200 chars",
        "description missing 'Use when/before' trigger",
        "metadata.family absent",
        f"SKILL.md {len(text.splitlines())} > 60 lines",
        "more than 7 rules",
        "no fenced sample block",
        "9 shouted absolutes > 8 — explain the reason instead",
        "lib.md absent and omission not documented (add '- No `lib.md` — <reason>.')",
        "reference 'a-b.md' has a hyphen (must be snake_case)",
        "reference 'a-b.md' links another reference 'references/c.md'",
    )


async def test_law_skill_scope_must_be_known() -> None:
    assert SkillLaw.check("algo-zz-core", LAWFUL.replace("algo-py-core", "algo-zz-core"), {"lib.md": ""}) == (
        "scope 'zz' not in ['en', 'es', 'gen', 'py', 'rs', 'sh', 'sql']",
    )


async def test_law_agent_lawful_holds() -> None:
    assert AgentLaw.check(AGENT, servers=frozenset(), **CORPUS) == ()


async def test_law_agent_names_every_breach() -> None:
    agent = {
        **AGENT,
        "id": "Builder-x",
        "mode": "subagent",
        "model": "gpt",
        "description": "d" * 201,
        "mcp_servers": ["ghost"],
        "skills_preload": ["algo-py-core"],
        "skills_ondemand": {"algo-py-core": "two\nlines", "nope": ""},
        "permission": {
            "task": "allow",
            "question": "allow",
            "weird": "allow",
            "ghost_tool": "allow",
            "bash": {"git push*": "allow"},
            "skill": {"*": "allow"},
        },
    }
    assert AgentLaw.check(agent, servers=frozenset(), **CORPUS) == (
        "id 'Builder-x' not kebab-lowercase",
        "specialist 'Builder-x': no base agent 'Builder'",
        "mcp server 'ghost' not declared in the core's mcp config",
        "model 'gpt' not a house tier",
        "description 201 > 200 chars",
        "unknown permission keys ['weird']",
        "subagent with task delegation",
        "question/todowrite allow on non-primary",
        "'git push*' is allow — destructive/push must be ask or deny",
        "skill both preloaded and on-demand",
        "skill 'nope' not canonical or missing in core",
        "permission.skill must default deny (role scope)",
        "skill grant ≠ scope: only-granted [], only-scoped ['algo-py-core', 'nope']",
        "ondemand trigger for 'algo-py-core' must be a single line",
        "ondemand trigger for 'nope' must be a single line",
    )


async def test_law_agent_mode_must_be_known() -> None:
    assert AgentLaw.check({**AGENT, "mode": "boss"}, servers=frozenset(), **CORPUS) == ("mode 'boss' invalid",)


async def test_law_agent_full_scope_skips_the_grant() -> None:
    agent = {**AGENT, "skills_preload": [], "skills_full_scope": True, "permission": {"skill": {"*": "allow"}}}
    assert AgentLaw.check(agent, servers=frozenset(), **CORPUS) == ()


async def test_law_command_lawful_holds() -> None:
    assert CommandLaw.check(COMMAND, folder="ship", template="Ship $note", **CORPUS) == ()


@pytest.mark.parametrize(
    ("change", "template", "expected"),
    [
        ({"id": "Ship"}, "x $note", ("id 'Ship' not kebab-lowercase", "id 'Ship' != folder 'ship'")),
        ({"description": "d" * 201}, "$note", ("description 201 > 200 chars",)),
        ({"subtask": "yes"}, "$note", ("subtask must be a boolean",)),
        ({"model": "gpt"}, "$note", ("model 'gpt' not a house tier",)),
        ({"agent": "ghost"}, "$note", ("agent 'ghost' not in core",)),
        (
            {"skills": {"preload": ["algo-py-core"], "ondemand": {"algo-py-core": "t", "nope": "t"}}},
            "$note",
            ("skill both preloaded and on-demand", "skill 'nope' not canonical or missing in core"),
        ),
        ({"template": "body.md"}, "$note", ("template must export to template.md (structured always exports)",)),
        ({}, " ", ("template.md empty", "inputs declared but unused in template: ['note']")),
        ({}, "$1 $note", ("positional $N literal in template — declare an input and use $name",)),
        (
            {"inputs": {"Bad": "b"}},
            "$Bad $other",
            ("template uses undeclared $vars: ['other']", "input name 'Bad' not kebab-lowercase"),
        ),
    ],
    ids=["id", "description", "subtask", "model", "agent", "skills", "template", "empty", "positional", "inputs"],
)
async def test_law_command_breach(change: dict[str, Any], template: str, expected: tuple[str, ...]) -> None:
    assert CommandLaw.check({**COMMAND, **change}, folder="ship", template=template, **CORPUS) == expected
