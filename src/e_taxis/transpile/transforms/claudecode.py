"""transforms.claudecode: the named transforms of `specs/tekton/claudecode.yaml`, one handler per contract there.

`TRANSFORMS` is the table the renderer reads; a test holds it equal to the spec's `transforms:` block.

`ClaudeWorkflow` turns a core workflow into a Claude Code dynamic workflow (`workflows/<id>.js`): a script the Workflow
tool runs, with no shell and no filesystem of its own. So taxis stays the executor of every deterministic decision:
each node is one promise that waits only for its parents; a command step, a step whose upstream is not green, or one
whose `when` does not hold is `taxis workflow step` — the engine's own step, its ledger, its exit-3 skip — run by a
cheap agent that answers the step's JSON line; a semantic step that is due runs its house agent (`agentType`), and a
cheap scribe keeps the answer through `taxis workflow put`, typed downstream exactly as in the engine. A loop's copies
`<id>_<k>` run in order; the engine idles those after the loop ended. `{{param}}` binds at run time in the script.
`readonly`, `steps` and `timeout` have no Workflow-API equivalent: the house agent's own tools are the fence here."""

import json
import re
import shlex
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from e_taxis.transpile.models.error import RenderError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from e_taxis.transpile.engine.context import RowContext

##### DEFAULTS #####
BACKEND: str = "claudecode"
### the lead's own agent: a step with an instruction and no actor is the lead acting directly (engine LEAD).
LEAD: str = "orchestrator"
### the cheap tier for the plumbing agents (run a command, write an answer): never the reasoning.
PLUMBING: str = "haiku"
UNSAFE: Final[re.Pattern[str]] = re.compile(r"\W")
PRELUDE: Final[str] = """const Q = s => "'" + String(s).replace(/'/g, "'\\\\''") + "'"
const NOUS = P.nous ? ` --nous ${Q(P.nous)}` : ''
const KV = Object.entries(P).filter(([k]) => k !== 'rundir' && k !== 'nous').map(([k, v]) => ' ' + Q(`${k}=${v}`)).join('')
const STEP = {type: 'object', required: ['node', 'status'], properties: {node: {type: 'string'}, status: {type: 'string'}, reason: {type: 'string'}, out: {type: 'string'}}}
const green = r => Boolean(r) && (r.status === 'ok' || r.status === 'idle')
const bind = s => s.replace(/\\{\\{(\\w+)\\}\\}/g, (m, k) => k === 'rundir' ? RUNDIR : k in P ? String(P[k]) : m)

async function run(id, phase) {
  return agent(`Run exactly this one command with the Bash tool and nothing else. Whatever its exit code, answer with the JSON object printed on its last stdout line.\\n\\ntaxis workflow step ${Q(id)} --workflow ${Q(WORKFLOW)} --rundir ${Q(RUNDIR)}${NOUS}${KV}`, {label: id, phase, model: PLUMBING, effort: 'low', schema: STEP})
}

async function think(id, actor, instruction, deps) {
  const answer = await agent(`${bind(instruction)}\\n\\nThis run's folder is ${RUNDIR}; the output of each step you depend on (${deps.join(', ') || 'none'}) is ${RUNDIR}/nodes/<step>/out.md.`, {label: id, phase: id, agentType: actor})
  const file = `${RUNDIR}/nodes/${id}/answer.md`
  return answer === null ? run(id, id) : agent(`Write the text between the markers, verbatim and nothing else, to ${file} with the Write tool. Then run exactly this one command with the Bash tool and answer with the JSON object printed on its last stdout line.\\n\\ntaxis workflow put ${Q(id)} --workflow ${Q(WORKFLOW)} --rundir ${Q(RUNDIR)}${NOUS} --file ${Q(file)}\\n\\n<<<ANSWER\\n${answer}\\nANSWER>>>`, {label: `${id} · keep`, phase: id, model: PLUMBING, effort: 'low', schema: STEP})
}

async function gate(id, deps, due, act) {
  const ups = await Promise.all(deps)
  return act && ups.every(green) && due() ? act() : run(id, id)
}
"""
SIGNALS: Final[tuple[str, ...]] = ("metrics", "logs", "traces")


##### UTILITIES #####
def reaches(entry: Mapping[str, Any] | str, backend: str) -> bool:
    """A bare entry reaches every backend; `{…, backends}` only those it names."""
    return isinstance(entry, str) or backend in (entry.get("backends") or [backend])


