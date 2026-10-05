<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# IDL condition compilation contract

Slice 18 translates IDL constraints into ordinary `udb.conditions.Condition` values.
It does not introduce a second solver or evaluate unknown parameters to invented defaults.
The public boundary is:

```python
from udb.idl_conditions import compile_idl_condition, resolve_idl_conditions

condition = compile_idl_condition(text, symtab, source=idl_source)
resolved = resolve_idl_conditions(condition_tree, symtab)
```

`symtab` is explicit. The translation module does not import `udb.architecture`.
Compilation parses the `constraint_body` root and type-checks in an independent scope;
neither success nor failure may change the caller's bindings, scope depth, or AST.
`resolve_idl_conditions` recursively replaces `UnresolvedIdlCondition` leaves in every
logical operator without dropping siblings, antecedents, reason metadata, or source
information from failures. Plain condition parsing still needs no architecture.

## Translation

All 50 live standard-database conditions must match the frozen Ruby oracle, after
canonical condition normalization. The two commented-out blocks are not live inputs.
Translation is configuration-independent: configuration values must not fold a symbolic
parameter or an extension-presence predicate into a constant. Compile-time constants,
loop variables, array indices, range endpoints, and comparison values may be evaluated.

Supported constructs are Boolean literals and parameter references; `!`, `&&`, `||`;
implications; the six comparisons; parameter element, bit-range, and size selectors;
`$array_includes?`; `implemented?`, `implemented_version?`, `xlen() == 32/64` and its
inequality form; and statically bounded constraint loops. An unconditional implication
translates to its consequent. A loop unrolls in source order and translates its
implications using the current local iterator value. Empty loops are true. Returns,
unsupported calls/operators, unknown comparison values or indices, and nonterminating
loops produce source-aware explicit errors, never free propositions or silent defaults.

Comparisons with a parameter on the right reverse ordered operators. Thus `3 < P` is
`P > 3`, not `P < 3`. Right-side element access uses the array variable's name, not a
nonexistent accessor on the element node. These are reproduced Ruby defects, not
parity requirements. Equality remains symmetric. A literal expression containing no
symbolic parameters may fold to a Boolean, but a configured parameter stays symbolic.

Finite loop expansion has an explicit configurable ceiling and detects repeated states
or nonprogress where possible. Exceeding the ceiling is an error identifying the loop.
No cache or mutable compiler state is process-global.

## Architecture integration

Every architecture, extension-version, parameter, and configuration requirement is
compiled before its solver encoding. Parameter and extension requirements retain their
original `definedBy` or extension-version antecedent; an absent owner cannot make an
otherwise valid configuration inconsistent. Mixed YAML/IDL logical trees preserve all
ordinary constraints. IDL conditions used in object presence queries are resolved too.

Construction must avoid circular dependence on architecture presence queries: the
translation bootstrap uses database parameter types and symbolic builtin predicates,
not a partly initialized architecture solver. Register files and CSR execution are not
needed to translate constraints. Configuration-dependent globals must not specialize
the condition expressions during this bootstrap.

The resulting architecture has no Stage 3 IDL deferrals for supported constraints.
Generic `_`, `rv32`, and `rv64` pass validity checks; `qc_iu` agrees with the reviewed
Ruby baseline under owner gating. Under `rv32`, the SXLEN invariant proves the seven
64-bit supervisor extensions absent. Invalid custom IDL requirements produce actionable
diagnostics, not a `DEFERRED` success-shaped fallback.

Runtime version callbacks expose solver-proven absence, including version queries
matching no declared catalog version. Ruby returns unknown for such queries in partial
and unconfigured architectures. Live environment parity refines only those unknown
version observations after independently proving the catalog intersection empty.
Possible versions, definite Ruby answers, extension presence and all other observations
remain unchanged. This is an explicit precision difference, not a new Ruby defect.

## Gates

The offline suite compares all frozen translations, checks synthetic boundary cases,
and tests solver integration and owner gating. The Ruby-gated freshness check runs all
four configurations serially. CI registers `regress-python-idl-condition-parity`, and
the installed wheel/sdist gate compiles a constraint and asserts `rv64` is valid with
no Ruby, repository access, or downloads. API documentation describes the boundary.
