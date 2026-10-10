# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
from io import StringIO
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

from udb import (
    ArchitectureCheck,
    ArchitectureCheckStatus,
    ArchitectureDiagnostic,
    Configuration,
    ResolvedDatabase,
)
from udb.cli import main
from udb.configuration_diagnostics import (
    explain_conflict,
    format_check_diagnostics,
    summarize_value,
)
from udb.source import parse_yaml


@pytest.mark.parametrize("length,index", [(32, 3), (9, 7), (4, 0)])
def test_array_summary_identifies_observed_exception_without_dump(length, index):
    values = [True] * length
    values[index] = False
    before = values.copy()
    summary = summarize_value(values)
    assert f"array of {length} entries" in summary
    assert f"{length - 1} entries are true" in summary
    assert f"[{index}]=false" in summary
    assert "cause" not in summary
    assert str(tuple(values)) not in summary
    assert values == before


def test_mixed_array_preserves_typed_values():
    assert summarize_value([True, 1, True, "on", False]) == (
        "array of 5 entries; 2 entries are true; other entries: [1]=1, [3]='on', [4]=false"
    )


def test_summary_is_bounded_for_many_distinct_entries():
    summary = summarize_value(list(range(1000)))
    assert "[8]=8" in summary
    assert "[9]=9" not in summary
    assert "991 more other entries omitted" in summary
    assert len(summary) < 250


@pytest.mark.parametrize(
    "value,expected",
    [(True, "true"), (False, "false"), (7, "7"), ("on", "'on'"), ([], "array of 0 entries")],
)
def test_non_array_and_empty_values(value, expected):
    assert summarize_value(value) == expected


def extension(name, **extra):
    return {
        "kind": "extension",
        "name": name,
        "versions": [{"version": "1.0", "state": "ratified"}],
        **extra,
    }


def parameter(name, schema, defined_by=True, **extra):
    return {
        "kind": "parameter",
        "name": name,
        "schema": schema,
        "definedBy": defined_by,
        **extra,
    }


def configuration(name="small-example", **extra):
    return {
        "$schema": "config_schema.json#",
        "kind": "architecture configuration",
        "type": "partially configured",
        "name": name,
        "description": "Reduced diagnostic fixture, not an original implementation.",
        **extra,
    }


def captured_database(documents, directory):
    sources = {}
    texts = {}
    data = {}
    for relative, document in documents.items():
        if isinstance(document, str):
            text = document
        else:
            output = StringIO()
            YAML().dump(document, output)
            text = output.getvalue()
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        parsed = parse_yaml(text, source=str(path), layer="fixture")
        sources[relative] = parsed.sources
        texts[("fixture", str(path))] = text
        data[relative] = parsed.value
    return ResolvedDatabase(data, sources=sources, source_texts=texts)


@pytest.fixture
def reduced(tmp_path):
    length, index = 9, 7
    requirement = {
        "idl()": LiteralScalarString(
            f"for (U32 i = 0; i < {length}; i++) {{ SUPPORTED[i] -> WRITABLE[i]; }}\n"
        ),
        "reason": "Every supported entry must be writable.",
    }
    arrays = {"type": "array", "items": {"type": "boolean"}, "minItems": length, "maxItems": length}
    database = captured_database(
        {
            "ext/Xbase.yaml": extension("Xbase"),
            "ext/Xrw.yaml": extension("Xrw", requirements=requirement),
            "param/SUPPORTED.yaml": parameter("SUPPORTED", arrays),
            "param/WRITABLE.yaml": parameter("WRITABLE", arrays),
            "param/PRECISION.yaml": parameter(
                "PRECISION",
                {"type": "integer", "minimum": 0, "maximum": 255},
                {
                    "allOf": [
                        {"extension": {"name": "Xbase"}},
                        {"param": {"name": "SUPPORTED", "index": index, "equal": True}},
                    ]
                },
            ),
        },
        tmp_path / "isa",
    )
    writable = [True] * length
    writable[index] = False
    path = tmp_path / "cfg.yaml"
    path.write_text(
        json.dumps(
            configuration(
                mandatory_extensions=[{"name": "Xrw", "version": ">= 1"}],
                params={"WRITABLE": writable, "PRECISION": 13},
            )
        ),
        encoding="utf-8",
    )
    return database.configure(Configuration.from_file(path)), tmp_path


