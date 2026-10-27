# algo-py-core — task set

```toml
[[task]]
id = "t1"
split = "train"
prompt = "Deduplicate a list keeping order."
checks = [{ op = "contains", arg = "dict.fromkeys" }]

[[task]]
id = "t2"
split = "val"
prompt = "Top-3 of a stream."
checks = [{ op = "regex", arg = "heapq\\.nlargest" }]

[[task]]
id = "t3"
split = "test"
prompt = "Binary search."
checks = [{ op = "no_refusal" }]
```
