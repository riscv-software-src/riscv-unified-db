# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from pathlib import Path

import pytest

from udb import Configuration, Database, ResolvedDatabase, layouts
from udb.errors import DataError
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
    resolved_exception_names,
)


def test_structured_exception_names_are_immutable_and_resolved():
    inputs = ProseInputs(
        "test",
        extensions={"H": True},
        exception_codes=(
            CodeRecord(
                9,
                "{% if extensions.H %}HS{% else %}S{% endif %}call",
                "Scall",
                ("Sm",),
            ),
            CodeRecord(2, "IllegalInstruction", extensions=("Sm",)),
        ),
    )
    result = resolved_exception_names(inputs)
    assert result == (
        {"num": 2, "name": "IllegalInstruction", "var": "IllegalInstruction", "ext": "Sm"},
        {"num": 9, "name": "HScall", "var": "Scall", "ext": "Sm"},
    )
    with pytest.raises(TypeError):
        result[0]["name"] = "changed"


def test_native_format_rejects_legacy_syntax():
    prose = CapturedProse(
        "{% if extensions.H %}H{% else %}M{% endif %}:"
        "{% for name in names %}{{ name }};{% endfor %}"
    )
    assert render_native(prose, {"extensions": {"H": True}, "names": ("a", "b")}) == "H:a;b;"
    with pytest.raises(ProseError):
        render_native(CapturedProse("<% if ext?(:H) %>H<% end %>"), {})
    with pytest.raises(ProseError):
        render_native(CapturedProse("{{ __import__('os') }}"), {})
    with pytest.raises(ProseError):
        render_native(
            CapturedProse("{% if flag %}{{ value.__class__ }}{% endif %}"), {"flag": False}
        )


def test_captured_source_survives_deleted_tree(tmp_path):
    root = tmp_path / "spec"
    (root / "csr").mkdir(parents=True)
    text = "kind: csr\nname: a\ndescription: |\n  x{% if extensions.H %}H{% endif %}\n"
    path = root / "csr/a.yaml"
    path.write_text(text)
    database = Database.from_path(root).resolve()
    prose = CapturedProse.from_record(database, database.csr("a"), "description")
    path.unlink()
    (root / "csr").rmdir()
    root.rmdir()
    assert prose.source_text == text
    assert prose.span is not None
    assert prose.span.source == "csr/a.yaml"
    inputs = ProseInputs("offline", extensions={"H": True})
    assert render_native(prose, native_prose_values(prose, inputs)) == "xH\n"


@pytest.mark.parametrize("path", [("missing",), ("description", 0), ("names", 4), ("names", -1)])
def test_invalid_capture_paths_raise_repository_errors(tmp_path, path):
    root = tmp_path / "spec"
    (root / "csr").mkdir(parents=True)
    (root / "csr/a.yaml").write_text("kind: csr\nname: a\ndescription: text\nnames: [a]\n")
    database = Database.from_path(root).resolve()
    with pytest.raises(DataError, match=r"csr/a\.yaml.*invalid prose field path") as raised:
        CapturedProse.from_record(database, database.csr("a"), *path)
    assert isinstance(raised.value.__cause__, (KeyError, IndexError, TypeError))


def test_capture_does_not_swallow_source_load_errors(tmp_path, monkeypatch):
    root = tmp_path / "spec"
    (root / "csr").mkdir(parents=True)
    (root / "csr/a.yaml").write_text("kind: csr\nname: a\ndescription: text\n")
    database = Database.from_path(root).resolve()
    missing = DataError("No captured YAML source source:csr/a.yaml")

    def source_failure(self, source, *, layer):
        raise missing

    monkeypatch.setattr(ResolvedDatabase, "source_text", source_failure)
    with pytest.raises(DataError, match=r"cannot capture prose field.*description") as raised:
        CapturedProse.from_record(database, database.csr("a"), "description")
    assert "csr/a.yaml:3" in str(raised.value)
    assert raised.value.__cause__ is missing


