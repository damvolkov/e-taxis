"""models.graph: a workflow as the executor runs it — one typed step per node, loops already unrolled.

A loop is never a cycle: `LoopDecl` is unrolled into `max` copies of its steps (`<id>_<k>`), each copy waiting on the
previous one's exits; a copy names the `until` checks that end it (`closers`) and goes idle once one of them closed
the loop. Nothing here executes or reads a file."""

from collections.abc import Collection, Iterator

from msgspec import Struct


##### TYPES #####
class LoopDecl(Struct, frozen=True, forbid_unknown_fields=True):
    """A bounded loop over a run of a workflow's steps, ended by its `until` step."""

    nodes: tuple[str, ...]
    max: int
    until: str

    def problems(self, ids: Collection[str]) -> tuple[str, ...]:
        """Why this loop cannot be unrolled over steps `ids`; empty when it can."""
        return (
            *(f"loop: unknown step {node}" for node in self.nodes if node not in ids),
            *((f"loop: until {self.until} is not one of its steps",) if self.until not in self.nodes else ()),
            *(("loop: max must be at least 1",) if self.max < 1 else ()),
        )


class StepSpec(Struct, frozen=True, kw_only=True):
    """One step placed in the graph: what runs it (`run` a command, else an agent session), when, after what.

    `when` maps a parameter to the values that make the step due; `iteration`, `until`, `previous` and `closers`
    exist only on the copies of a loop."""

    id: str
    depends: tuple[str, ...] = ()
    run: str = ""
    actor: str = ""
    instruction: str = ""
    when: dict[str, tuple[str, ...]] = {}
    readonly: bool = False
    steps: int = 0
    timeout: int = 0
    iteration: int = 0
    until: bool = False
    previous: str = ""
    closers: tuple[str, ...] = ()

    @property
    def semantic(self) -> bool:
        """Whether an agent reasons here (tokens) rather than a command running (none)."""
        return not self.run


class GraphSpec(Struct, frozen=True, kw_only=True):
    """A whole graph in declaration order — the order the report reads it back in."""

    summary: str
    steps: tuple[StepSpec, ...]

    def __getitem__(self, key: str) -> StepSpec:
        return next(step for step in self.steps if step.id == key)

    def __iter__(self) -> Iterator[StepSpec]:
        return iter(self.steps)
