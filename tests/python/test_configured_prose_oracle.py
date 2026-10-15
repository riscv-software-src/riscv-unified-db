# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Frozen real Ruby outputs: source inventory, exact text, explicit error outcomes."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest
from regenerate_configured_prose import inventory

from udb import Configuration, Database, ResolvedDatabase
from udb.architecture import ConfiguredArchitecture
from udb.prose import (
    CapturedFailure,
    CapturedProse,
    CodeRecord,
    ParameterState,
    ProseError,
    ProseInputs,
    render_legacy,
    resolve_all_exception_records,
    resolve_exception_records,
    resolved_exception_names,
)

ROOT = Path(__file__).parents[2]
CORPUS = json.loads((ROOT / "tests/python/fixtures/configured_prose.json").read_text())
CONFIGURATIONS = tuple(CORPUS["captures"])
SUPPLEMENT = json.loads(
    (ROOT / "tests/python/fixtures/configured_prose_supplement.json").read_text()
)
NAMES = json.loads((ROOT / "tests/python/fixtures/configured_prose_names.json").read_text())
WHITESPACE = json.loads(
    (ROOT / "tests/python/fixtures/configured_prose_whitespace.json").read_text()
)


def captured_inputs(name: str, corpus=CORPUS) -> ProseInputs:
    facts = corpus["captures"][name]["inputs"]
    parameters = {
        key: ParameterState(value["state"]) if "state" in value else value["value"]
        for key, value in facts["parameters"].items()
    }

    def fact(key, *, codes=False):
        result = facts[key]
        if "error" in result:
            return CapturedFailure(result["error"]["class"], result["error"]["message"])
        return (
            tuple(CodeRecord(**item) for item in result["value"])
            if codes
            else tuple(result["value"])
        )

    return ProseInputs(
        name,
        parameters,
        facts["extensions"],
        fact("possible_xlens"),
        fact("exception_codes", codes=True),
        fact("interrupt_codes", codes=True),
    )


def check_case(name: str, inputs: ProseInputs, corpus=CORPUS) -> tuple[int, int]:
    successes = errors = 0
    for template, expected in zip(
        corpus["templates"], corpus["captures"][name]["expected"], strict=True
    ):
        prose = CapturedProse(template["template"], template["source"], tuple(template["path"]))
        if "error" in expected:
            with pytest.raises(ProseError) as raised:
                render_legacy(prose, inputs)
            diagnostic = raised.value.diagnostic
            assert diagnostic.legacy_error_class == expected["error"]["class"], prose.label
            # Exact Ruby messages, including randomized anonymous-class addresses,
            # are retained in the corpus, not regenerated or output-normalized.
            if expected["error"]["class"] != "NameError":
                assert diagnostic.message == expected["error"]["message"], prose.label
            else:
                constant = expected["error"]["message"].rsplit("::", 1)[-1]
                assert constant in ("CACHE_BLOCK_SIZE", "PMP_GRANULARITY")
                assert diagnostic.code == "unavailable-parameter"
                assert diagnostic.message == f"uninitialized constant {constant}"
            assert diagnostic.prose is prose
            assert diagnostic.configuration == inputs.configuration
            assert diagnostic.tag in prose.text
            errors += 1
        else:
            assert render_legacy(prose, inputs) == expected["value"], prose.label
            successes += 1
    return successes, errors


def test_exact_source_inventory():
    actual = inventory()
    assert json.loads(json.dumps(actual)) == CORPUS["templates"]
    paths = {template["source"] for template in actual}
    assert Counter(path.split("/")[3] for path in paths) == {"csr": 111, "inst": 17}
    assert len(actual) == 255
    assert CORPUS["baseline"] == "d6b06ca3"
    assert sum(template["template"].count("<%") for template in actual) == 1746
    tags = Counter(
        body
        for template in actual
        for body in re.findall(r"<%(.*?)%>", template["template"], re.DOTALL)
    )
    assert len(tags) == 49
    assert tags == {entry["body"]: entry["occurrences"] for entry in CORPUS["tag_inventory"]}


@pytest.mark.parametrize("name", CONFIGURATIONS)
def test_all_frozen_scalar_outputs_and_error_outcomes(name):
    expected_successes = 255 if name in ("cache-small", "cache-large", "h64-mixed-sv57") else 251
    assert check_case(name, captured_inputs(name)) == (expected_successes, 255 - expected_successes)


@pytest.mark.parametrize("name", CONFIGURATIONS)
def test_real_structured_exception_name_consumer(name, source_database):
    capture = CORPUS["captures"][name]["inputs"]["structured_exception_records"]
    assert "value" in capture
    records = tuple(
        CodeRecord(item["num"], item["name"], item["var"], (item["ext"],))
        for item in capture["value"]
    )
    assert resolve_exception_records(records, captured_inputs(name)) == tuple(capture["value"])
    assert all(type(item["ext"]) is str and "<%" not in item["name"] for item in capture["value"])
    if name == "qc_iu":
        source_database = Database.from_path(
            ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas"
        ).resolve(overlays=[ROOT / "spec/custom/isa/qc_iu"])
    assert resolve_all_exception_records(source_database, captured_inputs(name)) == tuple(
        capture["value"]
    )


