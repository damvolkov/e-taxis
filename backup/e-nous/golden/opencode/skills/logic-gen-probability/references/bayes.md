# bayes — priors, likelihood, posterior

The engine of updating a belief. Every judgment under uncertainty is a prior moved by evidence; skip the prior and you skip the answer.

## The rule

```
posterior ∝ prior × likelihood
P(H | E) = P(E | H) · P(H) / P(E)
```

- **prior** `P(H)` — what you believed before this evidence, anchored in the **base rate**.
- **likelihood** `P(E | H)` — how well the hypothesis explains the evidence.
- **posterior** `P(H | E)` — the updated belief; it becomes the prior for the next update.

## Odds form (the one to reason in)

```
posterior_odds = prior_odds × likelihood_ratio
```

Odds multiply, so evidence composes cleanly: `LR = P(E|H) / P(E|¬H)`. An `LR = 99` on a prior of `1:200` gives `~1:2` — a strong test still loses to a rare base rate. Reason in odds and log-odds (evidence adds); convert to probability only at the end.

## Base rates dominate

The most common error is treating `P(E | H)` as if it were `P(H | E)` — the prosecutor's fallacy. A 99%-accurate test for a 0.5%-prevalence disease yields a ~33% posterior on a positive. Always ask: *what was the base rate before the evidence?*

## Updating incrementally

Beliefs are never final: each new observation multiplies the odds. Independent evidence multiplies likelihood ratios; correlated evidence does not (double-counting inflates confidence). Keep the prior explicit and the updates auditable — a belief you cannot decompose into prior × evidence is a belief you cannot correct.

## In practice

Spam filters, medical tests, fraud detection, an LLM-judge's confidence, "is this flake a real regression?" — all are the same shape: a base rate, a signal with a known error profile, and a posterior. Model the base rate first; it is the number people forget and the one that decides.
