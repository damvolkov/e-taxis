# Dependency injection

Injection is not a framework — it is a discipline: **an object receives its collaborators, it never constructs or fetches them.** The Rust instinct is the same: no globals, pass what you need, ownership is explicit. A DI container is only automation for the wiring you could write by hand.

## Constructor injection is the default

Ninety percent of the time the whole pattern is: take dependencies as constructor arguments, store them, use them. No library.

```python
class EntityPipeline:
    def __init__(self, store: KnowledgeStore, annotator: Annotator, clock: Clock) -> None:
        self._store, self._annotator, self._clock = store, annotator, clock
```

Every collaborator is a **port** (Protocol), so the class is trivially testable with fakes and knows no concretion. This is Inversion of Control with zero machinery.

## The composition root

There is exactly **one** place where concretions are named and the graph is assembled — the entrypoint (`main.py`) or its `deps.py`. Nothing else imports the app, the container, or a concrete adapter.

```python
# deps.py — the single wiring point
def build_pipeline() -> EntityPipeline:
    store = RedisKnowledgeStore(url=st.REDIS_URL)
    return EntityPipeline(store=store, annotator=SpacyAnnotator(), clock=SystemClock())
```

This is the same law as **explicit registration over decorators**: routers, commands and handlers are plain functions/classes; the root imports and registers them. A `@app.get` on a handler couples it to the app singleton and scatters the wiring — forbidden.

## Scopes / lifetimes

A dependency has a lifespan. Match it to the resource, not to convenience.

| Scope | Lives for | Examples | Mechanism |
|---|---|---|---|
| **Singleton** | the process | settings, model weights, connection pool | module-level object, built once at root |
| **Request/session** | one request or conversation | DB session, request headers, correlation id | built per-request, injected by the driving adapter |
| **Transient** | one call | a command object, a query | constructed at the call site |

A request-scoped resource must be **released at scope exit** — a generator dependency that `yield`s then cleans up is the RAII-shaped tool. → `lang-py-lifecycle`

## Config is an injected contract

12-factor III: config comes from the environment, is parsed **once** into a validated `pydantic-settings` object, and is *injected*. The core never calls `os.environ`, never reads a `.env`, never reaches config at point of use.

```python
from myapp.settings import settings as st     # one singleton per package, always aliased `st`
```

Reading config where you consume it re-couples the core to the environment and makes it untestable. Parse at the boundary, pass the value inward.

## Framework vs library vs by-hand

- **By hand (default):** constructor injection + a composition root. Nothing to learn, nothing to import, no magic. Reach further only when the graph is large enough that manual wiring becomes error-prone.
- **Framework-native:** FastAPI `Depends`, request-scoped, async — the right tool *inside* an API. Do not fight it with a second container.
- **Standalone container:** when the graph is deep and scoped across many entrypoints. Concrete choices, async-first, and what never to import → `lib.md`.

**Never:** a global singleton fetched via `import` deep in the core (that is a service locator hiding a hard dependency); a container passed around as a god-object; config read at point of use.
