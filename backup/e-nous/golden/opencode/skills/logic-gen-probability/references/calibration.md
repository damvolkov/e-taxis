# calibration — forecasts, scores, intervals

The ML-eval face of the skill: a model or an LLM-judge emits probabilities and metrics; this is how to tell whether to trust them.

## Calibration

A forecaster is **calibrated** when its stated confidence matches reality: of everything it calls 70%, ~70% is true. Overconfidence — 90% claims that are right 60% of the time — is the default failure of neural nets and LLM-judges.

- **Calibration curve** (reliability diagram): bin predictions by confidence, plot claimed vs observed; deviation from the diagonal is miscalibration.
- **Recalibrate** post-hoc: temperature scaling, Platt/isotonic; a well-ranked but overconfident model becomes usable without retraining.

## Proper scoring rules

Score a probabilistic forecast so that honesty maximizes the score:

- **Log loss** — punishes confident wrong answers hardest; the default for probabilities.
- **Brier score** — mean squared error of the probability; bounded, interpretable.
- Accuracy is not a scoring rule — it ignores confidence and rewards a lucky guess like a sure thing. Never rank probabilistic models by accuracy alone.

## An eval metric is an estimate

One eval run is a **sample**, not a verdict:

- Report a **confidence interval** on the metric; a 2-point gap on 100 examples is noise.
- **Sample size** sets resolution — you cannot detect a 1% change with 50 cases.
- **Regression to the mean** — the top model on run one drifts down on run two; re-rank on repeated runs, never a single leaderboard.

## Conformal prediction — distribution-free intervals

When you need a guaranteed error rate without assuming the distribution, **conformal prediction** wraps any model to emit a prediction *set* (classification) or *interval* (regression) that contains the truth with a chosen coverage (e.g. 90%), under exchangeability. It is model-agnostic, needs only a calibration split, and now extends to **risk control for LLM-as-judge** and segmentation — the modern tool for eval you can put a guarantee on.