def test_captured_generic_conflict_preserves_exact_core(reduced):
    architecture, _ = reduced
    before = architecture.configuration.to_dict()
    result = architecture.check()
    assert result.status is ArchitectureCheckStatus.UNSAT
    assert set(result.conflict) == {
        "extension Xrw requirements",
        "configuration mandatory extension Xrw",
        f"configuration parameter WRITABLE={architecture.configuration.params['WRITABLE']!r}",
        "configuration parameter PRECISION is defined",
    }
    explanations = explain_conflict(architecture, result)
    assert tuple(entry.label for entry in explanations) == result.conflict
    assert all(not entry.raw for entry in explanations)
    text = "\n".join(format_check_diagnostics(architecture, result))
    assert "Every supported entry must be writable." in text
    assert "SUPPORTED[i] -> WRITABLE[i]" in text
    assert "8 entries are true; other entries: [7]=false" in text
    assert "definition condition: (extension Xbase AND SUPPORTED[7] = true)" in text
    assert "This asserts existence, not a supplied value." in text
    assert "PRECISION = 13" not in text
    assert "jointly inconsistent" in text
    assert "cause" not in text
    assert architecture.configuration.to_dict() == before
    assert architecture.check().conflict == result.conflict


def test_provenance_and_reasons_survive_source_files_disappearing(reduced):
    architecture, root = reduced
    result = architecture.check()
    for path in root.rglob("*.yaml"):
        path.unlink()
    entries = explain_conflict(architecture, result)
    owner = next(entry for entry in entries if entry.label == "extension Xrw requirements")
    assert owner.source.source.endswith("ext/Xrw.yaml")
    assert owner.source.start_line is not None
    assert owner.source.layer == "fixture"
    rule, reason = owner.details
    assert rule.source.source.endswith("ext/Xrw.yaml")
    assert rule.source.start_line is not None
    assert reason.source.source.endswith("ext/Xrw.yaml")
    assert reason.source.start_line > rule.source.start_line
    text = "\n".join(format_check_diagnostics(architecture, result))
    assert "fixture:" in text
    assert "cfg.yaml:1:" in text
    assert "Every supported entry must be writable." in text


def test_unknown_metadata_is_explicit_and_preserves_membership(reduced):
    architecture, _ = reduced
    labels = ("unrecognized core member", "configuration parameter MISSING is defined")
    result = ArchitectureCheck(
        ArchitectureCheckStatus.UNSAT,
        (ArchitectureDiagnostic("unsatisfiable", "old raw message"),),
        conflict=labels,
    )
    entries = explain_conflict(architecture, result)
    assert tuple(entry.label for entry in entries) == labels
    assert all(entry.raw for entry in entries)
    assert all(entry.source is None for entry in entries)
    text = "\n".join(format_check_diagnostics(architecture, result))
    for label in labels:
        assert f"raw core label: {label}" in text
    assert text.count("No captured explanation is available") == len(labels)


@pytest.mark.parametrize("status", list(ArchitectureCheckStatus))
def test_non_core_diagnostics_keep_their_exact_format(reduced, status):
    architecture, _ = reduced
    result = ArchitectureCheck(
        status,
        (
            ArchitectureDiagnostic("specific-error", "exact message", source="file:4"),
            ArchitectureDiagnostic("second-error", "another message", label="label"),
        ),
    )
    assert explain_conflict(architecture, result) == ()
    assert format_check_diagnostics(architecture, result) == (
        "file:4: specific-error: exact message",
        "label: second-error: another message",
    )


