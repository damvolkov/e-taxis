"""tests/unit/e_taxis/runtime/locator: the ladder — the flag, TAXIS_NOUS, the nearest ancestor, the sibling `../e-nous`."""

from pathlib import Path

import pytest

from e_taxis.harness.models.error import NousLocatorError
from e_taxis.harness.runtime.locator import NousLocator


async def test_locator_explicit_relative_is_made_absolute(checkout: Path, workspace: Path) -> None:
    assert await NousLocator(env=None, cwd=workspace).locate(Path("e-nous")) == checkout


async def test_locator_explicit_wins_over_every_rung(checkout: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    (other / "core").mkdir(parents=True)
    (other / "specs").mkdir()
    (other / "core" / "schema.yaml").write_text("{}\n")
    (other / "specs" / "base.yaml").write_text("{}\n")
    assert await NousLocator(env=checkout, cwd=checkout).locate(other) == other


async def test_locator_explicit_invalid_never_falls_through(checkout: Path, tmp_path: Path) -> None:
    with pytest.raises(NousLocatorError, match="not an e-nous checkout") as error:
        await NousLocator(env=checkout, cwd=checkout).locate(tmp_path)
    assert error.value.exit_code == 31


async def test_locator_env_relative_to_the_cwd(checkout: Path, workspace: Path, tmp_path: Path) -> None:
    assert await NousLocator(env=Path("ws/e-nous"), cwd=tmp_path).locate(None) == checkout


async def test_locator_ancestor_from_a_nested_dir(checkout: Path) -> None:
    assert await NousLocator(env=None, cwd=checkout / "core" / "tekton").locate(None) == checkout


async def test_locator_env_invalid_falls_to_the_ancestor(checkout: Path, tmp_path: Path) -> None:
    assert await NousLocator(env=tmp_path, cwd=checkout / "specs").locate(None) == checkout


async def test_locator_sibling_from_another_repo_s_subdir(checkout: Path, sibling: Path) -> None:
    assert await NousLocator(env=None, cwd=sibling).locate(None) == checkout


async def test_locator_sibling_of_a_plain_dir(checkout: Path, workspace: Path) -> None:
    (plain := workspace / "plain").mkdir()
    assert await NousLocator(env=None, cwd=plain).locate(None) == checkout


async def test_locator_none_names_every_rung(tmp_path: Path) -> None:
    with pytest.raises(NousLocatorError) as error:
        await NousLocator(env=tmp_path / "gone", cwd=tmp_path).locate(None)
    assert all(rung in error.value.message for rung in ("--nous", "TAXIS_NOUS", "ancestor", "sibling"))
    assert str(tmp_path.parent / "e-nous") in error.value.message
