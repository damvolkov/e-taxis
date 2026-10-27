# algo-py-core — query set

Two cases: one that must load the skill, one near miss its rightful owner wins.

```toml
[[case]]
prompt = "ordeno una lista de tuplas por el segundo campo y me sale O(n²)"
expect = ["algo-py-core"]
reads = ["structures.md"]

[[case]]
prompt = "monta un makefile con lint y test"
reject = ["algo-py-core"]
owner = ["ops-gen-make"]
skips = ["nowhere.md"]
```
