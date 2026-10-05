# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Reviewed frozen legacy outputs and native configured-prose coverage."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from functools import cache
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from udb import Configuration, Database, ResolvedDatabase
from udb.architecture import ConfiguredArchitecture
from udb.prose import (
    CapturedFailure,
    CapturedProse,
    CodeRecord,
    ParameterState,
    ProseError,
    ProseInputs,
    native_prose_values,
    render_native,
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
NATIVE_NAME_TEMPLATES = {
    "Breakpoint": "{% if extensions.C %}Compressed{% else %}Base{% endif %}Breakpoint",
    "InstructionGuestPageFault": ("{% if extensions.H %}Guest{% else %}Host{% endif %}Fault"),
}


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


@cache
def native_templates() -> tuple[CapturedProse, ...]:
    yaml = YAML(typ="safe")
    documents: dict[str, object] = {}
    result = []
    for template in CORPUS["templates"]:
        source = template["source"]
        if source not in documents:
            documents[source] = yaml.load((ROOT / source).read_text())
        value = documents[source]
        for item in template["path"]:
            value = value[item]
        assert isinstance(value, str), (source, template["path"])
        result.append(CapturedProse(value, source, tuple(template["path"])))
    return tuple(result)


def check_native_case(name: str, inputs: ProseInputs, corpus=CORPUS) -> tuple[int, int]:
    successes = errors = 0
    for prose, expected in zip(
        native_templates(), corpus["captures"][name]["expected"], strict=True
    ):
        if "error" in expected:
            with pytest.raises(ProseError):
                render_native(prose, native_prose_values(prose, inputs))
            errors += 1
        else:
            assert render_native(prose, native_prose_values(prose, inputs)) == expected["value"], (
                prose.label
            )
            successes += 1
    return successes, errors


def test_exact_source_inventory():
    frozen = CORPUS["templates"]
    paths = {template["source"] for template in frozen}
    assert Counter(path.split("/")[3] for path in paths) == {"csr": 111, "inst": 17}
    assert len(frozen) == 255
    assert CORPUS["baseline"] == "d6b06ca3"
    assert sum(template["template"].count("<%") for template in frozen) == 1746
    tags = Counter(
        body
        for template in frozen
        for body in re.findall(r"<%(.*?)%>", template["template"], re.DOTALL)
    )
    assert len(tags) == 49
    assert tags == {entry["body"]: entry["occurrences"] for entry in CORPUS["tag_inventory"]}

    current = native_templates()
    assert len(current) == 255
    assert all("<%" not in prose.text for prose in current)
    assert all("{%" in prose.text or "{{" in prose.text for prose in current)
    roots = (ROOT / "spec/std/isa", ROOT / "spec/custom/isa")
    legacy_sources = [
        path.relative_to(ROOT).as_posix()
        for root in roots
        for suffix in ("*.yaml", "*.layout")
        for path in root.rglob(suffix)
        if "<%" in path.read_text()
    ]
    assert legacy_sources == []


@pytest.mark.parametrize("name", CONFIGURATIONS)
def test_all_native_source_outputs_and_error_outcomes(name):
    expected_successes = 255 if name in ("cache-small", "cache-large", "h64-mixed-sv57") else 251
    assert check_native_case(name, captured_inputs(name)) == (
        expected_successes,
        255 - expected_successes,
    )


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


def test_extended_whitespace_archive_has_not_been_rewritten():
    digest = hashlib.sha256(
        json.dumps(WHITESPACE, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    assert digest == "b3e69e7f734b069e55e5a53491a3c3c501acdb4543a52061d0ad62bf80440c5c"


@pytest.mark.parametrize("name", tuple(SUPPLEMENT["captures"]))
def test_supplemental_input_projection_matches_frozen_capture(name, source_database):
    inputs = ProseInputs.from_database(
        source_database, Configuration(SUPPLEMENT["configurations"][name]["declaration"])
    )
    assert resolve_all_exception_records(source_database, inputs) == tuple(
        SUPPLEMENT["captures"][name]["inputs"]["structured_exception_records"]["value"]
    )


@pytest.mark.parametrize("name", tuple(SUPPLEMENT["captures"]))
def test_supplemental_native_source_outputs(name):
    assert check_native_case(name, captured_inputs(name, SUPPLEMENT), SUPPLEMENT) == (
        (251, 4) if name == "mc100-full" else (255, 0)
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
        if data.get("kind") == "exception_code" and data["name"] in NATIVE_NAME_TEMPLATES:
            data["name"] = NATIVE_NAME_TEMPLATES[data["name"]]
            path = f"exception_code/{data['name']}.yaml"
        documents[path] = data
    database = ResolvedDatabase(documents)
    raw = NAMES["captures"][name]["inputs"]["templated_structured_exception_records"]
    assert "value" in raw
    native_by_legacy = {
        NAMES["templates"][record]: template for record, template in NATIVE_NAME_TEMPLATES.items()
    }
    expected = tuple(
        {**row, "var": native_by_legacy.get(row["var"], row["var"])} for row in raw["value"]
    )

    def sort_key(row):
        return row["ext"], row["num"], row["var"], row["name"]

    assert sorted(
        resolve_all_exception_records(database, captured_inputs(name)), key=sort_key
    ) == sorted(expected, key=sort_key)
    assert any("Fault" in row["name"] and "{%" in row["var"] for row in expected)
    assert all("<%" not in row["name"] for row in raw["value"])


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
def test_real_database_input_projection_matches_frozen_capture(name, source_database):
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
    names = resolved_exception_names(inputs)
    assert tuple(item["name"] for item in names) == tuple(
        code.name for code in inputs.exception_codes
    )
    assert all("var" in item and "ext" in item and type(item["num"]) is int for item in names)
