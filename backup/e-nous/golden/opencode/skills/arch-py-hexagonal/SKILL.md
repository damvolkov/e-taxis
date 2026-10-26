---
name: arch-py-hexagonal
description: "Python: structure a system as ports and adapters — dependencies point inward, boundaries are Protocols, wiring lives at one composition root. Use when laying out a service, module or app boundary."
metadata:
  family: design
---

# arch-py-hexagonal

The core is a pure decision-maker that has never heard of HTTP, Redis or a filesystem. Everything that touches the world is an adapter plugged into a port the core defines. Dependencies point **inward**: the edge knows the core, the core knows nothing of the edge. This is Rust's instinct — the domain speaks in traits, the runtime supplies the `impl`. SOLID and 12-factor are not extra layers; they are what this shape *is* once you name it.

## Rules

1. **Dependencies point inward.** The core imports abstractions, never concretions. An adapter may import the core; the core may never import an adapter. A domain module with `import wreq` in it is a boundary violation. (DIP) → `references/ports_adapters.md`
2. **A port is a Protocol, an adapter is its `impl`.** The core declares the interface it needs as a `@runtime_checkable Protocol`; the edge supplies a class that satisfies it. No ABC inheritance across the boundary — structural conformance only. → `references/ports_adapters.md`
3. **Wire at one composition root.** Objects are constructed and injected in exactly one place (`main.py`, `deps.py`). No module reaches for a global app or container. Explicit registration over decorators. → `references/dependency_injection.md`
4. **Persistence hides behind a Repository.** The core sees `Store`, never a client. Swapping Redis for Postgres edits one adapter, zero domain code. → `references/repository.md`
5. **Cross-cutting behaviour is a chain, not a sprinkle.** Auth, logging, retry, enrichment compose as ordered stages (middleware / processors), each a named unit — never inlined into a handler. → `references/pipeline.md`
6. **Config is an injected contract.** `pydantic-settings`, validated once, passed in. Never `os.environ` in the core; never read config where you use it. (12-factor III) → `references/dependency_injection.md`
7. **SOLID is the acceptance test.** SRP: one reason to change per module. OCP: a new case is a new adapter, not an edited core. LSP: every adapter is substitutable for its port. ISP: many small ports over one fat one. DIP: rule 1. If a change forces edits across layers, the shape is wrong.

## Sample

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Transcriber(Protocol):                          # port — lives in the core
    async def transcribe(self, audio: bytes) -> str: ...

class WhisperSTT:                                      # adapter — lives at the edge
    def __init__(self, endpoint: str) -> None: self._endpoint = endpoint
    async def transcribe(self, audio: bytes) -> str: ...   # satisfies Transcriber structurally

class Meeting:                                         # core — depends on the port only
    def __init__(self, stt: Transcriber) -> None: self._stt = stt
    async def minute(self, audio: bytes) -> str: return await self._stt.transcribe(audio)

# composition root — the ONLY place that names a concretion
meeting = Meeting(stt=WhisperSTT(endpoint=st.STT_URL))
```

`Meeting` is testable with a fake `Transcriber` and no I/O. The concretion appears once, at the edge.

## References

- `references/ports_adapters.md` — driving vs driven ports, Protocol conformance, where each side lives, the anti-corruption boundary
- `references/dependency_injection.md` — constructor injection, the composition root, scopes/lifetimes, config as contract, DI without a framework
- `references/repository.md` — Store Protocol, persistence abstraction, Unit of Work, query objects
- `references/pipeline.md` — Chain of Responsibility: middleware, processor chains, ordered stages, short-circuit
- `references/application_map.md` — the 9 software categories → which macro structure each needs, and how much
- `references/lib.md` — the DI stack: builtin injection → framework-native → dishka/svcs/dependency-injector, async·sync, and what never to import
