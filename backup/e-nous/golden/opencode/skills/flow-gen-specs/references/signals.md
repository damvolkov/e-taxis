# signals — de la señal a la fila

Una señal es `(backend, categoría, fuente, detalle)`. Su categoría dice **dónde** mirar, su contenido dice **qué peso** tiene según `core/versioning/matrix.yaml`. La tabla es la única clasificación: una señal que no cabe en ella detiene el run, no se improvisa un grado.

| Categoría | Señal típica | Grado | Qué se mueve |
|---|---|---|---|
| `core` | `versión X → Y` en releases/npm | el que dicten las filas tocadas más abajo | nada por sí sola: es el reloj, avisa de que las otras categorías merecen una pasada |
| `changelog` | línea nueva en notas de release | según su contenido | la categoría que la línea nombre |
| `config` | clave que aparece/desaparece en el JSON schema | `contract` si el harness la responde distinto; `surface` si es puramente aditiva | filas `keys:` de `config.yaml` y el módulo de `core/tekton/config/` que la alimente |
| `entities` | propiedad nueva de frontmatter; página de docs = entidad nueva; formato retirado | propiedad: el grado del slot en la matrix · entidad: `added`/`removed` de `lifecycle` | filas de `<entity>.yaml` (frontmatter keys, slots, plantilla) |
| `tools` | herramienta nueva/renombrada/retirada; permiso renombrado | `surface` / `contract` | `tools.yaml` (pending: nada se emite hasta `ready`) |
| `extensions` | campo de manifest de plugin; evento de hook nuevo | `contract` si cambia el artefacto que se transpila | `config.yaml` (plugins/mcp) y `agent.yaml`/`skill.yaml` según qué emita |
| `cli` | flag/subcomando nuevo | `surface` | solo si el flag altera un artefacto del corpus: ahí, la spec de la forma |
| `deprecations` | línea con `deprecated/removed/no longer` | `contract` | `status: obsolete` en la spec de la entidad retirada, con nota del porqué y la fuente |
| `community` | issue/announcements de diseño | ninguna: es contexto | alimenta el criterio de las anteriores; nunca escribe por sí sola |

**Reglas de clasificación.**

- El grado lo fija la matrix por **slot y entidad**, no la señal: dos señales iguales en backends distintos pesan igual. Si la matrix no tiene la fila, la fila se añade antes (humano), y el test de paridad lo recuerda.
- `release:` de una spec **no es un número upstream**: es la fecha del snapshot de docs que representa (así lo declaró la casa; el checker compara fuentes contra snapshots, nunca contra `release:`).
- Una página de docs nueva no es una entidad nueva: primero es superficie; se convierte en entidad cuando tiene **formato de fichero propio** (como cuando `workflows` ganó página y tiene `workflow.yaml`) y entonces abre spec en `common/` + ambos backends.
- La retirada es la señal más cara: `status: obsolete` conserva el fichero y su nota; borrar una spec borra el historial de su transpilación.
