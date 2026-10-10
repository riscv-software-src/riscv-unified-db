# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Native field reads must query access types only at applicable structural bases."""

from pathlib import Path

import pytest
from test_idl_architecture_review_fixes import _conditional_architecture

from udb import Configuration, Database, ResolvedDatabase
from udb.idl.errors import IdlValueUnknown
from udb.idl.parser import parse_expression
from udb.idl_architecture import ArchitectureCompiler


@pytest.mark.parametrize("base", [32, 64])
@pytest.mark.parametrize("access", ["RO", "RW"])
def test_symbolic_native_read_uses_only_structurally_applicable_access_types(base, access):
    original = _conditional_architecture(field_base=base)
    documents = {path: dict(data) for path, data in original.database.documents.items()}
    csr = documents["csr/demo.yaml"]
    field = dict(csr["fields"]["F"])
    field["type()"] = f"return CsrFieldType::{access};"
    field.pop("reset_value()")
    field["reset_value"] = 7
    csr["fields"] = {"F": field}
    database = ResolvedDatabase(documents, idl_sources=original.database.idl_sources)
    compiler = ArchitectureCompiler(database.configure(original.configuration))
    table = compiler.global_symbol_table
    assert table.possible_xlens == (32, 64)
    expression = parse_expression("CSR[demo].F")
    expression.type_check(table)
    if access == "RO":
        assert expression.value(table) == 7
    else:
        with pytest.raises(IdlValueUnknown, match="not RO"):
            expression.value(table)


def test_genuine_symbolic_xlen_function_checks_without_forcing_rv32_only_fields():
    root = Path(__file__).resolve().parents[2]
    database = Database.from_path(
        root / "spec/std/isa", schemas_path=root / "spec/schemas"
    ).resolve()
    architecture = database.configure(Configuration.from_file(root / "cfgs/_.yaml"))
    compiled = ArchitectureCompiler(architecture).compile_function("xlen")
    assert compiled.effective_xlen is None
    assert compiled.symtab.get("MXLEN").value is None
    assert compiled.expected_return_type.width == 8
