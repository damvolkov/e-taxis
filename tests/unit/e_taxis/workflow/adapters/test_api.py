"""tests/unit/e_taxis/workflow/adapters/api: one GET over wreq — the body and the Link header kept, a dead endpoint a
value (status 0), the GitHub token sent to api.github.com only."""

import socket

import pytest

from e_taxis.workflow.adapters.api import WreqApi


async def test_api_get_keeps_body_and_link(messages) -> None:
    messages.answer = b'{"total_count": 3}'
    url = f"http://127.0.0.1:{messages.server_address[1]}/search?q=1"
    got = await WreqApi(5.0, "secret").get(url)
    assert (got.status, got.body, got.link, got.ok) == (
        200,
        b'{"total_count": 3}',
        '<http://x/?page=3>; rel="last"',
        True,
    )
    path, headers, _ = messages.seen[0]
    assert (
        path,
        {k.lower(): v for k, v in headers.items()}.get("user-agent"),
        "authorization" in map(str.lower, headers),
    ) == ("/search?q=1", "e-taxis (soa-assess)", False)


async def test_api_get_a_dead_endpoint_is_status_zero() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    got = await WreqApi(2.0).get(f"http://127.0.0.1:{port}/")
    assert (got.status, got.ok, got.error.startswith("ConnectionError")) == (0, False, True)


@pytest.mark.parametrize(
    ("token", "url", "signed"),
    [
        ("t", "https://api.github.com/repos/o/r", "Bearer t"),
        ("t", "https://pypi.org/pypi/x/json", None),
        ("", "https://api.github.com/repos/o/r", None),
    ],
    ids=["github", "elsewhere", "no-token"],
)
async def test_api_headers_sign_github_only(token: str, url: str, signed: str | None) -> None:
    assert WreqApi(1.0, token)._get_headers(url).get("Authorization") == signed
