---
name: lang-py-lifecycle
description: "Python: deterministic resource cleanup and failing correctly — with, ExitStack, try/except/finally, exceptions, async cancellation. Use when managing a resource lifecycle or error path."
metadata:
  family: form
---

# lang-py-lifecycle

Rust's `Drop` and `Result` are one idea: a resource acquired in a scope is released when the scope ends, and a failure travels until someone can act on it. Python spells the first `with`, the second `raise`. Neither leaves cleanup to the GC.

## Rules

1. **Every resource has a scope.** `with`/`async with` owns acquisition and release. A dynamic count → `ExitStack`/`AsyncExitStack`. No lexical scope at all → `weakref.finalize`, never `__del__`. → `references/scopes.md`, `references/finalizers.md`
2. **`try` wraps only the line that fails.** The success path goes in `else`, cleanup in `finally`; a wide `try` buries unrelated bugs. → `references/errors.md`
3. **Catch specific, chain the cause.** No bare `except:`, no `except BaseException`; `except Exception` only at a boundary with log + re-raise. Re-wrap with `raise New(...) from e`, annotate with `add_note`. → `references/errors.md`
4. **`finally` never returns or breaks.** A `return`/`break`/`continue` in `finally` swallows the exception in flight (SyntaxWarning in 3.14). Cleanup only.
5. **Errors are a typed tree, named for their target.** An agnostic base per action-type (`ValidationError`, `RequestError`), a root per module, and a specific error inheriting both, named for the failing target (`SomethingDoerError`) and carrying its context in the constructor; the boundary catches the root, the acting site the specific type; parallel failures aggregate as `ExceptionGroup`/`except*`. → `references/errors.md`
6. **A `@contextmanager` guards its `yield`.** Wrap it in `try/finally` or a body failure skips cleanup. Constructors acquiring several resources use `ExitStack` + `pop_all()` to move ownership out on success. → `references/scopes.md`
7. **Async cleanup is not free.** `CancelledError` is a `BaseException` — never swallow it; clean up and `raise`. Shield critical async cleanup with a timeout. Half-consumed async generators need `aclosing`. Structured concurrency and orphan tasks → `conc-py-async`. → `references/async.md`

## Sample

```python
from contextlib import AsyncExitStack

async def open_pipeline(paths: list[str]) -> tuple[list[Conn], AsyncExitStack]:
    """Every connection opened, or none — ownership handed to the caller."""
    async with AsyncExitStack() as stack:
        conns = [await stack.enter_async_context(connect(p)) for p in paths]  # 3rd fails → 1st,2nd closed
        return conns, stack.pop_all()                                          # success: move cleanup out
```

`pop_all()` is Rust's *move*: the local `async with` stops cleaning up, the caller inherits an `AsyncExitStack` it must close.

## References

- `references/errors.md` — try/except/else/finally semantics and cost, EAFP vs LBYL, exception hierarchy, ExceptionGroup/except*
- `references/scopes.md` — sync context managers, the contextlib toolkit, ExitStack, safe construction and ownership move
- `references/async.md` — async context managers, AsyncExitStack, cancellation, async generators, blocking-in-async
- `references/finalizers.md` — the __del__ ban, weakref.finalize, ResourceWarning, dev mode
- `references/lib.md` — the stack: scopes, concurrency, timeouts, pools (async-first, sync alternative)
