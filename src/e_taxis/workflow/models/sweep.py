"""models.sweep: soa-sweep's data — the frame a sweep looks through, what the voices published, the findings.

**The frame.** `SoaConfig` is e-nous's `core/tekton/config/soa.yaml` (the plane, its topics, the voices heard first);
`Frame` is one run of it: a topic, its keywords, the window as two dates, the voices and the links that speak to it.

**The chain.** `Seen` (the ledger: every URL already reported, per voice) → `Entries` (what each voice published in
the window, its pages fetched) → `Findings` (systems, projects or ideas the agents named; ground keeps those a
fetched page holds, fit marks each have · considered · new) → `Report` (the sweep as written).

Every model here is a port: `PORTS` names them as the workflow's nodes do, one JSON Schema each in its `schemas/`."""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final

import msgspec


##### ENUMS #####
class VoiceKind(StrEnum):
    """How a voice is read: an Atom feed, a public LinkedIn profile, or a web page itself."""

    ATOM_FEED = "atom_feed"
    LINKEDIN_PROFILE = "linkedin_profile"
    WEB = "web"


class VoiceStatus(StrEnum):
    """`empty`: read, nothing inside the window — a result, not a failure."""

    OK = "ok"
    EMPTY = "empty"
    ERROR = "error"


class FindingKind(StrEnum):
    FRAMEWORK = "framework"
    LIBRARY = "library"
    TOOL = "tool"
    PLUGIN = "plugin"
    OSS_REPO = "oss_repo"
    ONTOLOGY = "ontology"
    PATTERN = "pattern"
    PAPER = "paper"
    CONCEPT = "concept"
    OPINION = "opinion"


class FindingStatus(StrEnum):
    """Set by fit, never by an agent: empty until then."""

    HAVE = "have"
    CONSIDERED = "considered"
    NEW = "new"
    UNSET = ""


##### THE CONFIG #####
class SoaTopic(msgspec.Struct, frozen=True, kw_only=True):
    keywords: tuple[str, ...] = ()


class SoaAuthor(msgspec.Struct, frozen=True, kw_only=True):
    name: str = ""
    url: str
    kind: VoiceKind
    topics: tuple[str, ...] = ()


class SoaLink(msgspec.Struct, frozen=True, kw_only=True):
    url: str
    topics: tuple[str, ...] = ()


class SoaDiscord(msgspec.Struct, frozen=True, kw_only=True):
    """`webhook` names the file holding the URL, never the URL."""

    webhook: str = ""


class SoaConfig(msgspec.Struct, frozen=True, kw_only=True):
    """e-nous's `core/tekton/config/soa.yaml`, as its schema entry (`tekton.soa`) declares it."""

    brief: str
    window: int
    topics: dict[str, SoaTopic]
    authors: dict[str, SoaAuthor] = {}
    links: dict[str, SoaLink] = {}
    discord: SoaDiscord = SoaDiscord()


##### THE PORTS #####
class Voice(msgspec.Struct, frozen=True, kw_only=True):
    """A preferred author or reference link."""

    id: str
    name: str = ""
    url: str
    kind: VoiceKind
    topics: tuple[str, ...] = ()


class Frame(msgspec.Struct, frozen=True, kw_only=True):
    """frame: what this sweep looks at — the brief, the topic, the window, the voices first."""

    brief: str
    topic: str
    keywords: tuple[str, ...]
    since: str
    until: str
    voices: tuple[Voice, ...]
    links: tuple[str, ...] = ()


class Seen(msgspec.Struct, frozen=True, kw_only=True):
    """ledger: every URL already reported, per voice, with the date it was seen."""

    seen: dict[str, dict[str, str]] = {}


class Entry(msgspec.Struct, frozen=True, kw_only=True):
    """One post or article, its page fetched. `teaser`: the page's body was not read (only the listing's text);
    `new`: its URL is not in the ledger."""

    url: str
    title: str = ""
    published_at: str
    text: str
    links: tuple[str, ...] = ()
    teaser: bool = False
    new: bool = True


class VoiceEntries(msgspec.Struct, frozen=True, kw_only=True):
    """One voice, read: `parsed` entries its listing holds, `in_window` of them inside the window, `new` of those."""

    id: str
    status: VoiceStatus
    error: str = ""
    parsed: int = 0
    in_window: int = 0
    new: int = 0
    entries: tuple[Entry, ...] = ()


class Entries(msgspec.Struct, frozen=True, kw_only=True):
    """fetch: what each voice published inside the window, read from its own pages."""

    voices: tuple[VoiceEntries, ...]


class Finding(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """Name the thing, not the post."""

    title: str
    kind: FindingKind
    description: str
    why: str
    facts: tuple[str, ...]
    links: tuple[str, ...]
    sources: tuple[str, ...]
    entities: tuple[str, ...] = ()
    published_at: str
    relevance: Annotated[int, msgspec.Meta(ge=1, le=5)]
    via: Annotated[str, msgspec.Meta(description="the voice id it came through, or `search`")]
    status: FindingStatus = FindingStatus.UNSET
    incumbent: Annotated[str, msgspec.Meta(description="set by fit: what already names it, and where")] = ""


class Findings(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """voices · search · ground · fit: systems, projects or ideas, each grounded in a fetched page."""

    findings: tuple[Finding, ...]
    notes: str = ""


class VoiceRow(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """One voice in the report: how it read, and how many findings came through it."""

    id: str
    status: VoiceStatus
    error: str = ""
    parsed: int = 0
    in_window: int = 0
    new: int = 0
    findings: int = 0


class Report(msgspec.Struct, frozen=True, kw_only=True):
    """report: the sweep as written — per voice, the ranked findings, the assess commands."""

    path: str
    voices: tuple[VoiceRow, ...]
    findings: tuple[Finding, ...]
    assess: tuple[str, ...]


### The search agent's findings come through no voice: the ledger keeps their links under this key.
SEARCH: Final[str] = "search"

### Every artifact passed between soa-sweep's steps, by the model name its ports declare.
PORTS: Final[Mapping[str, object]] = MappingProxyType(
    {"Frame": Frame, "Seen": Seen, "Entries": Entries, "Findings": Findings, "Report": Report}
)
