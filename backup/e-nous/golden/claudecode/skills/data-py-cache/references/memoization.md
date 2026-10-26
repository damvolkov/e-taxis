# memoization — extracting the thing worth caching

Most "we need a cache" is really "this function does three things and one of them is pure". Find that one, give it a name, and the cache becomes trivial. Skip the extraction and you end up caching a coroutine, a file read and a timestamp together, with one TTL for three different lifetimes.

## The extraction

A function is memoizable when it is **deterministic** (same arguments → same result, always), **hashable** in its arguments, and **free of effects** — no clock, no randomness, no I/O, no mutation the caller can observe. Almost nothing is born that way; you carve it out.

```python
# before — one function, three lifetimes tangled
async def rank(user_id: str, query: str) -> list[Hit]:
    profile = await db.fetch_profile(user_id)      # I/O, changes on write
    vectors = load_model_vectors()                  # I/O, changes on deploy
    return _softmax(profile.weights, vectors, query)  # pure maths, never changes

# after — each lifetime gets its own plane and its own clock
async def rank(user_id: str, query: str) -> list[Hit]:
    profile = await profiles.get(user_id)           # shared store, TTL 60s, purge on write
    vectors = model_vectors()                        # process-wide, @cache, dies on restart
    return _score(profile.weights, vectors, query)   # bounded memo, keyed on the tuple
```

The rule that falls out: **hoist the impure part up, push the pure part down, cache the bottom.** → `arch-py-adt` (functional core, imperative shell).

## Recursion

A recursion that re-solves subproblems is memoizable *as the recurrence*, not as the top call. Cache the node, not the tree: `f(n)` keyed on `n` gives you every subtree for free; caching only `f(root)` gives you one entry and no reuse.

Three conditions before you reach for it:

- **Overlapping subproblems.** No overlap, no memo — you are just paying for a dict. Divide-and-conquer with disjoint halves (mergesort) gains nothing.
- **A bounded key space.** `@cache` keyed on an `int` depth is fine; keyed on a `str` path from user input is a leak.
- **A depth Python can take.** Python has no TCO; past ~1000 frames convert to an explicit stack or bottom-up tabulation and the memo becomes a plain table. → `algo-py-core`

```python
@cache                                     # unbounded on purpose: key space is 0..max_depth
def _plan(depth: int, budget: int) -> int:
    if depth == 0 or budget <= 0:
        return 0
    return max(_plan(depth - 1, budget), value[depth] + _plan(depth - 1, budget - cost[depth]))
```

## Loops

The loop equivalent is **loop-invariant computation**: something inside the body whose value does not depend on the iteration variable. The first answer is not a cache — it is hoisting the expression out of the loop. Reach for a memo only when the repeated value *does* depend on the iteration variable but repeats across iterations.

| Inside the loop | Answer |
|---|---|
| Same value every iteration | Hoist it above the loop. No cache. |
| Depends on the item, repeats across items | Memoize the per-item function |
| Depends on the item, never repeats | Nothing to cache — you have an algorithm problem |
| Re-compiles a regex / re-opens a connection | Module-level constant or a pooled resource, not a cache |

The middle row is the only real memo. Measure the repeat rate before assuming it: a memo with a 2% hit rate is a dict that costs memory and a hash per call.

## Arguments must be hashable

The memo key is built from the arguments, so a `list`, `dict` or `set` argument raises `TypeError`. Convert at the boundary rather than weakening the core:

- `list` → `tuple`, `set` → `frozenset`, `dict` → `tuple(sorted(d.items()))` or a frozen dataclass.
- A model object → cache on its identity (`id`) only if it is immutable; otherwise key on the fields that matter.
- A large blob → key on its digest, not its bytes; hashing 10 MB per lookup is worse than the miss.

Keep the conversion in the impure caller. A core that accepts a `tuple[float, ...]` is honest about being memoizable; one that accepts a `list` and copies it internally is lying.

## Methods, properties and the `self` trap

`@cache` on a method keys on `self`, so the cache holds a strong reference and **the instance is never collected** — a per-request object becomes a permanent leak. Options, in order:

1. Make it a module-level function of the fields it actually reads. Usually the right answer: the method did not need `self`.
2. `@cached_property` — per instance, computed once, dies with the instance. Note it needs `__dict__`, so it is incompatible with bare `__slots__` unless `__dict__` is re-added. → `lang-py-datamodel`
3. A per-instance cache created in `__init__`. Explicit, bounded, and its lifetime is the object's.

## Async: the coroutine trap

`functools.lru_cache` on an `async def` caches the **coroutine object**, not the result. The first caller awaits it and it works; the second awaits an already-consumed coroutine and gets `RuntimeError: cannot reuse already awaited coroutine`. This is the single most common async caching bug and it passes every single-threaded test.

Use a decorator that caches the *awaited result*, not the coroutine. Inside a lazy pipeline that is `→ para-py-iteration`'s async toolkit; standalone, it is the dedicated async memo decorator this skill's stack names. Two properties matter beyond correctness:

- **Single-flight**: N concurrent misses on the same key should compute once, not N times. Without it a cold cache under load is a self-inflicted stampede.
- **Cancellation**: if the computing task is cancelled, the waiters must not inherit a poisoned entry. → `lang-py-lifecycle`

## When not to memoize

- The function is already sub-microsecond — the dict lookup and hash cost more than the call.
- The result is large and the hit rate is low — you are trading a lot of memory for a rare win.
- The arguments are effectively unique per call (request ids, timestamps, UUIDs) — a 0% hit rate with full memory cost.
- Correctness depends on re-reading the world. A memo makes a function *lie* about the present; if that matters, it is not cacheable at this plane.
