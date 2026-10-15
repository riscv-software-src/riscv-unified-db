# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""The genuine rotate body must retain its raw immediate binding."""

from pathlib import Path

import pytest

from udb import Configuration, Database
from udb.idl_architecture import ArchitectureCompiler

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def compiler():
    database = Database.from_path(
        ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas"
    ).resolve()
    return ArchitectureCompiler(database.configure(Configuration.from_file(ROOT / "cfgs/_.yaml")))


@pytest.mark.parametrize("xlen", [32, 64])
def test_actual_rori_body_checks_without_redeclaring_decode_immediate(compiler, xlen):
    compiled = compiler.compile_instruction("rori", effective_xlen=xlen)
    immediate = compiled.symtab.get("shamt")
    assert immediate.decode_var
    assert immediate.type.width == (5 if xlen == 32 else 6)
    assert compiled.effective_xlen == xlen
    assert "inst/B/rori.yaml" in compiled.source.label
