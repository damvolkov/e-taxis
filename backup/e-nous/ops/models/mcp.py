"""models.mcp — the house's MCP servers as data: what `core/tekton/config/mcp.yaml` declares, and what a probe of one saw.

One declaration feeds every backend: the render projects it into each coder's syntax, the
evaluator handshakes it. Pure vocabulary — no process, no network.
"""

from __future__ import annotations

from typing import Any

import msgspec

from ops.models.entity import BACKENDS, Backend, Harness


class Smoke(msgspec.Struct, frozen=True):
    """One tool call that proves a server does its job, beyond answering the handshake."""

    tool: str
    arguments: dict[str, Any] = {}


class McpServer(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """A server: a local argv (stdio) or a remote url (streamable HTTP), never both.

    `oauth` marks one that signs its client in: it is reached only where a client can hold that sign-in.
    `pinned` keeps its tools in the model's hand every turn, never behind a search: a server the assistant is built around.
    `consent` is the file holding the secret that approves its sign-in on its own consent page, unattended.
    """

    command: list[str] = []
    url: str = ""
    env: dict[str, str] = {}
    headers: dict[str, str] = {}
    enabled: bool = True
    oauth: bool = False
    pinned: bool = False
    consent: str = ""
    backends: tuple[Backend, ...] = BACKENDS[Harness.TEKTON]
    smoke: Smoke | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if bool(self.command) == bool(self.url):
            raise ValueError("an MCP server is a `command` or a `url`, exactly one")


class McpServers(msgspec.Struct, frozen=True):
    """`core/tekton/config/mcp.yaml`."""

    servers: dict[str, McpServer] = {}

    def of(self, backend: Backend) -> dict[str, McpServer]:
        """The servers one backend registers, in declaration order."""
        return {name: server for name, server in self.servers.items() if backend in server.backends}


class McpHealth(msgspec.Struct, frozen=True):
    """What one handshake saw: the server answered, which tools it offers, whether the smoke call held."""

    name: str
    ok: bool
    tools: tuple[str, ...] = ()
    smoke: str = ""
    error: str = ""

    def __str__(self) -> str:
        detail = self.error or f"{len(self.tools)} tools" + (f" · smoke {self.smoke}" if self.smoke else "")
        return f"{'PASS' if self.ok else 'FAIL'}  {self.name:<20} {detail}"
