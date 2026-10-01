# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Native, deterministic legacy instruction-table generation."""

from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from .database import Database
from .instruction_fields import (
    ArchitectureSource,
    DecodeField,
    EncodingFields,
    InstructionFieldBuilder,
    InstructionFields,
)

_HEADER = """# SPDX-License-Identifier: BSD-3-Clause-Clear
#
# GENERATED WITH https://github.com/riscv-software-src/riscv-unified-db
# "{command}"
#
# Each line of the instruction table should have the following format:
# NAME BASE FIXED_BITS [VARIABLE_LIST]
# NAME                        instruction name
# BASE                        instruction base size (common[,(32|64)])
#                             "common" means the instruction is valid on both architecture sizes
#                             "32" or "64" means the instruction is valid on that size
#                             if the instruction is valid on both architectures but has unique
#                             encodings, use a 32-bit entry "common,32" and 64-bit entry
# FIXED_BITS                  bitfields of the fixed bits of an instruction concatenated with '|'
#                             continuous grouping of fixed bits are in the form of 'bits<offset'
# VARIABLE_LIST               a variable sized list of all variables in the instruction definition
#                             in the form of name[~][<num][!num...]=(high[-low])|...
#                             symbols after the name represent different modifiers:
#                                 ~ sign extension, can only appear once
#                                 < left shift by 'num' amount on extraction, can only appear once
#                                 ! mark 'num' as an invalid input for this variable
"""


def _variable_column(field: DecodeField) -> str:
    text = field.name + ("~" if field.sign_extend else "")
    text += "".join(f"!{value}" for value in field.exclusions)
    if field.left_shift:
        text += f"<{field.left_shift}"
    return f"{text}={field.location}"


def _columns(encoding: EncodingFields | None) -> tuple[str, ...]:
    if encoding is None:
        return ()
    fixed = "|".join(f"{field.bits}<{field.location.low}" for field in encoding.opcodes)
    return (fixed, *(_variable_column(field) for field in encoding.variables))


@dataclass(frozen=True, slots=True)
class InstructionTableRow:
    name: str
    base: str
    columns: tuple[str, ...]

    def render(self) -> str:
        return " ".join((self.name, self.base, *self.columns))


def instruction_table_rows(
    instructions: Iterable[InstructionFields],
) -> tuple[InstructionTableRow, ...]:
    """Format descriptors without changing supplied field order or locations."""
    rows = []
    for instruction in instructions:
        rv32, rv64 = (_columns(instruction.encoding(xlen)) for xlen in (32, 64))
        if not rv32 and not rv64:
            raise ValueError(f"instruction {instruction.name} has no RV32 or RV64 encoding")
        if rv32 == rv64:
            rows.append(InstructionTableRow(instruction.name, "common", rv64))
        elif rv32 and rv64:
            rows.append(InstructionTableRow(instruction.name, "common,32", rv32))
            rows.append(InstructionTableRow(instruction.name, "common,64", rv64))
        else:
            rows.append(InstructionTableRow(instruction.name, "32" if rv32 else "64", rv32 or rv64))
    return tuple(sorted(rows, key=lambda row: row.render()))


def render_instruction_table_rows(
    rows: Iterable[InstructionTableRow], *, file_name: str | Path | None = None
) -> str:
    """Render the exact legacy artifact, including stdout/file command provenance."""
    command = "./bin/generate inst-table"
    if file_name is not None:
        command += f" -o {Path(file_name).name}"
    lines = sorted(row.render() for row in rows)
    return _HEADER.format(command=command) + "\n".join(lines) + "\n"


def render_instruction_table(
    source: ArchitectureSource | None = None, *, file_name: str | Path | None = None
) -> str:
    """Render all database instructions, preserving legacy configuration behavior."""
    builder = InstructionFieldBuilder(Database.bundled() if source is None else source)
    rows = instruction_table_rows(
        builder.describe(instruction) for instruction in builder.database.instructions
    )
    return render_instruction_table_rows(rows, file_name=file_name)


def generate_instruction_table(
    source: ArchitectureSource | None = None,
    *,
    output: str | Path | None = None,
    stdout: TextIO | None = None,
) -> str:
    """Write to stdout or a file, returning the exact bytes' Unicode text.

    File mode, like the legacy generator, overwrites a file without creating its
    parent. The artifact is fully validated before any output is written.
    """
    text = render_instruction_table(source, file_name=output)
    if output is None:
        (sys.stdout if stdout is None else stdout).write(text)
    else:
        with Path(output).open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    return text
