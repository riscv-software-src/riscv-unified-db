# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Missing optional semantics are explicit, not fabricated or type errors."""

import pytest
from test_idl_architecture_adapter import _architecture

from udb import DataError, ResolvedDatabase
from udb.idl.errors import IdlTypeError
from udb.idl_architecture import ArchitectureCompiler, ArchitectureTypeCheckResult


def _compiler(*, operation="g = imm;"):
    original = _architecture(operation=operation)
    documents = {path: dict(data) for path, data in original.database.documents.items()}
    missing = dict(documents["inst/inc.yaml"])
    missing["name"] = "missing"
    missing.pop("operation()")
    documents["inst/missing.yaml"] = missing
    database = ResolvedDatabase(documents, idl_sources=original.database.idl_sources)
    return ArchitectureCompiler(database.configure(original.configuration))


def test_absent_operation_is_explicit_unavailable_not_successful_compilation():
    compiler = _compiler()
    with pytest.raises(DataError, match=r"operation"):
        compiler.compile_instruction("missing", effective_xlen=32)
    result = compiler.type_check()
    assert result.ok
    assert not result.complete
    assert not result.diagnostics
    assert "instruction inc/RV32" in result.checked
    assert "instruction missing/RV32" not in result.checked
    assert len(result.unavailable) == 1
    unavailable = result.unavailable[0]
    assert unavailable.context == "instruction missing/RV32"
    assert "inst/missing.yaml" in str(unavailable.source)
    assert "operation()" in unavailable.reason


def test_invalid_present_body_stays_diagnostic_beside_unavailable_source():
    result = _compiler(operation="g = unknown;").type_check()
    assert not result.ok
    assert not result.complete
    assert len(result.unavailable) == 1
    assert [(item.context, type(item.error)) for item in result.diagnostics] == [
        ("instruction inc/RV32", IdlTypeError)
    ]


def test_empty_present_operation_is_checked_not_unavailable():
    result = ArchitectureCompiler(_architecture(operation="")).type_check()
    assert result.ok
    assert result.complete
    assert not result.unavailable
    assert "instruction inc/RV32" in result.checked


def test_existing_result_constructor_keeps_complete_default():
    result = ArchitectureTypeCheckResult(("existing",), ())
    assert result.ok
    assert result.complete
    assert result.unavailable == ()
