"""e-taxis entrypoint: `taxis` — the command tree is two tables, and nothing under commands/ loads until it runs.

`GROUPS` and `CARDS` are the whole surface. `build` is the composition root: it turns the tables into
cyclopts apps and mounts every card by its `module:function` string, so importing this module imports no
command, and `taxis --help` or any group listing is served from the cards alone. The meta app runs the
`Launcher` first on every call: global options, the run's lifespan, injection by type, the error boundary.

Adding a command is one row in `CARDS` plus one plain function; a command that needs a new group adds a
row in `GROUPS`, parents before children. `tests/unit/e_taxis/test_cli.py` resolves every target, so a
typo fails the gate, never a user.

    taxis map      [--target T] [--json]
    taxis plan     --target T (--profile P | --engineer PATH) [--json]
    taxis verify   --target T (--profile P | --engineer PATH) [--json]
    taxis doctor   [--json]
    taxis history  list · undo
"""

import sys
from importlib.metadata import version

from cyclopts import App

from e_taxis.models.command import CommandCard, CommandGroup
from e_taxis.runtime.launcher import Launcher

##### TREE #####
GROUPS: tuple[CommandGroup, ...] = (
    CommandGroup(path="history", help="Every run that wrote to the store, and the undo of the last one."),
)

CARDS: tuple[CommandCard, ...] = (
    CommandCard(path="map", target="e_taxis.commands.catalog:mapping", summary="The catalog, per target and profile."),
    CommandCard(path="plan", target="e_taxis.commands.stack:plan", summary="What apply would do; writes nothing."),
    CommandCard(path="verify", target="e_taxis.commands.stack:verify", summary="Run every wanted part's verify."),
    CommandCard(path="doctor", target="e_taxis.commands.catalog:doctor", summary="Check the catalog's integrity."),
    CommandCard(path="history list", target="e_taxis.commands.history:listing", summary="Every recorded run."),
    CommandCard(path="history undo", target="e_taxis.commands.history:undo", summary="Revert the last recorded run."),
)


def build() -> App:
    """Composition root: the tree from the tables, the launcher on the meta app. Imports no command module."""
    root = App(
        name="taxis",
        help="e-taxis — mounts agent harnesses after the transpile",
        version=version("e-taxis"),
        result_action="return_value",
    )
    apps = {"": root}
    for group in GROUPS:
        apps[group.path] = App(name=group.name, help=group.help)
        apps[group.parent].command(apps[group.path])
    for card in CARDS:
        apps[card.parent].command(card.target, name=card.name, help=card.summary)
    root.meta.default(Launcher(root, CARDS).run)
    return root


def main() -> None:
    """The `taxis` script: build, run, exit with the launcher's code."""
    sys.exit(build().meta(sys.argv[1:]))
