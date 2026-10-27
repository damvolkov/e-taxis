"""models.graphs: every plane graph, declared — which nodes each target's evaluation and enhancement run, in order.

A graph is data: `NodeUse(use, id, depends, params)` per line, the node's own card joined in by the reader. The
evaluator reads the tree (`render` with `tree=working`: the checkout as it stands, or the candidate an evaluation is
asked to measure), states laws and ledgers, and ends every subject with `needs`. The enhancer clones the checkout at
its base (`sandbox`), acts only on a reason (`intake`), lets its proposers write the sandbox (`manual`, `brief` →
`integrate`; `speckeeper` for a spec), renders each subject's candidate, verifies it, weighs it (`grade`), concludes
(`decide`) and cuts the patch `enhance promote` applies.

A skill carries the weekly heuristic measures too: the evaluator's `semantic` (the scan's LLM stage), `activation`
(routing over the base render) and `effect` (`value`: no skill against the skill); the enhancer measures routing on
its base render while the proposers write (`activation_base`), then verifies the candidate's (`activation_candidate`,
read against the base) and its `effect` (`delta`: the skill against the candidate).

Ported from e-nous `ops/{evaluator,enhancer}/graphs/*.md` without the SkillOpt proposer (`skillopt`) and the v1-only
nodes (`replication`, the MCP probes): docs/workflow.md §9 names each."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from e_taxis.workflow.models.plane import NodeUse, Plane, PlaneDecl, Target

##### DEFAULTS #####
SNAPSHOT: Final[NodeUse] = NodeUse(use="snapshot")
RENDER: Final[NodeUse] = NodeUse(use="render", depends=("snapshot",), params={"tree": "working"})
NEEDS: Final[tuple[str, ...]] = ("render",)


##### UTILITIES #####
def evaluate_kind(*gates: NodeUse) -> PlaneDecl:
    """An entity kind's evaluation: the render, its gates over the base render, the needs they add up to."""
    return PlaneDecl(
        summary="an entity as it stands: its law; its needs",
        nodes=(SNAPSHOT, RENDER, *gates, NodeUse(use="needs", depends=(*NEEDS, *(gate.key for gate in gates)))),
    )


def enhance_kind(*gates: NodeUse, measures: tuple[NodeUse, ...] = ()) -> PlaneDecl:
    """An entity kind's enhancement: one writer folds the reasons into the sandbox — `measures` read the base
    meanwhile — the candidate is verified, weighed, decided, and its patch cut."""
    ids, read = tuple(gate.key for gate in gates), tuple(measure.key for measure in measures)
    return PlaneDecl(
        summary="an entity, enhanced on its needs or your directive: one writer, verified, weighed, decided",
        nodes=(
            SNAPSHOT,
            NodeUse(use="sandbox", depends=("snapshot",)),
            NodeUse(use="render", depends=("sandbox",), params={"tree": "sandbox"}),
            NodeUse(use="intake", depends=("render",)),
            NodeUse(use="manual", depends=("intake",)),
            *measures,
            NodeUse(use="brief", depends=("intake",)),
            NodeUse(use="integrate", depends=("manual", "brief"), params={"sources": "brief"}),
            NodeUse(use="candidate", depends=("integrate", "manual")),
            *gates,
            NodeUse(use="grade", depends=("candidate",)),
            NodeUse(
                use="decide",
                depends=("candidate", "grade", "intake", "manual", "brief", "integrate", *read, *ids),
                params={"gates": ",".join(("candidate", "integrate", *ids, "grade")), "proposers": "manual,integrate"},
            ),
            NodeUse(use="patch", depends=("decide",)),
        ),
    )


##### GRAPHS #####
LAW: Final[NodeUse] = NodeUse(use="law", depends=("render",), params={"tree": "base"})
QUERIES: Final[NodeUse] = NodeUse(use="queries", depends=("render",))
TASKS: Final[NodeUse] = NodeUse(use="tasks", depends=("render",))
LAW_CANDIDATE: Final[NodeUse] = NodeUse(
    use="law", id="law_candidate", depends=("candidate",), params={"tree": "candidate"}
)

