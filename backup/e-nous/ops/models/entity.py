"""models.entity — the vocabulary of the corpus: the entity kinds, the facets, the harnesses, the backends, the two shapes.

Two axes meet here. Inside, core/ is split by **facet** — the side of Demian an entity
serves (`tekton`, the engineer — the technical hemisphere; `nomos`, the polymath — the human one), with
`core/base` shared by all. Outside, every backend belongs to a **harness** family named after the facet it
renders (`tekton`: the coding agents; `nomos`: whole assistant architectures), and a harness renders only the facets `FACETS` grants it.

Every plane speaks these words. Where each kind lives on disk is configuration
(`settings.layout`), not vocabulary: a rename of a folder is a settings change.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Final


class Entity(StrEnum):
    """What the corpus holds: one member per agentic entity type.

    The first five are instance-shaped — one directory per id, one flat file out.
    `persona` and `config` are singular: one structured source each, rendered by a
    document or config spec rather than a flat one. Everything that versions,
    grades or audits the corpus treats all seven alike; only the transpiler's
    entity sweep skips the two that declare no `flat`.
    """

    SKILL = "skill"
    AGENT = "agent"
    COMMAND = "command"
    WORKFLOW = "workflow"
    TOOL = "tool"
    PERSONA = "persona"
    CONFIG = "config"


class Facet(StrEnum):
    """A side of Demian with its own corpus under core/; `core/base` is what every facet shares."""

    TEKTON = "tekton"
    NOMOS = "nomos"


class Harness(StrEnum):
    """A family of backends with one shape of specs: `specs/<harness>/<backend>/`."""

    TEKTON = "tekton"
    NOMOS = "nomos"


class Backend(StrEnum):
    """Every tool we transpile for; opencode is the house default."""

    OPENCODE = "opencode"
    CLAUDECODE = "claudecode"
    OPENHUMAN = "openhuman"
    HERMES = "hermes"


class Form(StrEnum):
    """The two shapes of every entity: structured source (core/) vs flat runtime target."""

    STRUCTURED = "structured"
    FLAT = "flat"


#: The entities the transpiler sweeps instance by instance; the rest render singly.
#: A tuple, not a set: the sweep order reaches the output, and output is not a place for chance.
INSTANCED: Final[tuple[Entity, ...]] = (Entity.SKILL, Entity.AGENT, Entity.COMMAND, Entity.WORKFLOW, Entity.TOOL)

#: The harness family each backend belongs to.
HARNESS: Final[Mapping[Backend, Harness]] = MappingProxyType(
    {
        Backend.OPENCODE: Harness.TEKTON,
        Backend.CLAUDECODE: Harness.TEKTON,
        Backend.OPENHUMAN: Harness.NOMOS,
        Backend.HERMES: Harness.NOMOS,
    }
)

#: The facets a harness renders beside core/base. A tuple: one more facet is one more member, never a migration.
FACETS: Final[Mapping[Harness, tuple[Facet, ...]]] = MappingProxyType(
    {
        Harness.TEKTON: (Facet.TEKTON,),
        Harness.NOMOS: (Facet.NOMOS,),
    }
)

#: The backends of each harness, in declaration order.
BACKENDS: Final[Mapping[Harness, tuple[Backend, ...]]] = MappingProxyType(
    {harness: tuple(b for b in Backend if HARNESS[b] is harness) for harness in Harness}
)

#: Where each backend's live tree sits when no setting says otherwise: a coder's own user-level dir;
#: for openhuman, the XDG config home its two roots share — `memory/persona/` (the real-files persona
#: dir its workspace links into, never the workspace, whose links an atomic write would replace) and
#: `openhuman/users/<profile>/` (its config); for hermes, its HERMES_HOME. A backend absent from
#: `transpiler.targets` is swept by nothing.
CANONICAL: Final[Mapping[Backend, Path]] = MappingProxyType(
    {
        Backend.OPENCODE: Path.home() / ".config" / "opencode",
        Backend.CLAUDECODE: Path.home() / ".claude",
        Backend.OPENHUMAN: Path.home() / ".config",
        Backend.HERMES: Path.home() / ".hermes",
    }
)

#: The env var that moves each coder off its canonical dir — needed only for a target elsewhere.
#: opencode's layers a dir over the global one; Claude Code's relocates its whole home.
CONFIG_ENV: Final[Mapping[Backend, str]] = MappingProxyType(
    {
        Backend.OPENCODE: "OPENCODE_CONFIG_DIR",
        Backend.CLAUDECODE: "CLAUDE_CONFIG_DIR",
    }
)
