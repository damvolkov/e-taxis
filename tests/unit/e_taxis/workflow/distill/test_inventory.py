"""tests/unit/e_taxis/workflow/distill/inventory: every plane read without a model, three-way against the base."""

from typing import TYPE_CHECKING

from e_taxis.workflow.distill.inventory import DistillInventory
from e_taxis.workflow.distill.scope import DistillScope
from e_taxis.workflow.models.distill import Direction, FactStatus, Plane

if TYPE_CHECKING:
    from pathlib import Path

    from e_taxis.workflow.adapters.command import ShellCommand


async def test_inventory_reads_every_plane_three_way(
    command: ShellCommand, cores: tuple[Path, Path, Path, str], tree
) -> None:
    templates, harness, project, v1 = cores
    tree(project, {"src/e_proj/adapters/uncommitted.py": ""})
    manifest = await DistillScope(command).intake(await DistillScope(command).guard(project, (), "", ""))
    taken = await DistillInventory(command, harness=harness, blueprint=templates, ref="main").take(manifest)
    found = {(f.plane, f.subject, f.status, f.direction) for f in taken.facts}
    assert found == {
        (Plane.LIBRARY, "psqlpy", FactStatus.ABSENT, None),
        (Plane.LIBRARY, "pytest-resources", FactStatus.ABSENT, None),
        (Plane.MODULE, "src/e_proj/adapters/http.py", FactStatus.DIVERGED, Direction.AHEAD),
        (Plane.MODULE, "src/e_proj/ops/file.py", FactStatus.DIVERGED, Direction.BOTH),
        (Plane.MODULE, "src/e_proj/adapters/postgres.py", FactStatus.ABSENT, None),
        (Plane.COMMON, "prek.toml", FactStatus.DIVERGED, Direction.AHEAD),
        (Plane.SERVICE, "tei", FactStatus.ABSENT, None),
        (Plane.SERVICE, "redis", FactStatus.ABSENT, None),
        (Plane.PROJECT, "mcp", FactStatus.ABSENT, None),
        (Plane.PROJECT, "retrieval", FactStatus.ABSENT, None),
        (Plane.PROJECT, "Makefile", FactStatus.DIVERGED, Direction.AHEAD),
        (Plane.PROJECT, "pyproject.toml", FactStatus.DIVERGED, Direction.AHEAD),
        (Plane.TOOLING, "e-proj", FactStatus.ABSENT, None),
        (Plane.OPS, "make golden", FactStatus.ABSENT, None),
        (Plane.OPS, "deploy/", FactStatus.ABSENT, None),
        (Plane.OPS, "scripts/", FactStatus.ABSENT, None),
        (Plane.OPS, ".github/workflows/nightly.yml", FactStatus.ABSENT, None),
        (Plane.OPS, "scripts/bench.py", FactStatus.ABSENT, None),
        (Plane.OPS, "tests/bench/", FactStatus.ABSENT, None),
    }
    assert {(f.subject, f.status, f.direction) for f in taken.stale} == {
        ("src/e_proj/adapters/ports.py", FactStatus.DIVERGED, Direction.BEHIND),
        (".gitattributes", FactStatus.MISSING, None),
        ("make core-check", FactStatus.MISSING, None),
        ("make common-check", FactStatus.MISSING, None),
        (".templates.yaml", FactStatus.MISSING, None),
    }
    by = {f.subject: f for f in taken.facts}
    assert (by["src/e_proj/ops/file.py"].base, by["psqlpy"].id) == (v1, "library:psqlpy")
    assert by["psqlpy"].detail == "blueprint: api"
    assert by["pytest-resources"].detail == "blueprint: none"
    assert by["src/e_proj/ops/file.py"].detail.startswith("project +1 -0, template +1 -1 since base")
    assert by["src/e_proj/adapters/http.py"].detail.endswith(
        "1/2 of its new definitions already in projects/python/core/src/e_core/adapters/thing.py"
    )
    assert "removals only" not in by["prek.toml"].detail


async def test_inventory_takes_the_recorded_base(
    command: ShellCommand, cores: tuple[Path, Path, Path, str], git, tree, commit
) -> None:
    templates, harness, project, v1 = cores
    head = (await git(templates, "rev-parse", "HEAD")).strip()
    tree(
        project,
        {
            ".templates.yaml": f"system: projects/python/api\ncommit: {head}\ndirty: false\n",
            "src/e_proj/adapters/thing.py": "",
        },
    )
    await commit(project, "chore: origin")
    manifest = await DistillScope(command).intake(await DistillScope(command).guard(project, (), "", ""))
    taken = await DistillInventory(command, harness=harness, blueprint=templates, ref="main").take(manifest)
    ports = next(f for f in taken.facts if f.subject == "src/e_proj/adapters/ports.py")
    assert (ports.direction, ports.base) == (Direction.AHEAD, head)
    thing = next(f for f in taken.facts if f.subject == "src/e_proj/adapters/thing.py")
    assert thing.detail.endswith("removals only: what the generator pruned or the project does not use")
    assert ".templates.yaml" not in {f.subject for f in taken.stale}
    assert v1 != head


async def test_inventory_without_a_base_reads_a_plain_divergence(
    command: ShellCommand, cores: tuple[Path, Path, Path, str], tree, commit
) -> None:
    """A recorded commit the blueprint does not hold, and a module the project never added: no base, a bare diff."""
    templates, harness, project, _ = cores
    tree(project, {".templates.yaml": "commit: 0000000\n"})
    await commit(project, "chore: a lost origin")
    manifest = await DistillScope(command).intake(await DistillScope(command).guard(project, (), "", ""))
    taken = await DistillInventory(command, harness=harness, blueprint=templates, ref="main").take(manifest)
    http = next(f for f in taken.facts if f.subject == "src/e_proj/adapters/http.py")
    assert (http.direction, http.detail) == (None, "+5 -0 vs projects/python/core/src/e_core/adapters/http.py")


async def test_inventory_unpackaged_project_skips_the_package_planes(
    command: ShellCommand, cores: tuple[Path, Path, Path, str], tree, commit
) -> None:
    templates, harness, project, _ = cores
    tree(project, {"src/second/x.py": ""})
    await commit(project, "feat: a second package")
    manifest = await DistillScope(command).intake(await DistillScope(command).guard(project, (), "", ""))
    taken = await DistillInventory(command, harness=harness, blueprint=templates, ref="main").take(manifest)
    assert not {f.plane for f in taken.facts} & {Plane.MODULE, Plane.TOOLING}
