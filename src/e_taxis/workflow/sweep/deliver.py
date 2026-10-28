"""sweep.deliver: the sweep posted to Discord — a short summary as the message, soa/report.md attached.

The webhook URL is a secret, so soa.yaml never holds it: its `discord.webhook` names the file that does (`~`
expanded; a relative path is read from the e-nous checkout). No name, no file, or an empty one stops the step
with the reason. The summary is one line per voice, the counts, the best findings; Discord's message limit cuts
it, never the attachment. Mentions are disabled: a report never pings anyone."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

import anyio

from e_taxis.workflow.models.error import SweepError

if TYPE_CHECKING:
    from e_taxis.workflow.models.ports import WebPort
    from e_taxis.workflow.models.sweep import Frame, Report, VoiceRow

##### DEFAULTS #####
LIMIT: int = 1900
TOP: int = 3
NAME: str = "report.md"
PLANE: str = "the whole plane"


##### TYPES #####
class SweepDeliver:
    """Over the web port."""

    __slots__ = ("_web",)

    def __init__(self, web: WebPort) -> None:
        self._web = web

    ##### PRIVATE METHODS #####

    @staticmethod
    async def _deliver_url(webhook: str, base: Path) -> str:
        match webhook:
            case "":
                msg = "soa.yaml names no webhook file (discord.webhook is empty): nothing to deliver to"
                raise SweepError(msg)
            case _:
                path = base / Path(await anyio.Path(webhook).expanduser())
        try:
            url = (await anyio.Path(path).read_text()).strip()
        except FileNotFoundError as missing:
            msg = f"no webhook file at {path}"
            raise SweepError(msg) from missing
        match url:
            case "":
                msg = f"the webhook file {path} is empty"
                raise SweepError(msg)
            case _:
                return url

    @staticmethod
    def _deliver_voice(row: VoiceRow) -> str:
        counts = f"{row.parsed} parsed · {row.in_window} in window · {row.new} new · {row.findings} findings"
        return f"{row.status} **{row.id}** — {row.error or counts}"

    @classmethod
    def _deliver_summary(cls, frame: Frame, report: Report) -> str:
        lines = (
            f"**soa-sweep** · {frame.topic or PLANE} · {frame.since} → {frame.until}",
            *(cls._deliver_voice(row) for row in report.voices),
            f"{len(report.findings)} findings · {len(report.assess)} to assess",
            *(f"- {f.title} ({f.relevance}/5, {f.status or 'unfit'})" for f in report.findings[:TOP]),
            "Full report attached.",
        )
        return "\n".join(lines)[:LIMIT]

    ############################################################

    ##### PUBLIC #####

    async def deliver(self, *, webhook: str, base: Path, frame: Frame, report: Report, markdown: str) -> str:
        """Post the summary and `markdown`; answer the summary posted."""
        url = await self._deliver_url(webhook, base)
        summary = self._deliver_summary(frame, report)
        payload = {"content": summary, "allowed_mentions": {"parse": []}, "attachments": [{"id": 0, "filename": NAME}]}
        await self._web.post(
            url,
            fields={"payload_json": json.dumps(payload, ensure_ascii=False)},
            files={"files[0]": (NAME, markdown.encode())},
        )
        return summary
