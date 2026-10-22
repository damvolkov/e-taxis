# Iteration types

## The protocols

| Type | Contract | Consumed by |
|---|---|---|
| `Iterable[T]` | `__iter__` → `Iterator[T]` | `for`, `iter()` |
| `Iterator[T]` | `Iterable` + `__next__` → `T`, raises `StopIteration` | `next()`, one pass |
| `Generator[Y,S,R]` | `Iterator` built by `yield` (S sent in, R returned) | `for`, `send`/`throw`, `close` |
| `Awaitable[T]` | `__await__` | `await` |
| `Coroutine[Y,S,R]` | awaitable generator; `await` suspends the loop | `await`, `create_task` |
| `AsyncIterable[T]` | `__aiter__` → `AsyncIterator[T]` | `async for`, `aiter()` |
| `AsyncIterator[T]` | `AsyncIterable` + `__anext__` → `Awaitable[T]`, raises `StopAsyncIteration` | `anext()`, one pass |
| `AsyncGenerator[Y,S]` | `async def` with `yield` | `async for`, must be closed |

The only structural difference: `__next__` is synchronous by contract (a step, not a task) while `__anext__` returns an **awaitable**. An async iterator's items may arrive over the loop; a sync iterator's must not block it.

## Return-type contract

- produce many, computed lazily → `AsyncIterator`/`Iterator` (a generator)
- one eventual value → `Coroutine`/`Awaitable[T]`
- re-loopable → return `Iterable` (re-callable `__iter__`); an `Iterator`/`AsyncIterator` is **single-use** — if a caller loops twice, return an Iterable or document re-creating the source
- need `len`/index/slice → convert to a Sequence at that point, not earlier
- membership / dedup → `Set`; stable-order dedup → `dict`

## Cleanup & scoping

An async generator holding a resource must be closed, not merely dropped: `aclose()`, or `async with contextlib.aclosing(gen)`. Wrap the *terminal*, not the generator, so exceptions surface where you expect them. The async twin manages iterator lifetime for you — its eager-aclose behaviour and the escape hatches (`borrow`, `scoped_iter`) are handled by the async twin.

## Boundary (lives in other skills)

- **Generator mechanics** — `yield from`, two-way `send`, `@contextlib.contextmanager` / `asynccontextmanager` — are language plumbing, not a paradigm; context-manager authoring → `lang-py-lifecycle`.
- **Async context managers** as a topic — `__aenter__`/`__aexit__`, `AsyncExitStack` composition — → `lang-py-lifecycle`. This skill uses them only at a stream's edge (the row above).
