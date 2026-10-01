# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Retained human reports and structured fixed-bit instruction queries."""

from .formatting import ReportError
from .matching import (
    DecodedVariable,
    DisassemblyReport,
    InstructionMatch,
    InstructionMatcher,
    InstructionSelection,
    MatchingError,
    XlenMatches,
    decode_variable,
    parse_encoding,
    possible_xlens,
)
from .reports import (
    ExtensionReport,
    ParameterListReport,
    ParameterReport,
    ParameterRow,
    ReportBuilder,
    catalog_names,
    render_extension,
    render_names,
    render_parameter,
)

__all__ = [
    "DecodedVariable",
    "DisassemblyReport",
    "ExtensionReport",
    "InstructionMatch",
    "InstructionMatcher",
    "InstructionSelection",
    "MatchingError",
    "ParameterListReport",
    "ParameterReport",
    "ParameterRow",
    "ReportBuilder",
    "ReportError",
    "XlenMatches",
    "catalog_names",
    "decode_variable",
    "parse_encoding",
    "possible_xlens",
    "render_extension",
    "render_names",
    "render_parameter",
]
