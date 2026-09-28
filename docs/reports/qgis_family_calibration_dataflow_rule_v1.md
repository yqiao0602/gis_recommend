# QGIS family calibration dataflow rule v1

## Scope

The dissolve -> multipart-to-singleparts calibration auditor now supports a
bounded cross-variable dataflow shape in addition to direct aliases and
subscripted Processing results:

- a Processing result is written through `list.append`, `list.extend`, or
  `list.insert`;
- a later `for item in container` loop iterates that explicit container; and
- the later family call consumes the loop-bound item or an explicitly assigned
  alias.

Arbitrary object mutation, dynamic aliases, unknown container provenance, and
runtime-dependent control flow remain deferred. The rule is intentionally
source-AST based and does not infer dependency from operator order alone.

## Verification

Local regression coverage includes direct aliases, subscripted results,
list/loop propagation, and an unrelated-list negative case. All family-related
tests pass (`47 passed`), and `compileall` plus `git diff --check` pass.

The frozen server packet has not been rerun in this local environment because
its source ledger and packet live under the server-only `/home/qy` diagnostics
path. The prior server evidence remains 70 passed, 16 deferred, zero semantic
or structural failures, 86/86 SHA verified, and zero calibration/holdout SHA
overlap. No training, authority, evaluation, or output data changed.

## Next action

Run the unchanged 86-occurrence packet with this auditor on the server. Only
after the rerun resolves or explicitly bounds the remaining deferred rows may
the family enter independent task/L3/I-O/dedup qualification or batch
expansion.
