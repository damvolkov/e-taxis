from typing import TYPE_CHECKING

from e_taxis.project.adapters.graph import GraphStore
from e_taxis.project.models.graph import SCHEMA

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.project.models.manifest import Template

REDIS = "providers/drivers/store/redis"


async def test_build_units(repo: Path, template: Template) -> None:
    graph = GraphStore(repo).build(template, "sys")
    assert graph.areas == ("infra", "ops", "providers")
    assert [unit.key for unit in graph.units] == [
        "infra/config/providers/drivers/store/redis",
        "infra/settings",
        "ops/file",
        "providers/drivers/http/wreq",
        "providers/drivers/store/redis",
        "providers/drivers/store/sqlite",
    ]


async def test_build_edges(repo: Path, template: Template) -> None:
    redis = GraphStore(repo).build(template, "sys").unit(REDIS)
    assert redis.deps == ("infra/config/providers/drivers/store/redis", "ops/file")
    assert redis.dependents == ("providers/drivers/store/sqlite",)
    assert redis.closure == ("infra/config/providers/drivers/store/redis", "infra/settings", "ops/file")
    assert redis.tests == ("tests/unit/providers/drivers/store/test_redis.py",)
    assert (redis.area, redis.name) == ("providers", "drivers/store/redis")


async def test_build_pins_what_the_app_imports(repo: Path, template: Template) -> None:
    graph = GraphStore(repo).build(template, "sys")
    assert graph.required == {"ops/file"}
    assert graph.unit(REDIS).detachable
    assert graph.unit("ops/file").level == 0


async def test_build_skips_declared(repo: Path, template: Template) -> None:
    assert "ops/tui" not in {unit.key for unit in GraphStore(repo).build(template, "sys").units}


async def test_drift_lifecycle(repo: Path, template: Template) -> None:
    store = GraphStore(repo)
    assert store.drift(template, "sys") == ["graph.lock.yml: missing"]
    store.write(template, "sys")
    assert store.drift(template, "sys") == []
    assert store.read(template).schema == SCHEMA == 2
    (repo / "projects/sys/src/ops/file.py").write_text("x = 1\n")
    assert store.drift(template, "sys") == ["graph.lock.yml: drifted from sources, run make graph"]
