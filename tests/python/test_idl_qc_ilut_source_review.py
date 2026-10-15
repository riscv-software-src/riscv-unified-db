# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""The ILUT double-entry count is a runtime CSR value, not an IDL constant."""

from pathlib import Path

from udb import Configuration, Database
from udb.idl_architecture import ArchitectureCompiler

ROOT = Path(__file__).resolve().parents[2]


def test_genuine_qc_ilut_compiles_with_runtime_double_entry_count():
    configuration = Configuration.from_file(ROOT / "cfgs/qc_iu.yaml")
    database = Database.from_path(
        ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas"
    ).resolve(overlays=(ROOT / "spec/custom/isa/qc_iu",))
    compiler = ArchitectureCompiler(database.configure(configuration))
    compiled = compiler.compile_instruction("qc.cm.ilut", effective_xlen=32)
    assert compiled.effective_xlen == 32
    assert compiled.source.label == "overlay[0]:inst/Xqccmi/qc.cm.ilut.yaml"
    count = compiled.symtab.get("double_entry_count")
    assert count is not None
    assert count.type.width == 32
    assert not count.type.is_const
    assert count.value is None
    decode = compiled.symtab.get("ilut_index")
    assert decode.decode_var
    assert decode.type.width == 11
    assert "XReg double_entry_count = {21'b0, CSR[qc.itdec].dec};" in compiled.source.text
    assert "if (ilut_index < double_entry_count)" in compiled.source.text
    assert "(double_entry_count * 8) + ((ilut_index - double_entry_count) * 4)" in (
        compiled.source.text
    )
