"""tests/unit/e_taxis/ops: `taxis logo` — the wordmark command: lands, idempotes, refuses, forces."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def test_logo_lands_one_svg_per_name(taxis: Callable[..., tuple[int, str, str]], tmp_path: Path) -> None:
    code, _, _ = taxis("logo", "taxis", "arkhetypo", "--out", str(tmp_path))
    assert code == 0
    assert sorted(path.name for path in tmp_path.glob("*.svg")) == ["e-arkhetypo.svg", "e-taxis.svg"]
    svg = tmp_path.joinpath("e-taxis.svg").read_text()
    assert svg.startswith('<svg width="2263" height="692" viewBox="0 0 2263 692"')
    assert 'aria-label="e-taxis"' in svg


def test_logo_squares_on_demand(taxis: Callable[..., tuple[int, str, str]], tmp_path: Path) -> None:
    assert taxis("logo", "taxis", "--out", str(tmp_path), "--square")[0] == 0
    assert tmp_path.joinpath("e-taxis.svg").read_text().startswith('<svg width="1024" height="1024"')


def test_logo_is_idempotent(taxis: Callable[..., tuple[int, str, str]], tmp_path: Path) -> None:
    taxis("logo", "taxis", "--out", str(tmp_path))
    first = tmp_path.joinpath("e-taxis.svg").read_bytes()
    assert taxis("logo", "taxis", "--out", str(tmp_path))[0] == 0
    assert tmp_path.joinpath("e-taxis.svg").read_bytes() == first


def test_logo_leaves_an_already_prefixed_name_single(
    taxis: Callable[..., tuple[int, str, str]], tmp_path: Path
) -> None:
    assert taxis("logo", "e-taxis", "--out", str(tmp_path))[0] == 0
    assert tmp_path.joinpath("e-taxis.svg").exists()
    assert not list(tmp_path.glob("e-e-*"))


def test_logo_colors_and_bare_prefix_reach_the_svg(taxis: Callable[..., tuple[int, str, str]], tmp_path: Path) -> None:
    code, _, _ = taxis("logo", "eager", "--out", str(tmp_path), "--prefix", "", "--background", "#ffffff")
    assert code == 0
    svg = tmp_path.joinpath("eager.svg").read_text()
    assert 'aria-label="eager"' in svg
    assert "#ffffff" in svg
    assert "#166b7e" in svg


def test_logo_refuses_to_change_an_existing_asset_without_force(
    taxis: Callable[..., tuple[int, str, str]], tmp_path: Path
) -> None:
    target = tmp_path / "e-taxis.svg"
    target.write_text("hand-drawn brand")
    code, _, err = taxis("logo", "taxis", "--out", str(tmp_path))
    assert code == 15
    assert "--force" in err
    assert target.read_text() == "hand-drawn brand"


def test_logo_replaces_under_force(taxis: Callable[..., tuple[int, str, str]], tmp_path: Path) -> None:
    target = tmp_path / "e-taxis.svg"
    target.write_text("hand-drawn brand")
    assert taxis("logo", "taxis", "--out", str(tmp_path), "--force")[0] == 0
    assert 'aria-label="e-taxis"' in target.read_text()


def test_logo_refuses_a_name_outside_the_font(taxis: Callable[..., tuple[int, str, str]], tmp_path: Path) -> None:
    code, _, err = taxis("logo", "tax!s", "--out", str(tmp_path))
    assert code == 15
    assert "letters outside" in err


def test_logo_refuses_a_color_that_is_not_hex(taxis: Callable[..., tuple[int, str, str]], tmp_path: Path) -> None:
    code, _, err = taxis("logo", "taxis", "--background", "navy", "--out", str(tmp_path))
    assert code == 15
    assert "hex" in err


def test_logo_names_nothing_fails_in_parsing(taxis: Callable[..., tuple[int, str, str]], tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exit_:
        taxis("logo", "--out", str(tmp_path))
    assert exit_.value.code != 0
