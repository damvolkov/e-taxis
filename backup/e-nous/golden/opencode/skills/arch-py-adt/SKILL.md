---
name: arch-py-adt
description: "Python: model data, state and errors as typed values — sum types + exhaustive match, Result over exceptions, newtypes, state machines. Use when defining a domain type, a state or a failure path."
metadata:
  family: design
---

# arch-py-adt

Make illegal states unrepresentable. A branch you can forget is a bug waiting; a case the compiler makes you handle is not. The move is Rust's: push meaning into the type — a value is an `enum` of its possible shapes, a failure is a `Result`, a quantity is a newtype, a lifecycle is a state machine. Then `match` exhaustively and the wrong states have nowhere to live. Data and errors are **values you handle**, never control flow you scatter.

## Rules

1. **A thing that is one-of-several is a sum type.** `type Event = Created | Updated | Deleted`, then `match` — exhaustively, no `case _` that swallows the future. Adding a variant should make the type checker flag every unhandled site. → `references/sum_types.md`
2. **Expected failure is a value, not an exception.** Return `Result[T, E]` (`Ok`/`Err`) and `match` the caller. Exceptions are for the genuinely exceptional, raised at and caught at the boundary — never for control flow the caller is meant to handle. → `references/result.md`
3. **Parse, don't validate.** Turn unstructured input into a precise type once, at the edge; the core receives only values that cannot be malformed. A `str` that is really an email becomes `Email`. → `references/newtype.md`
4. **A primitive with meaning is a newtype.** `UserId`, `Score`, `Meters` — never a bare `str`/`float` that any other `str`/`float` can be confused with. → `references/newtype.md`
5. **A lifecycle is a state machine, not a pile of booleans.** `is_active`/`is_done`/`is_failed` as separate flags admits contradictory states. One `StrEnum` state + an explicit transition table admits only the legal ones. → `references/state_machine.md`
6. **Data is immutable and slotted.** `@dataclass(frozen=True, slots=True)` or a frozen Pydantic model. A command, an event, a value object never mutates — a new state is a new value. Mutate through `replace`/`model_copy`.
7. **Pure core, impure shell.** Domain logic is total functions over values: same input, same output, no I/O. Effects live at the edge. This is what makes rules 1–6 testable without a single mock. → `references/functional_core.md`

## Sample

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Ok[T]: value: T
@dataclass(frozen=True, slots=True)
class Err[E]: error: E
type Result[T, E] = Ok[T] | Err[E]

type Reason = Literal["empty", "too_long"]

def parse_tag(raw: str) -> Result[Tag, Reason]:        # failure is a value
    match raw.strip():
        case "":                       return Err("empty")
        case s if len(s) > MAX:        return Err("too_long")
        case s:                        return Ok(Tag(s))   # Tag is a newtype

match parse_tag(user_input):
    case Ok(tag):          store.add(tag)
    case Err("empty"):     log.warning("EMPTY_TAG")
    case Err("too_long"):  log.warning("TAG_TOO_LONG")
    # no `case _`: a new Reason makes `ty` flag this match as non-exhaustive
```

The illegal states — an empty `Tag`, an unhandled reason — cannot occur. The type carries the proof.

## References

- `references/sum_types.md` — ADT, tagged unions, exhaustive match, recursive (Composite), command-as-data
- `references/result.md` — Result/Either, Option, railway composition, the exception boundary
- `references/newtype.md` — newtypes, parse-don't-validate, typestate, the builder
- `references/state_machine.md` — lifecycle as an FSM: states, transition table, guards (→ para-py-dispatch)
- `references/functional_core.md` — pure core / imperative shell, total functions, combinators (→ para-py-iteration)
- `references/application_map.md` — the 9 software categories → which modeling patterns each leans on
- `references/lib.md` — the stack: returns, python-statemachine, cytoolz, async·sync, and when builtin wins
