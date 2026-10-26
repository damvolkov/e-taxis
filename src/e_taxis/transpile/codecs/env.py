"""codecs.env: a dotenv file — `KEY=value` lines, ours in row order; read back by key (comments and blanks carry none)."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from e_taxis.transpile.models.placement import Placement


##### UTILITIES #####
def encode_env(_: str, __: Mapping[str, Any], placements: Sequence[Placement]) -> bytes:
    return "".join(f"{placement.fragment}={placement.value}\n" for placement in placements).encode()


def key_env(line: str) -> str:
    """The variable a dotenv line sets, or "" for a comment, a blank or a line without `=`."""
    stripped = line.strip()
    return (
        stripped.partition("=")[0].strip().removeprefix("export ").strip()
        if stripped and not stripped.startswith("#") and "=" in stripped
        else ""
    )


def read_env(data: bytes) -> dict[str, str]:
    return {
        key: line.partition("=")[2].strip().strip('"').strip("'")
        for line in data.decode().splitlines()
        if (key := key_env(line))
    }
