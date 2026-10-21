"""adapters.undo: one recorded effect put back — the reverting end of the journal.

A whole file is restored, or removed where the run created it — with the directories the run made for it,
while they are empty; a JSON key and a marked block go back through the primitive that wrote them, which knows
their shape; a CLI registration runs its recorded inverse."""

from pathlib import Path
from typing import TYPE_CHECKING

from e_taxis.adapters.disk import remove_dirs, remove_file, write_file
from e_taxis.harness.models.journal import JournalBlock, JournalFile, JournalKey

if TYPE_CHECKING:
    from e_taxis.adapters.primitives.file import FilePrimitive
    from e_taxis.adapters.primitives.settings import SettingsPrimitive
    from e_taxis.harness.models.journal import JournalEffect
    from e_taxis.harness.models.ports import RunnerPort


##### TYPES #####
class EffectUndo:
    """Satisfies UndoPort."""

    __slots__ = ("_file", "_runner", "_settings")

    def __init__(self, runner: RunnerPort, settings: SettingsPrimitive, file: FilePrimitive) -> None:
        self._runner = runner
        self._settings = settings
        self._file = file

    async def run(self, effect: JournalEffect) -> None:
        match effect:
            case JournalFile(path=path, before=before, mode=mode, created=created):
                await (remove_file(Path(path)) if before is None else write_file(Path(path), before, mode))
                await remove_dirs(Path(path), created if before is None else 0)
            case JournalKey():
                await self._settings.revert(effect)
            case JournalBlock():
                await self._file.revert(effect)
            case _:
                await self._runner.run(effect.undo)
