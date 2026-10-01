# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Source-preserving architecture IDL compilation using the ordinary compiler."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .architecture import QueryPresence
from .encoding import instruction_encodings
from .errors import DataError
from .idl.ast import FunctionBody, FunctionDef, Node
from .idl.errors import IdlError, IdlInternalError, IdlValueUnknown
from .idl.parser import parse_function_body
from .idl.source import IdlSource
from .idl.symbols import SymbolTable, Var
from .idl.types import (
    VOID_TYPE,
    BitfieldType,
    FunctionType,
    Qualifier,
    Type,
    TypeKind,
)
from .idl_environment import possible_xlens, symbol_table
from .idl_global_environment import global_ast
from .idl_yaml_source import idl_field_source

if TYPE_CHECKING:
    from .architecture import ConfiguredArchitecture
    from .database import DatabaseObject


@dataclass(frozen=True, slots=True)
class CompiledIdl:
    """A compiled AST and its independent binding/effective-XLEN context."""

    ast: Node
    symtab: SymbolTable
    source: IdlSource
    effective_xlen: int | None
    expected_return_type: Type

    def return_value(self) -> object:
        """Evaluate with fresh bindings so repeated queries do not share mutations."""
        if not isinstance(self.ast, FunctionBody):
            raise IdlValueUnknown("A generated/builtin function has no evaluable body", self.ast)
        return self.ast.return_value(self.symtab.deep_clone())


@dataclass(frozen=True, slots=True)
class IdlDiagnostic:
    context: str
    error: Exception


@dataclass(frozen=True, slots=True)
class IdlUnavailable:
    context: str
    source: str
    behavior: str
    reason: str