GRAPHS: Final[Mapping[Plane, Mapping[Target, PlaneDecl]]] = MappingProxyType(
    {
        Plane.EVALUATOR: MappingProxyType(
            {
                Target.SKILL: evaluate_kind(
                    LAW,
                    NodeUse(use="security", depends=("render",), params={"tree": "base"}),
                    NodeUse(use="semantic", depends=("render",), params={"tree": "base"}),
                    QUERIES,
                    TASKS,
                    NodeUse(use="activation", depends=("queries",), params={"tree": "base"}),
                    NodeUse(use="effect", depends=("tasks",), params={"mode": "value"}),
                ),
                Target.AGENT: evaluate_kind(LAW),
                Target.COMMAND: evaluate_kind(LAW),
                Target.WORKFLOW: evaluate_kind(),
                Target.TOOL: evaluate_kind(),
                Target.PERSONA: evaluate_kind(),
                Target.CONFIG: evaluate_kind(),
                Target.SPEC: PlaneDecl(
                    summary="a backend's spec: upstream drift and the spec law; its needs",
                    nodes=(
                        SNAPSHOT,
                        RENDER,
                        NodeUse(use="signals", depends=("snapshot",)),
                        LAW,
                        NodeUse(use="needs", depends=("signals", "law")),
                    ),
                ),
                Target.CORPUS: PlaneDecl(
                    summary="the whole corpus: what the real harness, fenced on the render, loads of it",
                    nodes=(SNAPSHOT, NodeUse(use="loading", depends=("snapshot",))),
                ),
            }
        ),
        Plane.ENHANCER: MappingProxyType(
            {
                Target.SKILL: enhance_kind(
                    LAW_CANDIDATE,
                    NodeUse(
                        use="security", id="security_candidate", depends=("candidate",), params={"tree": "candidate"}
                    ),
                    NodeUse(
                        use="activation",
                        id="activation_candidate",
                        depends=("candidate", "activation_base"),
                        params={"tree": "candidate"},
                    ),
                    NodeUse(use="effect", depends=("candidate", "tasks"), params={"mode": "delta"}),
                    measures=(
                        QUERIES,
                        TASKS,
                        NodeUse(
                            use="activation",
                            id="activation_base",
                            depends=("queries", "intake"),
                            params={"tree": "base"},
                        ),
                    ),
                ),
                Target.AGENT: enhance_kind(LAW_CANDIDATE),
                Target.COMMAND: enhance_kind(LAW_CANDIDATE),
                Target.WORKFLOW: enhance_kind(),
                Target.TOOL: enhance_kind(),
                Target.PERSONA: enhance_kind(),
                Target.CONFIG: enhance_kind(),
                Target.SPEC: PlaneDecl(
                    summary="a backend's spec, updated by the speckeeper on the drift an evaluation found",
                    nodes=(
                        SNAPSHOT,
                        NodeUse(use="sandbox", depends=("snapshot",)),
                        NodeUse(use="render", depends=("sandbox",), params={"tree": "sandbox"}),
                        NodeUse(use="intake", depends=("render",)),
                        NodeUse(use="manual", depends=("intake",)),
                        NodeUse(use="speckeeper", depends=("intake", "manual")),
                        NodeUse(use="candidate", depends=("speckeeper", "manual")),
                        LAW_CANDIDATE,
                        NodeUse(use="grade", depends=("candidate",)),
                        NodeUse(
                            use="decide",
                            depends=("candidate", "grade", "intake", "manual", "speckeeper", "law_candidate"),
                            params={
                                "gates": "candidate,speckeeper,law_candidate,grade",
                                "proposers": "manual,speckeeper",
                            },
                        ),
                        NodeUse(use="patch", depends=("decide",)),
                    ),
                ),
            }
        ),
    }
)
