"""tests/unit/e_taxis/models/command: a path splits into the node it mounts under and its own name."""

from e_taxis.harness.models.command import CommandCard, CommandGroup


def test_command_card_splits_its_path() -> None:
    card = CommandCard(path="history undo now", target="m:f", summary="s")
    assert (card.parent, card.name) == ("history undo", "now")


def test_command_group_at_the_top_mounts_on_the_root() -> None:
    group = CommandGroup(path="history", help="h")
    assert (group.parent, group.name) == ("", "history")