@dataclass(frozen=True, slots=True)
class ArchitectureTypeCheckResult:
    checked: tuple[str, ...]
    diagnostics: tuple[IdlDiagnostic, ...]
    unavailable: tuple[IdlUnavailable, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.diagnostics

    @property
    def complete(self) -> bool:
        return self.ok and not self.unavailable

    def raise_errors(self) -> None:
        if self.diagnostics:
            detail = "\n".join(f"{item.context}: {item.error}" for item in self.diagnostics)
            raise IdlInternalError(f"Architecture IDL type checking failed:\n{detail}")


class ArchitectureCompiler:
    """Compile operations, globals and CSR behaviors from a resolved architecture."""

    def __init__(self, cfg_arch: ConfiguredArchitecture) -> None:
        self.architecture = cfg_arch
        self.database = cfg_arch.database
        self.global_ast = global_ast(self.database)
        self._globals = symbol_table(cfg_arch)
        self._globals.freeze_globals()
        for csr in self._globals.csr_hash.values():
            csr._bases._compiler = self

    @property
    def global_symbol_table(self) -> SymbolTable:
        return self._globals.global_clone()

    def _validate_xlen(self, effective_xlen: int | None) -> None:
        if effective_xlen not in (None, 32, 64):
            raise ValueError("effective XLEN must be 32 or 64")
        if effective_xlen is not None and effective_xlen not in possible_xlens(self.architecture):
            raise DataError(
                f"Effective XLEN RV{effective_xlen} is not defined for this architecture"
            )

    def _source(self, record: DatabaseObject, path: tuple[str, ...]) -> IdlSource:
        value: object = record.data
        for part in path:
            if not isinstance(value, Mapping) or part not in value:
                raise DataError(f"{record.path}#/{'/'.join(path)} is not defined")
            value = value[part]
        if not isinstance(value, str):
            raise DataError(f"{record.path}#/{'/'.join(path)} must be an IDL string")
        span = record.source_at(*path)
        if span is None:
            return IdlSource(text=value, label=f"{record.path}#/{'/'.join(path)}")
        text = self.database.source_text(span.source, layer=span.layer)
        label = span.source if span.layer == "source" else f"{span.layer}:{span.source}"
        return idl_field_source(text, span, value, label=label)

    def _scope(
        self, ast: Node, effective_xlen: int | None, expected: Type, encoding_width: int = 32
    ) -> SymbolTable:
        self._validate_xlen(effective_xlen)
        table = self._globals.global_clone()
        table.push(ast)
        table.add("__expected_return_type", expected)
        table.add(
            "__instruction_encoding_size",
            Var(
                "__instruction_encoding_size",
                Type(TypeKind.BITS, width=encoding_width.bit_length()),
                encoding_width,
            ),
        )
        if effective_xlen is not None:
            table.add(
                "__effective_xlen",
                Var("__effective_xlen", Type(TypeKind.BITS, width=7).make_const(), effective_xlen),
            )
        return table

    def _body(
        self,
        record: DatabaseObject,
        path: tuple[str, ...],
        effective_xlen: int | None,
        expected: Type,
        *,
        specialize_mxlen: bool = True,
    ) -> CompiledIdl:
        source = self._source(record, path)
        ast = parse_function_body(source.text, source=source)
        table = self._scope(ast, effective_xlen, expected)
        if specialize_mxlen and table.get("MXLEN") is not None and table.get("MXLEN").value is None:
            table.add(
                "MXLEN",
                Var("MXLEN", Type(TypeKind.BITS, width=7).make_const(), effective_xlen, param=True),
            )
        return CompiledIdl(ast, table, source, effective_xlen, expected)

    def compile_instruction(
        self, name: str, *, effective_xlen: int, type_check: bool = True
    ) -> CompiledIdl:
        """Compile one applicable encoding with constant, signed decode bindings."""
        self._validate_xlen(effective_xlen)
        if effective_xlen is None:
            raise ValueError("instruction compilation requires an explicit effective XLEN")
        record = self.database.instruction(name)
        if record.data.get("base") not in (None, effective_xlen):
            raise DataError(f"Instruction {name} is not defined for RV{effective_xlen}")
        source = self._source(record, ("operation()",))
        ast = parse_function_body(source.text, source=source)
        encoding = next(
            (
                item
                for item in instruction_encodings(self.architecture, record)
                if item.xlen == effective_xlen
            ),
            None,
        )
        if encoding is None:
            raise DataError(f"Instruction {name} has no RV{effective_xlen} encoding")
        table = self._scope(ast, effective_xlen, VOID_TYPE, encoding.length)
        raw = record.data.get("encoding", record.data.get("format"))
        if not isinstance(raw, Mapping):
            raise DataError(f"Instruction {name} has no encoding definition")
        raw = raw if "match" in raw or "length" in raw else raw.get(f"RV{effective_xlen}")
        if not isinstance(raw, Mapping):
            raise DataError(f"Instruction {name} has no RV{effective_xlen} decoder definition")
        variables = raw.get("variables", {})
        variables = (
            ({**data, "name": var_name} for var_name, data in variables.items())
            if isinstance(variables, Mapping)
            else variables
        )
        for variable in variables:
            width = self._decode_width(variable.get("location")) + variable.get("left_shift", 0)
            dtype = Type(TypeKind.BITS, width=width, qualifiers=(Qualifier.CONST,))
            if variable.get("sign_extend", False):
                dtype = dtype.qualify(Qualifier.SIGNED)
            table.add_unique(variable["name"], Var(variable["name"], dtype, decode_var=True))
            alias = variable.get("alias")
            if isinstance(alias, str):
                table.add_unique(alias, Var(alias, dtype, decode_var=True))
        if type_check:
            ast.type_check(table)
        return CompiledIdl(ast, table, source, effective_xlen, VOID_TYPE)

    @staticmethod
    def _decode_width(location: object) -> int:
        if isinstance(location, int):
            return 1
        if not isinstance(location, str):
            raise DataError(f"Unsupported decode-variable location: {location!r}")
        width = 0
        for part in location.split("|"):
            bits = part.split("-")
            if len(bits) == 1:
                int(bits[0])
                width += 1
            elif len(bits) == 2 and int(bits[0]) >= int(bits[1]):
                width += int(bits[0]) - int(bits[1]) + 1
            else:
                raise DataError(f"Invalid decode-variable location: {location!r}")
        return width

    def compile_function(
        self, name: str, *, effective_xlen: int | None = None, type_check: bool = True
    ) -> CompiledIdl:
        function = self._globals.get(name)
        if not isinstance(function, FunctionType) or not isinstance(
            function.func_def_ast, FunctionDef
        ):
            raise DataError(f"No architecture IDL function {name!r}")
        definition = function.func_def_ast
        ast = definition.body if definition.body is not None else definition
        table = self._scope(ast, effective_xlen, VOID_TYPE)
        for dtype, argument in definition.semantic_arguments(table):
            if table.defined_in_current_scope(argument):
                definition.type_error(
                    f"Function argument {argument!r} is already bound in this scope"
                )
            table.add(argument, Var(argument, dtype))
        expected = definition.return_type(table)
        table.add("__expected_return_type", expected)
        if type_check:
            global_context = self._globals.global_clone()
            for binding in ("__effective_xlen", "__instruction_encoding_size"):
                if table.get(binding) is not None:
                    global_context.add(binding, table.get(binding))
            definition.type_check(global_context)
        return CompiledIdl(ast, table, ast.source, effective_xlen, expected)

    def compile_csr(
        self,
        name: str,
        behavior: str = "sw_read()",
        *,
        effective_xlen: int | None = None,
        type_check: bool = True,
    ) -> CompiledIdl:
        self._validate_xlen(effective_xlen)
        if behavior != "sw_read()":
            raise IdlInternalError(f"Unsupported CSR behavior signature {behavior!r}")
        record = self.database.csr(name)
        if effective_xlen is not None and not self._globals.csr_hash[name].defined_in_base(
            effective_xlen
        ):
            raise DataError(f"CSR {name} is not defined for RV{effective_xlen}")
        result = self._body(record, (behavior,), effective_xlen, Type(TypeKind.BITS, width=128))
        if type_check:
            result.ast.type_check(result.symtab)
        return result

    def compile_field(
        self,
        csr_name: str,
        field_name: str,
        behavior: str,
        *,
        effective_xlen: int | None = None,
        type_check: bool = True,
    ) -> CompiledIdl:
        self._validate_xlen(effective_xlen)
        csr = self._globals.csr_hash[csr_name]
        field = next((item for item in csr.fields if item.name == field_name), None)
        if field is None:
            raise DataError(f"No CSR field {csr_name}.{field_name}")
        if effective_xlen is not None and (
            not csr.defined_in_base(effective_xlen) or not field.defined_in_base(effective_xlen)
        ):
            raise DataError(
                f"CSR field {csr_name}.{field_name} is not defined for RV{effective_xlen}"
            )
        if behavior == "type()":
            field_type = self._globals.get("CsrFieldType")
            if field_type is None:
                raise IdlInternalError(
                    "Global CsrFieldType is missing; supply genuine architecture IDL sources"
                )
            expected = field_type.ref_type
        elif behavior == "reset_value()":
            effective_xlen = self.architecture.configuration.mxlen
            widths = [field.width(base) for base in (32, 64) if field.defined_in_base(base)]
            expected = Type(TypeKind.BITS, width=max(widths))
        elif behavior == "sw_write(csr_value)":
            expected = Type(TypeKind.BITS, width=128)
        else:
            raise IdlInternalError(f"Unsupported CSR field behavior signature {behavior!r}")
        result = self._body(
            self.database.csr(csr_name),
            ("fields", field_name, behavior),
            effective_xlen,
            expected,
            specialize_mxlen=behavior != "reset_value()",
        )
        if behavior == "sw_write(csr_value)":
            fields = [
                item
                for item in csr.fields
                if effective_xlen is None or item.defined_in_base(effective_xlen)
            ]
            dtype = BitfieldType(
                f"{csr_name}_value",
                csr.length(effective_xlen),
                [item.name for item in fields],
                [item.location(effective_xlen) for item in fields],
            )
            result.symtab.add("csr_value", Var("csr_value", dtype))
        if type_check:
            result.ast.type_check(result.symtab)
        return result

    def type_check(self) -> ArchitectureTypeCheckResult:
        """Check applicable defined bodies and explicitly report missing semantics."""
        checked: list[str] = []
        diagnostics: list[IdlDiagnostic] = []
        unavailable: list[IdlUnavailable] = []

        def visit(context, operation):
            checked.append(context)
            try:
                operation()
            except (
                IdlError,
                DataError,
                ValueError,
                TypeError,
                AttributeError,
                ArithmeticError,
                KeyError,
                NotImplementedError,
            ) as error:
                diagnostics.append(IdlDiagnostic(context, error))

        if self.global_ast is not None:
            for function in self.global_ast.functions:
                visit(
                    f"function {function.name}",
                    lambda name=function.name: self.compile_function(name),
                )
        for instruction in self.database.instructions:
            if self.architecture.object_presence(instruction) is QueryPresence.ABSENT:
                continue
            for xlen in possible_xlens(self.architecture):
                if instruction.data.get("base") not in (None, xlen):
                    continue
                context = f"instruction {instruction.name}/RV{xlen}"
                if "operation()" not in instruction.data:
                    unavailable.append(
                        IdlUnavailable(
                            context,
                            f"{instruction.path}#/operation()",
                            "operation()",
                            "operation() is not defined",
                        )
                    )
                    continue
                visit(
                    context,
                    lambda name=instruction.name, base=xlen: self.compile_instruction(
                        name, effective_xlen=base
                    ),
                )
        for record in self.database.csrs:
            if self.architecture.object_presence(record) is QueryPresence.ABSENT:
                continue
            csr = self._globals.csr_hash[record.name]
            fields = {field.name: field for field in csr.fields}
            reset_checked: set[str] = set()
            for xlen in possible_xlens(self.architecture):
                if not csr.defined_in_base(xlen):
                    continue
                if "sw_read()" in record.data:
                    visit(
                        f"CSR {record.name}.sw_read()/RV{xlen}",
                        lambda name=record.name, base=xlen: self.compile_csr(
                            name, effective_xlen=base
                        ),
                    )
                for field in self.architecture.csr_fields(record):
                    if self.architecture.condition_presence(
                        field.condition
                    ) is QueryPresence.ABSENT or not fields[field.name].defined_in_base(xlen):
                        continue
                    for behavior in ("type()", "reset_value()", "sw_write(csr_value)"):
                        if behavior in field.data:
                            suffix = f"RV{xlen}"
                            if behavior == "reset_value()":
                                if field.name in reset_checked:
                                    continue
                                reset_checked.add(field.name)
                                mxlen = self.architecture.configuration.mxlen
                                suffix = f"RV{mxlen}" if mxlen is not None else "MXLEN"
                            visit(
                                f"CSR {record.name}.{field.name}.{behavior}/{suffix}",
                                lambda name=record.name, fname=field.name, body=behavior, base=xlen: (
                                    self.compile_field(name, fname, body, effective_xlen=base)
                                ),
                            )
        return ArchitectureTypeCheckResult(tuple(checked), tuple(diagnostics), tuple(unavailable))
