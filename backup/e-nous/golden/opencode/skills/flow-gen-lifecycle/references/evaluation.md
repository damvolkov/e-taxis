# evaluation — does it fire, and does it help

Two questions, never one. **Activation**: does the description win the routing decision? **Effect**: did the skill make the output better? A skill can be perfect at the first and negative at the second, and an eval that only measures activation never notices.

## The routing fact

An agent consults a skill only for what it cannot already do well. A simple one-step prompt will not trigger a skill however good the description — the model just does the thing. Two consequences:

- A trivial query is a worthless test case. Write queries substantive enough that consulting a skill is the rational move.
- The failure mode is **under**triggering, not over. The remedy is *not* a longer, pushier description: that budget is tier 2 and is paid on every message. Front-load the trigger keywords and name the artifact the user will actually say.

## Gate 2a — activation

Twenty queries, roughly half positive, half negative.

Realism is the whole game. A query is what a person types: file paths, job context, column names, company names, URLs, typos, lowercase, uneven lengths.

```
Bad   "Format this data"                          ← tests nothing, matches everything
Good  "ok mi jefa me ha pasado un xlsx (está en descargas, algo como
       'Q4 ventas final FINAL v2.xlsx') y quiere una columna con el margen
       en %. Ingresos van en la C y costes en la D creo"
```

**Positives (8–10)** — the same intent in different registers, formal and casual; cases where the user never names the domain or the artifact; uncommon uses; cases where this skill competes with a sibling and should win.

**Negatives (8–10)** — near-misses only. They share vocabulary with the skill and need something else: adjacent domains, ambiguous phrasing a keyword match would swallow. An obviously irrelevant negative measures zero — "escribe un fibonacci" against a PDF skill proves nothing.

Split 60/40 train/test. Iterate the description against the train split, judge on the held-out one. Selecting by train score is overfitting to twenty sentences.

## Gate 2b — effect

Always paired, always launched in the same batch: one run **with** the skill, one **baseline**. Baseline = no skill for a new skill; a snapshot of the previous version for an edit. An unpaired number measures the model, not the skill.

### The discrimination matrix

Read every assertion across both configurations before reading any average:

| with skill | baseline | reading |
|---|---|---|
| pass | pass | non-discriminating — it measures the model; drop the assertion |
| fail | fail | broken assertion, or beyond the model |
| pass | fail | the only cell that proves value |
| fail | pass | **the skill is hurting** — the most valuable signal here |
| high variance | — | flaky assertion or non-deterministic task; fix it before trusting the mean |

Read time and tokens alongside: +50% pass rate for +13 s and +80% tokens is a trade to decide, not a win to assume.

## What the runs say about the skill

- **Every run independently wrote the same helper** → the skill should ship that script. Write it once, bundle it, and no future invocation reinvents it — deterministic beats re-derived (rule #17).
- **The model burns steps on a section** → cut the section and re-measure. Length is never neutral; a rule that changes no behaviour is costing tokens on every trigger.
- **A fix that only works on the eval prompts is overfitting.** You iterate on three examples because the feedback loop is fast; the skill ships to thousands of prompts you will never see.
- **Prefer the reason over the decree.** A model with theory of mind follows an explained constraint further than a capitalised one, and generalises it to cases you did not enumerate. Reserve the absolute form for what is genuinely absolute.
