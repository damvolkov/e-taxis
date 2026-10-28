Every non-trivial task in a project is planned before work starts, in `./.plans/` at the project root (git-ignored): one file, `TODO_<word>.md`, `<word>` a single representative word. Its shape is fixed, always — the steps, then their breakdown:

```
# TODO_<word> — <the goal in one line>
---------------
PROGRESS: ACTIVE
---------------
1. ~~<step done>~~
2. <step>
---------------
### 2. <step>
<the breakdown of every step that needs one>
```

- **The plan is always true.** `PROGRESS` is `ACTIVE`, `BLOCKED`, `FINISHED` or `CANCELLED`; a step is struck through in the list — `1. ~~<step>~~` — the moment it is done.
- **An ended plan is renamed**: `TODO_<word>_FINISHED.md` or `TODO_<word>_CANCELLED.md`, its `PROGRESS` set to match.
- **Then, always**: a mini summary of what was done, naming `TODO_<word>`, goes into the project's `CHANGELOG.md` under `## [Unreleased]`.
- The `plans` check enforces it on every stop: a state, a strike, a file name or a CHANGELOG that disagree block until fixed.
