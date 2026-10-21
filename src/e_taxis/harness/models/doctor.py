"""models.doctor: catalog integrity — one problem per broken rule, named for the rule and the entry it broke on."""

from enum import StrEnum

from msgspec import Struct


##### ENUMS #####
class DoctorRule(StrEnum):
    PARSE = "parse"
    DUPLICATE = "duplicate"
    REQUIRES = "requires"
    CYCLE = "cycle"
    PRIMITIVE = "primitive"
    OWNS = "owns"


##### TYPES #####
class DoctorProblem(Struct, frozen=True, kw_only=True):
    rule: DoctorRule
    id: str
    detail: str


class DoctorReport(Struct, frozen=True, kw_only=True):
    """How many entries parsed, and every problem found across them."""

    checked: int
    problems: tuple[DoctorProblem, ...] = ()
