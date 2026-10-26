# Classes

## Surname

A class ends in the PascalCase name of the module it lives in. The module states the category once; the class states its identity.

| Location | Classes |
|---|---|
| `providers.py` | `MinioProvider`, `FileProvider` |
| `providers/minio.py` | `MinioProvider` |
| `providers/minio.py`, several classes | `AgnosticMinioProvider`, `StreamingMinioProvider` |
| `adapters/tts/kokoro.py` | `KokoroTTS` |

The second qualifier sits **before** the surname and appears only when one module holds more than one class needing differentiation. A single class never carries it.

When the surname would repeat the package (`providers/provider.py`), the folder is wrong, not the class.

## Body order

```python
class MinioProvider:
    """One-line purpose."""

    ##### PRIVATE #####

    async def _run_fetch(self, key: str) -> bytes: ...
    async def _run_decode(self, raw: bytes) -> Payload: ...
    async def _common_log(self, event: Event) -> None: ...

    ############################################################

    ##### PUBLIC #####

    async def run(self, key: str) -> Payload: ...
```

Privates first, publics after, the two blocks split by a bare `#` rule. Within a block, privates group by the public they serve, in the order those publics appear.

## Atomicity

A class is monolithic in scope and atomic in method. One method holds one decision; when logic thickens, it is extracted into a private that declares its parent, never absorbed into the caller. Cognitive complexity stays low by construction: a method that needs a comment to be followed is a method that needed a private.

Extract when: a block repeats, a step calls a third party, recursion begins, or a name would make the step obvious. Do not extract 1–3 line fragments used once — inline them.

## Other names

| Kind | Form | Example |
|---|---|---|
| Base / contract | `{Concept}` | `Adapter`, `Pipeline` |
| Domain model | `{Concept}` | `Entity`, `Session` |
| DTO | `{Concept}Request` · `{Concept}Response` | `TokenRequest` |
| Owned concept | `{Entity}{Suffix}` | `TaskState`, `TaskSpec` |
| Registry | `{Concept}Registry` | `TaskRegistry` |
| Settings | `Settings`, composed of `{Domain}Settings` | `Settings(CoreSettings, ApiSettings)` |
| Error | `{Concept}Error(AppError)` | `NotFoundError` |

Canonical suffixes: `State` (not Status), `Spec` (not Config), `Effect` (not Result), `Policy` (not Strategy), `Priority` (not Weight). One canonical term per semantic field, held consistent across the whole bounded context, overrides these defaults — never two synonyms for one concept.
