<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Stage 3 conditions and solving

`udb.conditions` parses the UDB condition YAML grammar into immutable expression values. It
supports conjunction, disjunction, exact-one, none-of, negation, implication, extension version
requirements, parameter comparisons and selectors, XLEN, named free terms, and unresolved `idl()`
conditions.
`to_data()` returns a deterministic serializable form, including canonical version requirements.
Because normalization can produce the `true` and `false` identities, `schema_defs.json` v0.4 accepts
Boolean values anywhere a YAML condition is accepted. Named free terms remain an internal algebra
form and are not admitted by the architecture-data schema.

Concrete evaluation uses `TruthValue.TRUE`, `FALSE`, and `UNKNOWN`. An `EvaluationContext`
distinguishes partial configurations from closed worlds, so an omitted extension or parameter can
remain unknown or evaluate false as appropriate. `partial_evaluate()` replaces known subexpressions
and retains the unresolved expression. `normalize()` applies Boolean identities, flattens
associative nodes, removes duplicates, detects complements, and pushes supported negations inward;
it is deterministic and idempotent. `Condition.has_unresolved` detects an IDL boundary without
requiring callers to inspect node types. `FreeTerm` values come from `EvaluationContext.free_terms`
and are distinct from extension requirements whose catalog is missing.

`udb.solver` gives each `ConditionSolver` its own Z3 context, symbols, constraints, and caches.
`SolverContext` supplies extension version catalogs, parameter domains, fixed values, and XLEN.
The solver applies metadata-driven extension compatibility, at-most-one version selection, scalar
and bounded-array domains, array length/index/membership/uniqueness/contains constraints, and the
relationship `XLEN <= MXLEN`. Repeated `check(extra=...)` calls are isolated with solver push/pop.
`finite_check()` enumerates small finite extension, parameter, XLEN, and free-term products without
initializing Z3. The Boolean query helpers use it first and fall back to Z3 when a domain is absent,
infinite, or above the explicit case limit.

`check()` returns `SAT`, `UNSAT`, or `UNKNOWN`. An unresolved IDL node is represented explicitly:
a result whose proof depends on it is deferred as `UNKNOWN`, while truth or contradiction that
holds independently of it remains `SAT` or `UNSAT`. Boolean satisfiability, implication, and
equivalence helpers raise `SolverUnknownError` rather than collapsing `UNKNOWN` to `False`.
Implication and equivalence return true only after a definite unsatisfiability proof of the
corresponding counterexample.
For an unconstrained scalar parameter `oneOf`, homogeneous Boolean, integer, or string choices
provide the Z3 symbol type. Heterogeneous or array-valued choices require an explicit parameter
domain of the appropriate type and otherwise raise `SolverError`; the condition grammar rejects
empty and singleton choice lists.
Models are available after `SAT`; labeled constraints provide Z3 unsat cores and a deterministic
deletion-minimal conflict relative to any unlabeled background constraints.

The Z3 adapter consumes `ParameterDomain` metadata and does not add solver state to the domain
objects. Array solving materializes one symbol per possible index, so a referenced array domain
must have a finite `maxItems`; an unbounded array without a fixed-value length is rejected with
`SolverError`. When `maxItems` exceeds 4096 (for example `HPM_EVENTS`, whose `maxItems` is
`2**64`), only a 64-item prefix is materialized, as in Ruby. The length remains bounded by
`maxItems`, and a constraint that reaches past the prefix (a larger index, an `includes`, a long
fixed value) is over-approximated, so no satisfiable configuration is rejected. Ruby instead ignores
items past index 64. Parameter symbols are lazy, so large array domains that no condition or fixed
value references cost nothing.

`tests/python/test_conditions.py` covers parsing, canonical serialization, three-valued evaluation,
partial evaluation, actual `ExtensionVersionSet` compatibility, actual scalar and array domains,
normalization and De Morgan properties, finite/Z3 agreement, independent solver contexts, models,
unsat diagnostics, XLEN/MXLEN constraints, free terms, and IDL deferral.
Set `UDB_TEST_RUBY=1` to run the representative live differential through
`tests/python/ruby_condition_oracle.rb`. The oracle is test-only; production and installed-package
code never invokes Ruby.

## Ruby test-corpus disposition

- `test_logic.rb` Boolean construction, duplicate terms, evaluation, `to_h`, NNF/De Morgan, and
  equivalence are covered by builder identities, exhaustive Boolean assignments, normalization
  idempotence, serialization round trips, and bidirectional XOR equivalence tests.
- Its prime-implicant, Espresso, `eqntott`, and Tseytin-format tests are replaced by deterministic
  native AST normalization plus semantic Z3 equivalence. Exact minimum textual formulas and an
  exported Tseytin tree are not API contracts.
- Its failing-conjunct diagnostics and the `must` executable are replaced by labeled Z3 unsat cores
  and deterministic deletion-minimal conflicts.
- `test_conditions.rb` XLEN, extension requirements, unconditional and conditional implications,
  local extension/parameter Boolean grammar, parameter comparisons, arrays, assertions, models,
  and unsat cores map to focused Python tests in `test_conditions.py`, `test_domains.py`, and
  `test_versions.py`.
- `test_z3.rb`, `test_z3_extensions.rb`, `test_z3_finite_array.rb`, and
  `test_z3_parameter_constraints.rb` map to typed domain constraints, every comparison operator,
  version catalogs and compatibility boundaries, array equality/index/size/includes/contains/
  uniqueness, repeated push/pop checks, independent contexts, and model tests. Unsupported schema
  forms are rejected by `ParameterDomain` rather than approximated.
- `Constraint` compilation and `test_idl_funcs` are the only condition categories deferred to
  Stage 4. Stage 3 preserves their source text and reason in `UnresolvedIdlCondition`.

The implementation intentionally corrects three reproduced legacy behaviors: empty conjunction
uses the true identity, bit-range extraction uses a full-width mask, and equivalence checks both
directions. Run the durable reproduction with:

```bash
mise exec -- bundle exec ruby tests/python/ruby_condition_defects.rb
```

It reports `false` for the empty conjunction, `true` for a non-equivalent one-way implication, and
`"no"` for extracting `3` from the two-bit value `3`. The Python property tests assert the corrected
results. The Python solver also keeps all mutable solver state on each `ConditionSolver`; the
parallel-context test verifies that fixed values and models do not cross instances.

Z3 is packaged as the `z3-solver>=4.13,<5` Python dependency and locked for offline artifact
installation. Espresso and `eqntott` are removed from condition normalization, and `must` is
removed from conflict diagnostics. None of these tools is downloaded or executed at runtime.
