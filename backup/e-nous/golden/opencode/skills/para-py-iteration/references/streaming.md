# Laziness & backpressure

## Composition

A stage takes an iterable and returns an iterator, so the pipeline builds nothing in between:

```python
def parse(lines): return (Record.from_line(l) for l in lines if l.strip())
def enrich(rs):   return (replace(r, score=score(r)) for r in rs)

total = sum(r.score for r in enrich(parse(source)))
```

Async, the same shape holds — `async for`, async generators, and each operator's async twin.

## Where laziness breaks

| Situation | Consequence |
|---|---|
| Consume twice | iterator is single-pass — materialize deliberately or recreate the source |
| `len` / index / `reversed` | need a Sequence; convert at that point |
| sort / `Counter` / set | terminals that must see everything — the natural pipeline end |
| Exceptions | raised at consumption, not definition — wrap the terminal |
| Open resources | a generator holding a file must be fully consumed or closed (`aclosing`) |

## When materializing is right

Laziness buys memory, short-circuit and streaming — not CPU. Three cases invert it:

- **Small, resident data.** A list comprehension has less per-item overhead than a generator; on a handful of values it is faster. Lazy pays off at scale, on short-circuit, or on a live stream — not on a short in-memory list.
- **Second pass or `len`.** Needing either means materializing once, on purpose, into a Sequence — not re-deriving the source twice by accident.
- **Numeric mass.** Neither generators nor lists: vectorize. Polars/Arrow/NumPy beat any element-at-a-time Python pipeline by orders of magnitude — leave the iterator paradigm behind.

A materializing comprehension over a collection that fits in memory is clearer and equally declarative. Laziness is a means, not a goal.

## Eager → lazy

The rewrites, applied:

| Eager | Lazy |
|---|---|
| `open(p).readlines()` then slice | `islice(f, n)` over the open file — stops early, closes deterministically |
| `range(len(xs))` | `enumerate(xs)`, or `zip(xs, ys)` for parallel walks |
| `sum([x * x for x in xs])` | `sum(x * x for x in xs)` — drop the brackets, no intermediate list |
| `s += chunk` in a loop | `"".join(gen)` — one allocation, not n |
| `x in a_list` inside a loop | build one `set` before the loop |
| function returns a `list` | it `yield`s |

A generator over `range(10**6)` is ~200 bytes; the equivalent list is ~8 MB. The saving is memory and early exit, realized only while the chain stays lazy end to end.

## Backpressure

A pull chain — a generator, or a single-task stream — is consumer-paced: the producer advances only when asked, so memory stays flat, but every stage shares one task and there is no concurrency. Real inter-stage concurrency needs a **bounded channel between tasks**: the producer blocks when the buffer is full, the consumer drains it. That is the CSP model, and its cost is one task per stage. → `conc-py-async`
