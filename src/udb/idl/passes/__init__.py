# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Whole-tree IDL semantic and rendering passes.

Semantic state is explicit. Pruning owns its tree and symbol values; reachability
caches are caller-owned and hold complete specialized transitive closures.
``constexpr``, ``control_flow``, and ``written`` replace the hart generator's
AST monkey patches. Decoder records describe one effective XLEN and accept
consumer-supplied C++ names and implementation guards.

AsciiDoc functions emit source only, entirely in Python. Rendering is an
external consumer step using an already installed Asciidoctor/official PDF
renderer; no renderer or Ruby-backed IDL pass is bundled here.
"""

from .adoc import to_adoc, to_option_adoc
from .decode_tree import (
    DecodeEncoding,
    DecodeGenerator,
    DecodeNodeKind,
    DecodeTreeNode,
    DecodeVariable,
    build_decode_tree,
    decode_variable_allowed_condition,
    extract_decode_variable,
)
from .discovery import (
    RegisterRef,
    destination_registers,
    referenced_csrs,
    source_registers,
)
from .hart import constexpr, control_flow, written
from .pruning import prune
from .reachability import reachable_exceptions, reachable_functions
from .returns import ConditionalReturnValue, return_values

__all__ = [
    "ConditionalReturnValue",
    "DecodeEncoding",
    "DecodeGenerator",
    "DecodeNodeKind",
    "DecodeTreeNode",
    "DecodeVariable",
    "RegisterRef",
    "build_decode_tree",
    "constexpr",
    "control_flow",
    "decode_variable_allowed_condition",
    "destination_registers",
    "extract_decode_variable",
    "prune",
    "reachable_exceptions",
    "reachable_functions",
    "referenced_csrs",
    "return_values",
    "source_registers",
    "to_adoc",
    "to_option_adoc",
    "written",
]
