---
name: para-py-iteration
description: "Python: lazy pipelines over iterables, streams, files; async by default (asyncstdlib/aiostream). Use when traversing, filtering or grouping a source. Not bulk sorting, dedup or event-driven flows."
metadata:
  family: form
---

# para-py-iteration

A raw loop fuses traversal, selection and accumulation into one mutable block. Separate them and each stage becomes a named, lazy, testable step. The model is Rust's `Iterator`: adapters chain lazily, `collect` materializes once, at the end. Async is the working mode: reach for the async operator first, the sync builtin only where awaiting buys nothing. The libraries every example draws on, and the ones never to import, live in one place → `references/lib.md`.

## Rules

1. **Lazy by default — a means, not a law.** A function producing many values returns `AsyncIterator`/`Iterator`; materialize only at the boundary that needs it, and say why. Small resident data, a second pass, `len`, or numeric mass invert it — materialize consciously, or vectorize. → `references/streaming.md`
2. **The pipeline is the algorithm.** source → transform → filter → terminal, each a named lazy stage; no intermediate collection between stages.
3. **Terminals over accumulators.** `sum`, `min`, `max`, `any`, `all`, `reduce`, `heapq.nlargest`, `Counter`. A `total = 0` before a loop is an unnamed terminal.
4. **Resolve operators async first; `operator` over lambdas.** Never hand-write a traversal the stdlib already has, never drain an async source to sync to reach `itertools`. The async twin is the default, the sync builtin the alternative when the source is resident and nothing awaits; `itemgetter`/`attrgetter`/`methodcaller` are the keys and mappers, never a lambda. The ladder, every operator and what never to import → `references/lib.md`.
5. **Membership is a set.** `set`/`frozenset` for lookup and dedup, `dict` when order must be stable; never `x in a_list` inside a traversal — that is O(n²).
6. **Async never drains to sync.** A stream stays a stream across `async for` and async generators; paths and files stream async too. Close what you open → `references/protocols.md`.
7. **Traversal is iteration over depth.** Nested and tree structures stream too: `yield from` when depth is bounded and small, an explicit stack/`deque` frontier when it is not — Python has no TCO, so never raise the recursion limit. → `references/recursion.md`

## Sample

```python
import asyncstdlib as asl
from operator import attrgetter

async def top_tags(records: AsyncIterable[Record], limit: int = 10) -> list[tuple[str, int]]:
    """The most frequent tags among records above the score threshold."""
    kept = asl.filter(lambda r: r.score > MIN, records)
    tags = asl.chain.from_iterable(asl.map(attrgetter("tags"), kept))
    counts = Counter([tag async for tag in tags])   # the one materialization, at the terminal
    return counts.most_common(limit)
```

`asl.filter`, `asl.map`, `asl.chain.from_iterable` are the async twins of the sync operators; the shape is unchanged. `Counter` drains only at the end. Every name here is fixed by `references/lib.md`.

## References

- `references/protocols.md` — iteration types, return contracts, cleanup/scoping, generator boundary
- `references/recursion.md` — nested/tree/graph traversal: lazy recursion vs explicit stack/deque frontier
- `references/streaming.md` — lazy composition, where laziness breaks, when to materialize, backpressure
- `references/lib.md` — the stack: libraries (async-first, sync alternative), the operator catalog, paths/files, and what never to import
