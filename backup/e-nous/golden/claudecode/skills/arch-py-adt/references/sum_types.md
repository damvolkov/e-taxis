# Sum types — ADTs and exhaustive match

A sum type says "this value is exactly one of these shapes." It is Rust's `enum` with data: the whole point is that the set of possibilities is *closed and named*, so a `match` can be checked for completeness and a forgotten case is a type error, not a runtime surprise.

## Product vs sum

- **Product type** — a value that is A *and* B *and* C: a `dataclass`/Pydantic model. Fields held together.
- **Sum type** — a value that is A *or* B *or* C: a `Union` of variants. This file is about the *or*.

Real domains are sums of products: `Event = Created(...) | Updated(...) | Deleted(...)` — each variant a product, the whole a sum.

## Declaring one

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Created: entity_id: str; at: float
@dataclass(frozen=True, slots=True)
class Updated: entity_id: str; fields: frozenset[str]
@dataclass(frozen=True, slots=True)
class Deleted: entity_id: str

type Event = Created | Updated | Deleted        # the sum — closed set of shapes
```

- Each variant is a distinct **type**, not an enum member with an untyped payload — that is what lets `match` bind the payload with full typing.
- `type Event = ...` (PEP 695) names the union once; every signature uses `Event`.
- For variants with **no payload**, a `StrEnum` is the right sum (`type Colour = Literal[...]` or `class Colour(StrEnum)`). Payload-carrying variants need classes.

## Exhaustive match is the payoff

```python
def project(event: Event) -> State:
    match event:
        case Created(entity_id=eid, at=t):   return State.new(eid, t)
        case Updated(entity_id=eid):         return State.touch(eid)
        case Deleted(entity_id=eid):         return State.gone(eid)
        # NO `case _`
```

Omit the wildcard. Then when a fourth variant `Merged` joins `Event`, `ty` flags every `match` that does not handle it — the type system hands you the to-do list. A `case _: pass` throws that away and reintroduces the forgotten-branch bug the whole pattern exists to kill. → `para-py-dispatch` for the full match-vs-mapping decision.

Guards live in the pattern, not the body: `case Updated(fields=f) if "score" in f:`.

## Recursive sum type = Composite

A tree of uniform nodes is a sum type that refers to itself. This is the Composite pattern with no class hierarchy — Rust's recursive `enum`.

```python
@dataclass(frozen=True, slots=True)
class Leaf: value: int
@dataclass(frozen=True, slots=True)
class Branch: children: tuple["Node", ...]

type Node = Leaf | Branch

def total(node: Node) -> int:
    match node:
        case Leaf(value=v):       return v
        case Branch(children=cs): return sum(total(c) for c in cs)   # structural recursion
```

ASTs, document trees, agent trees, nested config — all are this. Traversal is a `match` per level; unbounded depth uses an explicit frontier, not recursion (Python has no TCO) → `para-py-iteration`.

## Command as data

A command — an intent to do something — is a value, not a method call. Model it as a sum type of frozen dataclasses; a single dispatcher interprets it. This is what makes queues, undo, event sourcing and replay possible: the intent is serializable and inspectable.

```python
@dataclass(frozen=True, slots=True)
class Enqueue: payload: bytes; priority: int
@dataclass(frozen=True, slots=True)
class Cancel: task_id: str

type Command = Enqueue | Cancel
```

The executor `match`es the command to an effect. The command carries no behaviour — behaviour lives in the interpreter, so the same command runs in-process, over a wire, or from a log. Selecting the handler is dispatch → `para-py-dispatch`.

## When NOT to

- Two mutually exclusive shapes used in one place → a plain `A | B` inline is enough; do not manufacture named variants for a local choice.
- An **open** set (plugins, user-registered kinds) is not a sum type — you cannot enumerate it. Use a registry + dispatch instead → `para-py-dispatch`. Sum types are for *closed* sets you own.
