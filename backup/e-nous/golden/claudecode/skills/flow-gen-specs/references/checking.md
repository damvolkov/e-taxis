# checking — el ojo mecánico

El nodo `spec/check` de `op eval run spec [backend]` lee `specs/tekton/<backend>/sources.yml`, obtiene cada fuente por su `kind` y diff-ea contra el snapshot anterior en `~/.local/state/e-nous/specs/`. Cero tokens, cero juicio: produce señales (`SignalMetrics`) o silencio, y `common/needs` las convierte en necesidades `drift`. El primer run sobre una fuente registra la línea base.

| kind | mecanismo | hecho que se guarda |
|---|---|---|
| `atom` | feed de releases/tags/commits | títulos de entradas; el primero, versión |
| `api` | JSON por forma: release, lista, dist-tags | `tag@fecha`, números de issue, pares `tag=versión` |
| `npm` | registry `/latest` | la versión |
| `json` | JSON schema → propiedades a dos niveles | espacio de claves diff-eable |
| `markdown` / `html` | texto de la página | índice: conjunto de enlaces https (página nueva = superficie nueva); en `changelog`/`deprecations`: líneas con `deprecated/removed/no longer` |
| `git` | — | nada: esa fuente la abre el agente por señal, no el checker |

**Semántica del diff.** `baseline registrado` la primera vez que se ve una fuente; las señales empiezan en la segunda pasada. `+N nueva(s)` / `-N desaparecida(s)` con cuatro ejemplos. `versión X → Y` cuando el campo de versión de la fuente se movió. Una fuente que falla el fetch emite señal `fetch fallido` — un enlace roto es mantenimiento, no ruido.

**Dónde no manda el checker.** Qué pesa cada señal y qué hace el run con ella lo decide el router de la skill (`SKILL.md`), que es el único hub: este fichero describe el instrumento, no el juicio. El gate estructural (`op eval specs`) es otro instrumento: valida el contrato de las specs, no la verdad de upstream.

**Cadencia.** El snapshot es memoria de máquina, no corpus: se puede borrar (`--reset`) sin tocar nada del repo. La cadencia la fija el cron de Damien; el comando es idempotente entre pasadas.
