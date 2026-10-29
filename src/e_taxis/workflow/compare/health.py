"""compare.health: every incumbent's and every rival's health — radar-tech's measure, plus where the hot path runs.

Each subject is measured as radar-tech measures a candidate (`AssessHealth`, the same KPIs from the same no-auth
sources). On top: `rust`, true when Rust, C or C++ hold a fifth or more of the subject's repository's bytes by
GitHub's own `/languages` count — a compiled extension, the house's preferred hot path; and the repository's stars, a tie-breaker
for the rank and nothing more. A subject without a repository has neither; the basis says why."""

import asyncio
from typing import TYPE_CHECKING, Any, Final

import msgspec

from e_taxis.workflow.models.assess import Candidate
from e_taxis.workflow.models.compare import Healths, Subject, Vital

if TYPE_CHECKING:
    import datetime as dt

    from e_taxis.workflow.assess.health import AssessHealth
    from e_taxis.workflow.models.compare import Rivals
    from e_taxis.workflow.models.ports import ApiPort

##### DEFAULTS #####
REPO: str = "https://api.github.com/repos/{repo}"
LANGUAGES: str = REPO + "/languages"
COMPILED: Final[frozenset[str]] = frozenset({"Rust", "C", "C++"})
### a hot path is compiled when compiled languages hold at least this share of the repository's bytes: a binding's
### repository is mostly Python (its API, tests, stubs) — msgspec 40 % C, orjson 44 % Rust; a pure one holds 0 %.
COMPILED_SHARE: float = 0.2


##### TYPES #####
class CompareHealth:
    """Health per subject over the public APIs; one subject named twice is measured once."""

    __slots__ = ("_api", "_health")

    def __init__(self, api: ApiPort, health: AssessHealth) -> None:
        self._api = api
        self._health = health

    ##### PRIVATE METHODS #####

    @staticmethod
    def _measure_subjects(rivals: Rivals) -> tuple[Subject, ...]:
        subjects = (subject for rivalry in rivals.incumbents for subject in (rivalry.incumbent, *rivalry.rivals))
        return tuple({subject.name: subject for subject in subjects}.values())

    async def _measure_json(self, url: str) -> Any:
        fetched = await self._api.get(url)
        return msgspec.json.decode(fetched.body) if fetched.ok else None

    async def _measure_rust(self, repo: str) -> tuple[bool, tuple[str, ...]]:
        """Whether compiled languages hold most of the repository's bytes, and how that was decided."""
        match await self._measure_json(LANGUAGES.format(repo=repo)) if repo else None:
            case dict() as languages if languages:
                total = sum(int(size) for size in languages.values())
                compiled = sum(int(size) for name, size in languages.items() if name in COMPILED)
                share = compiled / total if total else 0.0
                return share >= COMPILED_SHARE, (f"Rust/C/C++ hold {share:.0%} of {repo}'s bytes (GitHub /languages)",)
            case _:
                return False, (f"no language breakdown for {repo or 'a subject without a repository'}",)

    async def _measure_stars(self, repo: str) -> int | None:
        match await self._measure_json(REPO.format(repo=repo)) if repo else None:
            case {"stargazers_count": int() as stars}:
                return stars
            case _:
                return None

    async def _measure_one(self, subject: Subject, now: dt.datetime) -> Vital:
        candidate = Candidate(
            tech=subject.name, name=subject.name, repo=subject.repo, package=subject.package, registry=subject.registry
        )
        health, (rust, basis), stars = await asyncio.gather(
            self._health.measure(candidate, now), self._measure_rust(subject.repo), self._measure_stars(subject.repo)
        )
        return Vital(name=subject.name, health=health, rust=rust, basis=basis, stars=stars)

    ############################################################

    ##### PUBLIC #####

    async def measure(self, rivals: Rivals, now: dt.datetime) -> Healths:
        """Every subject the rivals' answer names, measured concurrently."""
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(self._measure_one(subject, now)) for subject in self._measure_subjects(rivals)]
        return Healths(measured_at=now.isoformat(), subjects=tuple(task.result() for task in tasks))
