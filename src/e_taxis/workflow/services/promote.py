"""services.promote: the one step that writes an enhancement's verdicts into the checkout.

It refuses outright when HEAD moved since the run's base: every measurement was taken against that base, and a
patch applied on top of anything else is a change nobody measured. Otherwise it applies, three-way, the patches of
every `adopt` verdict, the `propose` verdicts named with `ids`, or every promotable verdict (`everything`). A patch
already present in the checkout (a hand edit) is `already`, not applied twice. The record lands in the run folder
(`promote.json`); committing, and landing the transpile, stay the human's next steps. Who may call it — a human — is
the command's to check; this holds the run lock like every plane run."""

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
import msgspec

from e_taxis.workflow.models.error import PlaneError, StaleError
from e_taxis.workflow.models.plane import Plane
from e_taxis.workflow.models.verdict import Decision, Promotion, Verdict

if TYPE_CHECKING:
    from e_taxis.workflow.models.ports import LockPort, SandboxPort
    from e_taxis.workflow.services.plane import PlaneRun

##### DEFAULTS #####
LOCK: str = ".lock"
RECORD: str = "promote.json"


##### TYPES #####
class PlanePromote:
    """The run's reader, the git it applies with, the checkout's lock."""

    __slots__ = ("_lock", "_runs", "_sandbox")

    def __init__(self, runs: PlaneRun, sandbox: SandboxPort, lock: LockPort) -> None:
        self._runs = runs
        self._sandbox = sandbox
        self._lock = lock

    ##### PRIVATE METHODS #####

    @staticmethod
    def _run_chosen(verdicts: tuple[Verdict, ...], ids: tuple[str, ...], *, everything: bool) -> tuple[Verdict, ...]:
        return tuple(
            verdict
            for verdict in verdicts
            if verdict.decision.promotable
            and verdict.patch
            and (verdict.decision is Decision.ADOPT or everything or verdict.subject in ids)
        )

    async def _run_one(self, root: Path, verdict: Verdict) -> tuple[str, str]:
        """(bucket, why): applied, already, or refused with the reason."""
        patch = Path(verdict.patch)
        already = await self._sandbox.apply(root, patch, check=True, reverse=True)
        applies = await self._sandbox.apply(root, patch, check=True)
        match (already, applies):
            case (True, _):
                return "already", ""
            case (False, True):
                return ("applied", "") if await self._sandbox.apply(root, patch) else ("refused", "3-way apply failed")
            case _:
                return "refused", "patch does not apply to the working tree"

    ############################################################

    ##### PUBLIC #####

    async def run(self, root: Path, run: str, ids: tuple[str, ...], *, everything: bool) -> tuple[Promotion, Path]:
        folder = await self._runs.folder(root, run, Plane.ENHANCER)
        report = await self._runs.load(folder)
        manifest = report.manifest
        async with self._lock.hold(self._runs.reports(root) / LOCK, f"enhance promote {manifest.run_id}"):
            head = await self._sandbox.head(root)
            match (head == manifest.base_sha, sorted(set(ids) - {v.subject for v in report.verdicts})):
                case (False, _):
                    msg = f"HEAD {head[:10]} ≠ run base {manifest.base_sha[:10]}: run the enhancement again"
                    raise StaleError(msg)
                case (_, [_, *_] as unknown):
                    msg = f"no verdict for {', '.join(unknown)} in {manifest.run_id}"
                    raise PlaneError(msg)
                case _:
                    pass
            chosen = self._run_chosen(report.verdicts, ids, everything=everything)
            buckets = {verdict.subject: await self._run_one(root, verdict) for verdict in chosen}
        promotion = Promotion(
            run_id=manifest.run_id,
            base_sha=manifest.base_sha,
            at=dt.datetime.now(dt.UTC),
            applied=tuple(subject for subject, (bucket, _) in buckets.items() if bucket == "applied"),
            already=tuple(subject for subject, (bucket, _) in buckets.items() if bucket == "already"),
            refused={subject: why for subject, (bucket, why) in buckets.items() if bucket == "refused"},
        )
        target = folder / RECORD
        await anyio.Path(target).write_bytes(msgspec.json.format(msgspec.json.encode(promotion)))
        return promotion, target
