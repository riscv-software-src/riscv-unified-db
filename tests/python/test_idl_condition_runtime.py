# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Real architecture validity and compiled-context boundaries after IDL closure."""

from pathlib import Path

import pytest

from udb import ArchitectureCheckStatus, Configuration, Database
from udb.idl.types import TypeKind

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module", params=("_", "rv32", "rv64", "qc_iu"))
def runtime_architecture(request):
    if request.param == "qc_iu":
        database = Database.from_path(
            ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas"
        ).resolve(overlays=(ROOT / "spec/custom/isa/qc_iu",))
    else:
        database = Database.bundled().resolve()
    return database.configure(Configuration.from_file(ROOT / "cfgs" / f"{request.param}.yaml"))


def test_real_runtime_architecture_is_valid_without_idl_deferrals(runtime_architecture):
    result = runtime_architecture.check()
    assert result.status is ArchitectureCheckStatus.VALID, result.diagnostics
    assert not any(item.code == "idl-deferred" for item in result.diagnostics)
    assert all(not condition.has_unresolved for condition, _ in runtime_architecture._constraints)


def test_real_runtime_instruction_and_csr_hooks(runtime_architecture):
    xlen = runtime_architecture.configuration.mxlen or 32
    instruction = runtime_architecture.instruction_operation("addi", effective_xlen=xlen)
    assert instruction.effective_xlen == xlen
    assert instruction.source.label == "inst/I/addi.yaml"
    assert (
        instruction.source.text
        == runtime_architecture.database.instruction("addi").data["operation()"]
    )
    assert instruction.symtab.get("__effective_xlen").value == xlen
    assert instruction.symtab.get("__instruction_encoding_size").value == 32
    assert instruction.symtab.get("imm").decode_var

    csr = runtime_architecture.csr_behavior("misa", effective_xlen=xlen)
    assert csr.effective_xlen == xlen
    assert csr.source.label == "csr/misa.yaml"
    assert csr.source.text == runtime_architecture.database.csr("misa").data["sw_read()"]
    assert csr.expected_return_type.kind is TypeKind.BITS
