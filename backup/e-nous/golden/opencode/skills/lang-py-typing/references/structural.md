# structural — Protocols over inheritance

Duck typing, made static. A `Protocol` says *what a value must do*, not *what it must inherit* — the checker matches by shape, so a type satisfies it without importing or subclassing it.

```python
from typing import Protocol

class Reader(Protocol):
    async def read(self, key: str) -> bytes: ...

async def load(src: Reader, key: str) -> bytes:   # any object with async read(str)->bytes fits
    return await src.read(key)
```

## Protocol vs ABC

| | Protocol | ABC |
|---|---|---|
| Conformance | structural — matched by shape | nominal — must subclass/register |
| Coupling | zero; the implementer never sees the protocol | the implementer imports the base |
| Use for | boundaries, adapters, ports, third-party types | a shared base with real implementation |

Prefer `Protocol` for a contract a caller depends on (ports in `arch-py-hexagonal`, adapters). Reach for an ABC only when you ship shared behaviour, not just a shape.

## runtime_checkable

`@runtime_checkable` lets `isinstance(x, Reader)` work — but it only checks **method presence, not signatures**, and it is slower. Use it only when a runtime check is unavoidable; prefer static conformance. Real runtime enforcement of the full signature is `beartype`'s job.

## Boundary

`Protocol` as the *selector* of a typed multiple-dispatch table is `para-py-dispatch`. Here it is the interface contract itself — the shape a port, adapter or boundary requires. Generic protocols (`class Store[T](Protocol)`) combine a Protocol contract with a PEP 695 generic.
