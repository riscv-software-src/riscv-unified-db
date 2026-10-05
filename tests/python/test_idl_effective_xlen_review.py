# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Public compilation cannot invent execution widths for a fixed architecture."""

import pytest
from test_idl_architecture_adapter import _architecture

from udb import DataError
from udb.idl_architecture import ArchitectureCompiler


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("compile_instruction", ("inc",)),
        ("compile_csr", ("demo",)),
        ("compile_field", ("demo", "F", "type()")),
        ("compile_field", ("demo", "F", "sw_write(csr_value)")),
        ("compile_field", ("demo", "F", "reset_value()")),
    ],
)
def test_public_compilation_rejects_impossible_execution_width(method, args):
    compiler = ArchitectureCompiler(_architecture())
    compile_body = getattr(compiler, method)
    assert compile_body(*args, effective_xlen=32).effective_xlen == 32
    with pytest.raises((DataError, ValueError), match=r"XLEN|RV64"):
        compile_body(*args, effective_xlen=64)
