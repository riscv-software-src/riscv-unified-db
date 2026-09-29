# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from udb import Database, ResolutionError
from udb.resolver import YamlResolver, merge_patch


@pytest.mark.parametrize(
    ("target", "patch", "expected"),
    [
        ({"a": "b"}, {"a": "c"}, {"a": "c"}),
        ({"a": "b"}, {"b": "c"}, {"a": "b", "b": "c"}),
        ({"a": "b"}, {"a": None}, {}),
        ({"a": "b", "b": "c"}, {"a": None}, {"b": "c"}),
        ({"a": ["b"]}, {"a": "c"}, {"a": "c"}),
        ({"a": "c"}, {"a": ["b"]}, {"a": ["b"]}),
        ({"a": {"b": "c"}}, {"a": {"b": "d", "c": None}}, {"a": {"b": "d"}}),
        ({"a": [{"b": "c"}]}, {"a": [1]}, {"a": [1]}),
        (["a", "b"], ["c", "d"], ["c", "d"]),
        ({"a": "b"}, ["c"], ["c"]),
        ({"a": "foo"}, None, None),
        ({"a": "foo"}, "bar", "bar"),
        ({"e": None}, {"a": 1}, {"e": None, "a": 1}),
        ([1, 2], {"a": "b", "c": None}, {"a": "b"}),
        ({}, {"a": {"bb": {"ccc": None}}}, {"a": {"bb": {}}}),
    ],
)
def test_merge_patch_matches_rfc_7386_appendix_a(target, patch, expected) -> None:
    original_target = deepcopy(target)
    original_patch = deepcopy(patch)

    assert merge_patch(target, patch) == expected
    assert target == original_target
    assert patch == original_patch


def test_inheritance_deep_merges_maps_and_replaces_other_values() -> None:
    documents = {
        "objects.yaml": {
            "first": {
                "nested": {"from_first": 1, "winner": "first"},
                "sequence": [1, 2],
                "nullable": "first",
            },
            "second": {
                "nested": {"from_second": 2, "winner": "second"},
                "sequence": [3],
                "nullable": None,
            },
            "child": {
                "$inherits": ["#/first", "#/second"],
                "nested": {"from_child": 3, "winner": "child"},
                "sequence": [],
            },
        }
    }

    resolved = YamlResolver(documents).resolve()["objects.yaml"]

    assert resolved["child"] == {
        "$child_of": ["#/first", "#/second"],
        "nested": {
            "from_first": 1,
            "from_second": 2,
            "from_child": 3,
            "winner": "child",
        },
        "sequence": [],
        "nullable": None,
    }


def test_remove_deletes_immediate_keys_after_nested_resolution() -> None:
    documents = {
        "objects.yaml": {
            "base": {"keep": 1, "drop": 2, "nested": {"keep": 3, "drop": 4}},
            "child": {
                "$inherits": "#/base",
                "$remove": "drop",
                "nested": {"$remove": ["drop", "missing"], "added": 5},
            },
        }
    }

    child = YamlResolver(documents).resolve()["objects.yaml"]["child"]

    assert child == {
        "$child_of": "#/base",
        "keep": 1,
        "nested": {"keep": 3, "added": 5},
    }


def test_remove_in_a_later_parent_does_not_act_as_a_cross_parent_patch() -> None:
    documents = {
        "objects.yaml": {
            "first": {"keep": 1, "drop": 2},
            "second": {"$remove": "drop", "added": 3},
            "child": {"$inherits": ["#/first", "#/second"]},
        }
    }

    child = YamlResolver(documents).resolve()["objects.yaml"]["child"]

    assert child == {
        "$child_of": ["#/first", "#/second"],
        "keep": 1,
        "drop": 2,
        "added": 3,
    }


def test_same_file_cross_file_nested_and_root_references() -> None:
    documents = {
        "parents.yaml": {
            "nested": {"base": {"value": 1}},
            "root_value": 2,
        },
        "children.yaml": {
            "same_parent": {"value": 3},
            "same_child": {"$inherits": "#/same_parent", "own": 4},
            "cross_child": {"$inherits": "parents.yaml#/nested/base", "own": 5},
        },
        "root-child.yaml": {"$inherits": "parents.yaml#", "root_value": 6},
    }

    resolved = YamlResolver(documents).resolve()

    assert resolved["children.yaml"]["same_child"] == {
        "$child_of": "#/same_parent",
        "value": 3,
        "own": 4,
    }
    assert resolved["children.yaml"]["cross_child"] == {
        "$child_of": "parents.yaml#/nested/base",
        "value": 1,
        "own": 5,
    }
    assert resolved["root-child.yaml"]["root_value"] == 6
    assert resolved["root-child.yaml"]["nested"] == {"base": {"value": 1}}


