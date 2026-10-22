"""A corpus on disk and a store that versions it, both thrown away after each test."""

from __future__ import annotations

from pathlib import Path

import pytest

from ops.transpiler.history.store import Store

#: A miniature of the real thing: two entities, one reference, one generated root file.
CORPUS: dict[str, str] = {
    "skills/data-py-cache/SKILL.md": "# data-py-cache\n\nrule one\n",
    "skills/data-py-cache/references/lib.md": "# lib\n\nthe stack\n",
    "agents/builder.md": "---\ndescription: builds\n---\n\nprompt\n",
    "AGENTS.md": "# Demian\n",
}
#: What a runtime writes into the same tree and the store must never version.
RUNTIME: dict[str, str] = {
    "sessions/live.json": '{"open": true}',
    "skills/synced/ghost/SKILL.md": "runtime-owned",
}


def write(root: Path, files: dict[str, str]) -> None:
    """Materialise a mapping of relative paths to contents."""
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A config dir holding the corpus plus the runtime noise that surrounds it."""
    root = tmp_path / "ecoder"
    write(root, CORPUS | RUNTIME)
    return root


@pytest.fixture
def store(tree: Path, tmp_path: Path) -> Store:
    """A store whose git dir lives apart from the tree it versions, already initialised."""
    made = Store(tree, tmp_path / "state" / "corpus.git", exclude=("sessions/", "skills/synced/"))
    made.initialise()
    return made
