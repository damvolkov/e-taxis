"""codecs.raw: a target that is one value — text as it is, or bytes copied as they are."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from e_taxis.transpile.models.placement import Placement


##### UTILITIES #####
def encode_text(_: str, __: Mapping[str, Any], placements: Sequence[Placement]) -> bytes:
    return "".join(str(placement.value) for placement in placements).encode()


def encode_file(_: str, __: Mapping[str, Any], placements: Sequence[Placement]) -> bytes:
    return b"".join(placement.value for placement in placements)
