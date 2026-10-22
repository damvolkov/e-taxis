# Registries

A mapping is closed: someone edits it. A registry is open: handlers declare themselves at import time. Use it when handlers live across module boundaries.

## Subclass registry

```python
class Processor:
    """Base processor. Subclasses register themselves by kind."""

    registry: ClassVar[dict[Kind, type[Processor]]] = {}
    kind: ClassVar[Kind]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        Processor.registry[cls.kind] = cls

    async def run(self, node: Node) -> Node: ...


class Annotator(Processor):
    kind = Kind.ANNOTATE

    async def run(self, node: Node) -> Node: ...
```

`__init_subclass__` over a metaclass: same effect, one method, no new type hierarchy.

## Decorator registry

For the dispatch-handler exception — functions, not classes:

```python
HANDLERS: Final[dict[Kind, Handler]] = {}

def handles(kind: Kind) -> Callable[[Handler], Handler]:
    """Register a handler for a kind and return it unchanged."""
    def register(handler: Handler) -> Handler:
        HANDLERS[kind] = handler
        return handler
    return register


@handles(Kind.VECTOR)
async def run_vector(spec: Spec) -> Query: ...
```

## Rules

- A registry populates itself on import. Import the package holding the handlers explicitly; never depend on collection order.
- Registering over an existing key is a bug. Raise on duplicate.
- Closed set living in one file → plain frozen mapping. A registry earns its cost across modules.
