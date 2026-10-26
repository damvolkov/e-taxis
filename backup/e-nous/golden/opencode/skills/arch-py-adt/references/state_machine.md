# State machine — lifecycle as data

A lifecycle modelled as scattered booleans admits contradictory states: `is_active=True, is_done=True` should be impossible, yet the type allows it. A state machine makes the impossible unrepresentable — one state value, and an explicit table of which transitions are legal. Rust anchor: an `enum` for the state, `match` on `(state, event)` for the transition; illegal pairs simply have no arm.

## One state, never a flag pile

```python
from enum import StrEnum, auto

class TaskState(StrEnum):
    PENDING  = auto()
    RUNNING  = auto()
    DONE     = auto()
    FAILED   = auto()
```

One `TaskState` field replaces `is_pending`/`is_running`/`is_done`/`is_failed`. Four booleans admit 16 combinations, 12 of them nonsense; one enum admits exactly four. This is the whole idea — collapse the state space to only the legal points.

## The transition table is data

Do not encode transitions as `if state == ... and event == ...`. Encode them as a frozen mapping from `(state, event)` to the next state; an absent key *is* an illegal transition. This is dispatch, not branching → `para-py-dispatch`.

```python
from types import MappingProxyType
from typing import Final

class Event(StrEnum):
    START = auto(); FINISH = auto(); FAIL = auto(); RETRY = auto()

_TRANSITIONS: Final = MappingProxyType({
    (TaskState.PENDING, Event.START):  TaskState.RUNNING,
    (TaskState.RUNNING, Event.FINISH): TaskState.DONE,
    (TaskState.RUNNING, Event.FAIL):   TaskState.FAILED,
    (TaskState.FAILED,  Event.RETRY):  TaskState.PENDING,
})

def transition(state: TaskState, event: Event) -> Result[TaskState, Literal["illegal"]]:
    match _TRANSITIONS.get((state, event)):
        case None:       return Err("illegal")     # not in the table = not allowed
        case next_state: return Ok(next_state)
```

- The table is the specification — readable, testable, and complete on its face. A new transition is a new row (OCP), never an edited conditional.
- An illegal transition is a **value** (`Err("illegal")`), not a raised exception, so the caller decides — the Result pattern.
- The table is `Final` + `MappingProxyType`: immutable intent, enforced at runtime.

## Guards and effects

A transition may be conditional (a guard) or may cause an effect (a side action on entry). Keep the *decision* pure (state + event + guard → next state, in the table or a `match` with `if` guards) and the *effect* at the shell — the pure core computes the next state, the impure edge performs the I/O it implies — the functional-core split.

## When a library earns it

Hand-rolled table + enum is right for a **flat** machine with a handful of states. Reach for a library when you need **statecharts**: compound/nested states, parallel regions, history, entry/exit hooks, auto async/sync engines, or diagram generation. Concrete choices (async-first) → `lib.md`.

## Where this shows up

- **Async worker** — the job lifecycle (`PENDING→RUNNING→DONE/FAILED`, retry loop). The canonical case.
- **Agent system** — the double-loop: the agent's turn state, tool-call state.
- **Voice runtime** — VAD / turn-taking: silence → speech → endpoint → response.
- **API service** — a session or a long-running resource's status.

## When NOT to

- A value that only ever moves one way with no branches (a monotonic counter, a "seen" flag with no transitions worth naming): an enum is enough, a machine is overkill.
- Truly two states with one transition (`open`/`closed`) and a costly misordering: prefer typestate — let the type, not a table, forbid the illegal call.
