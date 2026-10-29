"""models.schedule: one unattended run as e-nous declares it, the systemd pair it renders into, and the plan that holds
the declared against the installed.

`core/tekton/config/schedules.yaml` is a map id → `Schedule`. An active one renders, byte-stable, into
`taxis-<id>.service` (a oneshot, one ExecStart per step: systemd stops at the first that fails) and `taxis-<id>.timer`;
both open with `HEADER`, the mark of ownership — a file without it is never taxis's. The plan is a pure diff of the two
sets of files, one action per id: create, update, remove or keep."""

import re
from collections.abc import Mapping
from enum import StrEnum
from itertools import groupby
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Final

from msgspec import Meta, Struct

##### DEFAULTS #####
HEADER: Final[str] = "# rendered by taxis schedule apply from core/tekton/config/schedules.yaml — do not edit"
PREFIX: Final[str] = "taxis-"
### a word of these characters needs no quotes on a systemd command line; any other is double-quoted with C escapes.
BARE: Final[re.Pattern[str]] = re.compile(r"[\w@+=:,./-]+")
### `$` expands on a command line only; `%` is a specifier everywhere systemd reads a value.
EXEC: Final[dict[int, str]] = str.maketrans({"\\": "\\\\", '"': '\\"', "\n": "\\n", "$": "$$", "%": "%%"})
ASSIGN: Final[dict[int, str]] = str.maketrans({"\\": "\\\\", '"': '\\"', "\n": "\\n", "%": "%%"})
SPECIFIER: Final[dict[int, str]] = str.maketrans({"%": "%%"})

### a unit name's characters (systemd.unit), `@` aside: an instance is not a schedule.
Ident = Annotated[str, Meta(pattern=r"^[A-Za-z0-9:_.-]+$")]
Argv = Annotated[tuple[str, ...], Meta(min_length=1)]


##### ENUMS #####
class ScheduleKind(StrEnum):
    """The two files of a schedule, by suffix."""

    SERVICE = ".service"
    TIMER = ".timer"

    def unit(self, ident: str) -> str:
        """The unit name of this kind for a schedule id."""
        return f"{PREFIX}{ident}{self}"

    @staticmethod
    def ident(name: str) -> str:
        """The schedule id a unit file name carries."""
        return name.removeprefix(PREFIX).rpartition(".")[0]


class ScheduleAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    REMOVE = "remove"
    KEEP = "keep"


### (wanted any, installed any, the same bytes) → the action; the other three keys cannot occur.
DIFF: Final[Mapping[tuple[bool, bool, bool], ScheduleAction]] = MappingProxyType(
    {
        (False, False, True): ScheduleAction.KEEP,
        (True, False, False): ScheduleAction.CREATE,
        (False, True, False): ScheduleAction.REMOVE,
        (True, True, True): ScheduleAction.KEEP,
        (True, True, False): ScheduleAction.UPDATE,
    }
)


##### TYPES #####
class Schedule(Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """One declared run: `calendar` is systemd's OnCalendar; `steps` are taxis argv without the binary, run in order;
    `off` keeps it declared and not installed."""

    doc: str
    calendar: str
    steps: Annotated[tuple[Argv, ...], Meta(min_length=1)]
    off: bool = False

    ##### PRIVATE METHODS #####

    @staticmethod
    def _render_word(word: str, table: dict[int, str]) -> str:
        return word if BARE.fullmatch(word) else f'"{word.translate(table)}"'

    def _render_service(self, root: Path, binary: Path) -> str:
        argvs = ((str(binary), *step) for step in self.steps)
        return "\n".join(
            (
                HEADER,
                "[Unit]",
                f"Description={' '.join(self.doc.split()).translate(SPECIFIER)}",
                "",
                "[Service]",
                "Type=oneshot",
                f"WorkingDirectory={str(root).translate(SPECIFIER)}",
                f"Environment={self._render_word(f'TAXIS_NOUS={root}', ASSIGN)}",
                *(f"ExecStart={' '.join(self._render_word(word, EXEC) for word in argv)}" for argv in argvs),
                "Nice=10",
                "",
            )
        )

    def _render_timer(self, ident: str) -> str:
        return "\n".join(
            (
                HEADER,
                "[Timer]",
                f"OnCalendar={self.calendar}",
                "Persistent=true",
                "RandomizedDelaySec=300",
                f"Unit={ScheduleKind.SERVICE.unit(ident)}",
                "",
                "[Install]",
                "WantedBy=timers.target",
                "",
            )
        )

    ############################################################

    ##### PUBLIC #####

    def render(self, ident: str, root: Path, binary: Path) -> dict[str, bytes]:
        """The pair by file name: the service runs `binary` per step in `root`, the timer fires it on the calendar."""
        return {
            ScheduleKind.SERVICE.unit(ident): self._render_service(root, binary).encode(),
            ScheduleKind.TIMER.unit(ident): self._render_timer(ident).encode(),
        }


class ScheduleStep(Struct, frozen=True, kw_only=True):
    id: str
    action: ScheduleAction


class SchedulePlan(Struct, frozen=True, kw_only=True):
    """One step per id: the declared ones in their order, then the installed ones no longer declared, by id."""

    steps: tuple[ScheduleStep, ...] = ()

    ##### PRIVATE METHODS #####

    @staticmethod
    def _diff_key(item: tuple[str, bytes]) -> str:
        return ScheduleKind.ident(item[0])

    @classmethod
    def _diff_group(cls, files: Mapping[str, bytes]) -> dict[str, dict[str, bytes]]:
        ordered = sorted(files.items(), key=cls._diff_key)
        return {ident: dict(group) for ident, group in groupby(ordered, key=cls._diff_key)}

    @staticmethod
    def _diff_action(want: Mapping[str, bytes], have: Mapping[str, bytes]) -> ScheduleAction:
        return DIFF[bool(want), bool(have), want == have]

    ############################################################

    ##### PUBLIC #####

    @classmethod
    def diff(cls, want: Mapping[str, bytes], have: Mapping[str, bytes], declared: tuple[str, ...]) -> SchedulePlan:
        """The action per id that turns the installed files (`have`) into the rendered ones (`want`)."""
        wanted, had = cls._diff_group(want), cls._diff_group(have)
        ids = (*declared, *sorted(had.keys() - set(declared)))
        return cls(
            steps=tuple(
                ScheduleStep(id=ident, action=cls._diff_action(wanted.get(ident, {}), had.get(ident, {})))
                for ident in ids
            )
        )


class ScheduleState(Struct, frozen=True, kw_only=True):
    """One schedule as the user manager sees it: declared and off per the core, installed per the units dir; the rest
    read verbatim from `systemctl --user show` — empty when systemd has nothing to say."""

    id: str
    declared: bool
    off: bool = False
    installed: bool
    enabled: str = ""
    next: str = ""
    last: str = ""
    result: str = ""
    status: str = ""
