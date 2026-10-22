# antipatterns — testing

❌ the smell, ✅ the fix, with the cost.

| ❌ Antipattern | Cost | ✅ Fix |
|---|---|---|
| tautological test — restates the implementation | green forever, proves nothing | assert the observable outcome, derived independently |
| change-detector — `mock.assert_called_with(what_I_passed)` | dies at every refactor, catches no bug | assert the value, row or event the collaborator produced |
| a test nobody watched fail | green for the wrong reason — bad import, unbound fixture, skipped | break the code or switch the feature off; confirm the red is the expected one |
| asserting on internals — private attrs, call counts, call order | couples the test to the structure, not the behaviour | rendered text, response, DB row, published event, exit code |
| mocking what you own | tests the mock, not the code | a pure core that needs no mock → `arch-py-adt` |
| one regression test per bug, by default | suite bloat, duplicate coverage, slower every fix | only when the behaviour had a genuine gap; otherwise extend the parametrize |
| `sleep` to wait for async work | flaky under load, slow when it passes | wait on the condition, with a timeout → `conc-py-async` |
| weakening, skipping or deleting a red test to go green | throws away the only information the suite produced | fix the code, or fix the expectation and say why |
| the simplest scenario as the acceptance test | passes while the product is broken | the medium-hard case — several entities, restored state, backwards compat, the misconfiguration the default protects against |
| shared mutable state between tests | order-dependent runs, ghost failures | per-test state, isolated and torn down by its fixture |
| one test asserting several behaviours | a failure names the test, not the cause | one behaviour per test, named after it |
