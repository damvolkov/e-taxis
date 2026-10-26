"""models.placement: the intermediate form of a render — one value placed at one fragment, with its provenance.

Every row a spec declares yields placements: where the value lands (`target` path, `fragment` in it), the value
itself after its transforms, and where it came from (`section`, `row` index, the core paths it read). A target's
bytes are its placements, encoded by its format in declaration order; a report or a reverse walks them back to
the row and the core path that produced each fragment."""

from dataclasses import dataclass
from typing import Any

##### DEFAULTS #####
GLUE: str = "\n\n"


##### TYPES #####
@dataclass(frozen=True, slots=True)
class Placement:
    """`glue` joins Markdown parts of one block; `sources` are the core paths the row read."""

    target: str
    fragment: str
    value: Any
    section: str
    row: int
    sources: tuple[str, ...] = ()
    glue: str = GLUE

    @property
    def origin(self) -> str:
        """`config[3]`: the spec row behind the fragment."""
        return f"{self.section}[{self.row}]"
