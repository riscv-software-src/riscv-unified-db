# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Independent public-compiler oracles for the real CSR descriptor protocol."""

import pytest
from test_idl_architecture_adapter import _architecture

from udb import ResolvedDatabase
from udb.idl_architecture import ArchitectureCompiler


def _compiler(*, dynamic_reset=False, present=True):
    original = _architecture()
    documents = {path: dict(data) for path, data in original.database.documents.items()}
    csr = documents["csr/demo.yaml"]
    csr["sw_read()"] = "return CSR[demo].F;"
    field = dict(csr["fields"]["F"])
    field.pop("type()")
    field["type"] = "RO"
    if not dynamic_reset:
        field.pop("reset_value()")
        field["reset_value"] = 7
    field["definedBy"] = present
    csr["fields"] = {"F": field}
    database = ResolvedDatabase(documents, idl_sources=original.database.idl_sources)
    return ArchitectureCompiler(database.configure(original.configuration))


@pytest.mark.parametrize("dynamic_reset", [False, True])
def test_public_csr_read_returns_integer_reset_value(dynamic_reset):
    compiled = _compiler(dynamic_reset=dynamic_reset).compile_csr("demo", effective_xlen=32)
    result = compiled.return_value()
    assert type(result) is int
    assert result == 7


def test_public_absent_csr_field_read_returns_zero():
    compiled = _compiler(present=False).compile_csr("demo", effective_xlen=32)
    assert compiled.return_value() == 0


def test_public_field_descriptor_matches_ast_property_protocol():
    compiler = _compiler()
    field = compiler.global_symbol_table.csr_hash["demo"].fields[0]
    for name, expected in (
        ("defined_in_all_bases", True),
        ("defined_in_base32", True),
        ("defined_in_base64", True),
        ("base32_only", False),
        ("base64_only", False),
        ("exists", True),
    ):
        assert getattr(field, name) is expected, name
    assert field.type(32) == "RO"
    assert type(field.reset_value) is int
    assert field.reset_value == 7
