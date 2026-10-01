# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Document-lifetime memoization of the existing compiler's immutable contexts."""

from __future__ import annotations

from ..conditions import parse_condition
from ..idl.ast import FunctionCallExpression, FunctionDef
from ..idl.parser import parse_function_body
from ..idl.types import FunctionType
from ..idl_architecture import ArchitectureCompiler


class _QueryMemo:
    """Forward the immutable architecture API, memoizing only its query results."""

    def __init__(self, architecture):
        self._architecture = architecture
        self._presence = {}

    def __getattr__(self, name):
        return getattr(self._architecture, name)

    def condition_presence(self, condition):
        parsed = parse_condition(condition)
        if parsed not in self._presence:
            self._presence[parsed] = self._architecture.condition_presence(parsed)
        return self._presence[parsed]


class DocumentCompiler(ArchitectureCompiler):
    """Reuse contexts during the thousands of field-type reads in a document.

    All parsing, binding and semantics stay in ArchitectureCompiler. Contexts
    are keyed by the whole compilation request in this one fixed architecture.
    Return-value evaluation and pruning already own their symbol-table clones.
    """

    def __init__(self, architecture):
        self._document_contexts = {}
        self.source_functions = {}
        super().__init__(_QueryMemo(architecture))

    def compile_instruction(self, name, *, effective_xlen, type_check=True):
        key = ("instruction", name, effective_xlen, type_check)
        if key not in self._document_contexts:
            self._document_contexts[key] = super().compile_instruction(
                name, effective_xlen=effective_xlen, type_check=type_check
            )
        return self._document_contexts[key]

    def instruction_ast(self, name):
        key = ("instruction-source", name)
        if key not in self._document_contexts:
            source = self._source(self.database.instruction(name), ("operation()",))
            self._document_contexts[key] = parse_function_body(source.text, source=source)
            self.record_source_functions(self._document_contexts[key])
        return self._document_contexts[key]

    def record_source_functions(self, tree):
        nodes = [tree]
        while nodes:
            node = nodes.pop()
            if isinstance(node, FunctionCallExpression):
                function = self.global_symbol_table.get(node.name)
                if isinstance(function, FunctionType) and isinstance(
                    function.func_def_ast, FunctionDef
                ):
                    self.source_functions[node.name] = function.func_def_ast
            nodes.extend(node.children)

    def source_function_closure(self, functions):
        result = dict(functions)
        pending = list(result.values())
        while pending:
            self.record_source_functions(pending.pop())
            for name, function in self.source_functions.items():
                if name not in result:
                    result[name] = function
                    pending.append(function)
        return tuple(result.values())

    def compile_csr(self, name, behavior="sw_read()", *, effective_xlen=None, type_check=True):
        key = ("csr", name, behavior, effective_xlen, type_check)
        if key not in self._document_contexts:
            self._document_contexts[key] = super().compile_csr(
                name, behavior, effective_xlen=effective_xlen, type_check=type_check
            )
            if not type_check:
                self.record_source_functions(self._document_contexts[key].ast)
        return self._document_contexts[key]

    def compile_field(
        self, csr_name, field_name, behavior, *, effective_xlen=None, type_check=True
    ):
        key = ("field", csr_name, field_name, behavior, effective_xlen, type_check)
        if key not in self._document_contexts:
            self._document_contexts[key] = super().compile_field(
                csr_name,
                field_name,
                behavior,
                effective_xlen=effective_xlen,
                type_check=type_check,
            )
        return self._document_contexts[key]
