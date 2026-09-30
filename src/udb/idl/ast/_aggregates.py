# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Array/concatenation/replication literals, element/field access, and function calls."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from ..errors import IdlInternalError, IdlTypeError, IdlValueUnknown
from ..symbols import SymbolTable
from ..types import (
    POSSIBLY_UNKNOWN_BITS1_TYPE,
    WIDTH_UNKNOWN,
    BitfieldType,
    Qualifier,
    RegFileElementType,
    StructType,
    Type,
    TypeKind,
)
from ._base import Node, _check_kind, _idl_join, _source_and_span, from_h
from ._leaves import UnknownLiteral


@dataclass(frozen=True, slots=True, kw_only=True)
class ArrayLiteral(Node):
    """An array literal (``[a, b, c]``); Ruby's ``ArrayLiteralAst``."""

    kind: ClassVar[str] = "array_literal"

    def to_idl(self) -> str:
        return f"[{_idl_join(self.children, sep=',')}]"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"values": [c.to_h() for c in self.children]}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ArrayLiteral:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        values = tuple(from_h(v, sources) for v in data["values"])
        return cls(source=source, start=start, end=end, children=values)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        for node in self.children:
            node.type_check(symtab, strict=strict)
        first_type = self.children[0].type(symtab)
        if not all(e.type(symtab).equal_to(first_type) for e in self.children):
            self.type_error("Array elements must be identical")

    def type(self, symtab: SymbolTable) -> Type:
        if len(self.children) > 0:
            return Type(
                TypeKind.ARRAY, width=len(self.children), sub_type=self.children[0].type(symtab)
            )
        return Type(TypeKind.ARRAY, width=0, sub_type=None)

    def value(self, symtab: SymbolTable) -> Any:
        return [e.value(symtab) for e in self.children]


@dataclass(frozen=True, slots=True, kw_only=True)
class ConcatenationExpression(Node):
    """A bit concatenation expression (``{a, b, c}``); Ruby's ``ConcatenationExpressionAst``."""

    kind: ClassVar[str] = "concat_expr"

    def to_idl(self) -> str:
        return f"{{{_idl_join(self.children, sep=',')}}}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"exprs": [c.to_h() for c in self.children]}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ConcatenationExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        exprs = tuple(from_h(v, sources) for v in data["exprs"])
        return cls(source=source, start=start, end=end, children=exprs)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if len(self.children) < 2:
            self.type_error("Must concatenate at least two objects")
        for exp in self.children:
            exp.type_check(symtab, strict=strict)
            e_type = exp.type(symtab)
            if e_type.kind != TypeKind.BITS:
                self.type_error("Concatenation only supports Bits<> types")
            if e_type.width != WIDTH_UNKNOWN and e_type.width <= 0:
                self.internal_error(f"Negative width for element {exp.text}")

    def type(self, symtab: SymbolTable) -> Type:
        all_known_values = True
        width_known = True
        total_width = 0
        for exp in self.children:
            e_type = exp.type(symtab)
            if e_type.width == WIDTH_UNKNOWN:
                width_known = False
            elif width_known:
                total_width += e_type.width
            all_known_values = all_known_values and e_type.is_known

        # NOTE: Ruby's equivalent `is_const` local is a confirmed-bug dead
        # variable (always `true`, never updated from each `e_type.const?`
        # -- see doc/python-migration-bugfixes.md), so the Ruby oracle always
        # reports concatenation as `const` even when a constituent is not.
        # Python computes it correctly here.
        is_const = all(exp.type(symtab).is_const for exp in self.children)
        qualifiers: list[Qualifier] = [Qualifier.CONST] if is_const else []

        if all_known_values:
            qualifiers.append(Qualifier.KNOWN)
        return Type(
            TypeKind.BITS,
            width=total_width if width_known else WIDTH_UNKNOWN,
            qualifiers=tuple(qualifiers),
        )

    def value(self, symtab: SymbolTable) -> Any:
        result: int | UnknownLiteral = UnknownLiteral(known_value=0, unknown_mask=0)
        total_width = 0
        for exp in reversed(self.children):
            result = result | (exp.value(symtab) << total_width)
            total_width += exp.type(symtab).width
        if isinstance(result, UnknownLiteral):
            return result.known_value if result.unknown_mask == 0 else result
        return result


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplicationExpression(Node):
    """A bit replication expression (``{n{v}}``); Ruby's ``ReplicationExpressionAst``."""

    kind: ClassVar[str] = "repl_expr"

    @property
    def n(self) -> Node:
        return self.children[0]

    @property
    def v(self) -> Node:
        return self.children[1]

    def to_idl(self) -> str:
        return f"{{{self.n.to_idl()}{{{self.v.to_idl()}}}}}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"count": self.n.to_h(), "expr": self.v.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ReplicationExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        n = from_h(data["count"], sources)
        v = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(n, v))

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.n.type_check(symtab, strict=strict)
        self.v.type_check(symtab, strict=strict)
        if self.v.type(symtab).kind != TypeKind.BITS:
            self.type_error("value of replication must be a Bits type")
        try:
            n_value = self.n.value(symtab)
            if n_value <= 0:
                self.type_error(f"replication amount must be positive ({n_value})")
        except IdlValueUnknown:
            pass

    def type(self, symtab: SymbolTable) -> Type:
        try:
            width = self.n.value(symtab) * self.v.type(symtab).width
            return Type(TypeKind.BITS, width=width, qualifiers=(Qualifier.KNOWN,))
        except IdlValueUnknown:
            return Type(TypeKind.BITS, width=WIDTH_UNKNOWN)

    def value(self, symtab: SymbolTable) -> Any:
        result: int | UnknownLiteral = UnknownLiteral(known_value=0, unknown_mask=0)
        v_width = self.v.type(symtab).width
        for i in range(self.n.value(symtab)):
            result = result | (self.v.value(symtab) << (i * v_width))
        if isinstance(result, UnknownLiteral):
            return result.known_value if result.unknown_mask == 0 else result
        return result


