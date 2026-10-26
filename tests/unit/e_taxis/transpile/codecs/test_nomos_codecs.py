"""tests/unit/e_taxis/transpile/codecs/nomos: TOML, YAML and dotenv — encoded in row order, read back by key."""

from e_taxis.transpile.codecs.env import encode_env, key_env, read_env
from e_taxis.transpile.codecs.structured import encode_toml, encode_yaml, read_toml, read_yaml
from e_taxis.transpile.models.placement import Placement


def _at(fragment: str, value: object) -> Placement:
    return Placement("t", fragment, value, "config", 0)


async def test_nomos_codecs_toml_and_yaml_round_trip() -> None:
    placements = [_at("default_model", "a:b"), _at("agent.max", 3), _at("agent.on", True)]
    assert read_toml(encode_toml("t", {}, placements)) == {"default_model": "a:b", "agent": {"max": 3, "on": True}}
    assert read_yaml(encode_yaml("t", {}, placements)) == {"default_model": "a:b", "agent": {"max": 3, "on": True}}
    assert read_toml(b"") == {}
    assert read_yaml(b"") == {}
    assert read_yaml(b"- a\n") == {}


async def test_nomos_codecs_env() -> None:
    assert encode_env("t", {}, [_at("A", "1"), _at("B", "x,y")]) == b"A=1\nB=x,y\n"
    assert read_env(b"# note\nexport A='1'\n\nB=\"2\"\nnoequals\n") == {"A": "1", "B": "2"}
    assert (key_env("  # c"), key_env(""), key_env("X=1")) == ("", "", "X")
