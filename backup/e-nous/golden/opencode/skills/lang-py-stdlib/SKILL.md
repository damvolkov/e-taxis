---
name: lang-py-stdlib
description: "Python: stdlib first, then Rust-backed, then async — disk access, binary/mmap, embedded backends (sqlite, config via e-serde), time, uuid, secrets. Use when picking a stdlib primitive or its upgrade."
metadata:
  family: form
---

# lang-py-stdlib

The standard library is the first reach: know which module does the job, and know exactly when to leave it for a Rust-backed engine or an async twin. Owns the systems plumbing — disk and OS access, binary and buffered IO, embedded backends, time and identity — plus the upgrade ladder. The functional/iteration surface is `para-py-iteration`, `contextlib` is `lang-py-lifecycle`, `collections`/`heapq`/`bisect` are `algo-py-core`, `math`/`decimal` are `algo-py-numeric`, `typing` is `lang-py-typing`. The upgrade map → `references/lib.md`.

## Rules

1. **Stdlib first, then Rust-backed, then async.** Reach the standard-library primitive before any dependency; upgrade to a Rust/C engine on the hot path, and to the async twin when it touches the loop. The ladder is a per-call-site decision, not a blanket import. → `references/lib.md`
2. **Target the latest Python.** 3.14 is the baseline: deferred annotations, t-strings for safe interpolation, `compression.zstd`, `concurrent.interpreters`, free-threading where it earns it. Don't hand-roll what a new stdlib module now ships.
3. **Every path is `pathlib`; every durable write is atomic.** `Path`, never string concatenation or `os.path`; a crash-safe write is temp-file + `os.replace` (atomic rename), never truncate-in-place. Throughput/async file IO → `para-py-iteration`. → `references/io.md`
4. **Binary is buffered and zero-copy.** `io` buffered readers, `struct` for packed layouts, `mmap` + `memoryview` to read large files without copying, `bytes`/`bytearray` chosen deliberately. → `references/io.md`
5. **Reach an embedded backend before a service.** `sqlite3` for local structured storage, `csv` for tabular text, `dbm`/`shelve` for a key-value file, `compression` for bytes at rest; **`e-serde`** (Rust, async-native) is the house loader for any structured config — json/jsonc/yaml/toml/ini through one API, `tomllib`/`json` only for a zero-dep cold path. → `references/backends.md`
6. **One right module for time, identity, randomness.** `datetime` + `zoneinfo` (never a naive datetime across a boundary), `time.monotonic`/`perf_counter` for durations, `uuid` for ids, `secrets` for anything security-sensitive — never `random` there. → `references/primitives.md`
7. **Don't misplace the building block.** `itertools`/`functools`/`operator` → `para-py-iteration`; `contextlib` → `lang-py-lifecycle`; `collections`/`heapq`/`bisect` → `algo-py-core`; `math`/`decimal`/`statistics` → `algo-py-numeric`; `asyncio`/threads/processes → `conc-py-async`. Reach them where they live.

## Sample

```python
from pathlib import Path
import eserde, os, tempfile

def load_config(path: Path) -> dict:
    """House config loader: one Rust-backed call for json/jsonc/yaml/toml/ini, format from the suffix."""
    return eserde.load(path)                    # sync; `eserde.aload(path)` is the async twin

def write_atomic(path: Path, data: bytes) -> None:
    """Durable write — a crash mid-write never leaves a half-written file."""
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)                       # atomic rename on the same filesystem
```

The path primitive and the atomic-write pattern are stdlib; the structured config load is the Rust-backed `e-serde` upgrade — stdlib for the primitive, the engine for the format.

## References

- `references/io.md` — filesystem access (pathlib, atomic write, tempfile, os, glob, stat, locking) and binary/buffered IO (io, struct, mmap, memoryview)
- `references/backends.md` — embedded backends: `e-serde` config loader, `sqlite3`, `csv`, `dbm`/`shelve`, `compression`
- `references/primitives.md` — `datetime`+`zoneinfo`, `time`, `uuid`, `secrets`/`random`
- `references/lib.md` — the reach ladder and the stdlib → Rust-backed / async upgrade map
