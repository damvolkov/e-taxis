# scheduling — el run desatendido

El mantenimiento de specs son dos planos y un workflow. `op eval run spec` mide la deriva upstream (cero tokens) y la deja como necesidades `drift`; `op enhance run spec --from latest` monta a `speckeeper` (hidden, tier scout, `edit` solo bajo `specs/`, preload `flow-gen-specs`) **en un sandbox**, con las señales exactas que registró esa evaluación — nunca re-descargadas. El workflow `smaintenance` encadena ambos, una revisión del `auditor`, y —solo con `publish=true`— promote y `op transpiler bench`.

**El informe es el producto.** Cada run deja en `.reports/<run>/`: `command.json`, `ledger.jsonl`, `report.md`, y en la mejora `patches/spec/<backend>.patch`:

- `check` — las señales tal cual las emitió el ojo (`SignalMetrics`)
- `needs` — cada señal como necesidad `drift`
- `speckeeper` — la réplica del agente y los ficheros tocados **medidos por git** en el sandbox, no afirmados
- `law` · `candidate` · `grade` — el contrato de specs, un render limpio, el peso por la matriz
- `decide` — `adopt` si el grado cabe en `settings.promote.spec` (`deepening`), `propose` si mueve un `status:`

**Lo que el run nunca hace.**

1. Tocar fuera de `specs/tekton/<backend>/` — ni `core/`, ni `ops/`, ni `sources.yml`. El detector solo lo amplía un humano (regla 2 de la skill).
2. Promocionar a `ready` sin spec completa y fuentes citadas leídas hoy — puede, pero está obligado a decirlo con la fuente que lo justifica.
3. `op enhance promote` sin `publish=true`, y `op transpiler apply` nunca: el corpus vivo lo toca el humano con plan previo.
4. Ampliarse permisos, reescribirse el brief o declararse limpio tras un gate rojo.
5. Borrar una spec: la retirada es `status: obsolete` con nota.

**Idempotencia.** Dos evaluaciones seguidas sobre el mismo estado: la segunda no ve señales (los snapshots ya registraron el estado) y el enhancer no tiene nada que hacer.
