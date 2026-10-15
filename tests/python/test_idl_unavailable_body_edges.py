# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Edge cases for explicit coverage without synthetic instruction semantics."""

from dataclasses import FrozenInstanceError

import pytest
from test_idl_architecture_adapter import _architecture

from udb import DataError, ResolvedDatabase
from udb.idl_architecture import ArchitectureCompiler


def _changed_instruction(**changes):
    original = _architecture()
    documents = {path: dict(data) for path, data in original.database.documents.items()}
    instruction = documents["inst/inc.yaml"]
    instruction.pop("operation()")
    instruction.update(changes)
    database = ResolvedDatabase(documents, idl_sources=original.database.idl_sources)
    return ArchitectureCompiler(database.configure(original.configuration))


def test_known_absent_instruction_has_no_attempt_or_coverage_gap():
    result = _changed_instruction(definedBy=False).type_check()
    assert result.complete
    assert result.unavailable == ()
    assert not any(context.startswith("instruction inc/") for context in result.checked)


def test_present_non_string_body_is_diagnostic_not_unavailable():
    result = _changed_instruction(**{"operation()": None}).type_check()
    assert not result.complete
    assert result.unavailable == ()
    assert "instruction inc/RV32" in result.checked
    assert [(item.context, type(item.error)) for item in result.diagnostics] == [
        ("instruction inc/RV32", DataError)
    ]


def test_unavailable_source_is_honest_immutable_record_behavior_reference():
    result = _changed_instruction().type_check()
    assert result.ok
    assert not result.complete
    result.raise_errors()
    unavailable = result.unavailable[0]
    assert unavailable.source == "inst/inc.yaml#/operation()"
    assert unavailable.behavior == "operation()"
    with pytest.raises(FrozenInstanceError):
        unavailable.reason = "fabricated semantics"