def test_explicit_parameters_are_deeply_immutable():
    values = {"WIDTHS": [32, 64]}
    inputs = ProseInputs("captured", values)
    values["WIDTHS"].append(128)
    assert inputs.parameters["WIDTHS"] == (32, 64)
    with pytest.raises(TypeError):
        inputs.parameters["MXLEN"] = 64


def test_all_code_database_names_render_offline_without_source_or_subprocess(tmp_path, monkeypatch):
    root = tmp_path / "spec"
    (root / "ext").mkdir(parents=True)
    (root / "exception_code").mkdir()
    (root / "ext/A.yaml").write_text("kind: extension\nname: A\nversions: [{version: '1.0'}]\n")
    (root / "ext/B.yaml").write_text(
        "kind: extension\nname: B\nversions: [{version: '1.0'}]\n"
        "requirements: {extension: {name: A}}\n"
    )
    template = "Dynamic{{ params.MXLEN }}"
    (root / "exception_code" / f"{template}.yaml").write_text(
        f"kind: exception_code\nname: '{template}'\nnum: 3\ndefinedBy: {{extension: {{name: B}}}}\n"
    )
    database = Database.from_path(root).resolve()
    inputs = ProseInputs("no-implemented-extensions", {"MXLEN": 64})

    def forbidden(*args, **kwargs):
        pytest.fail("rendering attempted source reopening or a subprocess")

    with monkeypatch.context() as guard:
        guard.setattr(Path, "open", forbidden)
        guard.setattr("builtins.open", forbidden)
        guard.setattr("subprocess.run", forbidden)
        result = resolve_all_exception_records(database, inputs)
    assert result == (
        {"num": 3, "name": "Dynamic64", "var": template, "ext": "A"},
        {"num": 3, "name": "Dynamic64", "var": template, "ext": "B"},
    )


def test_xlen_relations_add_direct_mentions_without_reexpanding_requirements():
    database = ResolvedDatabase(
        {
            "ext/A.yaml": {
                "kind": "extension",
                "name": "A",
                "versions": [{"version": "1.0"}],
                "requirements": {"xlen": 32},
            },
            "ext/B.yaml": {
                "kind": "extension",
                "name": "B",
                "versions": [{"version": "1.0"}],
                "requirements": {"extension": {"name": "C"}},
            },
            "ext/C.yaml": {
                "kind": "extension",
                "name": "C",
                "versions": [{"version": "1.0"}],
            },
            "param/MXLEN.yaml": {
                "kind": "parameter",
                "name": "MXLEN",
                "requirements": {"extension": {"name": "B"}},
            },
            "exception_code/Code.yaml": {
                "kind": "exception_code",
                "name": "Code",
                "num": 1,
                "definedBy": {"extension": {"name": "A"}},
            },
        }
    )
    rows = resolve_all_exception_records(database, ProseInputs("unconfigured"))
    assert rows == (
        {"num": 1, "name": "Code", "var": "Code", "ext": "A"},
        {"num": 1, "name": "Code", "var": "Code", "ext": "B"},
    )


def test_unobserved_malformed_operands_have_python_not_invented_ruby_diagnostics():
    with pytest.raises(ProseError) as bit_length:
        prose = CapturedProse("{{ derived.cache_block_size_log2 }}")
        inputs = ProseInputs("test", parameters={"CACHE_BLOCK_SIZE": True})
        render_native(prose, native_prose_values(prose, inputs))
    assert bit_length.value.diagnostic.legacy_error_class is None
    assert "must be an integer" in bit_length.value.diagnostic.message
    with pytest.raises(ProseError) as minimum:
        prose = CapturedProse("{{ derived.min_cache_granularity }}")
        inputs = ProseInputs("test", parameters={"PMP_GRANULARITY": 3, "PMA_GRANULARITY": False})
        render_native(prose, native_prose_values(prose, inputs))
    assert minimum.value.diagnostic.legacy_error_class is None
    assert "must be an integer" in minimum.value.diagnostic.message


