# decisions — choosing under uncertainty

A decision is not a prediction. You act on a distribution of outcomes weighted by what each costs — the probability is only half the calculation.

## Expected value, then expected utility

```
EV = Σ  p(outcome) · value(outcome)
```

- Rank options by expected value, but **value is not linear**: losing the rent is not the negative of gaining it. Weight by **utility** (the real cost/benefit to you), which curves — risk-aversion is rational when a loss is ruinous.
- A positive-EV bet you cannot afford to lose is a bad bet; size to survive the tail, not to maximize the mean.

## Asymmetric loss

The cost of a false positive rarely equals a false negative. A test-suite flake that blocks a deploy and a real bug that ships are not symmetric; a cache miss and a cache serving stale money are not symmetric. Pick the threshold that minimizes **expected loss**, not error rate — move it toward the cheaper mistake.

## Value of information

Measuring costs time; it is worth it only when the result **could change the decision**. If every plausible outcome of the experiment leads to the same action, skip the experiment and act. Compute the decision boundary first, then ask whether new evidence can cross it — this is the probabilistic form of "Determinism first": don't gather data a decision doesn't depend on.

## Explore vs exploit

When repeated choices feed back (which model, which retriever, which config), pure exploitation locks in an early, noisy winner; pure exploration never banks the gains. Bias toward the current best while sampling the alternatives in proportion to their upside and your uncertainty about them (Thompson sampling / UCB). Uncertainty is a reason to explore, not to freeze.

## Tail risk

The mean hides the outcome that ends the game. Reason about p95/p99 and the worst case, not the average: latency SLOs, memory ceilings, financial exposure, a rare prompt that jailbreaks the agent. Design so the tail is survivable; an expected value computed without the tail is a comfortable lie.
