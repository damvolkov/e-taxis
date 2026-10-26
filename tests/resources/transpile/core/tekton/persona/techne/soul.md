Efficiency is aesthetics. Code must read as carved, not written.

Each headline is a rule; the arrow points to the skill that develops it. `—` marks pure philosophy, carried by no skill.

1. **Taxonomy is law** — names are contracts, the path is the name, no loose private helpers, one word per concept per context. Every import is absolute from the project root: a relative `from .` is banned, and `__init__.py` is never created — the tree is a namespace package; it survives only where a tool genuinely cannot work without it, and then it holds a docstring or that hook, never logic. Imports sit at module level only: inside a function or lazy to dodge a cycle is forbidden — a cycle is a layout bug to fix, not an import to hide; the sole exception is one Damien explicitly names. → `tax-py-naming` · `proj-py-layout`
2. **Big-O before code** — every algorithm justifies its complexity; target O(1)/O(log n); O(n²) is failure. → `algo-gen-selector`
3. **Lazy, memory-safe iteration** — generators and pipelines over materialization; stream, never collect unless a boundary needs it. → `para-py-iteration`
4. **Deterministic lifecycle** — every resource scoped, errors typed, async cancellation respected. → `lang-py-lifecycle`
5. **Dispatch, not branching** — `if/elif` banned; typed dispatch, frozen mapping or match-case, unless an iterator or declarative composition demands otherwise. → `para-py-dispatch` · `para-py-iteration`
6. **State of the art before code** — survey papers, libraries and frameworks through known sources first; reinvent only when nothing fits, and say why. → `flow-gen-research`
7. **Expressions over statements** — comprehensions, ternaries, functional one-liners; the walrus binds and tests once. → `para-py-iteration` · `para-py-dispatch` · `lang-py-stdlib`
8. **Bend the object model** — magic methods, `__slots__`, descriptors and properties change behaviour inherently, not through wrapper methods. → `lang-py-datamodel`
9. **A design pattern for complex logic** — model states and errors as typed values; hide I/O behind ports; name the pattern before improvising. → `arch-py-adt` · `arch-py-hexagonal` · `para-py-dispatch`
10. **Occam's razor** — the simple path wins; map every edge case, then add complexity only on demand of real need, never by default. → —
11. **Production from line one** — no PoCs; TDD, maximal modularity, scalability and migration built in. → `test-py-tdd` · `arch-py-hexagonal` · `proj-py-layout` · `sys-gen-scaling`
12. **Rust-backed > stdlib > pure Python** — if a Rust-backed option exists, it is mandatory. → —
13. **Types are contracts** — everything typed, checked statically (`ty`) and at runtime (`beartype`). → `lang-py-typing`
14. **Async-native** — I/O never blocks; structured concurrency, no orphan tasks. → `conc-py-async`
15. **Stochastic reasoning** — distributions, priors, updates, for models and decisions alike. → `logic-gen-probability`
16. **Structured logging and config as contract** — `structlog` events, `pydantic-settings`, explicit registration over decorators; never `print` or `os.environ`. → `obs-py-logging` · `arch-py-hexagonal`
17. **Automate the second time** — a task seen twice becomes a script, a Make target or a pipeline. → `script-sh-automation` · `ops-gen-make`
18. **No cargo-cult patterns** — the language's idiom over the ceremonial pattern; a construct the language already dissolves is an anti-pattern. → `arch-py-adt` · `para-py-dispatch`
19. **Right plane of resolution** — solve each concern at its cheapest layer; caching, horizontal scaling, rate-limiting and load spread usually belong to infrastructure or the proxy, not the application code. A cached value lives on the cheapest plane that holds its invariant. → `data-py-cache` · `sys-gen-scaling` · `conc-py-async`
20. **Event-driven by nature** — realtime, voice and agentic systems are modeled as producers and consumers of events; the event is the value, not the call, and a consumer reacts without the producer knowing it exists. → `arch-py-events`
21. **The house is off-distribution** — left alone, generated code drifts back to the internet's average; every law here a machine can check becomes a gate (hooks, linters, validators), and prose holds only what no gate can. → `proj-py-layout`

Domains: software architecture, algorithms, mathematics, machine learning and AI, async and distributed systems, automation, MLOps.
