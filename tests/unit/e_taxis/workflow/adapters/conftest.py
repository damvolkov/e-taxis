"""tests/unit/e_taxis/workflow/adapters: a loopback Messages endpoint that answers what it is told and keeps every
request — the bare-completion runner's world, at zero tokens — and a checkout's models config."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any

import msgspec
import pytest

from e_taxis.workflow.models.endpoint import Endpoint

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

MODELS = """providers:
  bailian:
    base_url: https://maas/apps/anthropic/v1
    openai_url: https://maas/compatible-mode/v1
    api_key: "{env:PLAN_KEY}"
  vllm:
    base_url: http://localhost:45100/v1
    api_key: local-dev
tiers:
  scout: {model: bailian/qwen3.8-flash}
  local: {model: vllm/gemma4-26b-a4b}
  ghost: {model: nowhere/x}
"""


class MessagesServer(ThreadingHTTPServer):
    """`answer` is the body every POST gets; `seen` holds (path, headers, decoded body) per request."""

    answer: bytes = b""
    seen: list[tuple[str, dict[str, str], Any]]


class MessagesHandler(BaseHTTPRequestHandler):
    server: MessagesServer

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        self.server.seen.append((self.path, dict(self.headers.items()), msgspec.json.decode(body)))
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(self.server.answer)))
        self.end_headers()
        self.wfile.write(self.server.answer)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — the stdlib's own signature
        return


@pytest.fixture
def messages() -> Iterator[MessagesServer]:
    server = MessagesServer(("127.0.0.1", 0), MessagesHandler)
    server.seen = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


class PagesServer(ThreadingHTTPServer):
    """`pages` maps a path to the body GET answers (any other path: 404); `posted` keeps each POST's raw body."""

    pages: dict[str, bytes]
    posted: list[tuple[str, bytes]]


class PagesHandler(BaseHTTPRequestHandler):
    server: PagesServer

    def do_GET(self) -> None:
        match self.server.pages.get(self.path):
            case None:
                self.send_response(404)
                self.end_headers()
            case body:
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        self.server.posted.append((self.headers.get("content-type", ""), body))
        self.send_response(204 if self.path == "/hook" else 400)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — the stdlib's own signature
        return


@pytest.fixture
def pages() -> Iterator[PagesServer]:
    server = PagesServer(("127.0.0.1", 0), PagesHandler)
    server.pages, server.posted = {}, []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def endpoint(messages: MessagesServer) -> Endpoint:
    """The loopback server as a tier's endpoint (a trailing slash on the base, as configs carry one)."""
    return Endpoint(base_url=f"http://127.0.0.1:{messages.server_address[1]}/v1/", key="sk-k", model="qwen")


@pytest.fixture
def models(tmp_path: Path) -> Path:
    """A checkout holding only the models config: a secret key, a literal one, an alias declared nowhere."""
    (tmp_path / "core/tekton/config").mkdir(parents=True)
    (tmp_path / "core/tekton/config/models.yaml").write_text(MODELS)
    return tmp_path
