<!--
Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Python migration bug fixes

This is the running record of confirmed defects in the Ruby implementation
that the Python migration intentionally corrects. An entry belongs here only
after the Ruby behavior has been reproduced or established by the full
differential corpus. Review defects found only in new Python code are fixed and
tested, but are not labeled as Ruby defects.

| # | Confirmed Ruby behavior | Python correction and regression |
| ---: | --- | --- |
| 1 | The overlay merge claims RFC 7386 behavior, but an object patch applied where the target member is absent or non-object is copied directly. Nested `null` members therefore survive instead of deleting from the new empty object. For example, merging `{"a": 1}` with `{"a": {"drop": null, "keep": 2}}` produces `{"a": {"drop": null, "keep": 2}}`. | `merge_patch` implements RFC 7386: an object patch uses an empty object when its target is not an object, recursively removes `null` members, and does not mutate either input. Covered by the RFC Appendix A vectors and the additional nested-null case in [`test_resolution.py`](../tests/python/test_resolution.py). Passing. |
| 2 | `$inherits` fragments are split on `/` without RFC 6901 decoding. Keys containing `/` or `~` cannot be addressed with `~1` or `~0`. | References decode RFC 6901 tokens and reject malformed escapes. Covered by `test_json_pointer_unescapes_tokens_and_indexes_arrays` in [`test_resolution.py`](../tests/python/test_resolution.py). Passing. |
| 3 | `$inherits` pointer components remain strings, so traversing a YAML sequence with a numeric pointer component fails instead of selecting the array element. | Decimal JSON Pointer components index sequences, with invalid and out-of-range indices reported as `ResolutionError`. Covered by `test_json_pointer_unescapes_tokens_and_indexes_arrays` and the invalid-reference cases in [`test_resolution.py`](../tests/python/test_resolution.py). Passing. |
| 4 | A same-file reference is looked up in the raw document before its target is resolved. It cannot address a mapping member created by the target's own inheritance. | Pointer traversal resolves the necessary effective mapping before continuing. Same-file and cross-file forms are covered by `test_pointer_can_address_a_path_created_by_inheritance` in [`test_resolution.py`](../tests/python/test_resolution.py). Passing. |
| 5 | A nested child `$remove` is consumed before that child mapping is deep-merged with the inherited mapping. It therefore cannot remove a nested key supplied by the parent. | `$remove` is applied to each effective mapping after inheritance and child merging. Covered by `test_remove_deletes_immediate_keys_after_nested_resolution` in [`test_resolution.py`](../tests/python/test_resolution.py). Passing. |
| 6 | Cross-file `$parent_of` updates depend on file traversal and cache replacement. In the current standard database, Ruby omits or incompletely records 12 backlinks across instruction type/variable and profile records. | Provenance is collected in a global second pass over resolved documents, independent of input mapping order. The exact 12 current differences are asserted in [`test_resolution_parity.py`](../tests/python/test_resolution_parity.py); all other resolved values must match Ruby. Focused ordering and multi-child behavior is covered in [`test_resolution.py`](../tests/python/test_resolution.py). Passing. |
| 7 | When an inherited mapping contains nested resolved provenance, Ruby copies the nested `$child_of`. The copied reference is then interpreted relative to the child document. If that document has a matching path, Ruby can add a false `$parent_of`; otherwise it leaves stale provenance that describes a relationship in another document. | Inherited content recursively strips `$child_of` and `$parent_of`; provenance is rebuilt only from relationships declared in the source object at that location. Covered by `test_nested_inherited_provenance_is_not_copied_or_reinterpreted` in [`test_resolution.py`](../tests/python/test_resolution.py). Passing. |
| 8 | Inheritance cycles have no explicit detection and recurse until a runtime stack failure. | Same-file and cross-file cycles raise `ResolutionError` with the reference chain. Covered by `test_inheritance_cycles_report_the_reference_chain` in [`test_resolution.py`](../tests/python/test_resolution.py). Passing. |
| 9 | Schema validation normalizes YAML through the repository's pinned JSON 2.21.2. Distinct mapping keys that become the same JSON object name are emitted twice and silently collapse on parse, so `{1 => "bad", "1" => "good"}` validates only the last `"1"` value and the result depends on insertion order. | JSON normalization detects ambiguous keys recursively before schema validation and raises a source-aware `SchemaError`. Both insertion orders and a nested collision are covered by `test_json_key_normalization_rejects_collisions` in [`test_schema.py`](../tests/python/test_schema.py). Passing. |

The Stage 2a differential oracle invokes `Udb::Yaml::Resolver` directly with
`compile_idl: false` and `no_checks: true`, so it measures YAML resolution
without constructing an architecture or compiling IDL. Enable it with:

```sh
UDB_TEST_RUBY=1 mise exec -- uv run pytest -q tests/python/test_resolution_parity.py
```

The 2026-09-29 run compared every YAML document under `spec/std/isa`. It found
only the 12 exact provenance differences recorded in entry 6. The test removes
absolute `$source` paths and normalizes the Ruby output's schema-version prefix;
it does not broadly exclude provenance or other document data.

Schema defaults remain annotations during YAML resolution, matching the current
Ruby resolver's `insert_property_defaults: false`. Strict rejection of missing,
unknown, non-local, malformed, wrong-version, or wrong-dialect schemas is a
documented Python validation policy and is not listed as a Ruby bug without a
separate compatibility decision.
