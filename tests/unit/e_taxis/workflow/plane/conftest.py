"""tests/unit/e_taxis/workflow/plane: a one-skill world for the real routing probe — a render holding a single skill
and a checkout holding its query set (one case that must load it, one near miss that must not)."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

SKILL = """---
name: sort-py-keys
description: "Python: sorting records by a field with key functions and operator.itemgetter. Use when sorting tuples,
  dicts or objects by one or more fields."
---

Sort with `sorted(rows, key=itemgetter(1))`; never a hand-written comparison.
"""
QUERIES = """# sort-py-keys — query set

```toml
[[case]]
prompt = "How do I sort a list of tuples by their second field in Python?"
expect = ["sort-py-keys"]

[[case]]
prompt = "Write a Makefile with lint and test targets."
reject = ["sort-py-keys"]
```
"""


@pytest.fixture
def probe_render() -> dict[str, str]:
    """The render's one skill, as files to write under a run's base."""
    return {"skills/sort-py-keys/SKILL.md": SKILL}


@pytest.fixture
def probe_nous(tmp_path: Path, tree) -> Path:
    """A checkout holding only the skill's query set."""
    nous = tmp_path / "nous"
    tree(nous, {"core/tekton/evals/queries/sort-py-keys.md": QUERIES})
    return nous