def test_real_standard_captured_counter_requirement(tmp_path):
    """Known width 13 belongs to this reduced fixture, not the reported config."""

    names = ["Sscounterenw", "HPM_COUNTER_EN", "SCOUNTENABLE_EN", "HPM_COUNTER3_WIDTH"]
    standard = Path("spec/std/isa")
    documents = {}
    for name in names:
        kind = "ext" if name == "Sscounterenw" else "param"
        relative = f"{kind}/{name}.yaml"
        documents[relative] = (standard / relative).read_text(encoding="utf-8")
    for name in ("Sm", "S", "Zihpm", "Zicntr"):
        documents[f"ext/{name}.yaml"] = extension(name)
    database = captured_database(documents, tmp_path / "isa")
    writable = [True] * 32
    writable[3] = False
    architecture = database.configure(
        Configuration(
            configuration(
                name="reduced-standard-records",
                mandatory_extensions=[{"name": "Sscounterenw"}],
                params={"SCOUNTENABLE_EN": writable, "HPM_COUNTER3_WIDTH": 13},
            )
        )
    )
    result = architecture.check()
    assert result.status is ArchitectureCheckStatus.UNSAT
    assert set(result.conflict) == {
        "extension Sscounterenw requirements",
        "configuration mandatory extension Sscounterenw",
        f"configuration parameter SCOUNTENABLE_EN={tuple(writable)!r}",
        "configuration parameter HPM_COUNTER3_WIDTH is defined",
    }
    text = "\n".join(format_check_diagnostics(architecture, result))
    assert "31 entries are true; other entries: [3]=false" in text
    assert "HPM_COUNTER_EN[3] = true" in text
    assert "HPM_COUNTER_EN[i] -> SCOUNTENABLE_EN[i]" in text
    assert "corresponding bit in `scounteren` must be writable" in text
    assert "extension Zihpm" not in text  # The captured IDL spelling is retained instead.
    assert "implemented?(ExtensionName::Zihpm)" in text
    assert "implemented?(ExtensionName::S)" in text
    assert "HPM_COUNTER3_WIDTH = 13" not in text
    assert tuple(entry.label for entry in explain_conflict(architecture, result)) == result.conflict


@pytest.mark.parametrize(
    "value,required,schema,display",
    [
        (13, 7, {"type": "integer", "minimum": 0, "maximum": 255}, "13"),
        (False, True, {"type": "boolean"}, "false"),
        ("red", "blue", {"type": "string", "enum": ["red", "blue"]}, "'red'"),
    ],
)
def test_scalar_assignments_are_distinct_from_definition_constraints(
    value, required, schema, display
):
    database = ResolvedDatabase(
        {
            "ext/Xscalar.yaml": extension(
                "Xscalar", requirements={"param": {"name": "VALUE", "equal": required}}
            ),
            "param/VALUE.yaml": parameter("VALUE", schema),
        }
    )
    architecture = database.configure(
        Configuration(
            configuration(mandatory_extensions=[{"name": "Xscalar"}], params={"VALUE": value})
        )
    )
    result = architecture.check()
    assert result.status is ArchitectureCheckStatus.UNSAT
    assert f"configuration parameter VALUE={value!r}" in result.conflict
    assert "configuration parameter VALUE is defined" not in result.conflict
    entries = explain_conflict(architecture, result)
    assert tuple(entry.label for entry in entries) == result.conflict
    assignment = next(entry for entry in entries if entry.label.endswith(f"VALUE={value!r}"))
    assert assignment.summary == f"Configuration supplies VALUE = {display}"
    requirement = next(
        entry for entry in entries if entry.label == "extension Xscalar requirements"
    )
    assert requirement.source is None  # No captured spans, but the rule remains available.
    assert not requirement.raw
    assert requirement.details[0].source is None


def test_version_and_nested_idl_provenance(tmp_path):
    database = captured_database(
        {
            "ext/Xversion.yaml": extension(
                "Xversion",
                versions=[
                    {
                        "version": "1.0",
                        "state": "ratified",
                        "requirements": {
                            "allOf": [
                                {
                                    "idl()": LiteralScalarString("-> false;\n"),
                                    "reason": "This captured version is impossible.",
                                },
                                True,
                            ]
                        },
                    }
                ],
            )
        },
        tmp_path,
    )
    architecture = database.configure(
        Configuration(configuration(mandatory_extensions=[{"name": "Xversion"}]))
    )
    result = architecture.check()
    assert "extension Xversion@1.0.0 requirements" in result.conflict
    entries = explain_conflict(architecture, result)
    owner = next(entry for entry in entries if entry.label.endswith("@1.0.0 requirements"))
    idl = next(detail for detail in owner.details if detail.message.startswith("captured IDL"))
    assert idl.source == database.extension("Xversion").sources.at(
        "versions", 0, "requirements", "allOf", 0, "idl()"
    )
    assert "This captured version is impossible." in "\n".join(
        format_check_diagnostics(architecture, result)
    )


