"""commands.project: driving adapter for the demo domain — parse, call `ProjectService`, render.

No store, no encoding, no rule lives here: the service owns them. Every change goes through the store the
service was given, which the runtime wrapped in the undo journal, so each command here is undoable with
`taxis history undo` without a line of inverse logic. `create`, `remove` and `env set` declare `_me`, an
`Identity` they never read — which is exactly how a command says "authenticated only"."""

from rich.console import Console
from rich.table import Table

from e_taxis.models.identity import Identity
from e_taxis.models.project import ProjectState
from e_taxis.runtime.deps import Inject
from e_taxis.services.project import ProjectService

##### DEFAULTS #####
HEADER: str = "bold #6f9bff"


##### COMMANDS #####
async def listing(*, projects: Inject[ProjectService], console: Inject[Console]) -> None:
    """Every project, with its state and how many variables it holds."""
    table = Table("project", "state", "vars", "description", box=None, header_style=HEADER)
    async for project in projects.listing():
        table.add_row(project.name, project.state, str(len(project.env)), project.description)
    console.print(table if table.row_count else "[dim]no projects yet: `taxis project create NAME`[/]")


async def create(
    name: str,
    *,
    description: str = "",
    state: ProjectState = ProjectState.DRAFT,
    projects: Inject[ProjectService],
    _me: Inject[Identity],
    console: Inject[Console],
) -> None:
    """Create an empty project.

    Args:
        name: lowercase slug, 2-39 characters.
        description: one line on what it is, at most 120 characters.
        state: where the project starts its life.
    """
    project = await projects.create(name, description, state)
    console.print(f"[green]✓[/] created {project.name} · {project.state}")


async def remove(
    name: str, *, projects: Inject[ProjectService], _me: Inject[Identity], console: Inject[Console]
) -> None:
    """Delete a project and its variables — `taxis history undo` brings it back.

    Args:
        name: the project to delete.
    """
    project = await projects.remove(name)
    console.print(f"[green]✓[/] removed {project.name}")


async def env_set(
    project: str,
    key: str,
    value: str,
    *,
    projects: Inject[ProjectService],
    _me: Inject[Identity],
    console: Inject[Console],
) -> None:
    """Set one variable of a project.

    Args:
        project: the project to change.
        key: UPPER_SNAKE variable name.
        value: variable value.
    """
    await projects.assign(project, key, value)
    console.print(f"[green]✓[/] {project} · {key} set")


async def env_list(project: str, *, projects: Inject[ProjectService], console: Inject[Console]) -> None:
    """Every variable of one project.

    Args:
        project: the project to read.
    """
    found = await projects.get(project)
    table = Table("key", "value", box=None, header_style=HEADER)
    for key, value in sorted(found.env.items()):
        table.add_row(key, value)
    console.print(table if table.row_count else f"[dim]{project} has no variables[/]")
