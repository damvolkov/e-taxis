# fallacies — the errors chance invites

Each is refuted the same way: compute the probability instead of feeling it. Name it, then show the number.

| Fallacy | The error | The correction |
|---|---|---|
| **Base-rate neglect** | judging on the likelihood, ignoring how rare the event is | multiply by the prior; a strong test on a rare event still yields a low posterior |
| **Prosecutor's fallacy** | reading `P(evidence \| innocent)` as `P(innocent \| evidence)` | invert with Bayes; the two differ by the base rate |
| **Conjunction fallacy** | rating "A and B" more likely than "A" (the plausible-story bias) | `P(A∧B) ≤ P(A)` always; detail lowers probability |
| **Gambler's fallacy** | expecting independent trials to "balance out" | independent events have no memory; past flips don't shift the next |
| **Hot-hand / clustering** | reading streaks in randomness as a pattern | random sequences look clumpy; test against a null before believing a trend |
| **Survivorship bias** | studying only the winners that remain visible | the sample is conditioned on survival; the failures carry the signal |
| **Selection / sampling bias** | inferring from a non-representative sample | ask how the data was collected before what it says |
| **Simpson's paradox** | a trend reverses when groups are combined or split | the aggregate can contradict every subgroup; find the confounder before concluding |
| **Regression to the mean** | attributing a return-to-average to your intervention | extremes are partly noise; the next measurement drifts back on its own |
| **Multiple comparisons** | one "significant" result out of many tests | more tests, more false positives; correct the threshold or pre-register |
| **p-value worship** | treating p<0.05 as truth and effect size as irrelevant | a tiny effect can be "significant" at scale; report the interval and the magnitude |
| **Overconfidence** | narrow intervals, 90% claims right 60% of the time | calibrate; widen until the stated confidence matches the hit rate |

The discipline: when a claim about chance feels obvious, that feeling is the warning. Steelman it, then decide it with arithmetic — the number is the argument.
