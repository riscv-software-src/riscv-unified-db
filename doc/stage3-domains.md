<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Stage 3 parameter domains

`udb.domains` turns a parameter's Draft 7 JSON Schema fragment into an immutable,
typed value domain. Domain construction does not mutate the schema, insert its
`default`, contact the network, or initialize a solver.

```python
from udb.domains import IntegerDomain, ParameterDomain
from udb.schema import SchemaStore

store = SchemaStore("spec/schemas")
domain = ParameterDomain.from_schema(
    {
        "allOf": [
            {"$ref": "schema_defs.json#/$defs/uint64"},
            {"not": {"const": 0}},
        ]
    },
    schema_store=store,
    source="ARCH_ID_VALUE",
)

assert isinstance(domain, IntegerDomain)
assert 1 in domain
assert 0 not in domain
```

`ParameterDomain.from_schema()` returns `BooleanDomain`, `IntegerDomain`,
`StringDomain`, `ArrayDomain`, or `EmptyDomain`. The concrete classes expose
normalized metadata for later condition and solver adapters:

- integer `minimum` and `maximum` are `Bound(value, inclusive)` objects;
- scalar `allowed_values` and `excluded_values` preserve deterministic schema
  order;
- arrays expose `min_items`, `max_items`, `prefix_items`, `additional_items`,
  `contains`, and `unique_items`; `domain_for_index()` gives the effective item
  domain at an index;
- `schema` is a deeply immutable copy of the caller's original schema, or the
  exact `allOf` schema produced by `intersection()`.

The factory is the normal construction path. Direct concrete-class construction
is supported for tests and adapters; it validates and freezes collection fields
such as `allowed_values`, `prefix_items`, and `contains` so caller-owned lists
cannot change a domain after construction.

Use `accepts(value)` or `value in domain` for membership. `intersection()` and
`&` construct a new domain without changing either operand. `is_empty`,
`is_finite`, `is_singleton`, and `single_value` cover common condition-evaluation
queries.

Complete enumeration always requires an explicit bound:

```python
values = domain.enumerate_values(limit=100)
```

The method returns every value when the full domain fits. It raises
`InfiniteDomainError` for infinite domains and `EnumerationLimitError` if the
complete finite result would exceed `limit`; it never returns a truncated list.
It also raises `EnumerationLimitError` when proving completeness would exceed a
bounded amount of rejected-candidate work, so a sparse finite domain cannot
silently consume unbounded time.
`cardinality` is an inexpensive exact count when available and `None` for an
infinite or impractically large finite domain. Check `is_finite` to distinguish
those cases. Enumerated JSON arrays are immutable tuples.

The implementation covers every parameter schema in the current standard
database: Boolean, integer, string, and array types; `const`; homogeneous
`enum`; inclusive and exclusive integer bounds; `not` of constants; local
`$ref`; `allOf`; and array `items`, tuple items, `additionalItems`, `minItems`,
`maxItems`, `contains`, and `uniqueItems`. File references require an explicit
`SchemaStore` and use only its offline registry. Fragment-only references such
as `#/$defs/value` resolve within the supplied schema without a store. Reference
cycles raise `DomainError` with the offending reference instead of recursing.

Draft 7 treats integral JSON numbers such as `1.0` as integers and compares
`1.0` equal to `1` for `const`, `enum`, and `uniqueItems`. Membership follows
that rule while enumeration emits canonical Python integers. Booleans remain a
separate type.

Valid Draft 7 features outside the current parameter corpus fail with
`UnsupportedDomainError` rather than being approximated. These currently
include `anyOf` and `oneOf`, string patterns and length constraints, numeric
`multipleOf`, array-valued `const` and `enum`, object and null domains,
unconstrained or nested array items, non-integral numeric bounds, and conditional
schemas. A schema that uses type-specific keywords without restricting values
to that type is also rejected: for example, `{"maximum": 3}` accepts strings
under Draft 7 and cannot be silently narrowed to an integer domain. Solver
encodings are a separate Stage 3 layer and consume the normalized domain model;
this module does not contain a partial solver substitute.

Simple array emptiness is resolved analytically. Arrays combining
`uniqueItems` or `contains` use exact finite-state search up to 64 items, 12
independent `contains` constraints, and 100,000 search states. Shapes exceeding
those non-corpus bounds raise `UnsupportedDomainError`; they are never reported
as nonempty on the basis of an incomplete search.

The Python membership semantics intentionally correct three defects in the
legacy Ruby Z3 adapter: it reads `uniqueItems` (Ruby checked `unique`), applies
`contains` only to elements within the logical array length, and honors
`exclusiveMinimum` and `exclusiveMaximum`. Membership differential tests use
Ruby's JSON Schema validator as the semantic oracle, rather than preserving
those solver bugs. Run the durable Z3 reproduction with:

```bash
mise exec -- bundle exec ruby -Itools/ruby-gems/udb/lib \
  tests/python/ruby_domain_z3_defects.rb
```

The script reports `true` for each invalid value accepted by the legacy solver.
