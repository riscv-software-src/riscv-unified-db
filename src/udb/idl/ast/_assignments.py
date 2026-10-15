# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Assignment nodes: PC, variable, array-element/range, field, and multi-variable."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from ..errors import IdlValueUnknown
from ..symbols import SymbolTable, Var
from ..types import BITS1_TYPE, WIDTH_UNKNOWN, Type, TypeKind
from ._base import (
    Node,
    _check_kind,
    _idl_join,
    _source_and_span,
    extract_base_var_name,
    from_h,
    write_back_nested,
)


def invalidate_binding(target: Node, symtab: SymbolTable) -> None:
    """Conservatively invalidate a local aggregate's root without evaluating its index."""
    if target.kind == "csr_write":
        return
    name = extract_base_var_name(target)
    if name is None:
        target.internal_error(f"Cannot determine written binding for {target.kind}")
    variable = symtab.get(name)
    if not isinstance(variable, Var):
        target.internal_error(f"No variable {name}")
    if not variable.type.is_global:
        variable.value = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PcAssignment(Node):
    """``$pc = value``; Ruby's ``PcAssignmentAst``."""

    kind: ClassVar[str] = "pc_assignment"

    @property
    def is_executable(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        return False

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.rhs.type_check(symtab, strict=strict)

    def execute(self, symtab: SymbolTable) -> None:
        self.value_error("$pc is never statically known")

    def nullify_assignments(self, symtab: SymbolTable) -> None:
        # Hardware state has no compile-time binding to invalidate.
        pass

    @property
    def rhs(self) -> Node:
        return self.children[0]

    def to_idl(self) -> str:
        return f"$pc = {self.rhs.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"value": self.rhs.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> PcAssignment:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        rhs = from_h(data["value"], sources)
        return cls(source=source, start=start, end=end, children=(rhs,))


@dataclass(frozen=True, slots=True, kw_only=True)
class VariableAssignment(Node):
    """``var = value``; Ruby's ``VariableAssignmentAst``."""

    kind: ClassVar[str] = "var_assignment"

    @property
    def is_executable(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        if not self.lhs.const_eval(symtab):
            return False
        if self.rhs.const_eval(symtab):
            return True
        variable = symtab.get(self.lhs.name)
        if not isinstance(variable, Var):
            self.type_error(f"variable {self.lhs.name} was not declared")
        variable.const_incompatible()
        return False

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if self.rhs.kind == "post_decrement_expr":
            self.type_error("Post-decrement is not a valid assignment right-hand side")
        self.lhs.type_check(symtab, strict=strict)
        variable = symtab.get(self.lhs.name)
        if variable.type.is_const and not variable.for_loop_iter:
            self.type_error("Cannot assign to a const")
        self.rhs.type_check(symtab, strict=strict)
        if variable.type.is_const and variable.for_loop_iter and not self.rhs.type(symtab).is_const:
            self.type_error("Assignment would make iteration variable non-const")
        if not self.rhs.type(symtab).convertable_to(self.lhs.type(symtab)):
            self.type_error(
                f"Incompatible type in assignment ({self.lhs.type(symtab)}, {self.rhs.type(symtab)})"
            )

    def execute(self, symtab: SymbolTable) -> None:
        if self.lhs.kind == "csr_write":
            self.value_error("CSR writes are never compile-time-known")
        variable = symtab.get(self.lhs.text)
        if variable is None:
            self.internal_error(f"No variable {self.lhs.text}")
        if not variable.type.is_global:
            try:
                variable.value = self.rhs.value(symtab)
            except IdlValueUnknown:
                variable.value = None
                self.value_error("")

    def nullify_assignments(self, symtab: SymbolTable) -> None:
        invalidate_binding(self.lhs, symtab)

    @property
    def lhs(self) -> Node:
        return self.children[0]

    @property
    def rhs(self) -> Node:
        return self.children[1]

    def to_idl(self) -> str:
        return f"{self.lhs.to_idl()} = {self.rhs.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"var": self.lhs.to_h(), "value": self.rhs.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> VariableAssignment:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        lhs = from_h(data["var"], sources)
        rhs = from_h(data["value"], sources)
        return cls(source=source, start=start, end=end, children=(lhs, rhs))


@dataclass(frozen=True, slots=True, kw_only=True)
class AryElementAssignment(Node):
    """``lhs[index] = value``; Ruby's ``AryElementAssignmentAst``."""

    kind: ClassVar[str] = "array_element_assignment"

    @property
    def is_executable(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        if not self.lhs.const_eval(symtab):
            return False
        if self.index.const_eval(symtab) and self.rhs.const_eval(symtab):
            return True
        name = extract_base_var_name(self.lhs)
        if name is None:
            self.type_error(f"Cannot determine base variable for {self.lhs.text}")
        variable = symtab.get(name)
        if variable is None:
            self.type_error(f"array {name} has not been declared")
        variable.const_incompatible()
        return False

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.lhs.type_check(symtab, strict=strict)
        dtype = self.lhs.type(symtab)
        if dtype.kind not in (TypeKind.ARRAY, TypeKind.BITS):
            self.type_error(f"{self.lhs.text} must be an array or an integral type")
        if dtype.is_const:
            self.type_error("Assigning to a constant")
        self.index.type_check(symtab, strict=strict)
        if not self.index.type(symtab).is_integral:
            self.type_error("Index must be integral")
        try:
            index = self.index.value(symtab)
            if dtype.width != WIDTH_UNKNOWN and index >= dtype.width:
                self.type_error(
                    f"Array index ({self.index.text} = {index}) out of range (< {dtype.width})"
                )
        except IdlValueUnknown:
            pass
        self.rhs.type_check(symtab, strict=strict)
        target = dtype.sub_type if dtype.kind == TypeKind.ARRAY else BITS1_TYPE
        if not self.rhs.type(symtab).convertable_to(target):
            message = (
                "array assignment" if dtype.kind == TypeKind.ARRAY else "integer slice assignment"
            )
            self.type_error(f"Incompatible type in {message}")

    def execute(self, symtab: SymbolTable) -> None:
        dtype = self.lhs.type(symtab)
        if dtype.is_global:
            return
        if dtype.kind == TypeKind.ARRAY:
            try:
                index = self.index.value(symtab)
                value = self.lhs.value(symtab)
            except IdlValueUnknown:
                invalidate_binding(self.lhs, symtab)
                raise
            try:
                value[index] = self.rhs.value(symtab)
            except IdlValueUnknown:
                value[index] = None
                self.value_error("right-hand side of array element assignment is unknown")
        elif dtype.kind == TypeKind.BITS:
            try:
                value = self.lhs.value(symtab) | (
                    (self.rhs.value(symtab) & 1) << self.index.value(symtab)
                )
                write_back_nested(self.lhs, value, symtab)
            except IdlValueUnknown:
                name = extract_base_var_name(self.lhs)
                variable = symtab.get(name)
                if variable is None:
                    self.internal_error(f"did not find array base '{name}'")
                variable.value = None
        else:
            self.internal_error("unexpected type for array element assignment")

    def nullify_assignments(self, symtab: SymbolTable) -> None:
        invalidate_binding(self.lhs, symtab)

    @property
    def lhs(self) -> Node:
        return self.children[0]

    @property
    def index(self) -> Node:
        return self.children[1]

    @property
    def rhs(self) -> Node:
        return self.children[2]

    def to_idl(self) -> str:
        return f"{self.lhs.to_idl()}[{self.index.to_idl()}] = {self.rhs.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"array": self.lhs.to_h(), "index": self.index.to_h(), "value": self.rhs.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> AryElementAssignment:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        lhs = from_h(data["array"], sources)
        index = from_h(data["index"], sources)
        rhs = from_h(data["value"], sources)
        return cls(source=source, start=start, end=end, children=(lhs, index, rhs))


@dataclass(frozen=True, slots=True, kw_only=True)
class AryRangeAssignment(Node):
    """``variable[msb:lsb] = write_value``; Ruby's ``AryRangeAssignmentAst``."""

    kind: ClassVar[str] = "array_range_assignment"

    @property
    def is_executable(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        if not self.variable.const_eval(symtab):
            return False
        if all(node.const_eval(symtab) for node in (self.lsb, self.msb, self.write_value)):
            return True
        name = extract_base_var_name(self.variable)
        if name is None:
            self.type_error(f"Cannot determine base variable for {self.variable.text}")
        variable = symtab.get(name)
        if variable is None:
            self.type_error(f"array {name} has not be declared")
        variable.const_incompatible()
        return False

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.variable.type_check(symtab, strict=strict)
        dtype = self.variable.type(symtab)
        if dtype.kind != TypeKind.BITS:
            self.type_error(f"{self.variable.text} must be integral")
        if dtype.is_const:
            self.type_error("Assigning to a constant")
        self.msb.type_check(symtab, strict=strict)
        self.lsb.type_check(symtab, strict=strict)
        if not self.msb.type(symtab).is_integral:
            self.type_error("MSB must be integral")
        if not self.lsb.type(symtab).is_integral:
            self.type_error("LSB must be integral")
        try:
            msb, lsb = self.msb.value(symtab), self.lsb.value(symtab)
            if msb <= lsb:
                self.type_error("MSB must be > LSB")
            width = dtype.max_width if dtype.width == WIDTH_UNKNOWN else dtype.width
            if width is not None and msb >= width:
                self.type_error("MSB is out of range")
        except IdlValueUnknown:
            pass
        self.write_value.type_check(symtab, strict=strict)
        if not self.write_value.type(symtab).is_integral:
            self.type_error("Incompatible type in range assignment")

    def execute(self, symtab: SymbolTable) -> None:
        if self.variable.type(symtab).is_global:
            return
        try:
            msb, lsb = self.msb.value(symtab), self.lsb.value(symtab)
            if msb <= lsb:
                self.type_error(f"MSB ({msb}) is <= LSB ({lsb})")
            rhs = self.write_value.value(symtab)
            mask = ((1 << (msb - lsb + 1)) - 1) << lsb
            value = (self.variable.value(symtab) & ~mask) | ((rhs << lsb) & mask)
            write_back_nested(self.variable, value, symtab)
        except IdlValueUnknown:
            variable = symtab.get(extract_base_var_name(self.variable))
            if variable is None:
                self.internal_error("did not find array base")
            variable.value = None
            self.value_error(
                "Either the range or right-hand side of an array range assignment is unknown"
            )

    def nullify_assignments(self, symtab: SymbolTable) -> None:
        invalidate_binding(self.variable, symtab)

    @property
    def variable(self) -> Node:
        return self.children[0]

    @property
    def msb(self) -> Node:
        return self.children[1]

    @property
    def lsb(self) -> Node:
        return self.children[2]

    @property
    def write_value(self) -> Node:
        return self.children[3]

    def to_idl(self) -> str:
        return f"{self.variable.to_idl()}[{self.msb.to_idl()}:{self.lsb.to_idl()}] = {self.write_value.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "array": self.variable.to_h(),
            "range": {"lsb": self.lsb.to_h(), "msb": self.msb.to_h()},
            "value": self.write_value.to_h(),
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> AryRangeAssignment:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        variable = from_h(data["array"], sources)
        msb = from_h(data["range"]["msb"], sources)
        lsb = from_h(data["range"]["lsb"], sources)
        write_value = from_h(data["value"], sources)
        return cls(source=source, start=start, end=end, children=(variable, msb, lsb, write_value))


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldAssignment(Node):
    """``id.field_name = value``; Ruby's ``FieldAssignmentAst``."""

    kind: ClassVar[str] = "field_assignment"

    field_name: str

    @property
    def is_executable(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        variable = symtab.get(self.id.name)
        if variable is None:
            self.type_error(f"{self.id.name} is not declared!")
        if not variable.const_eval:
            return False
        if self.rhs.const_eval(symtab):
            return True
        variable.const_incompatible()
        return False

    def type(self, symtab: SymbolTable) -> Type:
        variable = symtab.get(self.id.name)
        if variable is None:
            self.type_error(f"{self.id.name} has not been declared")
        if variable.type.kind == TypeKind.BITFIELD:
            return Type(TypeKind.BITS, width=len(variable.type.range(self.field_name)))
        if variable.type.kind == TypeKind.STRUCT:
            return variable.type.member_type(self.field_name)
        self.internal_error(f"huh? {self.id.text} {variable.type.kind}")

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.id.type_check(symtab, strict=strict)
        variable = symtab.get(self.id.name)
        if variable is None:
            self.type_error(f"{self.id.name} has not been declared")
        dtype = variable.type
        if dtype.kind == TypeKind.BITFIELD:
            if self.field_name not in dtype.field_names:
                self.type_error(f"{self.field_name} is not a member of {dtype}")
        elif dtype.kind == TypeKind.STRUCT:
            if self.field_name not in dtype.member_names:
                self.type_error(f"{self.field_name} is not a member of {dtype}")
        else:
            self.type_error(f"{self.id.name} is not a bitfield  or struct (is {dtype})")
        if dtype.is_const:
            self.type_error("Cannot write const variable")
        self.rhs.type_check(symtab, strict=strict)
        if not self.rhs.type(symtab).convertable_to(self.type(symtab)):
            self.type_error(
                f"Incompatible type in assignment ({self.type(symtab)}, {self.rhs.type(symtab)})"
            )

    def execute(self, symtab: SymbolTable) -> None:
        variable = symtab.get(self.id.name)
        if variable is None:
            self.type_error(f"{self.id.name} has not been declared")
        if variable.type.kind == TypeKind.BITFIELD:
            field = variable.type.range(self.field_name)
            mask = (1 << len(field)) - 1
            try:
                variable.value = (self.id.value(symtab) & ~(mask << field.start)) | (
                    (self.rhs.value(symtab) & mask) << field.start
                )
            except IdlValueUnknown:
                invalidate_binding(self.id, symtab)
                raise
        elif variable.type.kind == TypeKind.STRUCT:
            value = self.id.value(symtab)
            try:
                value[self.field_name] = self.rhs.value(symtab)
            except IdlValueUnknown:
                value[self.field_name] = None
                self.value_error("")
        else:
            self.value_error("TODO: Field assignment execution")

    def nullify_assignments(self, symtab: SymbolTable) -> None:
        invalidate_binding(self.id, symtab)

    @property
    def id(self) -> Node:
        return self.children[0]

    @property
    def rhs(self) -> Node:
        return self.children[1]

    def to_idl(self) -> str:
        return f"{self.id.to_idl()}.{self.field_name} = {self.rhs.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"var": self.id.to_h(), "field_name": self.field_name, "value": self.rhs.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> FieldAssignment:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        id_node = from_h(data["var"], sources)
        rhs = from_h(data["value"], sources)
        return cls(
            source=source,
            start=start,
            end=end,
            children=(id_node, rhs),
            field_name=data["field_name"],
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class CsrFieldAssignment(Node):
    """``CSR[name].field = write_value``; Ruby's ``CsrFieldAssignmentAst``."""

    kind: ClassVar[str] = "csr_field_assignment"

    @property
    def is_executable(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        return False

    def type(self, symtab: SymbolTable) -> Type:
        return self.csr_field.type(symtab)

    def field(self, symtab: SymbolTable) -> Any:
        return self.csr_field.field_def(symtab)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.csr_field.type_check(symtab, strict=strict)
        self.write_value.type_check(symtab, strict=strict)
        if not self.write_value.type(symtab).convertable_to(self.type(symtab)):
            self.type_error("Incompatible type in assignment")

    def execute(self, symtab: SymbolTable) -> None:
        self.value_error("CSR field writes are never compile-time-executable")

    def nullify_assignments(self, symtab: SymbolTable) -> None:
        # CSR contents are runtime state, never values stored in the symbol table.
        pass

    @property
    def csr_field(self) -> Node:
        return self.children[0]

    @property
    def write_value(self) -> Node:
        return self.children[1]

    def to_idl(self) -> str:
        return f"{self.csr_field.to_idl()} = {self.write_value.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"csr_field": self.csr_field.to_h(), "value": self.write_value.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> CsrFieldAssignment:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        csr_field = from_h(data["csr_field"], sources)
        write_value = from_h(data["value"], sources)
        return cls(source=source, start=start, end=end, children=(csr_field, write_value))


@dataclass(frozen=True, slots=True, kw_only=True)
class MultiVariableAssignment(Node):
    """``(v1, v2, ...) = function_call()``; Ruby's ``MultiVariableAssignmentAst``."""

    kind: ClassVar[str] = "multi_var_assignment"

    @property
    def is_executable(self) -> bool:
        return True

    def const_eval(self, symtab: SymbolTable) -> bool:
        constant = self.function_call.const_eval(symtab)
        for node in self.variables:
            if node.kind == "dont_care_lval":
                continue
            variable = symtab.get(node.name)
            if variable is None:
                self.type_error(" was not declared")
            if not constant:
                variable.const_incompatible()
        return constant

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.function_call.type_check(symtab, strict=strict)
        for variable in self.variables:
            variable.type_check(symtab, strict=strict)
        if any(variable.type(symtab).is_const for variable in self.variables):
            self.type_error("Assigning value to a constant")
        dtype = self.function_call.type(symtab)
        name = self.function_call.name
        if dtype.kind != TypeKind.TUPLE:
            self.type_error(f"Function '{name}' only returns 1 variable")
        if len(dtype.tuple_types) != len(self.variables):
            self.type_error(
                f"function '{name}' returns {len(dtype.tuple_types)} arguments, but  "
                f"{len(self.variables)} were specified"
            )
        for i, node in enumerate(self.variables):
            if node.kind == "dont_care_lval":
                continue
            variable = symtab.get(node.text)
            if variable is None:
                self.type_error(f"No symbol named '{node.text}'")
            if not variable.type.convertable_to(dtype.tuple_types[i]):
                self.type_error(
                    f"'{name}' expecting a {dtype.tuple_types[i]} in argument {i}, "
                    f"but was given {variable.type}"
                )

    def execute(self, symtab: SymbolTable) -> None:
        try:
            values = self.function_call.execute(symtab)
            i = 0
            for node in self.variables:
                if node.kind == "dont_care_lval":
                    i += 1
                    continue
                if node.type(symtab).is_global:
                    continue
                variable = symtab.get(node.text)
                if variable is None:
                    self.internal_error("call type check")
                variable.value = values[i]
                i += 1
        except IdlValueUnknown:
            for node in self.variables:
                if node.kind == "dont_care_lval":
                    continue
                symtab.get(node.text).value = None
            self.value_error("value of right-hand side of multi-variable assignment is unknown")

    def nullify_assignments(self, symtab: SymbolTable) -> None:
        for node in self.variables:
            if node.kind != "dont_care_lval":
                invalidate_binding(node, symtab)

    @property
    def variables(self) -> tuple[Node, ...]:
        return self.children[:-1]

    @property
    def function_call(self) -> Node:
        return self.children[-1]

    def to_idl(self) -> str:
        return f"({_idl_join(self.variables)}) = {self.function_call.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "assignments": [v.to_h() for v in self.variables],
            "value": self.function_call.to_h(),
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> MultiVariableAssignment:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        variables = tuple(from_h(v, sources) for v in data["assignments"])
        function_call = from_h(data["value"], sources)
        return cls(source=source, start=start, end=end, children=(*variables, function_call))
