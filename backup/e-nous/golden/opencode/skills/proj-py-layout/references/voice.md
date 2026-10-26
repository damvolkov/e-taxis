# voice — streaming realtime runtime

The API service plus the realtime spine: audio and text flow as streams, STT/TTS behind adapters, an event bus between stages. Modeled on `e-voice`.

```
src/e_<name>/
├── main.py
├── core/                 # settings, logger, lifespan
├── config/
├── models/
├── api/                  # control-plane HTTP (health, config)
├── websockets/           # the realtime plane — mirrors api/
├── adapters/
│   ├── stt/              # whisper.py, … one word = the brand
│   └── tts/              # kokoro.py, qwen.py
├── streaming/            # the pipelines: stt/, text, vad, transcriber
├── events/              # bus + in-process concurrency: adapters, pool, monitor
├── middlewares/
└── operational/          # controller, monitor, server
```

## Non-negotiables

- **Streaming over request/response** — audio arrives and leaves as async streams; `streaming/` holds the lazy pipelines → `para-py-iteration`, backpressure → `conc-py-async`.
- **Adapters by subdomain** — `adapters/stt/`, `adapters/tts/`, `adapters/ww/` (wake-word), each with `base.py` + `registry.py` + one-word implementations; swap engine by config, never by edit.
- **Events between stages** — VAD → STT → agent → TTS is an event flow, decoupled through `events/` → `arch-py-events`; keep the log path off the audio hot loop → `obs-py-logging`.
- **Latency is the budget** — the hot loop allocates nothing per frame (`deque(maxlen=…)` ring buffers); heavy work is offloaded, never run on the loop.
- **WS lifecycle** — a session opens, streams, and must close deterministically (`aclosing`, graceful drain) → `lang-py-lifecycle`.
