# Bend the object model

Behaviour belongs in the object. Implement the protocol Python already calls; delete the method that reimplements it.

## Storage — `__slots__`

Every non-dynamic class declares `__slots__` (or `@dataclass(slots=True)`). Each subclass declares only its own; a repeated parent slot shadows and wastes. No `__slots__` → a per-instance `__dict__` and silent typo-attributes.

## Descriptors — reusable attribute logic

When validation or computation repeats across attributes or classes, it is a descriptor, not a property copied N times.

```python
class Positive:
    def __set_name__(self, owner: type, name: str) -> None: self._slot = f"_{name}"
    def __get__(self, obj, owner=None): return getattr(obj, self._slot)
    def __set__(self, obj, value):
        if value <= 0: raise ValueError(f"{self._slot[1:]} must be positive")
        setattr(obj, self._slot, value)
```

A data descriptor (`__set__`/`__delete__`) wins over the instance `__dict__`; a non-data one (only `__get__`) loses to it. `property` and `cached_property` are descriptors — reach for them first, write your own only when the logic is shared.

## Identity — value semantics

- `__repr__` always: unambiguous, ideally reconstructing.
- `__eq__` and `__hash__` together — or `@dataclass(frozen=True)`, which writes both. An `__eq__` without `__hash__` makes the object unhashable.
- Ordering: `@functools.total_ordering` + `__eq__` + one of `__lt__`/`__gt__`/…
- `__bool__` for emptiness; absent it, Python falls back to `__len__`.

## Emulation — behave like a builtin

`__call__` (callable), `__getitem__`/`__setitem__`/`__contains__`/`__len__` (container). Iteration (`__iter__`/`__anext__`) → `para-py-iteration`; context (`__enter__`/`__aenter__`) → `lang-py-lifecycle`.

## Construction & class customization

- `__new__` only when `__init__` cannot: immutables, caching/interning, returning a subclass.
- `__init_subclass__` for auto-registration — over a metaclass, always. → `para-py-dispatch`
- `__set_name__` lets a descriptor learn its attribute name.
- A metaclass is the last resort, when class *creation* itself must change.

## Serialization

`__getstate__`/`__setstate__` drive `copy` and `pickle`. A slotted class has no `__dict__`, so it must define them — or use dataclasses, which handle it. `__reduce__` for full control.
