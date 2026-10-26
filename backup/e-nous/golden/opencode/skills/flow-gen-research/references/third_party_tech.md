# third_party_tech — researching a third-party technology

For anything bigger than a package: a database, a queue, a framework, a model, an MCP server. Same law: **never one source.** Cross popularity + maturity + independent evidence + health + lifecycle. Distrust any benchmark the vendor published about itself.

## Flow

1. **DISCOVER** candidates — landscapes, best-of lists, MCP registry.
2. **FILTER by maturity** — Tech Radar, CNCF level, `endoflife.date`.
3. **VERIFY guarantees** — Jepsen (data & queues), independent reproducible benchmarks.
4. **MEASURE health** — deps.dev + GitHub (last release, open issues, contributors).
5. **DECIDE** with the project's preference (managed vs self-hosted, Rust/C backend, async-first).
6. **DATE every datum** — rankings and leaderboards expire.

## Recipe 1 — Ecosystem maps (what exists)

| Source | Use | URL |
|---|---|---|
| CNCF Landscape | cloud-native infra: queues, DBs, observability, orchestration; shows Sandbox/Incubating/Graduated | `https://landscape.cncf.io` |
| LF AI & Data Landscape | ML / AI / data infra | `https://landscape.lfai.foundation` |
| OSSInsight Collections | repo comparison by category | `https://ossinsight.io/collections` |
| best-of lists | rankings with a quality score | `https://github.com/best-of-lists/best-of` |
| awesome lists | broad catalogs, no score — discover only | `https://github.com/sindresorhus/awesome` |

## Recipe 2 — Maturity & expert opinion (what to adopt)

| Source | Use | URL |
|---|---|---|
| Thoughtworks Technology Radar | Adopt / Trial / Assess / Hold; semi-annual | `https://www.thoughtworks.com/radar` |
| InfoQ Trends Reports | adoption curve per area | `https://www.infoq.com/trends/` |
| CNCF maturity levels | Graduated ≈ production-ready | `https://www.cncf.io/projects/` |
| Stack Overflow Developer Survey | real usage, "admired vs desired" | `https://survey.stackoverflow.co` |

## Recipe 3 — Databases & storage

| Source | Use | URL |
|---|---|---|
| DB-Engines Ranking | popularity by type (relational, vector, TS, KV…) | `https://db-engines.com/en/ranking` |
| **Jepsen** | correctness under fault (consistency, data loss) — decisive | `https://jepsen.io/analyses` |
| ClickBench | reproducible OLAP analytics benchmark | `https://benchmark.clickhouse.com` |
| ANN-Benchmarks | vector search (recall vs QPS) | `https://ann-benchmarks.com` |
| TPC | audited standard benchmarks (H, C, DS) | `https://www.tpc.org` |
| Database of Databases (CMU) | technical fact-sheet for hundreds of DBs | `https://dbdb.io` |

## Recipe 4 — Queues, streaming, messaging

| Source | Use | URL |
|---|---|---|
| CNCF Landscape → Streaming & Messaging | map of NATS, Kafka, Pulsar, RabbitMQ… | `https://landscape.cncf.io` |
| Jepsen | real delivery guarantees per system | `https://jepsen.io/analyses` |
| OpenMessaging Benchmark | standard throughput/latency benchmark | `https://openmessaging.cloud/docs/benchmarks/` |

## Recipe 5 — Frameworks & software performance

| Source | Use | URL |
|---|---|---|
| TechEmpower Benchmarks | web frameworks by language | `https://www.techempower.com/benchmarks/` |
| endoflife.date (+ API) | support & EOL of runtimes, DBs, frameworks | `https://endoflife.date/docs/api` |
| deps.dev | stars, dependents, OpenSSF Scorecard (multi-ecosystem) | `https://deps.dev` |
| OpenSSF Scorecard | repo security health | `https://scorecard.dev` |

## Recipe 6 — Agentic world (models, agents, MCP)

| Source | Use | URL |
|---|---|---|
| MCP Registry (official API) | MCP servers, verified namespace | `https://registry.modelcontextprotocol.io/v0/servers?search={q}` |
| PulseMCP / Glama / Smithery | MCP directories with usage, quality, maintenance | `https://www.pulsemcp.com` · `https://glama.ai/mcp/servers` · `https://smithery.ai` |
| Artificial Analysis | models & providers: quality, price, speed | `https://artificialanalysis.ai` |
| LMArena | human preference between models | `https://lmarena.ai` |
| SWE-bench / Terminal-Bench | agentic capability in code & terminal | `https://www.swebench.com` · `https://www.tbench.ai` |
| OpenRouter Rankings | real model usage by tokens | `https://openrouter.ai/rankings` |
| Hugging Face | open-weight models, datasets, leaderboards | `https://huggingface.co` |

**Search tips.** For infra, read the CNCF *maturity badge* before the star count — Graduated is a stronger signal than any ranking. For data systems, a Jepsen analysis outweighs every benchmark: correctness first, speed second. For models, cross one preference board (LMArena) with one capability benchmark (SWE-bench) with one economics table (Artificial Analysis) — never decide on a single leaderboard, and re-check it, because they move weekly.
