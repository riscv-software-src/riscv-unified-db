# Copyright (c) 2026 Hitesh Sai
# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Tests for the parameter emitter and validator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML

sys.path.insert(0, str(Path(__file__).resolve().parent))

from param_emitter import (
    PARAM_DIR,
    ParamCandidate,
    ParamValidationError,
    audit,
    draft7_keywords,
    emit,
    render,
    validate_candidate,
)

YAML_SAFE = YAML(typ="safe")


def make(**overrides) -> ParamCandidate:
    """A minimal valid candidate, with fields overridable per test."""
    base = {
        "name": "DEMO_WIDTH",
        "long_name": "Width of the demo register",
        "description": "Number of implemented bits in the demo register.",
        "schema": {"type": "integer", "minimum": 0, "maximum": 64},
        "defined_by": {"extension": {"name": "Sm"}},
    }
    base.update(overrides)
    return ParamCandidate(**base)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def test_minimal_candidate_is_valid():
    assert validate_candidate(make()) == []


def test_name_must_match_schema_pattern():
    problems = validate_candidate(make(name="bad_name"))
    assert any("does not match" in p for p in problems)


def test_missing_required_field_is_rejected():
    # long_name is required by param_schema.json.
    candidate = make()
    doc = candidate.to_yaml_dict()
    del doc["long_name"]

    from param_emitter import validate_doc

    problems = validate_doc(doc)
    assert any("long_name" in p for p in problems)


def test_unknown_schema_keyword_is_reported():
    """A misspelled keyword is silently ignored by validators; flag it.

    param_schema.json sets additionalProperties: false on the `schema` subschema,
    but as a sibling of $ref, which draft-07 ignores. See issue #2173.
    """
    problems = validate_candidate(make(schema={"type": "integer", "minimun": 8}))
    assert any("minimun" in p for p in problems)


def test_non_strict_mode_defers_entirely_to_the_schema():
    """Without the advisory checks, the verdict is whatever param_schema.json says.

    That verdict is expected to change: once the inert `additionalProperties` on
    the `schema` subschema is repaired (issue #2173), the misspelling below starts
    being rejected by the schema itself. This test therefore asserts the two modes
    stay consistent with each other rather than pinning a particular answer.
    """
    candidate = make(schema={"type": "integer", "minimun": 8})
    lenient = validate_candidate(candidate, strict=False)
    strict = validate_candidate(candidate, strict=True)

    # Strict mode always reports the typo; lenient mode reports it only once the
    # schema can. Either way, strict must never be the weaker of the two.
    assert any("minimun" in p for p in strict)
    assert len(strict) >= len(lenient)


def test_unbounded_integer_is_reported():
    problems = validate_candidate(make(schema={"type": "integer"}))
    assert any("unconstrained" in p for p in problems)


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "integer", "minimum": 0},
        {"type": "integer", "maximum": 64},
        {"type": "integer", "enum": [8, 16, 32, 64]},
        {"type": "integer", "const": 64},
        {"$ref": "schema_defs.json#/$defs/64bit_unsigned_pow2"},
    ],
)
def test_constrained_integers_are_accepted(schema):
    assert validate_candidate(make(schema=schema)) == []


def test_non_integer_types_are_not_subject_to_the_bounds_check():
    assert validate_candidate(make(schema={"type": "boolean"})) == []


def test_requirements_are_optional_and_emitted_when_present():
    candidate = make(requirements={"idl()": "MXLEN == 32 -> DEMO_WIDTH <= 32;\n"})
    assert validate_candidate(candidate) == []
    assert "requirements:" in render(candidate)


def test_source_excerpt_is_never_emitted():
    """The excerpt is provenance for review, not a schema field."""
    candidate = make(source_excerpt="The demo register is an XLEN-bit read-write register.")
    text = render(candidate)
    assert "source_excerpt" not in text
    assert "XLEN-bit read-write" not in text


# --------------------------------------------------------------------------- #
# Emission
# --------------------------------------------------------------------------- #


def test_rendered_output_has_license_header_and_schema_hint():
    text = render(make())
    assert text.startswith("# Copyright (c)")
    assert "SPDX-License-Identifier: BSD-3-Clause-Clear" in text
    assert "yaml-language-server: $schema=../../../schemas/param_schema.json" in text


