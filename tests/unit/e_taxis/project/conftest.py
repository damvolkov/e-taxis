"""tests/unit/e_taxis/project: a synthetic system over a namespace tree — nested modules, no `__init__.py` anywhere."""

from typing import TYPE_CHECKING

import pytest

from e_taxis.project.models.manifest import Common, Detach, Template

if TYPE_CHECKING:
    from pathlib import Path

TREE: dict[str, str] = {
    "src/e_app/main.py": "from providers.drivers.store.redis import RedisDriver\nfrom ops import file\n",
    "src/ops/file.py": "",
    "src/ops/tui.py": "",
    "src/infra/settings.py": "",
    "src/infra/config/providers/drivers/store/redis.py": "from infra import settings\n",
    "src/providers/drivers/store/redis.py": (
        "from infra.config.providers.drivers.store.redis import RedisSettings\nimport ops.file\n"
    ),
    "src/providers/drivers/store/sqlite.py": "from providers.drivers.store import redis\n",
    "src/providers/drivers/http/wreq.py": "from infra.settings import settings\n",
    "src/providers/drivers/__pycache__/junk.py": "",
}
CORE_TESTS: tuple[str, ...] = (
    "tests/unit/e_infra/providers/drivers/store/test_redis.py",
    "tests/unit/e_infra/providers/drivers/store/test_sqlite_real.py",
    "tests/unit/e_infra/ops/test_file.py",
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository root holding the system under `projects/sys` and its common tests under `projects/common`."""
    [
        (path.parent.mkdir(parents=True, exist_ok=True), path.write_text(body))
        for rel, body in TREE.items()
        for path in [tmp_path / "projects/sys" / rel]
    ]
    [
        (path.parent.mkdir(parents=True, exist_ok=True), path.write_text(""))
        for rel in CORE_TESTS
        for path in [tmp_path / "projects/common" / rel]
    ]
    return tmp_path


@pytest.fixture
def template() -> Template:
    return Template(
        source="projects/sys",
        package="e_app",
        brand="e-app",
        common=Common(
            root="projects/common",
            skip=("ops/tui",),
            detach=(Detach(unit="providers/drivers/store/redis"),),
        ),
    )