@dataclass(frozen=True, slots=True, kw_only=True)
class PostIncrementExpression(Node):
    """A post-increment expression (``x++``); Ruby's ``PostIncrementExpressionAst``."""

    kind: ClassVar[str] = "post_increment_expr"

    @property
    def rval(self) -> Node:
        return self.children[0]

    def to_idl(self) -> str:
        return f"{self.rval.to_idl()}++"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"expr": self.rval.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> PostIncrementExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        rval = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(rval,))


@dataclass(frozen=True, slots=True, kw_only=True)
class PostDecrementExpression(Node):
    """A post-decrement expression (``x--``); Ruby's ``PostDecrementExpressionAst``."""

    kind: ClassVar[str] = "post_decrement_expr"

    @property
    def rval(self) -> Node:
        return self.children[0]

    def to_idl(self) -> str:
        return f"{self.rval.to_idl()}--"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"expr": self.rval.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> PostDecrementExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        rval = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(rval,))


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldAccessExpression(Node):
    """A struct/bitfield field access (``obj.field``); Ruby's ``FieldAccessExpressionAst``."""

    kind: ClassVar[str] = "field_access_expr"

    field_name: str

    @property
    def obj(self) -> Node:
        return self.children[0]

    def to_idl(self) -> str:
        return f"{self.obj.to_idl()}.{self.field_name}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"expr": self.obj.to_h(), "field_name": self.field_name}

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.obj.type_check(symtab, strict=strict)
        obj_type = self.obj.type(symtab)

        if obj_type.kind == TypeKind.BITFIELD:
            if not isinstance(obj_type, BitfieldType):
                self.internal_error(
                    f"{self.obj.text} Not a BitfieldType (is a {type(obj_type).__name__})"
                )
            if self.field_name not in obj_type.field_names:
                self.type_error(f"{self.field_name} is not a member of {obj_type}")
        elif obj_type.kind == TypeKind.STRUCT:
            assert isinstance(obj_type, StructType)
            if not obj_type.has_member(self.field_name):
                self.type_error(f"{self.field_name} is not a member of {obj_type}")
        else:
            self.type_error(f"{self.obj.text} is not a bitfield (is {obj_type})")

    def type(self, symtab: SymbolTable) -> Type:
        obj_type = self.obj.type(symtab)
        if obj_type.kind == TypeKind.BITFIELD:
            assert isinstance(obj_type, BitfieldType)
            return Type(TypeKind.BITS, width=len(obj_type.range(self.field_name)))
        if obj_type.kind == TypeKind.STRUCT:
            assert isinstance(obj_type, StructType)
            return obj_type.member_type(self.field_name)
        self.internal_error(f"huh? {self.obj.text} {obj_type.kind}")

    def value(self, symtab: SymbolTable) -> Any:
        obj_type = self.obj.type(symtab)
        if obj_type.kind == TypeKind.BITFIELD:
            assert isinstance(obj_type, BitfieldType)
            field_range = obj_type.range(self.field_name)
            return (self.obj.value(symtab) >> field_range.start) & ((1 << len(field_range)) - 1)
        if obj_type.kind == TypeKind.STRUCT:
            struct_val = self.obj.value(symtab)
            field_val = struct_val.get(self.field_name)
            if field_val is None:
                self.value_error(f"{self.field_name} is not known at compile-time")
            return field_val
        self.type_error(f"{self.obj.text} is Not a bitfield.")

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> FieldAccessExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        obj = from_h(data["expr"], sources)
        return cls(
            source=source, start=start, end=end, children=(obj,), field_name=data["field_name"]
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class AryElementAccess(Node):
    """An array/register-file element access (``var[index]``); Ruby's ``AryElementAccessAst``."""

    kind: ClassVar[str] = "array_access"

    @property
    def var(self) -> Node:
        return self.children[0]

    @property
    def index(self) -> Node:
        return self.children[1]

    def to_idl(self) -> str:
        return f"{self.var.to_idl()}[{self.index.to_idl()}]"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"array": self.var.to_h(), "index": self.index.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> AryElementAccess:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        var = from_h(data["array"], sources)
        index = from_h(data["index"], sources)
        return cls(source=source, start=start, end=end, children=(var, index))

    @staticmethod
    def _is_register_file_array(var_type: Type) -> bool:
        return (
            var_type.kind == TypeKind.ARRAY
            and isinstance(var_type.sub_type, RegFileElementType)
            and var_type.is_global
        )

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.var.type_check(symtab, strict=strict)
        self.index.type_check(symtab, strict=strict)

        if not self.index.type(symtab).is_integral:
            self.type_error("Array index must be integral")

        var_type = self.var.type(symtab)
        if var_type.kind == TypeKind.ARRAY:
            try:
                index_value = self.index.value(symtab)
                if var_type.width != WIDTH_UNKNOWN and index_value >= var_type.width:
                    self.type_error("Array index out of range")
            except IdlValueUnknown:
                pass  # OK, doesn't need to be known
        elif var_type.is_integral:
            if var_type.kind == TypeKind.BITS:
                try:
                    index_value = self.index.value(symtab)
                    if var_type.width != WIDTH_UNKNOWN and index_value >= var_type.width:
                        self.type_error(
                            f"Bits element index ({index_value}) out of range "
                            f"(max {var_type.width - 1}) in access '{self.text}'"
                        )
                except IdlValueUnknown:
                    pass  # OK, doesn't need to be known
        else:
            self.type_error("Array element access can only be used with integral types and arrays")

    def type(self, symtab: SymbolTable) -> Type:
        var_type = self.var.type(symtab)
        if var_type.kind == TypeKind.ARRAY:
            return var_type.sub_type
        if var_type.is_integral:
            # Ruby's ``AryElementAccessAst#type`` branches on ``var_type.known?`` between its
            # own ``Bits1Type`` (qualifiers ``[:known]``, defined inside ``class AstNode``) and
            # ``PossiblyUnknownBits1Type`` (no qualifiers). But a bare constant reference from
            # a *sibling* AstNode subclass resolves lexically to the top-level ``Idl`` module's
            # own (unqualified, no-``:known``) ``Bits1Type`` from type.rb, which shadows
            # ``AstNode::Bits1Type`` for every subclass -- confirmed empirically via the oracle
            # ((8'hff)[0]).type is "Bits<1>", never "known Bits<1>". Both of Ruby's branches
            # are therefore structurally identical in practice; mirror that by always returning
            # the unqualified type.
            return POSSIBLY_UNKNOWN_BITS1_TYPE
        self.internal_error("Bad ary element access")

    def value(self, symtab: SymbolTable) -> Any:
        var_val = self.var.value(symtab)
        if self.var.type(symtab).is_integral:
            index = self.index.value(symtab)
            # Ruby's Integer#[] reads a negative bit index as 0.
            return 0 if index < 0 else (var_val >> index) & 1

        try:
            var_type = self.var.type(symtab)
        except (IdlTypeError, IdlInternalError):
            var_type = None
        if isinstance(var_type, Type) and self._is_register_file_array(var_type):
            self.value_error("Register file registers are not compile-time-known")

        if not isinstance(var_val, list):
            self.internal_error(f"Not an array (is a {type(var_val).__name__})")

        idx = self.index.value(symtab)
        if idx >= len(var_val):
            self.internal_error("Index out of range; make sure type_check is called")
        return var_val[idx]


@dataclass(frozen=True, slots=True, kw_only=True)
class AryRangeAccess(Node):
    """An array bit-range access (``var[msb:lsb]``); Ruby's ``AryRangeAccessAst``."""

    kind: ClassVar[str] = "array_range_access"

    @property
    def var(self) -> Node:
        return self.children[0]

    @property
    def msb(self) -> Node:
        return self.children[1]

    @property
    def lsb(self) -> Node:
        return self.children[2]

    def to_idl(self) -> str:
        return f"{self.var.to_idl()}[{self.msb.to_idl()}:{self.lsb.to_idl()}]"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"array": self.var.to_h(), "range": {"lsb": self.lsb.to_h(), "msb": self.msb.to_h()}}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> AryRangeAccess:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        var = from_h(data["array"], sources)
        msb = from_h(data["range"]["msb"], sources)
        lsb = from_h(data["range"]["lsb"], sources)
        return cls(source=source, start=start, end=end, children=(var, msb, lsb))

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.var.type_check(symtab, strict=strict)
        self.msb.type_check(symtab, strict=strict)
        self.lsb.type_check(symtab, strict=strict)

        var_type = self.var.type(symtab)
        if not var_type.is_integral:
            self.type_error(f"Range operator only defined for integral types (found {var_type})")
        if not self.msb.type(symtab).is_integral:
            self.type_error("Range MSB must be an integral type")
        if not self.lsb.type(symtab).is_integral:
            self.type_error("Range LSB must be an integral type")

        try:
            msb_value = self.msb.value(symtab)
            lsb_value = self.lsb.value(symtab)
            if (
                strict
                and var_type.kind == TypeKind.BITS
                and var_type.width != WIDTH_UNKNOWN
                and msb_value >= var_type.width
            ):
                self.type_error(
                    f"Range too large for bits (msb = {msb_value}, range size = {var_type.width})"
                )
            range_size = msb_value - lsb_value + 1
            if range_size <= 0:
                self.type_error(f"zero/negative range ({msb_value}:{lsb_value})")
        except IdlValueUnknown:
            pass  # OK, don't have to know

    def type(self, symtab: SymbolTable) -> Type:
        try:
            msb_value = self.msb.value(symtab)
            lsb_value = self.lsb.value(symtab)
            range_size = msb_value - lsb_value + 1
            if self.var.type(symtab).is_known:
                return Type(TypeKind.BITS, width=range_size, qualifiers=(Qualifier.KNOWN,))
            return Type(TypeKind.BITS, width=range_size)
        except IdlValueUnknown:
            # Don't know the width at compile time... assume the worst.
            return self.var.type(symtab)

    def value(self, symtab: SymbolTable) -> Any:
        msb_val = self.msb.value(symtab)
        lsb_val = self.lsb.value(symtab)
        var_val = self.var.value(symtab)
        mask = (1 << (msb_val - lsb_val + 1)) - 1
        return (var_val >> lsb_val) & mask


@dataclass(frozen=True, slots=True, kw_only=True)
class FunctionCallExpression(Node):
    """A function call expression; Ruby's ``FunctionCallExpressionAst``."""

    kind: ClassVar[str] = "funcall_expr"

    name: str

    @property
    def args(self) -> tuple[Node, ...]:
        return self.children

    def to_idl(self) -> str:
        return f"{self.name}({_idl_join(self.args, sep=',')})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"func": self.name, "args": [a.to_h() for a in self.args]}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> FunctionCallExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        args = tuple(from_h(a, sources) for a in data["args"])
        return cls(source=source, start=start, end=end, children=args, name=data["func"])