def test_input_projection_does_not_claim_satisfiability():
    database = ResolvedDatabase(
        {
            "ext/A.yaml": {"kind": "extension", "name": "A", "versions": [{"version": "1.0.0"}]},
            "param/MXLEN.yaml": {"kind": "parameter", "name": "MXLEN", "definedBy": True},
        }
    )
    config = Configuration.builtin("_")
    inputs = ProseInputs.from_database(database, config)
    assert inputs.parameters["MXLEN"] is ParameterState.UNKNOWN
    assert inputs.extension("A") is False
    assert not hasattr(inputs, "solver")


def test_limits_and_invalid_inputs():
    with pytest.raises(ProseError):
        render_native(
            CapturedProse("{% for x in xs %}{{ x }}{% endfor %}"), {"xs": tuple(range(1025))}
        )
    with pytest.raises(DataError, match="1024 records"):
        ProseInputs("too many", exception_codes=tuple(CodeRecord(n, str(n)) for n in range(1025)))


def test_parameter_source_and_configuration_text_are_retained():
    config = Configuration.from_yaml(
        "$schema: config_schema.json#\nkind: architecture configuration\n"
        "name: malformed\ntype: partially configured\n"
        "description: prose test\nmandatory_extensions: []\nparams:\n  CACHE_BLOCK_SIZE: bad\n",
        source="captured-config.yaml",
    )
    database = ResolvedDatabase(
        {
            "param/CACHE_BLOCK_SIZE.yaml": {
                "kind": "parameter",
                "name": "CACHE_BLOCK_SIZE",
                "definedBy": True,
            },
        }
    )
    inputs = ProseInputs.from_database(database, config)
    prose = CapturedProse("{{ derived.cache_block_size_log2 }}")
    with pytest.raises(ProseError) as raised:
        render_native(prose, native_prose_values(prose, inputs))
    assert raised.value.diagnostic.configuration_source == config.source_text
    span = raised.value.diagnostic.input_sources["CACHE_BLOCK_SIZE"]
    assert span.source == "captured-config.yaml"
    assert span.start_line == 8


def test_code_rows_render_native_names_and_sort_by_number():
    template = CapturedProse("{% for row in exception_code_rows %}{{ row }}\n{% endfor %}")
    assert (
        render_native(
            template,
            native_prose_values(
                template,
                ProseInputs(
                    "test",
                    {"MXLEN": 64},
                    exception_codes=(CodeRecord(1, "{{ params.MXLEN }}"),),
                ),
            ),
        )
        == "! 1 ! 64\n"
    )
    assert (
        render_native(
            template,
            native_prose_values(
                template,
                ProseInputs(
                    "test",
                    exception_codes=(
                        CodeRecord(2, "b"),
                        CodeRecord(1, "a"),
                    ),
                ),
            ),
        )
        == "! 1 ! a\n! 2 ! b\n"
    )


def test_malformed_values_never_invoke_python_hooks():
    class NotCapturedData:
        def __eq__(self, other):
            pytest.fail("Python comparison hook executed")

    with pytest.raises(DataError, match="captured scalars"):
        ProseInputs("unsafe", {"MXLEN": NotCapturedData()})


def test_missing_version_facts_and_restricted_partial_scopes_are_explicit():
    with pytest.raises(ProseError, match="Missing captured version predicate"):
        prose = CapturedProse("{% if extension_queries.S_gt_1_9_1 %}S{% endif %}")
        inputs = ProseInputs("test", extensions={"S": True})
        render_native(prose, native_prose_values(prose, inputs))
    database = ResolvedDatabase({})
    config = Configuration(
        {
            "$schema": "config_schema.json#",
            "kind": "architecture configuration",
            "name": "restricted",
            "type": "partially configured",
            "description": "requires a caller-owned availability projection",
            "mandatory_extensions": [],
            "prohibited_extensions": [{"name": "H"}],
        }
    )
    with pytest.raises(DataError, match="explicitly captured prose"):
        ProseInputs.from_database(database, config)


