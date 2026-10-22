# Finalizers

The last resort, when there is no lexical scope. Ranked worst to best.

- **`__del__` — avoid.** Non-deterministic, not guaranteed at interpreter shutdown, can resurrect the object.
- **`weakref.finalize(obj, fn, *args)`** — the safety net. `fn` must not reference `obj` (that pins it alive). Idempotent: callable explicitly from `close()`.
- **Combined pattern** — explicit `close()` + `with` + `finalize` as a fallback that emits `ResourceWarning`.

```python
class Handle:
    def __init__(self):
        self._h = open_handle()
        self._fin = weakref.finalize(self, _release, self._h)   # _release, not self
    def close(self): self._fin()                                 # idempotent
    def __enter__(self): return self
    def __exit__(self, *exc): self.close()
```

Detect leaks in development: `python -X dev` or `-W error::ResourceWarning` turns an unclosed resource into an error.
