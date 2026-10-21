"""tests/unit/e_taxis/services/doctor: catalog integrity — every rule caught on the broken fixture, none on the sound one."""

from typing import TYPE_CHECKING

from e_taxis.adapters.catalog import FileCatalog
from e_taxis.harness.models.doctor import DoctorRule
from e_taxis.harness.services.doctor import DoctorService

if TYPE_CHECKING:
    from pathlib import Path


async def test_doctor_run_sound_catalog_has_no_problem(catalog_root: Path) -> None:
    report = await DoctorService(FileCatalog(catalog_root)).run()
    assert (report.checked, report.problems) == (5, ())


async def test_doctor_run_names_every_broken_rule(doctor: DoctorService) -> None:
    report = await doctor.run()
    assert report.checked == 3
    assert {(problem.rule, problem.id) for problem in report.problems} == {
        (DoctorRule.PARSE, "broken.yaml"),
        (DoctorRule.PARSE, "stray.yaml"),
        (DoctorRule.DUPLICATE, "two"),
        (DoctorRule.REQUIRES, "one"),
        (DoctorRule.CYCLE, "one"),
        (DoctorRule.PRIMITIVE, "one"),
        (DoctorRule.OWNS, "mcpServers.shared"),
    }


async def test_doctor_run_details_the_primitive_and_the_clash(doctor: DoctorService) -> None:
    details = {problem.rule: problem.detail for problem in (await doctor.run()).problems}
    assert details[DoctorRule.PRIMITIVE] == "claude-mcp under `any` cannot serve opencode"
    assert details[DoctorRule.OWNS] == "owned by one, two"
    assert details[DoctorRule.REQUIRES] == "requires missing, which no entry provides"
