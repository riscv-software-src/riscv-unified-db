# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Selection presentation, old entrypoint contracts and complete typed encodings."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from udb import Configuration, Database, SchemaStore
from udb.conditions import ParameterOperator, ParameterTerm
from udb.extension_docs import ExtensionDocumentError
from udb.extension_docs.compat import build_parser, repository_inputs, xqci_arguments
from udb.extension_docs.model import condition_adoc
from udb.extension_docs.xqci import xqci_selectors

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize(
    "operator,value,expected",
    [
        ("equal", True, "`P` == true"),
        ("notEqual", 0, "`P` != 0"),
        ("lessThan", 2, "`P` < 2"),
        ("greaterThan", 2, "`P` > 2"),
        ("lessThanOrEqual", 2, "`P` <= 2"),
        ("greaterThanOrEqual", 2, "`P` >= 2"),
        ("includes", 32, "32 in `P`"),
        ("oneOf", (32, 64), "`P` in [32, 64]"),
        ("equal", (True, False), "`P` == [true, false]"),
    ],
)
def test_parameter_condition_symbols_match_native(operator, value, expected):
    assert condition_adoc(ParameterTerm("P", ParameterOperator(operator), value)) == expected


@pytest.mark.parametrize(
    "selector,expected",
    [
        ({"index": 2}, "`P[2]` == 3"),
        ({"size": True}, "`P.size` == 3"),
        ({"bit_range": (7, 2)}, "`P[7:2]` == 3"),
    ],
)
def test_parameter_selectors_are_not_silently_discarded(selector, expected):
    assert condition_adoc(ParameterTerm("P", ParameterOperator.EQUAL, 3, **selector)) == expected


def test_repository_wrapper_requires_explicit_root_and_defaults_to_pdf():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["ext-doc", "-o", "output", "Zba"])
    args = parser.parse_args(["--root", str(ROOT), "ext-doc", "-o", "output", "Zba"])
    assert args.format == "pdf"
    assert args.config == "_" and args.extensions == ["Zba"]
    args = parser.parse_args(
        [
            "--root",
            str(ROOT),
            "ext-doc",
            "-c",
            "qc_iu",
            "-b",
            "chosen",
            "-o",
            "output",
            "-i",
            "--no-csr-field-desc",
            "--format",
            "adoc",
            "Xqcicsr@0.4",
        ]
    )
    assert (args.basename, args.implied_insts, args.no_csr_field_desc) == ("chosen", True, True)
    assert args.format == "adoc"


def test_xqci_selection_and_output_directory_match_original_script():
    configuration = Configuration.from_file(
        ROOT / "cfgs/qc_iu.yaml", schema_store=SchemaStore(ROOT / "spec/schemas")
    )
    database = Database.from_path(
        ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas"
    ).resolve(overlays=(ROOT / "spec/custom/isa" / configuration.overlay,))
    manifest = json.loads((ROOT / "tests/python/fixtures/extension_docs/manifest.json").read_text())
    case = next(item for item in manifest["outcomes"] if item["id"] == "xqci-original-script")
    expected = tuple(case["argv"][case["argv"].index("--no-csr-field-desc") + 1 :])
    assert xqci_selectors(database, "0.13.0") == expected
    assert xqci_selectors(database) == expected
    with pytest.raises(ExtensionDocumentError, match="exact match"):
        xqci_selectors(database, "0.13")
    args = xqci_arguments(database, "0.13.0", "adoc")
    assert args[args.index("-o") + 1] == "gen/ext-doc/pdf/Xqci-0.13.0.pdf"
    assert tuple(args[args.index("--no-csr-field-desc") + 1 :]) == expected


def test_wrapper_overlay_inputs_are_explicit_and_not_bundled(monkeypatch):
    from udb.extension_docs import compat

    calls = []
    configuration = SimpleNamespace(overlay="qc_iu")
    monkeypatch.setattr(
        compat.Configuration,
        "from_file",
        lambda path, **kwargs: calls.append(path) or configuration,
    )
    monkeypatch.setattr(
        compat.Database,
        "from_path",
        lambda *args, **kwargs: SimpleNamespace(
            resolve=lambda **kwargs: calls.append(kwargs["overlays"]) or "database"
        ),
    )
    db, cfg = repository_inputs(ROOT, "qc_iu")
    assert db == "database" and cfg is configuration
    assert calls == [ROOT / "cfgs/qc_iu.yaml", (ROOT / "spec/custom/isa/qc_iu",)]


def test_full_config_uses_native_open_instruction_but_closed_csr_and_extension_links():
    from udb.extension_docs.links import LinkResolver

    configuration = Configuration.from_file(
        ROOT / "cfgs/mc100-32-full-example.yaml", schema_store=SchemaStore(ROOT / "spec/schemas")
    )
    database = Database.from_path(
        ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas"
    ).resolve()
    resolver = LinkResolver(database.configure(configuration))
    assert resolver.resolve("`F` `fcsr` `fld` `c.fld` `satp`") == (
        "`F` `fcsr` xref:#udb-insn-fld[`fld`] xref:#udb-insn-c_fld[`c.fld`] `satp`"
    )
