---
name: tax-py-naming
description: "Python: naming and layout for paths, modules, classes, methods, functions, comments and tests. Use whenever creating, renaming or reviewing any Python file, identifier or class body."
metadata:
  family: form
---

# tax-py-naming

A name is a contract, and the path is part of the name. Say once what the location already says never.

## Rules

1. **The path is the name.** A module identifier is the concatenation of its path segments; the file keeps only the irreducible word. Modules and packages are single-word. An underscore in a module name is almost always a folder that was not created. The import is the path spelled in full from the root: `from .` banned, `__init__.py` is never created — the tree is a namespace package; only a tool that cannot resolve it without the file leaves one, holding a docstring or that hook and nothing else. Module level only: an import inside a function, or lazy to dodge a cycle, is banned outright — the cycle is the bug. → `references/tree.md`
2. **A class carries its module as surname.** PascalCase, ending in the module's name: `providers.py` → `MinioProvider`, `FileProvider`. A second qualifier goes *before* the surname, and only when one module holds several classes that must be told apart: `providers/minio.py` → `AgnosticMinioProvider`. → `references/classes.md`
3. **Methods.** Public: one representative word — `run`, `deploy`, `retrieve`. A second word only on genuine collision. Private: `_<public>_<what>`, naming the public method it exists to serve — `_run_fetch_sql`, `_run_log`. Serving several publics: `_common_<what>`. → `references/functions.md`
4. **Logic lives in its class.** Atomic module-level functions exist only in utility modules built for them, named `<purpose>_<scope>[_<detail>]`. The other exception is dispatch handlers. → `para-py-dispatch`
5. **Class body: privates first, publics after**, split by a full-width rule. Every method stays atomic — extract rather than thicken a single point. → `references/classes.md`
6. **Comments are banned.** Three forms survive: `##### SECTION NAME #####` to head a block, a bare `#` rule to divide one, and a single `### One-line reason.` where internal logic genuinely needs it. Anything else only on explicit request.
7. **Tests mirror the path and repeat nothing.** `test_<target>_<scenario>[_<aspect>]`, where the target drops whatever the module already states. → `references/tests.md`

## Sample

```python
##### PRIVATE #####

class MinioProvider:
    """Object storage backed by MinIO."""

    async def _run_fetch(self, key: str) -> bytes: ...

    async def _common_log(self, event: Event) -> None: ...

    ############################################################

    ##### PUBLIC #####

    async def run(self, key: str) -> Payload:
        """Payload retrieved and decoded for a key."""
        ### Decoding happens here because the bucket stores raw frames.
        return Payload.decode(await self._run_fetch(key))
```

```
src/e_voice/adapters/tts/kokoro.py   →   class KokoroTTS
tests/unit/e_voice/adapters/tts/test_kokoro.py   →   test_kokoro_stress
```

## References

- `references/tree.md` — the path law, folder vocabulary, project trees, parity, verification
- `references/classes.md` — surname rule, body order, atomicity
- `references/functions.md` — method genealogy, utility modules, verbs
- `references/tests.md` — mirror, economy, scenarios
- No `lib.md` — pure taxonomy; naming governs no library dimension.
