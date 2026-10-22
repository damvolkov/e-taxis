# skills — authoring a skill end to end

The create operation for the skill kind. The gate order and the source contract live in `SKILL.md`; this is the pipeline that turns a need into a green skill.

## 1. Model the domain

Before naming anything, know the bounded context: the entities, the one decision the skill governs, the trigger a user would phrase. If you can't state the single decision, the skill isn't ready — split it or drop it.

## 2. Name by the law

`<domain>-<scope>-<topic>`:
- **domain** — the primary decision, from the `README.md` catalog (never the tool).
- **scope** — the artifact's language (`gen/py/rs/sh/sql/en/es`); agnostic-to-libraries is still `py` if the artifact is Python.
- **topic** — one concept word, or a technology name only when the domain *is* that technology; never a library (libraries live in `lib.md`); two words → broaden the topic, move the detail to a reference.

Folder name == frontmatter `name`. Torn between two domains → pick the decision, not the tool.

## 3. Write the router

Copy `TEMPLATE.md`. `SKILL.md` is a router: ≤60 lines, ≤7 imperative checkable rules, one canonical sample. The description is `<Scope>: <what>. Use when <trigger>.`, ≤200 chars, trigger keywords front-loaded. Async-first for operations/stack skills; agnostic for paradigm/format skills.

## 4. Push depth to references

One `snake_case` file per independent topic or library; a reference never links another reference (`SKILL.md` is the only hub); point to other skills by `→ skill-name`, never into their files. Each layer references the one below, never duplicates it.

## 5. Write lib.md (or document its absence)

The single place vendors are named: the target × software-category matrix, builtin > Rust-backed > C/C++ > pure Python, async-first, 3–4 primaries, every datum dated (re-verify → `flow-gen-research`). Pure taxonomy/routing/method → omit and document: `- No lib.md — <reason>; governs no library dimension.`

## 6. Gate, then eval, then commit

Run the deterministic gate; fix every violation. Only when green, eval activation precision and iterate the description. Commit only after both gates pass.

## Staging for auto-generated candidates

A skill proposed by `opencode-autolearn` is a *candidate*, not a skill: it lands in staging, passes this pipeline (gate + eval above threshold), and only then moves to production. Never let a generated candidate go live ungated.
