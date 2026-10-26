A skill is the **what and the how** — methodology, paradigm, philosophy, the way to do a thing. Rules, not catalogs. Examples default to **pure Python**; a concrete library is named inside a skill only when it is the one you will almost certainly reach for — there is always a library, even if it is stdlib, so naming it in prose is expected. But the **explicit vendor list and its equivalence map live only in `lib.md`.** This distinction is absolute.

Budgets — tiers 1–2 (`AGENTS.md` + every `description`) load on every message, so keep them lean:

- `description` ≤200 chars: `<Scope>: <what it governs>. Use when <trigger>.`
- `SKILL.md` ≤60 lines, ≤7 rules, one sample — a router, not an encyclopedia.
- Depth → `references/<snake_case>.md`: many small files, one per independent topic or library. A reference never links another reference — `SKILL.md` is the only hub. Cross-skill by name: `→ skill-name`.

`lib.md` is **almost always present** — omit it only when the skill governs no library dimension (pure taxonomy). It is the **single place vendors are named with intent**, and it must carry one matrix: the skill's **target** (the entity it governs — design pattern, iterator kind, model kind…) **× software category**, cells = the typical **async / sync** library/framework, or `builtin`. Reach order in every cell: **builtin / Rust-backed → async twin → specialized library**. Date every datum; re-verify → `flow-gen-research`. Full checklist and naming law: `README.md`.
