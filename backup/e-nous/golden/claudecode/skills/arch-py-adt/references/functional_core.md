# Functional core, imperative shell

Split the program in two. The **core** is total functions over values: given the same input it returns the same output, touches no I/O, holds no clock, raises no surprise. The **shell** is a thin outer ring that reads the world, calls the core, and writes the results back. All the decisions live in the pure core; all the effects live in the impure shell. This is why the rest of this skill is testable without a single mock — pure functions over sum types and Results need no fakes, only inputs.

## The shape

```python
# core — pure: decisions as values, no I/O, no time, no randomness passed in as data
def plan_retries(task: Task, now: float, policy: RetryPolicy) -> list[Command]:
    match task.state:
        case TaskState.FAILED if task.attempts < policy.max:
            return [Command.retry(task.id, at=now + policy.backoff(task.attempts))]
        case TaskState.FAILED:
            return [Command.give_up(task.id)]
        case _:
            return []

# shell — impure: gathers inputs, runs the core, performs the effects it returned
async def tick(store: TaskStore, clock: Clock, policy: RetryPolicy) -> None:
    tasks = await store.list_failed()                 # read the world
    commands = chain.from_iterable(
        plan_retries(t, clock.now(), policy) for t in tasks)   # PURE decision
    await execute(commands, store)                    # write the world
```

Note what the core does *not* do: it does not fetch tasks, does not read the clock (the time is passed *in* as a value), does not perform the retries — it **returns the commands** and lets the shell run them. Effects become data (a `list[Command]`) the shell interprets — commands modeled as sum types.

## Why this is the payoff

- **Testable without mocks.** `plan_retries` is `(inputs) → outputs`. You assert on values. No `mocker`, no patched clock, no fake store — those belong to the thin shell, tested once at the integration layer. → `test-py-tdd`
- **Determinism.** Time, randomness and I/O results enter as arguments, so the core is reproducible — the stochastic and the effectful are pushed to the edge where they can be seen and controlled.
- **It composes with everything above.** The core speaks in sum types and Results; the shell is the hexagon's driving/driven adapters. Functional core / imperative shell *is* hexagonal seen from the inside. → `arch-py-hexagonal`

## Effects as values

The strong form: the core does not perform effects, it **describes** them. It returns `Command`/`Effect` values; the shell is the sole interpreter. This makes the same decision logic runnable in-process, over a queue, or replayed from a log — and makes "what would this do?" a pure question you can assert on.

```python
type Effect = SendEmail | WriteRow | EnqueueJob     # the core returns these
```

Do not go monadic-IO heavier than the domain warrants. In Python, "return the effects, let the shell run them" captures the value without importing an effect system. Reach for `returns`' `IO`/`Future` only when the composition genuinely needs it → `lib.md`.

## Combinators over statements

The core is expressions: comprehensions, `map`/`filter`, `reduce`, `compose`/`pipe`, the walrus — not accumulator loops and mutation. The iteration operators (async-first) and the lazy discipline live in → `para-py-iteration`; composition helpers (`compose`, `curry`, `pipe`) → `lib.md`.

## Where the line falls per category

- **Evaluation harness / ML pipeline** — thick pure core (metrics, scoring, transforms are naturally total), thin shell (load data, write report). The best fit.
- **Async worker** — the decision of *what to do* is pure (`plan_*`); the doing is the shell.
- **API service / Agent system** — the use-case decision is pure; transport, persistence and LLM calls are shell.
- **Voice runtime** — DSP/turn decisions pure where latency allows; device I/O is shell.

## When NOT to

- A pipeline that is *nothing but* I/O orchestration (copy a file, forward a request) has no meaningful core to extract — do not manufacture a pure layer with nothing to decide.
- Do not purify to dogma: if threading a value (a clock, a config) through ten call layers only to keep a leaf "pure" hurts readability more than a direct read helps testing, read it directly and say why. Occam over purity.
