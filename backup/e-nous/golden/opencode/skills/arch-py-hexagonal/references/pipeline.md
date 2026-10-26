# Pipeline — chain of handlers

Cross-cutting behaviour — auth, logging, retry, enrichment, validation — must not be inlined into the handler it wraps. It is a **chain of ordered stages**, each a named unit that does its part and passes control on. This is Chain of Responsibility and Middleware, one idea at two scales. Rust anchor: `tower`'s `Layer`/`Service` stack — composable, ordered, each layer wrapping the next.

Distinguish this from a **data** pipeline (lazy map/filter/reduce over a stream): that is → `para-py-iteration`. Here the elements are *handlers*, and the composition is the algorithm.

## Two scales, one shape

| Scale | Stage is | Passes | Example |
|---|---|---|---|
| **Middleware** (onion) | a wrapper around the whole request | the next handler down, then back up | ASGI middleware: auth → correlation-id → the route → logging on the way out |
| **Processor chain** (linear) | a transform on the payload | the payload to the next stage | ingest → clean → annotate → embed → index |

Middleware is bidirectional (before *and* after the inner call); a processor chain is one-directional. Pick by whether a stage needs to act on the way back.

## Processor chain

Each processor is a small object with one method; the chain is data (a list), composed at the root, executed by folding the payload through it.

```python
from typing import Protocol

class Processor[T](Protocol):
    async def process(self, item: T) -> T: ...

class Pipeline[T]:
    def __init__(self, stages: tuple[Processor[T], ...]) -> None:
        self._stages = stages
    async def run(self, item: T) -> T:
        for stage in self._stages:            # ordered fold; each stage sees the previous output
            item = await stage.process(item)
        return item

pipeline = Pipeline((Cleaner(), Annotator(), Embedder()))     # composed at the root
```

- The order **is** the configuration. A new step is a new element, never an edited stage (OCP).
- Stages are independently testable; each is a port implementation.
- Homogeneous payload (`T → T`) → this fold. Heterogeneous stages (`A → B → C`) → a typed sequence and multiple dispatch on stage type. → `para-py-dispatch`

## Middleware (onion)

Each layer wraps the next; the innermost is the real handler. Register the stack once, at the root — never with a decorator that binds a handler to the app.

```python
Handler = Callable[[Request], Awaitable[Response]]

def logging_mw(nxt: Handler) -> Handler:
    async def mw(req: Request) -> Response:
        log.info("REQUEST_IN", path=req.path)
        resp = await nxt(req)                  # descend
        log.info("REQUEST_OUT", status=resp.status)   # ascend
        return resp
    return mw

def compose(handler: Handler, *layers: Callable[[Handler], Handler]) -> Handler:
    return reduce(lambda h, layer: layer(h), reversed(layers), handler)
```

In a real API you use the framework's middleware registry (an ordered list at the root), not a hand-rolled `compose` — this shows the shape it implements.

## Short-circuit

A stage may end the chain early — a failed guard, a cache hit. Model the early exit as a **value**, not a raised exception used for control flow: return `Err(...)` or a sentinel the runner matches on, and stop the fold. → `arch-py-adt` (Result). Reserve exceptions for genuine faults, caught at the boundary.

## When NOT to

- Two steps with no cross-cutting concern and no reordering pressure: just call them in sequence. A `Pipeline` of two hard-wired stages is ceremony.
- A branch, not a chain: if stage selection depends on the payload's type or a value, that is dispatch, not a pipeline. → `para-py-dispatch`
