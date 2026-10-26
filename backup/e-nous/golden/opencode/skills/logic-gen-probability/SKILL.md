---
name: logic-gen-probability
description: "Gen: reasoning under uncertainty — priors/updates, distributions, EV decisions, calibration, conformal intervals, fallacies. Use when weighing a probabilistic judgment or ML-eval uncertainty."
metadata:
  family: philosophy
---

# logic-gen-probability

Chance is the texture of the real, not noise to hide: reason in distributions, hold priors, update on evidence. Owns the *thinking* under uncertainty — for models (calibration, metric intervals, sampling) and for decisions (which option, when to measure, tail risk). The numeric computation is `algo-py-numeric`; model training and inference are `ml`; the survey method is `flow-gen-research`. The inference/UQ stack → `references/lib.md`.

## Rules

1. **A posterior is a prior updated by evidence.** `posterior ∝ prior × likelihood`; the base rate dominates a strong likelihood on a rare event. Reasoning from evidence without a prior is the default error — base-rate neglect. → `references/bayes.md`
2. **A number without its uncertainty is a lie.** Think expectation, spread and **tail**, not a point; report an interval. Designing for the mean ignores the tail that actually hurts. → `references/decisions.md`
3. **Decide by expected value, weighted by asymmetric loss.** The cost of a false positive rarely equals a false negative; weight outcomes by utility, not probability alone. Measure more only when the information can change the decision (value of information). → `references/decisions.md`
4. **Calibration is the currency of a forecast.** A 70% claim must be right 70% of the time; proper scoring (log-loss, Brier) rewards honesty, and overconfidence is the default failure of a model or an LLM-judge. → `references/calibration.md`
5. **An eval metric is an estimate with an interval, not a proof.** One run is a sample; report a confidence or conformal interval, mind sample size and regression to the mean, never over-read a single number. → `references/calibration.md`
6. **Name the fallacy, steelman with the number.** Base-rate neglect, prosecutor's, conjunction, gambler's, survivorship and selection bias, Simpson's paradox — refute a probabilistic claim by computing it, not by intuition. → `references/fallacies.md`
7. **Determinism where a fact exists; probability for the world's uncertainty.** Do not spend a distribution where a native check answers exactly; reserve stochastic reasoning for what is genuinely uncertain. Compute → `algo-py-numeric`; ML → `ml`.

## Sample

```python
# 99% sensitive/specific test, disease base rate 0.5% — a positive is more likely a false alarm.
# Reason in odds, not raw percentages:
prior_odds       = 0.005 / 0.995          # the base rate, before any test
likelihood_ratio = 0.99 / 0.01            # P(+ | disease) / P(+ | healthy)
posterior_odds   = prior_odds * likelihood_ratio   # ≈ 0.497
p_disease        = posterior_odds / (1 + posterior_odds)   # ≈ 0.33, not 0.99
```

The test is "99% accurate" yet a positive means ~33% chance of disease — the base rate, not the likelihood, dominates. This is the shape of most reasoning errors under uncertainty.

## References

- `references/bayes.md` — priors, likelihood, posterior, base rates, incremental update, odds form
- `references/decisions.md` — expected value/utility, asymmetric loss, value of information, explore/exploit, tail risk
- `references/calibration.md` — proper scoring, calibration curves, metric intervals, sample size, conformal prediction
- `references/fallacies.md` — the named probabilistic fallacies and biases, each with its correction
- `references/lib.md` — the stack: Bayesian inference, conformal UQ, calibration, sampling