def test_selection_group_provenance_is_not_overwritten():
    database = ResolvedDatabase({"ext/Xchoice.yaml": extension("Xchoice")})
    config = Configuration.from_yaml(
        "$schema: config_schema.json#\n"
        "kind: architecture configuration\n"
        "name: incompatible-choice\n"
        "type: partially configured\n"
        "description: conflicting selection groups\n"
        "mandatory_extensions:\n"
        "  - name: Xchoice\n"
        "prohibited_extensions:\n"
        "  - name: Xchoice\n",
        source="choice.yaml",
    )
    architecture = database.configure(config)
    result = architecture.check()
    assert result.status is ArchitectureCheckStatus.UNSAT
    entries = {entry.label: entry for entry in explain_conflict(architecture, result)}
    assert entries["configuration mandatory extension Xchoice"].source.start_line == 7
    assert entries["configuration prohibited extension Xchoice"].source.start_line == 9


def test_invalid_idl_remains_an_error_not_a_requirement_explanation():
    database = ResolvedDatabase(
        {
            "ext/Xinvalid.yaml": extension(
                "Xinvalid",
                requirements={"idl()": "-> unknown_parameter;", "reason": "Not a proved rule."},
            )
        }
    )
    architecture = database.configure(
        Configuration(configuration(mandatory_extensions=[{"name": "Xinvalid"}]))
    )
    result = architecture.check()
    assert result.status is ArchitectureCheckStatus.UNSAT
    assert result.conflict == ()
    assert explain_conflict(architecture, result) == ()
    text = "\n".join(format_check_diagnostics(architecture, result))
    assert "invalid-idl-condition:" in text
    assert "unknown_parameter" in text
    assert "Not a proved rule" not in text
    assert "jointly inconsistent" not in text


def test_long_unknown_label_is_retained_exactly_even_when_display_is_bounded(reduced):
    architecture, _ = reduced
    label = "unknown constraint: " + "X" * 10000
    result = ArchitectureCheck(
        ArchitectureCheckStatus.UNSAT,
        (ArchitectureDiagnostic("unsatisfiable", "opaque"),),
        conflict=(label,),
    )
    (entry,) = explain_conflict(architecture, result)
    assert entry.label == label
    assert entry.raw
    assert "[truncated]" in entry.summary
    assert len("\n".join(format_check_diagnostics(architecture, result))) < 1000


def test_cli_explains_real_core_without_changing_stdout_or_exit(reduced, capsys):
    _, root = reduced
    source, config = root / "isa", root / "cfg.yaml"
    before = config.read_bytes()
    assert main(["--path", str(source), "validate-cfg", str(config)]) == 1
    output = capsys.readouterr()
    assert output.out == "small-example: unsat\n"
    assert "unsatisfiable: configuration constraints are mutually unsatisfiable" in output.err
    assert output.err.count("\n  - ") == 4
    assert "Every supported entry must be writable." in output.err
    assert "ext/Xrw.yaml:" in output.err
    assert f"{config}:1:" in output.err
    assert "8 entries are true; other entries: [7]=false" in output.err
    assert "PRECISION = 13" not in output.err
    assert config.read_bytes() == before


def test_cli_valid_output_is_unchanged(reduced, capsys):
    _, root = reduced
    config = root / "cfg.yaml"
    data = json.loads(config.read_text(encoding="utf-8"))
    data["params"]["WRITABLE"][7] = True
    config.write_text(json.dumps(data), encoding="utf-8")
    assert main(["--path", str(root / "isa"), "validate-cfg", str(config)]) == 0
    output = capsys.readouterr()
    assert output.out == "small-example: valid\n"
    assert output.err == ""


