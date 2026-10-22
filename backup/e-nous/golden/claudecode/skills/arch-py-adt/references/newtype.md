# Newtype, parse-don't-validate, typestate

A bare `str` that is really a user id, and another bare `str` that is really an email, are the same type to the checker — so it will happily let you pass one where the other is meant. A newtype closes that hole: wrap the primitive in a distinct type so the domain's distinctions become the compiler's distinctions. Rust anchor: `struct Meters(f64)` — a new type, zero runtime cost, incompatible with a raw `f64`.

## Three strengths of newtype

| Strength | Tool | Runtime cost | Use when |
|---|---|---|---|
| Nominal tag only | `NewType("UserId", str)` | zero | distinguish ids/keys that share a primitive; no validation needed |
| Tag + validation | `Annotated[str, AfterValidator(...)]` (Pydantic) | validation once | the value has a rule (email shape, range, non-empty) |
| Tag + behaviour | `@dataclass(frozen=True, slots=True)` one field | one object | the value has methods/invariants of its own |

```python
from typing import NewType
UserId = NewType("UserId", str)            # ty rejects a raw str where UserId is expected

type Email = Annotated[str, AfterValidator(_ensure_email)]   # validated alias

@dataclass(frozen=True, slots=True)
class Score:                                # value object with an invariant
    value: float
    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0: raise ValueError("score out of range")
```

Reach for the weakest one that closes the hole. `NewType` is free — use it liberally for ids and keys.

## Parse, don't validate

Do not check a value's validity and then keep passing the loose type around, re-checking at every use. **Parse it once** into a type that *cannot* be invalid, at the boundary; the core then receives only well-formed values and never re-checks.

```python
# validate (weak): the str stays a str; every consumer must re-trust it
def handle(raw: str) -> None:
    if not is_email(raw): raise ...
    send(raw)                       # send() still takes a plain str — hole reopened

# parse (strong): the boundary produces Email; the type carries the guarantee
def handle(raw: str) -> None:
    email = Email(raw)              # validated here, once
    send(email)                     # send(email: Email) — cannot receive an unvalidated str
```

The signature `send(email: Email)` *is* the guarantee. This is rule 3 of the skill, and it is the same instinct as an adapter's anti-corruption boundary: convert loose outside data into precise domain values at the edge → `arch-py-hexagonal`.

## Typestate — states the type forbids

Push not just validity but **lifecycle stage** into the type, so an operation illegal in the current state does not compile. Rust uses this for builders and protocols; in Python it is separate types per stage (or a phantom generic), each exposing only the operations legal there.

```python
@dataclass(frozen=True, slots=True)
class Draft:  body: str
@dataclass(frozen=True, slots=True)
class Sent:   body: str; at: float

def send(msg: Draft) -> Sent:                 # send only accepts a Draft
    return Sent(body=msg.body, at=time.time())
# send(a_Sent)  → type error: you cannot send what is already sent
```

There is no `is_sent` flag to check and forget; `Sent` simply has no `send`. Use typestate for the few lifecycles where a misordered call is costly (open/closed connections, draft/sent, unlocked/locked). It is advanced — most lifecycles are better as an explicit state machine.

## Builder — staged construction

When an object needs many parameters assembled in steps, the builder is a typestate chain: each step returns a type that exposes the next legal step, and only the terminal `build()` yields the finished value. In Python, most "builders" are just Pydantic models with defaults or keyword args — reach for a real staged builder only when construction has **ordering constraints** (a query that must set an index before a filter). Concrete builder libraries: → `lib.md`.

## When NOT to

- A local, obvious primitive with no confusion risk (a loop counter, a one-line `str`): a newtype is noise.
- Do not newtype to document — that is what the parameter *name* is for. Newtype when the checker must *enforce* the distinction, not merely when a reader would like a hint. → `tax-py-naming`
