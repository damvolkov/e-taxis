# Sync scopes

A context manager is `Drop`: acquisition in `__enter__`, release in `__exit__`, deterministic, GC-independent.

## The two forms

```python
class Resource:                       # class — full control, reusable
    def __enter__(self): self.h = open_handle(); return self.h
    def __exit__(self, et, e, tb): self.h.close(); return False   # True suppresses — almost never

@contextmanager                       # function — the common case
def resource():
    h = open_handle()
    try:
        yield h
    finally:                          # without try/finally a body error skips cleanup
        h.close()
```

## contextlib toolkit

| Tool | Use |
|---|---|
| `suppress(FileNotFoundError)` | a bounded, explicit `try/except: pass` |
| `closing(obj)` | `.close()` objects without the `with` protocol — generators included |
| `nullcontext(x)` | an optional context manager without duplicating branches |
| `ExitStack` | dynamic count of resources, callbacks, ownership transfer |
| `chdir(path)` (3.11+) | temporary working directory |

## ExitStack — dynamic resources and move

```python
with ExitStack() as stack:
    files = [stack.enter_context(open(p)) for p in paths]   # 3rd fails → 1st,2nd closed
    stack.callback(log, "opened")                            # arbitrary LIFO cleanup
    return files, stack.pop_all()                            # move ownership to the caller
```

`pop_all()` is a *move*: the local `with` stops cleaning up; the caller gets a fresh `ExitStack` it must close.

## Safe construction — the forgotten pattern

```python
def __init__(self):
    with ExitStack() as stack:
        self.a = stack.enter_context(A())
        self.b = stack.enter_context(B())    # B fails → A released
        self._stack = stack.pop_all()         # success: the object owns both
def close(self): self._stack.close()
```

An `__init__` that acquires more than one resource without this leaks the first when the second fails.

## Antipatterns

| ❌ | ✅ |
|---|---|
| `f = open(p); data = f.read()` | `with open(p) as f:` or `Path(p).read_text()` |
| `@contextmanager` without `try/finally` | `try: yield finally: cleanup` |
| nested dynamic `with` blocks | `ExitStack` / `AsyncExitStack` |
