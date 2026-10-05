# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Owned architecture/descriptor contexts for source generation."""

from __future__ import annotations

from dataclasses import dataclass

from udb.architecture import ConfiguredArchitecture
from udb.idl import ast
from udb.idl.passes import prune, reachable_functions
from udb.idl.types import Type, TypeKind
from udb.idl_architecture import ArchitectureCompiler, CompiledIdl, IdlUnavailable
from udb.idl_condition_binding import IdlConditionBinding
from udb.idl_environment import possible_xlens
from udb.instruction_fields import InstructionFieldBuilder

from .emitter import Emitter
from .types import CppGenerationError, literal, names


@dataclass(frozen=True)
class Body:
    ast: ast.Node
    emitter: Emitter

    def cpp(self, indent: int = 0) -> str:
        return self.emitter.statement(self.ast, indent)


class Context:
    """No generator/compiler state is shared between selected configurations."""

    def __init__(self, architecture: ConfiguredArchitecture):
        self.arch = architecture
        self.database = architecture.database
        self.name = architecture.configuration.name
        names(self.name, "cfg")
        self.compiler = ArchitectureCompiler(architecture)
        self.table = self.compiler.global_symbol_table
        self.global_ast = self.compiler.global_ast
        if self.global_ast is None or self.global_ast.fetch is None:
            raise CppGenerationError("C++ hart generation requires genuine global IDL and fetch")
        self.xlens = possible_xlens(architecture)
        self.mxlen = architecture.configuration.mxlen or max(self.xlens)
        self.multi = len(self.xlens) > 1
        builder = InstructionFieldBuilder(architecture)
        self.instructions = tuple(
            builder.describe(record) for record in architecture.possible_instructions
        )
        self.encodings = {
            (inst.name, enc.xlen): enc
            for inst in self.instructions
            for enc in inst.encodings
            if enc.xlen in self.xlens
        }
        self.largest_encoding = max((enc.length for enc in self.encodings.values()), default=32)
        self.csrs = tuple(
            (record, self.table.csr(record.name))
            for record in architecture.possible_csrs
            if any(self.table.csr(record.name).defined_in_base(xlen) for xlen in self.xlens)
        )
        self.parameters = tuple(self.database.objects("parameter"))
        self.binding = IdlConditionBinding(self.database, architecture.configuration)
        self.unavailable: list[IdlUnavailable] = []
        self._operations: dict[tuple[str, int], Body | None] = {}
        self._field_bodies: dict[tuple[str, str, str, int], Body] = {}
        self._csr_bodies: dict[tuple[str, int], Body] = {}
        self._functions = None

    def symbol(self, kind, *extra):
        return names(self.name, kind, *extra)

    def condition(self, record, raw=None):
        raw = record.data.get("definedBy", True) if raw is None else raw
        if isinstance(raw, str):
            raw = {"extension": {"name": raw}}
        return self.binding.resolve_record(raw, record, ("definedBy",))

    def body(self, compiled: CompiledIdl, *, prune_body=True) -> Body:
        tree = prune(compiled.ast, compiled.symtab) if prune_body else compiled.ast
        return Body(tree, Emitter(compiled.symtab))

    def operation(self, name, xlen) -> Body | None:
        key = name, xlen
        if key not in self._operations:
            record = self.database.instruction(name)
            if "operation()" not in record:
                self.unavailable.append(
                    IdlUnavailable(
                        f"instruction {name}/RV{xlen}",
                        f"{record.path}#/operation()",
                        "operation()",
                        "operation() is not defined",
                    )
                )
                self._operations[key] = None
            else:
                self._operations[key] = self.body(
                    self.compiler.compile_instruction(name, effective_xlen=xlen)
                )
        return self._operations[key]

    def field_body(self, csr, field, behavior, xlen):
        key = csr, field, behavior, xlen
        if key not in self._field_bodies:
            self._field_bodies[key] = self.body(
                self.compiler.compile_field(csr, field, behavior, effective_xlen=xlen)
            )
        return self._field_bodies[key]

    def csr_body(self, csr, xlen):
        key = csr, xlen
        if key not in self._csr_bodies:
            self._csr_bodies[key] = self.body(self.compiler.compile_csr(csr, effective_xlen=xlen))
        return self._csr_bodies[key]

    def fields(self, record, descriptor):
        present = {field.name for field in self.arch.possible_csr_fields(record)}
        return tuple(
            field
            for field in descriptor.fields
            if field.name in present and any(field.defined_in_base(xlen) for xlen in self.xlens)
        )

    def fetch(self):
        fetch = self.global_ast.fetch
        table = self.compiler.global_symbol_table
        table.push(fetch)
        size = table.get("INSTR_ENC_SIZE").value
        table.add("__expected_return_type", Type(TypeKind.BITS, width=size))
        fetch.body.type_check(table)
        return Body(prune(fetch.body, table), Emitter(table))

    def expression(self, text):
        from udb.idl.parser import parse_expression

        node = parse_expression(text)
        node.type_check(self.table)
        return Emitter(self.table).expression(node)

    @property
    def functions(self):
        if self._functions is None:
            roots = [self.fetch()]
            for inst in self.instructions:
                for xlen in self.xlens:
                    if (inst.name, xlen) in self.encodings:
                        body = self.operation(inst.name, xlen)
                        if body is not None:
                            roots.append(body)
            for record, descriptor in self.csrs:
                for xlen in self.xlens:
                    if not descriptor.defined_in_base(xlen):
                        continue
                    if "sw_read()" in record:
                        roots.append(self.csr_body(record.name, xlen))
                    for field in self.fields(record, descriptor):
                        if not field.defined_in_base(xlen):
                            continue
                        data = record["fields"][field.name]
                        for behavior in ("type()", "reset_value()", "sw_write(csr_value)"):
                            if behavior in data:
                                roots.append(
                                    self.field_body(record.name, field.name, behavior, xlen)
                                )
            functions = {}
            cache = {}
            for body in roots:
                for func in reachable_functions(body.ast, body.emitter.symtab, cache=cache):
                    functions[func.name] = func
            # These are native hart entry points independent of instruction roots.
            for name in ("raise", "mode", "xlen", "translate", "refresh_pending_interrupts"):
                binding = self.table.get(name)
                if binding is None:
                    raise CppGenerationError(f"Missing native hart entry point {name!r}")
                definition = binding.func_def_ast
                functions[name] = definition
                compiled = self.compiler.compile_function(name)
                if isinstance(compiled.ast, ast.FunctionBody):
                    for func in reachable_functions(compiled.ast, compiled.symtab, cache=cache):
                        functions[func.name] = func
            self._functions = tuple(functions[key] for key in sorted(functions))
        return self._functions

    def function(self, func):
        compiled = self.compiler.compile_function(func.name)
        return compiled, self.body(compiled)

    def register_width(self, name):
        # The ordinary compiler environment exposes the evaluated width callback.
        # Its register-file symbol type retains the maximum capacity separately.
        dtype = self.table.get(name).type.sub_type
        return dtype.width, dtype.max_width

    def globals(self):
        emitter = Emitter(self.table)
        for node in self.global_ast.globals:
            name = node.id
            dtype = self.table.get(name).type
            immutable = False
            initializer = None
            if isinstance(node, ast.GlobalWithInitialization) and dtype.is_const:
                try:
                    initializer = literal(node.rhs.value(self.table))
                    immutable = True
                except Exception as error:
                    from udb.idl.errors import IdlValueUnknown

                    if not isinstance(error, IdlValueUnknown):
                        raise
            if initializer is None and isinstance(node, ast.GlobalWithInitialization):
                initializer = emitter._array_cast(
                    dtype, node.rhs.type(self.table), emitter.expression(node.rhs)
                )
            yield name, dtype, immutable, initializer
