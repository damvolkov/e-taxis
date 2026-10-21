"""ops.rewrite: guarded whole-word text rules — a rename that can never eat a substring of a longer identifier."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from e_taxis.project.models.manifest import Strip


def rewrite_text(text: str, rules: Sequence[Strip]) -> str:
    """Every whole-word occurrence of each rule's ``frm`` replaced by ``to``; word guard on both ends."""
    for rule in rules:
        text = re.sub(rf"(?<!\w){re.escape(rule.frm)}(?!\w)", rule.to, text)
    return text


def rewrite_segment(segment: str, rules: Sequence[Strip]) -> str:
    """One path segment through the same rules — a file or directory name is text too."""
    return rewrite_text(segment, rules)
