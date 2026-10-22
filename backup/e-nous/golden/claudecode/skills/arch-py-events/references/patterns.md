# patterns — topology and coordination

How producers and consumers are wired, and how a multi-step flow holds together.

## Mediator vs broker

- **In-process mediator / event bus** — components in one process publish to a bus that dispatches to handlers. Decouples modules without a network; the whole thing lives and dies with the process. Reach for it inside a single service.
- **Message broker** — a separate system (the transport) carries events between processes/services, with durability and delivery guarantees. The broker choice (NATS, Redpanda, Kafka) is `sys-gen-scaling`; here it is the boundary you publish across.

Start in-process; promote to a broker when a consumer must outlive, scale, or deploy apart from the producer — not before.

## Choreography vs orchestration

Two ways to run a workflow across components:

| | Choreography | Orchestration |
|---|---|---|
| Control | each service reacts to events, no central brain | one orchestrator issues commands and awaits events |
| Coupling | low; add a consumer without touching others | higher; the orchestrator knows every step |
| Visibility | emergent — hard to see the whole flow | explicit — the flow is one readable process |
| Use when | simple fan-out, autonomous services | complex, ordered, needs a visible state machine |

Choreography scales team-autonomy; orchestration scales comprehensibility. Most systems mix: choreography between bounded contexts, an orchestrator within one.

## Sagas

A transaction spanning services cannot two-phase-commit; a **saga** is the substitute: a sequence of local steps, each with a **compensating action** that semantically undoes it if a later step fails (cancel the reservation, refund the charge). It is choreographed (events trigger the next step) or orchestrated (a saga coordinator drives it and runs compensations). The orchestrator's own state is best modeled as a state machine → `arch-py-adt`.

## Reactor / event loop

At the bottom, an event-driven program is a loop that waits for events and dispatches handlers — the async event loop. The concurrency, backpressure and structured-task rules for those handlers are `conc-py-async`; this file is the topology above them.
