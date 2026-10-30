from typing import TYPE_CHECKING

import pytest

from e_taxis.project.models.manifest import Common
from e_taxis.project.ops.graph import areas_of, catalog, core_tests, imports_of

if TYPE_CHECKING:
    from pathlib import Path

KEYS = frozenset({"ops/file", "providers/drivers/store/redis", "providers/drivers/store", "infra/settings"})


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("import ops.file", {"ops/file"}),
        ("from ops.file import read", {"ops/file"}),
        ("from ops import file", {"ops/file"}),
        ("from providers.drivers.store import redis", {"providers/drivers/store", "providers/drivers/store/redis"}),
        ("from providers.drivers.store.redis import RedisDriver", {"providers/drivers/store/redis"}),
        ("from infra.settings.deeper import x", {"infra/settings"}),
        ("import e_app.main\nimport json\nfrom ops import missing", set()),
    ],
    ids=["import", "from-module", "from-parent", "from-nested-module", "longest-wins", "attr-tail", "foreign"],
)
async def test_imports_resolution(text: str, expected: set[str]) -> None:
    assert imports_of(text, KEYS) == expected


async def test_areas_of_nested(repo: Path) -> None:
    assert areas_of(repo / "projects/sys/src", "e_app") == ("infra", "ops", "providers")


async def test_catalog_every_module(repo: Path) -> None:
    src = repo / "projects/sys/src"
    files = catalog(src, areas_of(src, "e_app"))
    assert files["providers/drivers/store/redis"] == ("src/providers/drivers/store/redis.py",)
    assert files["infra/config/providers/drivers/store/redis"] == ("src/infra/config/providers/drivers/store/redis.py",)
    assert not any("junk" in key or "__init__" in key for key in files)
    assert len(files) == 7


async def test_core_tests_nested(repo: Path) -> None:
    common = Common(root="projects/common")
    found = core_tests(common, repo / "projects/common", ["providers/drivers/store/redis", "ops/file", "ops/hash"])
    assert found == {
        "providers/drivers/store/redis": ("tests/unit/providers/drivers/store/test_redis.py",),
        "ops/file": ("tests/unit/ops/test_file.py",),
        "ops/hash": (),
    }
