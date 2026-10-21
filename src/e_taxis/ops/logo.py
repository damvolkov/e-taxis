"""ops/logo: `taxis logo` — family wordmarks into `assets/`, one deterministic svg per name.

Names pass through `LogoGenerator` untouched: `taxis` and `e-taxis` both spell `e-taxis.svg`; prefix
and colors vary per run. An existing asset whose bytes would change is refused without `--force` —
the hand-drawn brands are never silently overwritten."""

from pathlib import Path

from rich.console import Console

from e_taxis.harness.models.error import LogoWriteError
from e_taxis.ops.image import LogoError, LogoGenerator

##### COMMAND #####


async def logo(
    names: tuple[str, ...],
    *,
    out: Path = Path("assets"),
    prefix: str = "e",
    background: str | None = None,
    foreground: str | None = None,
    square: bool = False,
    force: bool = False,
) -> None:
    """Render every name to `<wordmark>.svg` under out, printing each path as it lands.

    Args:
        names: project words to render: taxis, e-taxis, templates…
        out: target directory.
        prefix: house prefix before the hyphen; empty for the bare brand.
        background: canvas hex color (default: the reference).
        foreground: letter hex color (default: the reference).
        square: the reference 1024 canvas instead of the hugging landscape banner.
        force: replace an existing asset whose bytes would change.
    """
    colors = {field: value for field, value in (("background", background), ("foreground", foreground)) if value}
    generator = _logo_generator(prefix, colors, square=square)
    console = Console()
    for name in names:
        svg = _logo_svg(generator, name)
        target = out / generator.filename(name)
        match target:
            case existing if not force and existing.exists() and existing.read_text("utf-8") != svg:
                msg = f"{existing}: exists with different bytes — pass --force to replace it"
                raise LogoWriteError(msg)
            case fresh:
                console.print(generator.save(name, fresh))


##### PRIVATE #####


def _logo_generator(prefix: str, colors: dict[str, str], *, square: bool) -> LogoGenerator:
    """The generator, its refusals translated into the cli's error tree."""
    try:
        return LogoGenerator(prefix=prefix, landscape=not square, **colors)
    except LogoError as refused:
        raise LogoWriteError(str(refused)) from refused


def _logo_svg(generator: LogoGenerator, name: str) -> str:
    """The wordmark bytes, the font's refusals translated the same way."""
    try:
        return generator.generate(name)
    except LogoError as refused:
        raise LogoWriteError(str(refused)) from refused
