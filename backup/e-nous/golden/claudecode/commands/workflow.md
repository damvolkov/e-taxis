---
description: Execute a declared workflow graph from core/tekton/workflows against the current request.
arguments:
- target
- request
argument-hint: "[target] [request]"
---

Target workflow: $target
Request: $request

First verify core/tekton/workflows/$target exists — use the `list` and `read` tools, never bash (compound commands defeat the permission globs). If it does not: list the ids under core/tekton/workflows/ and stop — never invent a graph, never improvise an equivalent flow.

Read the structured definition and its compiled graph, then execute it exactly:
1. Resolve the declared parameters from the request; anything missing and undeclared → stop and ask, do not guess.
2. Run the DAG: siblings with the same parents and no edge between them in parallel; a join waits for all parents; direct actions (no @agent) run inline.
3. Every node must return a structured result; a node without acceptance criteria is a defect in the graph — stop and report it.
4. Produce the declared output and verify it exists.

Report: nodes executed (and in what order/parallelism), agents invoked, output path, nodes failed or skipped with the reason.