def test_real_standard_local_extension_requirement(tmp_path, capsys):
    database = captured_database(
        {
            "ext/Zve32x.yaml": Path("spec/std/isa/ext/Zve32x.yaml").read_text(encoding="utf-8"),
            "ext/Zicsr.yaml": extension("Zicsr"),
            "ext/Zvl32b.yaml": extension("Zvl32b"),
        },
        tmp_path / "isa",
    )
    data = configuration(
        name="local-extension-example",
        mandatory_extensions=[{"name": "Zve32x"}],
        prohibited_extensions=[{"name": "Zicsr"}],
    )
    config = tmp_path / "cfg.yaml"
    config.write_text(json.dumps(data), encoding="utf-8")
    architecture = database.configure(Configuration.from_file(config))
    result = architecture.check()
    assert result.status is ArchitectureCheckStatus.UNSAT
    assert result.conflict == (
        "extension Zve32x requirements",
        "configuration mandatory extension Zve32x",
        "configuration prohibited extension Zicsr",
    )
    text = "\n".join(format_check_diagnostics(architecture, result))
    assert "requirement: (extension Zicsr AND extension Zvl32b)" in text
    assert "ext/Zve32x.yaml:" in text
    assert tuple(entry.label for entry in explain_conflict(architecture, result)) == result.conflict
    assert architecture.check().conflict == result.conflict
    assert main(["--path", str(tmp_path / "isa"), "validate-cfg", str(config)]) == 1
    output = capsys.readouterr()
    assert output.out == "local-extension-example: unsat\n"
    assert "requirement: (extension Zicsr AND extension Zvl32b)" in output.err


def test_nested_local_extension_anyof():
    database = ResolvedDatabase(
        {
            "ext/Xlocal.yaml": extension(
                "Xlocal",
                requirements={
                    "extension": {
                        "allOf": [
                            {"name": "Xbase"},
                            {"anyOf": [{"name": "Xleft"}, {"name": "Xright"}]},
                        ]
                    }
                },
            ),
            **{f"ext/{name}.yaml": extension(name) for name in ("Xbase", "Xleft", "Xright")},
        }
    )
    architecture = database.configure(
        Configuration(
            configuration(
                mandatory_extensions=[{"name": "Xlocal"}],
                prohibited_extensions=[{"name": "Xleft"}, {"name": "Xright"}],
            )
        )
    )
    result = architecture.check()
    assert result.status is ArchitectureCheckStatus.UNSAT
    text = "\n".join(format_check_diagnostics(architecture, result))
    assert "(extension Xbase AND (extension Xleft OR extension Xright))" in text
    assert tuple(entry.label for entry in explain_conflict(architecture, result)) == result.conflict


@pytest.mark.parametrize(
    "expression,display",
    [
        (
            {"allOf": [{"name": "VALUE", "equal": 3}, {"name": "VALUE", "greaterThan": 0}]},
            "(VALUE = 3 AND VALUE > 0)",
        ),
        (
            {"anyOf": [{"name": "VALUE", "equal": 3}, {"name": "VALUE", "equal": 5}]},
            "(VALUE = 3 OR VALUE = 5)",
        ),
        (
            {"oneOf": [{"name": "VALUE", "greaterThan": 0}, {"name": "VALUE", "equal": 7}]},
            "exactly one of (VALUE > 0, VALUE = 7)",
        ),
        (
            {"noneOf": [{"name": "VALUE", "equal": 7}, {"name": "VALUE", "equal": 3}]},
            "none of (VALUE = 7, VALUE = 3)",
        ),
        ({"not": {"name": "VALUE", "equal": 7}}, "NOT (VALUE = 7)"),
        (
            {
                "if": {"extension": {"name": "Xlocal"}},
                "then": {"name": "VALUE", "equal": 3},
            },
            "(extension Xlocal) implies (VALUE = 3)",
        ),
        (
            {
                "allOf": [
                    {"anyOf": [{"name": "VALUE", "equal": 3}, {"name": "VALUE", "equal": 5}]},
                    {"name": "VALUE", "greaterThan": 0},
                ]
            },
            "((VALUE = 3 OR VALUE = 5) AND VALUE > 0)",
        ),
        (
            {"name": "VALUE", "oneOf": [3, 5]},
            "VALUE is one of array of 2 entries",
        ),
    ],
)
def test_local_parameter_expressions_preserve_context(expression, display):
    database = ResolvedDatabase(
        {
            "ext/Xlocal.yaml": extension("Xlocal", requirements={"param": expression}),
            "param/VALUE.yaml": parameter(
                "VALUE", {"type": "integer", "minimum": 0, "maximum": 255}
            ),
        }
    )
    architecture = database.configure(
        Configuration(configuration(mandatory_extensions=[{"name": "Xlocal"}], params={"VALUE": 7}))
    )
    result = architecture.check()
    assert result.status is ArchitectureCheckStatus.UNSAT
    assert set(result.conflict) == {
        "extension Xlocal requirements",
        "configuration mandatory extension Xlocal",
        "configuration parameter VALUE=7",
    }
    assert f"requirement: {display}" in "\n".join(format_check_diagnostics(architecture, result))
    assert tuple(entry.label for entry in explain_conflict(architecture, result)) == result.conflict
    assert architecture.check().conflict == result.conflict


