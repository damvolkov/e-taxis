"""tests/unit/e_taxis/transpile/engine/reverse: why an edit folds back or is held, and the digest it is told by."""

from e_taxis.transpile.engine.reverse import absorbable_reverse, digest_reverse
from e_taxis.transpile.models.placement import Placement

SPEC = {
    "map": {
        "skill": {
            "rows": [{"from": "description", "to": "#fm.description"}, {"from": "name", "to": "#title", "via": "names"}]
        }
    }
}


async def test_reverse_absorbable_reasons() -> None:
    absorbing = {"absorb": True}
    plain = Placement("t", "fm.description", "d", "skill", 0, ("description",))
    shaped = Placement("t", "title", "x", "skill", 1, ("name",))
    assert absorbable_reverse(SPEC, absorbing, [plain]) == "absorbable into `description`"
    assert absorbable_reverse(SPEC, absorbing, [shaped]).startswith("held: its row transforms")
    assert absorbable_reverse(SPEC, {}, [plain]).startswith("the target does not absorb")


async def test_reverse_digest_is_canonical() -> None:
    assert digest_reverse({"a": 1, "b": 2}) == digest_reverse({"b": 2, "a": 1})
    assert digest_reverse(b"x") != digest_reverse("x")
