# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from udb import (
    Database,
    DataReference,
    ObjectNotFoundError,
    ReferenceError,
    ResolutionError,
    SchemaError,
    SchemaReference,
)

REPO_ROOT = Path(__file__).parents[2]


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_raw_sources_capture_comments_typed_keys_and_idl_scalar_span(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "ext/Xsource.yaml",
        """\
# document comment
kind: extension
name: Xsource
values:
  7: seven # defining comment
# IDL source
operation(): |
  return 1;
""",
    )

    record = Database.from_path(tmp_path).extension("Xsource")
    numeric = record.source_at("values", 7)
    operation = record.source_at("operation()")

    assert numeric is not None
    assert numeric.start_line == 5
    assert numeric.comments == ("# defining comment",)
    assert operation is not None
    assert operation.start_line == 7
    assert operation.style == "|"
    assert operation.comments == ("# IDL source",)
    assert record.to_dict()["values"] == {7: "seven"}
    assert record.sources is not None
    with pytest.raises(FrozenInstanceError):
        record.sources.document = "changed.yaml"  # type: ignore[misc]
    with pytest.raises(TypeError):
        record.sources[("values", 7)] = operation  # type: ignore[index]


def test_inheritance_and_overlays_retain_actual_defining_sources(tmp_path: Path) -> None:
    base = tmp_path / "base"
    overlay = tmp_path / "overlay"
    _write(
        base,
        "ext/Parent.yaml",
        """\
kind: extension
name: Parent
nested:
  inherited: parent
  replaced: parent
items: [base]
delete_me: base
""",
    )
    _write(
        base,
        "ext/Child.yaml",
        """\
kind: extension
name: Child
$inherits: ext/Parent.yaml#
nested:
  own: child
""",
    )
    _write(
        overlay,
        "ext/Parent.yaml",
        """\
nested:
  replaced: overlay
items: [overlay]
delete_me: null
""",
    )

    resolved = Database.from_path(base).resolve(overlays=(overlay,))
    child = resolved.extension("Child")

    assert child["nested"] == {
        "inherited": "parent",
        "replaced": "overlay",
        "own": "child",
    }
    assert child["items"] == ("overlay",)
    assert "delete_me" not in child
    inherited = child.source_at("nested", "inherited")
    replaced = child.source_at("nested", "replaced")
    own = child.source_at("nested", "own")
    array_item = child.source_at("items", 0)
    assert inherited is not None and inherited.source == "ext/Parent.yaml"
    assert inherited.layer == "source"
    assert replaced is not None and replaced.layer == "overlay[0]"
    assert own is not None and own.source == "ext/Child.yaml"
    assert array_item is not None and array_item.layer == "overlay[0]"


def test_inheritance_errors_point_to_original_yaml_field(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "ext/Bad.yaml",
        "kind: extension\nname: Bad\nnode:\n  $inherits: missing.yaml#/value\n",
    )

    with pytest.raises(ResolutionError, match=r"ext/Bad\.yaml:4:14.*#/node/\$inherits"):
        Database.from_path(tmp_path).resolve()


def test_multiple_inheritance_parent_links_retain_each_reference_span(tmp_path: Path) -> None:
    _write(tmp_path, "ext/A.yaml", "kind: extension\nname: A\n")
    _write(tmp_path, "ext/B.yaml", "kind: extension\nname: B\n")
    _write(
        tmp_path,
        "ext/Child.yaml",
        "kind: extension\nname: Child\n$inherits:\n  - ext/A.yaml#\n  - ext/B.yaml#\n",
    )

    resolved = Database.from_path(tmp_path).resolve()
    first = resolved.source_at("ext/A.yaml", "$parent_of")
    second = resolved.source_at("ext/B.yaml", "$parent_of")
    assert first is not None and (first.start_line, first.start_column) == (4, 5)
    assert second is not None and (second.start_line, second.start_column) == (5, 5)


def test_yaml_merge_members_point_to_their_anchor(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "ext/Merged.yaml",
        """\
kind: extension
name: Merged
defaults: &defaults
  inherited: anchor
effective:
  <<: *defaults
  own: local
""",
    )

    record = Database.from_path(tmp_path).extension("Merged")
    inherited = record.source_at("effective", "inherited")
    own = record.source_at("effective", "own")
    assert inherited is not None and inherited.start_line == 4
    assert own is not None and own.start_line == 7


