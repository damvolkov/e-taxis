---
description: "Create, update or retire one corpus entity through the emaintenance workflow: /maintenance entity op [id] [details] [publish]."
agent: orchestrator
subtask: true
---

Execute the workflow `emaintenance`: verify `core/tekton/workflows/emaintenance/workflow.yaml` exists (list and read tools, never bash), read it, and run its graph with these parameters:

entity: $1
op: $2
id: $3
details: $4
publish: $5

A step with `run:` is a command: execute it exactly, in the repo, and keep its output. A step with `when:` runs only if the parameters match; otherwise it is skipped. An unset `publish` is false: nothing is promoted, applied or shipped without the human's OK, and the report must name the commands left pending. Run the DAG exactly as declared — siblings in parallel, joins waiting for all parents. Stop and report on any command that fails.

Report: parameters resolved, steps executed / skipped with reasons, agents invoked, the enhancement's verdict, the evaluation's needs, and what is left to the human.
