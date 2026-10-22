# Methods and functions

## Public methods

One representative word naming the class's core act: `run`, `scan`, `deploy`, `retrieve`, `encode`, `resolve`. The class already says *what*; the method says *does*.

A second word appears only when one class genuinely needs two related public acts that would otherwise collide — `run_batch` beside `run`. Never to describe, only to distinguish.

## Private methods

A private exists to serve a public. Its name says which.

```
_<public>_<what>          serves exactly one public method
_common_<what>            serves two or more
```

```python
async def run(self, spec: Spec) -> Result:
    rows = await self._run_fetch(spec)
    await self._common_log(Event.FETCHED)
    return self._run_reduce(rows)

async def _run_fetch(self, spec: Spec) -> Sequence[Row]: ...
def _run_reduce(self, rows: Sequence[Row]) -> Result: ...
async def _common_log(self, event: Event) -> None: ...
```

The prefix is the call tree written into the names: reading `_run_fetch` tells you it is reachable only from `run`. When a `_run_*` private gains a second caller, it is renamed `_common_*` in the same commit.

`<what>` is one word, two in snake_case when one is not enough: `_run_fetch_sql`, `_scan_recursive_map`. Never `__` dunder, except magic methods.

## Module-level functions

Permitted only in modules built for them — `utils.py`, `helpers.py`, `operational/` — and in dispatch handlers. Elsewhere the logic belongs to a class.

```
<purpose>_<scope>[_<detail>]
```

```python
def encode_audio_pcm(frames: Iterable[Frame]) -> bytes: ...
def score_entity_confidence(node: Node) -> float: ...
def recursive_map(node: Node, target: type[Node]) -> Iterator[Node]: ...
```

Two levels by default, three when the second is ambiguous. Single-word when the purpose is irreducible (`softmax`, `attenuate`). Private module function: `_` prefix, no other change — the module is the domain.

## Verbs

Distinct operations, never synonyms of each other:

| Verb | Operation |
|---|---|
| `get` | Access something that already exists |
| `load` | Read from disk or an external source |
| `build` | Assemble a value from parts, no side effects |
| `create` | Instantiate something with identity or lifecycle |
| `update` | Modify existing state |
| `remove` | Delete |
| `send` | Transmit outward |
| `validate` | Check invariants |
| `format` | Render to text |
| `on` | React to an event |
| `from` | Alternative constructor (classmethod) |

## Constants and the rest

Module constants `UPPER_SNAKE`, private `_UPPER_SNAKE` · enum members `UPPER = auto()` · singletons lowercase (`settings`, `logger`, `router`) · `type` aliases PascalCase · TypeVars always bound.
