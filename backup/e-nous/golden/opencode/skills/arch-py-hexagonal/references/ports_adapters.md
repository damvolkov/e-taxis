# Ports & adapters

A **port** is a hole in the core shaped like a need. An **adapter** is a plug the outside world builds to fit it. The core owns the shape; the edge owns the plug. Rust anchor: the core declares a `trait`, the runtime provides the `impl for ConcreteType`.

## Two kinds of port

The direction of control decides the kind. Draw the hexagon: the core is inside, actors are outside.

| Kind | Also called | Who calls whom | Example | Where the Protocol is declared |
|---|---|---|---|---|
| **Driving** (primary) | inbound, API-side | the outside calls the core | HTTP router, CLI command, queue consumer, WS handler | the core exposes a **service/use-case** interface; the driver adapts *to* it |
| **Driven** (secondary) | outbound, SPI-side | the core calls the outside | DB, cache, LLM, STT, message bus, clock | the core declares the **port Protocol**; the adapter *implements* it |

The asymmetry matters: a driving adapter depends on the core's use-case type; a driven adapter depends on the core's port. **Both arrows point at the core.** That single fact *is* dependency inversion.

## Protocol conformance, not inheritance

The boundary is structural. The core defines the port; the adapter never imports an ABC to subclass.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Clock(Protocol):                       # driven port, in the core
    def now(self) -> float: ...

class SystemClock:                           # adapter — no base class, no import of the port
    def now(self) -> float: return time.time()
```

- `@runtime_checkable` lets `isinstance(x, Clock)` guard a boundary; it checks method *names*, not signatures — the type checker (`ty`) enforces the rest statically. → `lang-py-typing`
- One Protocol per capability (ISP). `Clock` and `IdGenerator` are two ports, not one `Infra` port with two methods.
- Prefer `Protocol` over `ABC` across the boundary. Reserve `ABC` for an intra-core hierarchy where you own every subclass and want shared implementation.

## Where each side lives

```
core/  domain/  models/     ← ports (Protocols), entities, use-cases. Zero I/O imports.
adapters/                    ← driven adapters: one module per external tech
api/router/  cli/  tasks/    ← driving adapters: translate transport → use-case call
main.py  deps.py             ← composition root: builds adapters, injects into core
```

The litmus test: **grep the core for `wreq`, `httpxr`, `redis`, `open(`, `os.environ`.** Any hit is a leak. The core imports `typing`, `dataclasses`, domain modules — nothing that touches the world.

## Anti-corruption boundary

An adapter does not leak the vendor's shape inward. It translates the external model into a domain model at the edge, so a vendor API change is contained to one adapter.

```python
class SearXNGAdapter:                         # driven adapter
    async def search(self, q: Query) -> list[Document]:      # returns DOMAIN types
        raw = await self._http.get(...)                       # vendor JSON stays here
        return [Document(title=r["title"], body=r["content"]) # translate at the boundary
                for r in raw.json()["results"]]
```

The core receives `list[Document]`, never a `dict` shaped by SearXNG. This is the Adapter pattern doing anti-corruption work.

## When NOT to hexagonalize

- A one-shot **System script** or a trivial **CLI**: the ceremony outweighs the gain. A pure function taking its inputs is already "the core"; call the real dependency directly.
- A throwaway spike. Add ports the moment a second adapter (a test fake counts) is needed — not before. Speculative ports are speculative generality.

The rule of thumb: **a port earns its place when a second implementation exists — even if that second one is only the test double.**
