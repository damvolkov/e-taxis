# lib — the inference, UQ and calibration stack

The tools that turn probabilistic reasoning into computation. The reasoning is the skill; the numeric primitives (`scipy.stats`, `numpy.Generator`, `math.fsum`) are `algo-py-numeric`, and model training is `ml`. Acceleration here is JAX/Numba/C (XLA, GPU), not Rust — the state of the art regardless. Verify against `flow-gen-research` before pinning. Dates: 2026-09.

## By software category

The probabilistic stack × the categories where uncertainty is first-class.

| Category | Probabilistic stack |
|---|---|
| **ML pipeline** | `MAPIE` conformal intervals on predictions; calibration; `scipy.stats` |
| **Evaluation harness** | metric intervals, proper scoring (`sklearn.metrics`), `MAPIE` risk control for LLM-judge |
| **Agent system** | calibrated tool/route confidence; Thompson sampling for explore/exploit |
| **API service** | `scipy.stats` for online A/B and rate anomaly; tail-latency reasoning |
| **ML pipeline (modeling)** | `PyMC`/`NumPyro` when the model itself is Bayesian |
| **Async worker** | Monte Carlo / sampling jobs (`numpy.Generator`, offloaded) |
| **Voice / CLI / script / library** | usually none — reasoning applies, no heavy dep |

## Primary tools

| Tool | Role | Reach for it when | License · maturity |
|---|---|---|---|
| `PyMC` | high-level Bayesian modeling (PyTensor → C/JAX/Numba) | build and fit a Bayesian model in readable syntax | Apache-2.0 — v5, mature |
| `NumPyro` · `BlackJAX` | low-level JAX inference (fast NUTS, modular samplers) | speed/GPU or a custom sampler; a PyMC backend | Apache-2.0, JAX |
| `MAPIE` | conformal prediction — distribution-free intervals/sets, risk control | a guaranteed error rate on any model, incl. LLM-judge | BSD-3, scikit-learn-contrib — v1 (2026) |
| `scikit-learn` · `netcal` | calibration (curves, temperature/isotonic) + proper scoring (log-loss, Brier) | check or fix a model's confidence | BSD / Apache-2.0 |

Diagnostics and reporting → `ArviZ` (posterior checks, trace plots); formula-style GLMs → `Bambi` (on PyMC). Raw distributions, tests and RNG → `scipy.stats` + `numpy.Generator` (`algo-py-numeric`).

**Never:** a point estimate reported without its interval · ranking probabilistic models by accuracy instead of a proper score · trusting a single eval run · assuming exchangeability for conformal without checking it · a Bayesian framework where a base-rate calculation on paper would do.

## Testing

Property-check the reasoning: a posterior moves monotonically with the likelihood ratio; a calibrated forecaster's reliability curve sits on the diagonal within tolerance; conformal coverage hits its target rate on held-out data (± sampling error). `hypothesis` for the invariants, a fixed seed for reproducibility → `test-py-tdd`.