##### TYPES #####
class ClaudeWorkflow:
    """One core workflow manifest → the text of `workflows/<id>.js`."""

    __slots__ = ("_decl",)

    def __init__(self, decl: Mapping[str, Any]) -> None:
        self._decl = decl

    ##### PRIVATE #####

    @staticmethod
    def _render_js(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _render_var(ident: str) -> str:
        return f"n_{UNSAFE.sub('_', ident)}"

    def _render_looped(self) -> tuple[str, ...]:
        return tuple((self._decl.get("loop") or {}).get("nodes") or ())

    def _render_deps(self, depends: Sequence[str]) -> str:
        """A node's parents as promises: a looped parent is the loop's last copy."""
        looped = self._render_looped()
        names = dict.fromkeys("n_loop" if dep in looped else self._render_var(dep) for dep in depends)
        return f"[{', '.join(names)}]"

    def _render_when(self, node: Mapping[str, Any]) -> str:
        checks = [
            f"{self._render_js([values] if isinstance(values, str) else list(values))}.includes(String(P[{self._render_js(key)}] ?? ''))"
            for key, values in (node.get("when") or {}).items()
        ]
        return " && ".join(checks) or "true"

    def _render_node(self, node: Mapping[str, Any]) -> str:
        ident, depends = node["id"], list(node.get("depends") or [])
        act = (
            "null"
            if node.get("run")
            else (
                f"() => think({self._render_js(ident)}, {self._render_js(node.get('actor') or LEAD)}, "
                f"{self._render_js(node.get('instruction') or '')}, {self._render_js(depends)})"
            )
        )
        return (
            f"const {self._render_var(ident)} = gate({self._render_js(ident)}, {self._render_deps(depends)}, "
            f"() => {self._render_when(node)}, {act})"
        )

    def _render_loop(self) -> list[str]:
        """The loop as one promise: its copies in order, after what the body waits for outside it."""
        looped = self._render_looped()
        match looped:
            case ():
                return []
            case _:
                pass
        semantic = [node["id"] for node in self._decl["nodes"] if node["id"] in looped and not node.get("run")]
        match semantic:
            case []:
                pass
            case _:
                msg = f"{self._decl['id']}: a loop with agent steps ({', '.join(semantic)}) has no Claude workflow form"
                raise RenderError(msg)
        outside = [
            d
            for node in self._decl["nodes"]
            if node["id"] in looped
            for d in node.get("depends") or []
            if d not in looped
        ]
        body = self._render_js(list(looped))
        return [
            "const n_loop = (async () => {",
            f"  await Promise.all({self._render_deps(outside)})",
            "  let last = null",
            f"  for (let k = 1; k <= {int(self._decl['loop']['max'])}; k++) for (const id of {body}) last = await run(`${{id}}_${{k}}`, id)",
            "  return last",
            "})()",
        ]

    ############################################################

    ##### PUBLIC #####

    def render(self) -> str:
        """The whole script, deterministic: same manifest, same bytes."""
        decl, looped = self._decl, self._render_looped()
        ident = decl["id"]
        meta = {
            "name": ident,
            "description": " ".join(str(decl["description"]).split()),
            "phases": [{"title": node["id"]} for node in decl["nodes"]],
        }
        params = dict.fromkeys(decl.get("parameters") or {}, "")
        steps = [self._render_node(node) for node in decl["nodes"] if node["id"] not in looped]
        finals = [self._render_var(node["id"]) for node in decl["nodes"] if node["id"] not in looped]
        return "\n".join(
            [
                f"export const meta = {self._render_js(meta)}",
                "",
                f"const WORKFLOW = {self._render_js(ident)}",
                f"const PLUMBING = {self._render_js(PLUMBING)}",
                f"const P = Object.assign({self._render_js(params)}, args && typeof args === 'object' ? args : {{}})",
                f"const RUNDIR = String(P.rundir || {self._render_js(f'.reports/{ident}/run')})",
                PRELUDE,
                *self._render_loop(),
                *steps,
                "",
                f"return {{workflow: WORKFLOW, rundir: RUNDIR, steps: await Promise.all([{', '.join([*finals, *(['n_loop'] if looped else [])])}])}}",
                "",
            ]
        )


##### HANDLERS #####
def claude_telemetry(value: Mapping[str, Any], _: RowContext) -> dict[str, str]:
    signals = value["signals"]
    return {
        "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
        **{f"OTEL_{signal.upper()}_EXPORTER": "otlp" for signal in SIGNALS if signal in signals},
        "OTEL_EXPORTER_OTLP_PROTOCOL": value["protocol"],
        "OTEL_EXPORTER_OTLP_ENDPOINT": value["endpoint"],
    }


def claude_hooks(value: Mapping[str, Sequence[Mapping[str, Any]]], ctx: RowContext) -> dict[str, list[dict[str, Any]]]:
    return {
        event: [
            ({"matcher": matcher} if matcher else {})
            | {"hooks": [{"type": "command", "command": shlex.join(ctx.bind(arg) for arg in entry["run"])}]}
            for entry in entries
            for matcher in entry.get("matchers") or [""]
        ]
        for event, entries in value.items()
    }


def claude_plugins(value: list[str], _: RowContext) -> dict[str, bool]:
    return dict.fromkeys(value, True)


def at_imports(value: list[Any], ctx: RowContext) -> str:
    return "".join(
        f"@{ctx.bind(entry if isinstance(entry, str) else entry['path'])}\n"
        for entry in value
        if reaches(entry, BACKEND)
    )


def mcp_claudecode(value: Mapping[str, Any], ctx: RowContext) -> dict[str, Any] | None:
    """One registry entry in the shape Claude stores it, or None when the server does not reach Claude."""
    match (reaches(value, BACKEND), value.get("command")):
        case (False, _):
            return None
        case (_, [head, *args]):
            shape = {
                "type": "stdio",
                "command": ctx.bind(head),
                "args": [ctx.bind(arg) for arg in args],
                "env": {key: ctx.bind(item) for key, item in (value.get("env") or {}).items()},
            }
        case _:
            shape = {"type": "http", "url": ctx.bind(value["url"]), "headers": dict(value.get("headers") or {})}
    return {key: item for key, item in shape.items() if item or key == "args"}


def claude_workflow(_: Any, ctx: RowContext) -> str:
    return ClaudeWorkflow(ctx.instance or {}).render()


##### TABLE #####
TRANSFORMS: Final[Mapping[str, Callable[[Any, RowContext], Any]]] = MappingProxyType(
    {
        "claude_telemetry": claude_telemetry,
        "claude_hooks": claude_hooks,
        "claude_plugins": claude_plugins,
        "at_imports": at_imports,
        "mcp_claudecode": mcp_claudecode,
        "claude_workflow": claude_workflow,
    }
)
