"""tests/unit/e_taxis/models/stack: e-nous's registry is foreign — read what e-taxis needs, ignore the rest."""

import msgspec

from e_taxis.harness.models.stack import Stack


def test_stack_ignores_foreign_fields_and_defaults_the_rest() -> None:
    stack = msgspec.convert({"parts": {"x": {"kind": "tool", "what": "w", "link": "l"}}}, Stack)
    assert (stack.parts["x"].pin, stack.parts["x"].used) == ("", ())