def test_source_mapping_handles_yaml_numeric_spelling_and_merge_precedence(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "ext/MergeShapes.yaml",
        """\
kind: extension
name: MergeShapes
numeric:
  0x7: seven
defaults: &defaults
  value:
    nested: parent
first:
  <<: *defaults
  value: child
second:
  value: child
  <<: *defaults
""",
    )

    record = Database.from_path(tmp_path).extension("MergeShapes")
    assert record.source_at("numeric", 7).start_line == 4  # type: ignore[union-attr]
    assert record["first"]["value"] == "child"
    assert record["second"]["value"] == "child"
    assert record.source_at("first", "value").start_line == 10  # type: ignore[union-attr]
    assert record.source_at("second", "value").start_line == 12  # type: ignore[union-attr]


def test_yaml_merge_shape_replacements_discard_stale_descendant_sources(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "ext/MergeReplacement.yaml",
        """\
kind: extension
name: MergeReplacement
mapping: &mapping
  item:
    nested: true
scalar: &scalar
  item: scalar
explicit:
  <<: *mapping
  item: scalar
sequence:
  <<: [*scalar, *mapping]
""",
    )

    record = Database.from_path(tmp_path).extension("MergeReplacement")
    assert record["explicit"]["item"] == "scalar"
    assert record["sequence"]["item"] == "scalar"
    assert record.source_at("explicit", "item").start_line == 10  # type: ignore[union-attr]
    assert record.source_at("sequence", "item").start_line == 7  # type: ignore[union-attr]
    assert record.source_at("explicit", "item", "nested") is None
    assert record.source_at("sequence", "item", "nested") is None


def test_duplicate_identities_fail_during_resolution(tmp_path: Path) -> None:
    for directory in ("one", "two"):
        _write(
            tmp_path,
            f"ext/{directory}/Same.yaml",
            "kind: extension\nname: Same\n",
        )

    with pytest.raises(ResolutionError, match=r"duplicate 'extension' identity 'Same'"):
        Database.from_path(tmp_path).resolve()


def test_schema_error_uses_the_overlay_field_span(tmp_path: Path) -> None:
    base = tmp_path / "base"
    overlay = tmp_path / "overlay"
    schemas = tmp_path / "schemas"
    schemas.mkdir()
    (schemas / "demo_schema.json").write_text(
        json.dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$id": "v0.1",
                "type": "object",
                "properties": {"count": {"type": "integer"}},
            }
        ),
        encoding="utf-8",
    )
    (schemas / "json-schema-draft-07.json").write_text(
        json.dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$id": "http://json-schema.org/draft-07/schema#",
                "type": ["object", "boolean"],
            }
        ),
        encoding="utf-8",
    )
    _write(
        base,
        "ext/X.yaml",
        "$schema: demo_schema.json#\nkind: extension\nname: X\ncount: 1\n",
    )
    _write(overlay, "ext/X.yaml", "count: wrong\n")

    with pytest.raises(SchemaError, match=r"overlay\[0\]:ext/X\.yaml:1:8.*\$\.count"):
        Database.from_path(base, schemas_path=schemas).resolve(overlays=(overlay,), validate=True)


def test_data_references_are_lazy_typed_and_allow_cycles(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "profile/A.yaml",
        """\
kind: profile
name: A
peer: { $ref: profile/B.yaml#/items/0 }
schema_value: { $ref: schema_defs.json#/$defs/uint64 }
""",
    )
    _write(
        tmp_path,
        "profile/B.yaml",
        """\
kind: profile
name: B
items:
  - back: { $ref: profile/A.yaml# }
""",
    )
    resolved = Database.from_path(tmp_path).resolve()

    peer = resolved.reference_at("profile/A.yaml", "peer")
    schema = resolved.reference_at("profile/A.yaml", "schema_value")
    assert isinstance(peer, DataReference)
    assert isinstance(schema, SchemaReference)
    assert peer.target.value["back"]["$ref"] == "profile/A.yaml#"
    back = peer.target.child("back").reference()
    assert isinstance(back, DataReference)
    assert back.target.value["name"] == "A"
    assert len(resolved.references()) == 3


def test_data_reference_json_pointer_and_invalid_array_indexes(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "profile/Target.yaml",
        "kind: profile\nname: Target\nvalues:\n  - { 'a/b': { '~key': hit } }\n",
    )
    _write(
        tmp_path,
        "profile/Origin.yaml",
        "kind: profile\nname: Origin\nlink: { $ref: 'profile/Target.yaml#/values/0/a~1b/~0key' }\n",
    )
    resolved = Database.from_path(tmp_path).resolve()
    reference = resolved.reference_at("profile/Origin.yaml", "link")
    assert isinstance(reference, DataReference)
    assert reference.target.value == "hit"

    _write(
        tmp_path,
        "profile/Origin.yaml",
        "kind: profile\nname: Origin\nlink: { $ref: 'profile/Target.yaml#/values/\u0660' }\n",
    )
    invalid = Database.from_path(tmp_path).resolve().reference_at("profile/Origin.yaml", "link")
    with pytest.raises(ReferenceError, match="missing value"):
        assert isinstance(invalid, DataReference)
        _ = invalid.target


