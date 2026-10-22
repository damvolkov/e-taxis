# api — REST / realtime service

The default served backend, and the base every other served archetype builds on. Async worker is this layout minus `api/`, plus a `tasks/` consumer.

```
src/e_<name>/
├── main.py               # FastAPI/Robyn app; include_router explicitly, no @app decorators
├── core/                 # settings, logger, lifespan, middlewares (registry list), security, deps
├── config/               # CoreSettings, ApiSettings, … one BaseSettings per domain
├── models/               # core (RequestHeaders, Session), error, api (Request/Response DTOs), <domain>
├── api/                  # router/ — one file per resource (health, <resource>); deps.py DI chains
├── websockets/           # WS routes, mirrors api/ (only if realtime)
├── adapters/             # base, registry, <domain>/<impl>.py — external clients
├── middlewares/          # ASGI: base, cors, correlation-id (a registry list, not decorators)
└── operational/          # controller, monitor — domain orchestration
```

## Non-negotiables

- **Entrypoint** — `main.py` creates the app and `include_router`s each router; lifespan is an `asynccontextmanager` on the app. Nothing else imports the app instance.
- **DI** — `api/deps.py` holds the dependency chains (headers → session → store); routers depend on them, request-scoped.
- **Settings** — composed in `core/settings.py` from the `config/` modules; `st.PORT`, `st.CORS`, never `os.environ`.
- **Errors** — one `AppError` root; an exception-handler registry maps them to responses at the boundary → `lang-py-lifecycle`.
- **Async worker variant** — drop `api/`/`websockets/`, add `tasks/` (queue consumers, cron); the broker/topology is `sys-gen-scaling` · `arch-py-events`, the concurrency `conc-py-async`.

The web framework and its test client are named in that stack, not here; this file is the shape.
