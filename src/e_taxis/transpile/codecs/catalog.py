"""codecs.catalog: target format → its encoder. A format a spec declares and this table lacks is refused."""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from e_taxis.transpile.codecs.env import encode_env
from e_taxis.transpile.codecs.markdown import encode_markdown
from e_taxis.transpile.codecs.matter import encode_matter
from e_taxis.transpile.codecs.raw import encode_file, encode_text
from e_taxis.transpile.codecs.structured import encode_json, encode_toml, encode_yaml

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from e_taxis.transpile.models.placement import Placement

##### TABLE #####
ENCODERS: Final[Mapping[str, Callable[[str, Mapping[str, Any], Sequence[Placement]], bytes]]] = MappingProxyType(
    {
        "md": encode_markdown,
        "md+fm": encode_matter,
        "json": encode_json,
        "toml": encode_toml,
        "yaml": encode_yaml,
        "env": encode_env,
        "text": encode_text,
        "file": encode_file,
    }
)
