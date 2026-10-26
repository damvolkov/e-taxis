# persona — the singular identity, in layers of slots

The persona is one entity, not a directory of instances. Its source is a registry of slots in three layers: `core/base/persona.yaml` (Demian, shared by every facet), `core/tekton/persona.yaml` (tekton, the engineer, only) and `core/nomos/persona.yaml` (nomos, the polymath, only). Each layer maps slot → inline text or `{source: persona/<group>/<slot>.md}`, grouped by `self · character · pathos · logos · ethos · telos · world · bond · praxis · techne · voice` — the faculties of a mind (the map and its sources: `core/README.md`). No layer knows files or order: `specs/<harness>/<backend>/persona.yaml` declares the documents, their blocks, their `limit` and the regions the harness owns, and the transpiler renders base + the harness's facets (`FACETS`) into them — `AGENTS.md`/`CLAUDE.md` for the coder, six files for openhuman, three for hermes.

## Update

1. Edit the slot's `.md` in its layer, never a rendered file; hand-editing a target is editing a byte artifact that the next export erases — or, once absorb lands, a harness move to fold back.
2. **Where a slot lives**: abstract and shared → `core/base`; useful only to one harness → that facet. A facet never reads another facet's slot; what both need moves down to base. A slot lives in one layer (the render refuses a duplicate) and lands once per spec (the law refuses a second place).
3. A new slot is a layer entry first, a spec block second, a `matrix.yaml` row third (the coverage gate fails until it is graded). An empty `.md` is a declared slot with nothing in it: the render skips it.
4. **This is the most expensive text in the corpus.** Every slot a coder spec emits is paid on every message, in every runtime; openhuman caps its files (`limit`) and the render refuses past the cap rather than let the harness truncate. Doctrine that belongs to a domain moves to a skill.
5. Gate: `op transpiler plan` before `op transpiler apply`; read the rendered result after.

## Retire / boundaries

There is no retirement, only rewriting, and it is identity work: the persona changes when Damien changes, not when an agent proposes. **Scheduled maintenance must treat persona as read-only** — an audit run may report incoherence between persona and corpus, or a harness that moved a document, but only a human rewrites the self.