def test_layout_authoring_can_quote_native_configured_tags_without_a_second_renderer():
    authoring = (
        'before\n{{ "{%- if extensions.H -%}" }}\nH\n'
        '{{ "{%- endif -%}" }}\n{{ "{{ params.MXLEN }}" }}\nafter\n'
    )
    generated = layouts._render_template(authoring, Path("csr/prose.layout"), {})
    assert generated == (
        "before\n{%- if extensions.H -%}\nH\n{%- endif -%}\n{{ params.MXLEN }}\nafter\n"
    )
    assert (
        render_native(
            CapturedProse(generated), {"extensions": {"H": True}, "params": {"MXLEN": 64}}
        )
        == "before\nH\n64\nafter\n"
    )
    assert (
        render_native(
            CapturedProse(generated), {"extensions": {"H": False}, "params": {"MXLEN": 64}}
        )
        == "before\n64\nafter\n"
    )


def test_native_prose_values_support_the_source_contract():
    prose = CapturedProse(
        "{% if extensions.H and extension_queries.S_gt_1_9_1 %}H:S{% endif %}:"
        "{{ params.MXLEN }}:{{ derived.va_size }}:{{ derived.cache_block_size_log2 }}:"
        "{{ derived.min_cache_granularity }}:"
        "{% if derived.has_xlen_32 %}32{% else %}64{% endif %}\n"
        "{% for row in interrupt_code_rows %}{{ row }}\n{% endfor %}"
        "{% for row in exception_code_rows %}{{ row }}\n{% endfor %}"
    )
    inputs = ProseInputs(
        "native",
        {
            "MXLEN": 64,
            "CACHE_BLOCK_SIZE": 64,
            "PMP_GRANULARITY": 5,
            "PMA_GRANULARITY": 7,
        },
        {"H": True, "Sv48": True, "S@> 1.9.1": True},
        possible_xlens=(32, 64),
        interrupt_codes=(CodeRecord(7, "Timer"),),
        exception_codes=(CodeRecord(2, "Illegal"),),
    )
    values = native_prose_values(prose, inputs)
    assert set(values) == {
        "extensions",
        "extension_queries",
        "params",
        "derived",
        "interrupt_code_rows",
        "exception_code_rows",
    }
    assert render_native(prose, values) == "H:S:64:48:6:5:32\n! 7 ! Timer\n! 2 ! Illegal\n"


def test_native_prose_inputs_are_lazy_and_keep_native_diagnostics():
    inputs = ProseInputs(
        "native",
        {"CACHE_BLOCK_SIZE": "invalid"},
        {"H": False},
        possible_xlens=CapturedFailure("LegacyError", "width projection failed"),
        exception_codes=CapturedFailure("LegacyError", "code projection failed"),
    )
    inactive = CapturedProse(
        "{% if extensions.H %}{{ derived.cache_block_size_log2 }}"
        "{% for row in exception_code_rows %}{{ row }}{% endfor %}"
        "{{ derived.has_xlen_32 }}{% endif %}safe"
    )
    assert render_native(inactive, native_prose_values(inactive, inputs)) == "safe"

    malformed = CapturedProse("{{ derived.cache_block_size_log2 }}", "cache.yaml")
    with pytest.raises(ProseError, match="CACHE_BLOCK_SIZE must be an integer") as raised:
        render_native(malformed, native_prose_values(malformed, inputs))
    assert raised.value.diagnostic.legacy_error_class is None
    assert raised.value.diagnostic.observed_inputs == {"CACHE_BLOCK_SIZE": "invalid"}

    failed = CapturedProse("{% if derived.has_xlen_32 %}32{% endif %}", "width.yaml")
    with pytest.raises(ProseError, match="width projection failed") as captured:
        render_native(failed, native_prose_values(failed, inputs))
    assert captured.value.diagnostic.legacy_error_class is None