@pytest.mark.parametrize(
    "reference",
    ["#/middle/inherited", "parent.yaml#/middle/inherited"],
)
def test_pointer_can_address_a_path_created_by_inheritance(reference: str) -> None:
    parent_path = "child.yaml" if reference.startswith("#") else "parent.yaml"
    documents = {
        "parent.yaml": {
            "base": {"inherited": {"value": 1}},
            "middle": {"$inherits": "#/base"},
        },
        "child.yaml": {"child": {"$inherits": reference, "own": 2}},
    }
    if parent_path == "child.yaml":
        documents["child.yaml"]["base"] = {"inherited": {"value": 1}}
        documents["child.yaml"]["middle"] = {"$inherits": "#/base"}

    child = YamlResolver(documents).resolve()["child.yaml"]["child"]

    assert child["value"] == 1
    assert child["own"] == 2


def test_reference_to_a_resolved_sibling_inside_an_inheriting_object_is_not_a_cycle() -> None:
    documents = {
        "nodes.yaml": {
            "base": {"x": 1},
            "child": {
                "$inherits": "#/base",
                "first": {"k": 1},
                "second": {"$inherits": "#/child/first", "own": 2},
            },
        }
    }

    child = YamlResolver(documents).resolve()["nodes.yaml"]["child"]

    assert child["x"] == 1
    assert child["second"] == {
        "$child_of": "#/child/first",
        "k": 1,
        "own": 2,
    }


def test_json_pointer_unescapes_tokens_and_indexes_arrays() -> None:
    documents = {
        "objects.yaml": {
            "a/b": {"~name": [{"value": 7}]},
            "empty": {"": {"empty_key": True}},
            "escaped": {"$inherits": "#/a~1b/~0name/0", "own": 8},
            "empty_key": {"$inherits": "#/empty/", "own": 9},
        }
    }

    resolved = YamlResolver(documents).resolve()["objects.yaml"]

    assert resolved["escaped"] == {
        "$child_of": "#/a~1b/~0name/0",
        "value": 7,
        "own": 8,
    }
    assert resolved["empty_key"] == {
        "$child_of": "#/empty/",
        "empty_key": True,
        "own": 9,
    }


def test_provenance_is_global_deterministic_and_does_not_propagate() -> None:
    documents = {
        "parent.yaml": {"base": {"value": 1}},
        "children.yaml": {
            "one": {"$inherits": "parent.yaml#/base", "value": 2},
            "two": {"$inherits": "parent.yaml#/base", "value": 3},
            "grandchild": {"$inherits": "#/one", "value": 4},
        },
    }

    forward = YamlResolver(documents).resolve()
    reverse = YamlResolver(dict(reversed(documents.items()))).resolve()

    assert forward == reverse
    assert forward["parent.yaml"]["base"]["$parent_of"] == [
        "children.yaml#/one",
        "children.yaml#/two",
    ]
    assert forward["children.yaml"]["one"]["$parent_of"] == "children.yaml#/grandchild"
    assert "$parent_of" not in forward["children.yaml"]["grandchild"]
    assert forward["children.yaml"]["grandchild"]["$child_of"] == "#/one"


def test_nested_inherited_provenance_is_not_copied_or_reinterpreted() -> None:
    resolved = YamlResolver(
        {
            "objects.yaml": {
                "base": {"value": 1},
                "parent": {"nested": {"$inherits": "#/base"}},
                "child": {"$inherits": "#/parent"},
            }
        }
    ).resolve()["objects.yaml"]

    assert resolved["base"]["$parent_of"] == "objects.yaml#/parent/nested"
    assert resolved["parent"]["$parent_of"] == "objects.yaml#/child"
    assert resolved["parent"]["nested"]["$child_of"] == "#/base"
    assert resolved["child"]["nested"] == {"value": 1}


