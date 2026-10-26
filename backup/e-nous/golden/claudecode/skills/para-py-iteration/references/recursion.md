# Recursion & traversal

Traversal is iteration over depth. Python has no tail-call optimization: every call is a frame, the default ceiling is ~1000 frames, and `sys.setrecursionlimit` past it segfaults the interpreter rather than raising. Depth decides the form, not elegance.

## Decision

| Structure | Depth | Form |
|---|---|---|
| AST, balanced tree, known-shallow | bounded, small | recursion, lazy via `yield from` |
| graph, linked list, filesystem, arbitrary user data | unbounded | explicit stack/`deque` frontier — no ceiling, less overhead |
| overlapping subproblems | — | memoize (`functools.cache`) or iterative DP |

## Lazy recursion — bounded depth

`yield from` keeps recursion lazy: the consumer pulls one node at a time, nothing materializes. The frame ceiling still bounds it, so use it only for shapes you know stay shallow.

```python
def walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.children:
        yield from walk(child)
```

Each level adds a frame and a forwarding cost; `yield from` buys laziness, not unbounded depth.

## Explicit frontier — unbounded depth

Move the recursion onto the heap, where there is no ceiling and no per-frame cost. The `yield` inside the loop keeps it lazy; memory is bounded by the graph's width, not its depth.

```python
def walk(root: Node) -> Iterator[Node]:
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))   ### reversed → children yielded left-to-right
```

`stack.pop()` is DFS. Swap the list for `collections.deque` and `pop()` for `popleft()` and the identical shape becomes BFS.

## Async frontier

The same loop, awaiting the expansion:

```python
async def walk(root: Node) -> AsyncIterator[Node]:
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(await node.fetch_children())
```

## Cycles

Any graph that is not a tree needs a `seen: set[NodeId]`, checked before pushing, or the frontier never empties.

```python
def walk(root: Node) -> Iterator[Node]:
    seen: set[NodeId] = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if node.id in seen:
            continue
        seen.add(node.id)
        yield node
        stack.extend(node.children)
```