def test_rendered_output_parses_and_round_trips():
    candidate = make()
    doc = YAML_SAFE.load(render(candidate))
    assert doc["$schema"] == "param_schema.json#"
    assert doc["kind"] == "parameter"
    assert doc["name"] == "DEMO_WIDTH"
    assert doc["schema"] == {"type": "integer", "minimum": 0, "maximum": 64}
    assert doc["definedBy"] == {"extension": {"name": "Sm"}}


def test_rendered_output_ends_with_exactly_one_newline():
    text = render(make())
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_multiline_description_uses_a_block_scalar():
    candidate = make(description="First line.\n\nSecond paragraph.\n")
    text = render(candidate)
    assert "description: |" in text
    # The escaped one-line form would contain a literal \n sequence.
    assert "\\n" not in text


def test_render_refuses_an_invalid_candidate():
    with pytest.raises(ParamValidationError) as excinfo:
        render(make(name="bad_name"))
    assert "bad_name" in str(excinfo.value)


def test_emit_writes_a_file_that_validates(tmp_path):
    path = emit(make(), out_dir=tmp_path)
    assert path.name == "DEMO_WIDTH.yaml"

    doc = YAML_SAFE.load(path.read_text(encoding="utf-8"))
    from param_emitter import validate_doc

    assert validate_doc(doc) == []


def test_emit_refuses_to_clobber_by_default(tmp_path):
    emit(make(), out_dir=tmp_path)
    with pytest.raises(FileExistsError):
        emit(make(), out_dir=tmp_path)
    # ...but will replace when asked.
    assert emit(make(), out_dir=tmp_path, overwrite=True).exists()


def test_emit_does_not_write_when_validation_fails(tmp_path):
    with pytest.raises(ParamValidationError):
        emit(make(name="bad_name"), out_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_emitted_file_uses_lf_line_endings(tmp_path):
    path = emit(make(), out_dir=tmp_path)
    assert b"\r\n" not in path.read_bytes()


# --------------------------------------------------------------------------- #
# Fidelity against the existing database
# --------------------------------------------------------------------------- #


def test_every_existing_parameter_passes_schema_validation():
    """The validator must agree with the database as it stands.

    Run without the advisory checks, this is exactly param_schema.json, so any
    failure here means the validator is wrong rather than the data.
    """
    assert audit(strict=False) == {}


def test_existing_parameters_can_be_reloaded_as_candidates_and_re_emitted(tmp_path):
    """Round-trip every real parameter file through the emitter.

    Each file is read, rebuilt as a ParamCandidate, and re-emitted. The re-emitted
    document must be semantically identical to the original. This checks the
    emitter reproduces the full variety of real `schema` and `definedBy` shapes,
    not just the simple ones in the unit tests above.

    Key order and scalar style are deliberately not compared: existing files vary
    in both, and the emitter normalises them.
    """
    paths = sorted(PARAM_DIR.glob("*.yaml"))
    assert paths, "no parameter files found"

    for path in paths:
        original = YAML_SAFE.load(path.read_text(encoding="utf-8"))
        candidate = ParamCandidate(
            name=original["name"],
            long_name=original["long_name"],
            description=original["description"],
            schema=original["schema"],
            defined_by=original["definedBy"],
            requirements=original.get("requirements"),
        )
        reloaded = YAML_SAFE.load(render(candidate, strict=False))

        for key in ("$schema", "kind", "name", "long_name", "schema", "definedBy"):
            assert reloaded[key] == original[key], f"{path.name}: {key} changed"
        assert reloaded.get("requirements") == original.get("requirements"), path.name
        # Description is re-flowed as a block scalar, so compare content.
        assert reloaded["description"].strip() == original["description"].strip(), path.name


def test_draft7_keywords_come_from_the_vendored_metaschema():
    kw = draft7_keywords()
    assert "minimum" in kw
    assert "propertyNames" in kw
    assert "minimun" not in kw
    # Draft 2019-09 keyword, deliberately absent from draft-07.
    assert "unevaluatedProperties" not in kw
