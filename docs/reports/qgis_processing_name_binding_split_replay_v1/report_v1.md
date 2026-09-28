# QGIS Processing Name-Binding Split Replay v1

- Input parents: 20 fully normalized sources with two to six whole-scope
  operators and existing `recover_call_graph` or `split_subworkflow` routing.
- Source SHA verification: 20/20; splitter failures: 0.
- Local units emitted: 63; 31 are single-step local units and 32 are deferred.
- Eligible two-to-six local units: 0; training rows emitted: 0.
- Deferred reasons are pre-existing fail-closed families: control flow
  (`if` 15, `try` 8, `for` 4), downstream data transforms 18, low-level edit
  transforms, and two legacy positional Processing signatures.
- No rule is changed for this population. The Name-binding family is closed at
  zero trainable local units under the frozen Processing boundary contract.