def test_root_child_provenance_keeps_legacy_trailing_slash_spelling() -> None:
    resolved = YamlResolver(
        {
            "parent.yaml": {"base": 1},
            "child.yaml": {"$inherits": "parent.yaml#", "own": 2},
        }
    ).resolve()

    assert resolved["child.yaml"]["$child_of"] == "parent.yaml#"
    assert resolved["parent.yaml"]["$parent_of"] == "child.yaml#/"


def test_shared_parents_and_repeated_resolution_do_not_alias_or_mutate_inputs() -> None:
    documents = {
        "objects.yaml": {
            "base": {"nested": {"value": 1}, "items": [1]},
            "left": {"$inherits": "#/base", "nested": {"left": True}},
            "right": {"$inherits": "#/base", "nested": {"right": True}},
        }
    }
    original = deepcopy(documents)
    resolver = YamlResolver(documents)

    first = resolver.resolve()
    first["objects.yaml"]["left"]["nested"]["value"] = 99
    first["objects.yaml"]["left"]["items"].append(2)
    second = resolver.resolve()

    assert documents == original
    assert second["objects.yaml"]["base"]["nested"]["value"] == 1
    assert second["objects.yaml"]["right"]["nested"] == {"value": 1, "right": True}
    assert second["objects.yaml"]["right"]["items"] == [1]


def _write_yaml(root: Path, relative: str, contents: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def test_database_resolve_applies_overlay_trees_in_order_and_adds_records(tmp_path: Path) -> None:
    base = tmp_path / "base"
    first_overlay = tmp_path / "first"
    second_overlay = tmp_path / "second"
    _write_yaml(
        base,
        "ext/Xbase.yaml",
        """\
kind: extension
name: Xbase
description: base
nested:
  retained: true
  winner: base
removed: base
""",
    )
    _write_yaml(
        first_overlay,
        "ext/Xbase.yaml",
        """\
nested:
  first: true
  winner: first
removed: null
""",
    )
    _write_yaml(
        second_overlay,
        "ext/Xbase.yaml",
        """\
nested:
  winner: second
""",
    )
    _write_yaml(
        first_overlay,
        "ext/Xnew.yaml",
        """\
kind: extension
name: Xnew
description: overlay-only record
""",
    )

    source = Database.from_path(base)
    resolved = source.resolve(overlays=(first_overlay, second_overlay))

    assert source.is_resolved is False
    assert resolved.is_resolved is True
    assert resolved.extension("Xbase").to_dict() == {
        "kind": "extension",
        "name": "Xbase",
        "description": "base",
        "nested": {"retained": True, "first": True, "winner": "second"},
    }
    assert resolved.extension("Xnew")["description"] == "overlay-only record"
    assert set(resolved.documents) == {"ext/Xbase.yaml", "ext/Xnew.yaml"}


@pytest.mark.parametrize(
    ("documents", "message"),
    [
        ({"a.yaml": {"a": {"$inherits": "#/missing"}}}, "missing"),
        ({"a.yaml": {"a": {"$inherits": "missing.yaml#/base"}}}, "missing.yaml"),
        ({"a.yaml": {"base": 1, "a": {"$inherits": "#/base"}}}, "mapping"),
        ({"a.yaml": {"a": {"$inherits": 7}}}, "inherits"),
        ({"a.yaml": {"a": {"$inherits": "#/bad~2escape"}}}, "escape"),
        ({"a.yaml": {"items": [], "a": {"$inherits": "#/items/0"}}}, "0"),
    ],
)
def test_invalid_inheritance_references_are_descriptive(documents, message: str) -> None:
    with pytest.raises(ResolutionError, match=message):
        YamlResolver(documents).resolve()


@pytest.mark.parametrize(
    "documents",
    [
        {"same.yaml": {"a": {"$inherits": "#/b"}, "b": {"$inherits": "#/a"}}},
        {
            "a.yaml": {"a": {"$inherits": "b.yaml#/b"}},
            "b.yaml": {"b": {"$inherits": "a.yaml#/a"}},
        },
    ],
)
def test_inheritance_cycles_report_the_reference_chain(documents) -> None:
    with pytest.raises(ResolutionError, match=r"(?i)cycl") as error:
        YamlResolver(documents).resolve()

    message = str(error.value)
    assert "a.yaml" in message or "same.yaml" in message
    assert "#/a" in message