def test_corrections_are_precise_and_independently_reproduced():
    corrected_indices = {
        index
        for index, template in enumerate(CORPUS["templates"])
        if "implemented_interrupt_codes" in template["template"]
    }
    assert len(corrected_indices) == 3
    for name, case in CORPUS["captures"].items():
        facts = case["inputs"]
        assert facts["interrupt_codes_raw"] == facts["exception_codes_raw"]
        for index, (raw, expected) in enumerate(zip(case["raw"], case["expected"], strict=True)):
            if index not in corrected_indices:
                assert raw == expected
        if name in ("qc_iu", "full64", "cache-small", "cache-large", "cache-unknown"):
            proof = facts["code_selection_reproduction"]
            assert proof == {"h_implemented": False, "vscall_condition": False}
            assert "VScall" in {code["name"] for code in facts["exception_codes_raw"]["value"]}
            assert "VScall" not in {code["name"] for code in facts["exception_codes"]["value"]}


def test_raw_parity_is_separate_from_substitutions_and_errors():
    counts = Counter()
    for name, case in CORPUS["captures"].items():
        for raw, expected in zip(case["raw"], case["expected"], strict=True):
            if "error" in expected:
                assert raw == expected
                counts["explicit_error"] += 1
            elif raw == expected:
                counts["raw_equal"] += 1
            elif "error" in raw:
                assert name in ("cache-malformed", "cache-min-malformed")
                assert raw["error"] == {
                    "class": "ArgumentError",
                    "message": "comparison of Z3::BitvecSort with Z3::BoolSort failed",
                }
                counts["raw_error_substitution"] += 1
            elif name == "h64-mixed-sv57":
                assert case["inputs"]["exception_codes_raw"] == {"value": []}
                counts["synthetic_unsat_substitution"] += 1
            else:
                counts["defect_projection"] += 1
    assert counts == {
        "raw_equal": 3484,
        "defect_projection": 33,
        "raw_error_substitution": 6,
        "synthetic_unsat_substitution": 3,
        "explicit_error": 44,
    }


