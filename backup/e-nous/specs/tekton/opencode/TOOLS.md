# tools

Dos mitades: `converter/` es el paquete Python (`ecli`: structured ⇄ flat determinista); `agentic/` son los validadores que invocan los agentes. El root `tools/` queda **reservado** para las custom tools TS de OpenCode.

## Built-in tools (OpenCode, verificada 2026-09)

| Tool | Descripción | Permiso que la controla | Notas |
|---|---|---|---|
| `bash` | Ejecuta comandos de shell en el entorno del proyecto | `bash` | `npm install`, `git status`, etc. |
| `edit` | Modifica archivos existentes con reemplazos exactos de texto | `edit` | Vía de edición principal del LLM |
| `write` | Crea archivos nuevos o sobrescribe existentes | `edit` (no tiene permiso propio) | Controlada por la misma clave que `edit`/`apply_patch` |
| `read` | Lee el contenido de archivos | `read` | Soporta rangos de líneas para archivos grandes |
| `grep` | Busca contenido en archivos con regex | `grep` | Filtrado por patrón de archivo |
| `glob` | Encuentra archivos por patrón (`**/*.ts`) | `glob` | Resultados ordenados por fecha de modificación |
| `lsp` (experimental) | Interactúa con servidores LSP: `goToDefinition`, `findReferences`, `hover`, `documentSymbol`, `workspaceSymbol`, `goToImplementation`, `prepareCallHierarchy`, `incomingCalls`, `outgoingCalls` | `lsp` | Solo con `OPENCODE_EXPERIMENTAL_LSP_TOOL=true` (o `OPENCODE_EXPERIMENTAL=true`) |
| `apply_patch` | Aplica patches/diffs a archivos | `edit` (misma clave) | Usa `patchText` con marcadores `*** Update File: ...` |
| `skill` | Carga un `SKILL.md` y lo mete en la conversación | `skill` | |
| `todowrite` | Crea y actualiza listas de tareas durante la sesión | `todowrite` | Deshabilitada por defecto para subagentes; se puede activar |
| `webfetch` | Descarga y lee el contenido de una URL concreta | `webfetch` | Retrieval de una página específica |
| `websearch` | Busca en la web | `websearch` | Solo con provider OpenCode/OpenCode Go, o `OPENCODE_ENABLE_EXA=1` / `OPENCODE_ENABLE_PARALLEL=1`; usa Exa o Parallel sin API key propia |
| `question` | Pregunta al usuario durante la ejecución, con opciones seleccionables | `question` | Útil para clarificar requisitos o decisiones |

**`webfetch` vs `websearch`.** `websearch` para *descubrir* información; `webfetch` para *recuperar* una URL concreta que ya conoces.

## Lo que NO es built-in (completa el sistema)

- **Custom tools** — definidas por nosotros en `.opencode/tool/*.ts` (o `.opencode/tools/`).
- **MCP servers** — tools externas vía protocolo MCP (aquí: `context7`, `serena`).

Ambas se gestionan con el mismo sistema de `permission` que las built-in, incluidos los wildcards (`"mymcp_*": "ask"`).

## Custom tools

*(vacío — aquí se documentará cada tool propia al nacer: nombre, firma, permiso que la gobierna y para qué existe.)*

| Tool | Propósito | Permiso | |
