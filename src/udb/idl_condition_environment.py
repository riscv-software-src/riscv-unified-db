# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Translation-only signatures and genuine configuration-independent globals."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .idl.ast import GlobalWithInitialization
from .idl.parser import parse_isa
from .idl.source import IdlSource
from .idl.symbols import SymbolTable
from .idl_global_environment import global_ast

if TYPE_CHECKING:
    from .database import ResolvedDatabase

_PREDICATE_SIGNATURES = """%version: 1.0
generated function implemented? {
  returns Boolean
  arguments ExtensionName extension
  description { Configuration-dependent extension presence. }
}
generated function implemented_version? {
  returns Boolean
  arguments ExtensionName extension, String version_requirement
  description { Configuration-dependent extension version presence. }
}
generated function implemented_csr? {
  returns Boolean
  arguments Bits<12> csr_addr
  description { Configuration-dependent CSR address presence. }
}
builtin function xlen {
  returns Bits<8>
  description { Effective XLEN, symbolic until an execution scope is supplied. }
}
"""


def add_predicate_signatures(symtab: SymbolTable) -> None:
    """Register generated predicates and xlen's native signature, never its stateful body."""
    source = IdlSource(text=_PREDICATE_SIGNATURES, label="<condition-predicate-signatures>")
    for function in parse_isa(source.text, source=source).functions:
        function.add_symbol(symtab)


def add_encoding_size_constant(database: ResolvedDatabase, symtab: SymbolTable) -> None:
    """Register only the translation constant from genuine captured globals."""
    isa = global_ast(database)
    if isa is None:
        return
    for definition in isa.definitions:
        if (
            isinstance(definition, GlobalWithInitialization)
            and definition.var_decl_with_init.lhs.name == "INSTR_ENC_SIZE"
        ):
            definition.type_check(symtab)