def test_original_raw_archive_has_not_been_rewritten():
    raw = {name: case["raw"] for name, case in CORPUS["captures"].items()}
    digest = hashlib.sha256(
        json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    assert digest == "efe15672fa29e89c0f046e5e0511e3c5c5164f5f8a6a311112df061eb7f68ffa"


@pytest.mark.parametrize("case", WHITESPACE, ids=lambda case: repr(case["template"]))
def test_extended_whitespace_is_exact_raw_tilt(case):
    inputs = ProseInputs(
        "whitespace",
        {"MXLEN": 64},
        {"H": True, "A": True},
        exception_codes=(CodeRecord(1, "One"), CodeRecord(2, "Two")),
    )
    assert "value" in case["raw"]
    assert render_legacy(CapturedProse(case["template"]), inputs) == case["raw"]["value"]


@pytest.mark.parametrize("name", tuple(SUPPLEMENT["captures"]))
def test_supplemental_real_ruby_scalar_captures(name, source_database):
    assert check_case(name, captured_inputs(name, SUPPLEMENT), SUPPLEMENT) == (
        (251, 4) if name == "mc100-full" else (255, 0)
    )
    inputs = ProseInputs.from_database(
        source_database, Configuration(SUPPLEMENT["configurations"][name]["declaration"])
    )
    assert check_case(name, inputs, SUPPLEMENT) == ((251, 4) if name == "mc100-full" else (255, 0))
    assert resolve_all_exception_records(source_database, inputs) == tuple(
        SUPPLEMENT["captures"][name]["inputs"]["structured_exception_records"]["value"]
    )


@pytest.mark.parametrize("name", tuple(NAMES["captures"]))
def test_templated_names_are_selected_from_database_not_rendered_captures(name, source_database):
    if name == "qc_iu":
        source_database = Database.from_path(
            ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas"
        ).resolve(overlays=[ROOT / "spec/custom/isa/qc_iu"])
    documents = {}
    for path, source in source_database.documents.items():
        data = dict(source)
        if data.get("kind") == "exception_code" and data["name"] in NAMES["templates"]:
            data["name"] = NAMES["templates"][data["name"]]
            path = f"exception_code/{data['name']}.yaml"
        documents[path] = data
    database = ResolvedDatabase(documents)
    raw = NAMES["captures"][name]["inputs"]["templated_structured_exception_records"]
    assert "value" in raw
    assert resolve_all_exception_records(database, captured_inputs(name)) == tuple(raw["value"])
    assert any("Fault" in row["name"] and "<%" in row["var"] for row in raw["value"])
    assert all("<%" not in row["name"] for row in raw["value"])


@pytest.mark.parametrize(
    "mutation",
    ("bitlen+1", "bitlen-1", "min+1", "min-1", "min-to-max", "min-first", "min-second"),
)
def test_cache_boundary_corpus_kills_review_mutations(monkeypatch, mutation):
    from udb.prose.render import _Adapter

    bit_length = _Adapter.bit_length
    minimum = _Adapter.minimum
    if mutation.startswith("bitlen"):
        offset = 1 if mutation.endswith("+1") else -1
        monkeypatch.setattr(
            _Adapter, "bit_length", lambda self, name: bit_length(self, name) + offset
        )
    elif mutation == "min-to-max":
        monkeypatch.setattr(
            _Adapter, "minimum", lambda self, names: max(self.parameter(name) for name in names)
        )
    elif mutation in ("min-first", "min-second"):
        index = 0 if mutation == "min-first" else 1
        monkeypatch.setattr(_Adapter, "minimum", lambda self, names: self.parameter(names[index]))
    else:
        offset = 1 if mutation.endswith("+1") else -1
        monkeypatch.setattr(_Adapter, "minimum", lambda self, names: minimum(self, names) + offset)
    cases = tuple(name for name in SUPPLEMENT["captures"] if name.startswith("cache-"))
    assert any(
        render_legacy(CapturedProse(template["template"]), captured_inputs(name, SUPPLEMENT))
        != expected["value"]
        for name in cases
        for template, expected in zip(
            SUPPLEMENT["templates"], SUPPLEMENT["captures"][name]["expected"], strict=True
        )
        if "bit_length" in template["template"]
    ), f"surviving mutation: {mutation}"


def test_independent_valid_mc100_witness_separates_defects_from_synthetic_shapes():
    witness = json.loads(
        (ROOT / "tests/python/fixtures/configured_prose_mc100_witness.json").read_text()
    )
    facts = SUPPLEMENT["captures"]["mc100-full"]["inputs"]
    assert (
        witness["validity"]
        == facts["configuration_validity"]["value"]
        == {
            "valid": True,
            "reasons": [],
        }
    )
    assert witness["smdbltrp_implemented"] is False
    assert witness["double_trap_available"] is False
    assert witness["double_trap_solver_available"] is True
    assert "DoubleTrap" in witness["raw_exception_names"]
    assert "DoubleTrap" not in {code["name"] for code in facts["exception_codes"]["value"]}
    assert witness["raw_exception_names"] == witness["raw_interrupt_names"]
    assert witness["raw_exception_names"] == [
        code["name"] for code in facts["exception_codes_raw"]["value"]
    ]
    # MC100 constrains H's prerequisites, so it does not reproduce VScall inclusion.
    assert witness["h_implemented"] is False
    assert witness["vscall_available"] is False
    assert "VScall" not in witness["raw_exception_names"]


@pytest.fixture(scope="module")
def source_database():
    return Database.from_path(ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas").resolve()


def test_from_architecture_is_the_documented_declaration_projection(source_database):
    configuration = Configuration.builtin("rv64")
    architecture = ConfiguredArchitecture(source_database, configuration)
    assert ProseInputs.from_architecture(architecture) == ProseInputs.from_database(
        source_database, configuration
    )


@pytest.mark.parametrize("name", CONFIGURATIONS)
def test_real_database_input_projection_matches_ruby(name, source_database):
    declaration = CORPUS["configurations"][name].get("declaration")
    config = Configuration(declaration) if declaration else Configuration.builtin(name)
    if name == "qc_iu":
        source_database = Database.from_path(
            ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas"
        ).resolve(overlays=[ROOT / "spec/custom/isa/qc_iu"])
    inputs = ProseInputs.from_database(source_database, config)
    facts = CORPUS["captures"][name]["inputs"]
    expected_inputs = captured_inputs(name)
    for parameter in facts["parameters"]:
        assert inputs.parameters[parameter] == expected_inputs.parameters[parameter], parameter
    for query in CORPUS["extension_queries"]:
        assert (
            inputs.extension(
                query["name"], query["requirements"][0] if query["requirements"] else None
            )
            == facts["extensions"][query["key"]]
        ), query
    assert inputs.possible_xlens == tuple(facts["possible_xlens"]["value"])
    assert [
        {"num": code.num, "name": code.name, "display_name": code.display_name}
        for code in inputs.exception_codes
    ] == facts["exception_codes"]["value"]
    assert [
        {"num": code.num, "name": code.name, "display_name": code.display_name}
        for code in inputs.interrupt_codes
    ] == facts["interrupt_codes"]["value"]
    assert check_case(name, inputs) == (
        255 if name in ("cache-small", "cache-large", "h64-mixed-sv57") else 251,
        0 if name in ("cache-small", "cache-large", "h64-mixed-sv57") else 4,
    )
    names = resolved_exception_names(inputs)
    assert tuple(item["name"] for item in names) == tuple(
        code.name for code in inputs.exception_codes
    )
    assert all("var" in item and "ext" in item and type(item["num"]) is int for item in names)