def test_reference_pointer_percent_decoding_and_node_boundaries(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "profile/Target.yaml",
        "kind: profile\nname: Target\n'': empty\n'~1': tilde-one\n"
        "a:\n  b: nested\n'a/b': literal\nitems: [zero]\n",
    )
    _write(
        tmp_path,
        "profile/Origin.yaml",
        "kind: profile\nname: Origin\nlink: { $ref: 'profile/Target.yaml#/a%2Fb' }\n",
    )
    resolved = Database.from_path(tmp_path).resolve()
    reference = resolved.reference_at("profile/Origin.yaml", "link")
    assert isinstance(reference, DataReference)
    assert reference.target.value == "nested"
    _write(
        tmp_path,
        "profile/Origin.yaml",
        "kind: profile\nname: Origin\n"
        "empty: { $ref: 'profile/Target.yaml#/' }\n"
        "escaped_once: { $ref: 'profile/Target.yaml#/~01' }\n",
    )
    pointer_cases = Database.from_path(tmp_path).resolve()
    empty = pointer_cases.reference_at("profile/Origin.yaml", "empty")
    escaped_once = pointer_cases.reference_at("profile/Origin.yaml", "escaped_once")
    assert isinstance(empty, DataReference) and empty.target.value == "empty"
    assert isinstance(escaped_once, DataReference) and escaped_once.target.value == "tilde-one"
    _write(
        tmp_path,
        "profile/Origin.yaml",
        "kind: profile\nname: Origin\nlink: { $ref: 'profile/Target.yaml#/bad%2' }\n",
    )
    with pytest.raises(ReferenceError, match="percent escape"):
        Database.from_path(tmp_path).resolve().reference_at("profile/Origin.yaml", "link")
    with pytest.raises(ObjectNotFoundError):
        resolved.node("profile/Target.yaml", "items", -1)
    with pytest.raises(ObjectNotFoundError):
        resolved.node("profile/Target.yaml", "items", True)


def test_malformed_reference_uri_reports_the_ref_value_span(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "profile/Origin.yaml",
        "kind: profile\nname: Origin\nlink:\n  $ref: 'http://['\n",
    )
    resolved = Database.from_path(tmp_path).resolve()

    with pytest.raises(
        ReferenceError,
        match=r"profile/Origin\.yaml:4:9: invalid reference URI 'http://\['",
    ):
        resolved.reference_at("profile/Origin.yaml", "link")

    _write(
        tmp_path,
        "profile/Origin.yaml",
        "kind: profile\nname: Origin\nlink:\n  $ref: '\\bad.yaml#'\n",
    )
    invalid_path = Database.from_path(tmp_path).resolve()
    with pytest.raises(
        ReferenceError,
        match=r"profile/Origin\.yaml:4:9: data reference path must use POSIX separators",
    ):
        invalid_path.reference_at("profile/Origin.yaml", "link")


def test_embedded_parameter_schema_refs_are_not_data_refs(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "param/P.yaml",
        "kind: parameter\nname: P\nschema:\n  $defs: { local: { type: integer } }\n"
        "  allOf:\n    - { $ref: '#/$defs/local' }\n",
    )
    resolved = Database.from_path(tmp_path).resolve()
    reference = resolved.reference_at("param/P.yaml", "schema", "allOf", 0)
    assert isinstance(reference, SchemaReference)


def test_nodes_from_different_databases_are_not_equal(tmp_path: Path) -> None:
    _write(tmp_path, "profile/A.yaml", "kind: profile\nname: A\n")
    first = Database.from_path(tmp_path).resolve()
    second = Database.from_path(tmp_path).resolve()
    assert first.node("profile/A.yaml") != second.node("profile/A.yaml")


def test_all_standard_data_references_resolve_and_schema_refs_stay_distinct() -> None:
    resolved = Database.from_path(
        REPO_ROOT / "spec" / "std" / "isa", schemas_path=REPO_ROOT / "spec" / "schemas"
    ).resolve()
    references = resolved.references()

    data = [reference for reference in references if isinstance(reference, DataReference)]
    schemas = [reference for reference in references if isinstance(reference, SchemaReference)]
    assert data
    assert schemas
    for reference in data:
        _ = reference.target
