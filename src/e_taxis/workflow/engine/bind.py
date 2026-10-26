"""engine.bind: a step's `{{name}}` placeholders bound to the run's parameters — never re-parsed by a shell.

A value is data, never code. Into a shell command it travels as an environment variable (`TAXIS_PARAM_<name>`) and
the placeholder becomes a reference to it, quoted for the context it sits in: `"${V}"` bare, `${V}` inside double
quotes, `'"${V}"'` inside single quotes (close, expand quoted, reopen). bash expands a variable once and never
evaluates what it holds, so quotes, `$(…)`, backticks and newlines in a value arrive as themselves. Into an agent's
instruction — plain text, no shell — the value is substituted as is. A placeholder that names no parameter stays."""

import re
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

##### DEFAULTS #####
PARAM: Final[re.Pattern[str]] = re.compile(r"\{\{\s*(\w+)\s*\}\}")
### single-quoted · double-quoted (backslash escapes kept) · a bare run (backslash escapes kept) · a lone quote char.
SEGMENT: Final[re.Pattern[str]] = re.compile(r"""'[^']*'|"(?:\\.|[^"\\])*"|(?:\\.|[^'"\\])+|.""", re.DOTALL)
PREFIX: str = "TAXIS_PARAM_"


##### TYPES #####
class ParamBind:
    """Stateless: the parameters come in on every call."""

    __slots__ = ()

    ##### PRIVATE METHODS #####

    @staticmethod
    def _shell_reference(segment: str, name: str) -> str:
        """The reference to `name`'s variable that expands to exactly its value inside this segment."""
        variable = f"${{{PREFIX}{name}}}"
        match segment[:1]:
            case "'":
                return f"'\"{variable}\"'"
            case '"':
                return variable
            case _:
                return f'"{variable}"'

    @classmethod
    def _shell_segment(cls, segment: str, params: Mapping[str, str]) -> str:
        return PARAM.sub(
            lambda found: cls._shell_reference(segment, found.group(1)) if found.group(1) in params else found.group(0),
            segment,
        )

    ############################################################

    ##### PUBLIC #####

    @classmethod
    def shell(cls, template: str, params: Mapping[str, str]) -> tuple[str, dict[str, str]]:
        """The command with every known placeholder a quoted variable reference, and the variables it reads."""
        command = "".join(cls._shell_segment(found.group(0), params) for found in SEGMENT.finditer(template))
        named = {found.group(1) for found in PARAM.finditer(template)} & params.keys()
        return command, {f"{PREFIX}{name}": params[name] for name in sorted(named)}

    @staticmethod
    def text(template: str, params: Mapping[str, str]) -> str:
        """Plain text with every known placeholder replaced by its value."""
        return PARAM.sub(lambda found: params.get(found.group(1), found.group(0)), template)

    @staticmethod
    def due(when: Mapping[str, tuple[str, ...]], params: Mapping[str, str]) -> bool:
        """Whether every condition holds: the parameter's value is one of the listed ones."""
        return all(params.get(key, "") in values for key, values in when.items())