@pytest.mark.parametrize("idl", [False, True])
def test_real_unsat_preserves_literal_whitespace_in_values_and_rules(tmp_path, idl, capsys):
    required, supplied = "two  words", "two words"
    snippet = '-> MODE == "two  words";\n'
    requirement = (
        {"idl()": LiteralScalarString(snippet)}
        if idl
        else {"param": {"name": "MODE", "equal": required}}
    )
    database = captured_database(
        {
            "ext/Xspacing.yaml": extension("Xspacing", requirements=requirement),
            "param/MODE.yaml": parameter("MODE", {"type": "string", "enum": [required, supplied]}),
        },
        tmp_path / "isa",
    )
    config = tmp_path / "cfg.yaml"
    config.write_text(
        json.dumps(
            configuration(
                name="whitespace-example",
                mandatory_extensions=[{"name": "Xspacing"}],
                params={"MODE": supplied},
            )
        ),
        encoding="utf-8",
    )
    architecture = database.configure(Configuration.from_file(config))
    result = architecture.check()
    assert result.status is ArchitectureCheckStatus.UNSAT
    assert set(result.conflict) == {
        "extension Xspacing requirements",
        "configuration mandatory extension Xspacing",
        "configuration parameter MODE='two words'",
    }
    entries = explain_conflict(architecture, result)
    assert tuple(entry.label for entry in entries) == result.conflict
    owner = next(entry for entry in entries if entry.label == "extension Xspacing requirements")
    if idl:
        assert owner.details[0].message == "requirement: IDL: " + snippet
    else:
        assert owner.details[0].message == "requirement: MODE = 'two  words'"
    assignment = next(
        entry for entry in entries if entry.label.startswith("configuration parameter")
    )
    assert assignment.summary == "Configuration supplies MODE = 'two words'"
    assert architecture.check().conflict == result.conflict
    assert main(["--path", str(tmp_path / "isa"), "validate-cfg", str(config)]) == 1
    output = capsys.readouterr()
    assert output.out == "whitespace-example: unsat\n"
    assert "Configuration supplies MODE = 'two words'" in output.err
    assert ('MODE == "two  words"' if idl else "MODE = 'two  words'") in output.err


@pytest.mark.parametrize(
    "first,second",
    [
        ("two  words", "two words"),
        (" two words", "two words"),
        ("two words ", "two words"),
        ("two\twords", "two words"),
        ("two\nwords", "two words"),
    ],
)
def test_value_summaries_preserve_literal_whitespace(first, second):
    assert summarize_value(first) == repr(first)
    assert summarize_value(second) == repr(second)
    assert summarize_value(first) != summarize_value(second)
    summary = summarize_value([first, second, first])
    assert f"2 entries are {first!r}" in summary
    assert f"[1]={second!r}" in summary


def test_value_truncation_preserves_original_prefix():
    value = "two  words " * 40
    summary = summarize_value(value)
    assert summary == repr(value)[:240] + "... [truncated]"
