# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""``$``-builtin expressions (``$width``, casts, enum/array introspection) and implication."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from ..errors import IdlValueUnknown
from ..symbols import SymbolTable
from ..types import (
    BITS_UNKNOWN_TYPE,
    BOOL_TYPE,
    WIDTH_UNKNOWN,
    EnumerationType,
    Qualifier,
    Type,
    TypeKind,
)
from ._base import Node, _check_kind, _source_and_span, from_h
from ._leaves import EnumRef, UserTypeName


@dataclass(frozen=True, slots=True, kw_only=True)
class WidthReveal(Node):
    """``$width(expr)``; Ruby's ``WidthRevealAst``."""

    kind: ClassVar[str] = "bits_width_cast"

    @property
    def expression(self) -> Node:
        return self.children[0]

    def to_idl(self) -> str:
        return f"$width({self.expression.to_idl()})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"expr": self.expression.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> WidthReveal:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        expr = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(expr,))

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.expression.type_check(symtab, strict=strict)
        e_type = self.expression.type(symtab)
        if e_type.kind != TypeKind.BITS:
            self.type_error(f"{self.expression.text} is not a Bits<N> type")

    def type(self, symtab: SymbolTable) -> Type:
        e_width = self.expression.type(symtab).width
        if e_width == WIDTH_UNKNOWN:
            return BITS_UNKNOWN_TYPE
        return Type(TypeKind.BITS, width=e_width.bit_length())

    def value(self, symtab: SymbolTable) -> Any:
        v = self.expression.type(symtab).width
        if v == WIDTH_UNKNOWN:
            self.value_error("Width is not known")
        return v


@dataclass(frozen=True, slots=True, kw_only=True)
class SignCast(Node):
    """``$signed(expr)``; Ruby's ``SignCastAst``."""

    kind: ClassVar[str] = "sign_cast"

    @property
    def expression(self) -> Node:
        return self.children[0]

    def to_idl(self) -> str:
        return f"$signed({self.expression.to_idl()})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"expr": self.expression.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> SignCast:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        expr = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(expr,))

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.expression.type_check(symtab, strict=strict)
        if self.expression.type(symtab).kind != TypeKind.BITS:
            self.type_error("$signed cast only works on Bits types")

    def type(self, symtab: SymbolTable) -> Type:
        return self.expression.type(symtab).make_signed()

    def value(self, symtab: SymbolTable) -> Any:
        t = self.expression.type(symtab)
        if t.kind != TypeKind.BITS:
            self.internal_error("Expecting a bits type")
        v = self.expression.value(symtab)
        if ((v >> (t.width - 1)) & 1) == 1:
            # twos complement negate the value
            return -(2**t.width - v)
        return v


@dataclass(frozen=True, slots=True, kw_only=True)
class BitsCast(Node):
    """``$bits(expr)``; Ruby's ``BitsCastAst``."""

    kind: ClassVar[str] = "bits_cast"

    @property
    def expression(self) -> Node:
        return self.children[0]

    def to_idl(self) -> str:
        return f"$bits({self.expression.to_idl()})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"expr": self.expression.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> BitsCast:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        expr = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(expr,))

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.expression.type_check(symtab, strict=strict)
        etype = self.expression.type(symtab)
        if etype.kind not in (TypeKind.BITS, TypeKind.ENUM_REF, TypeKind.BITFIELD, TypeKind.CSR):
            self.type_error(f"{etype} Cannot be cast to bits")

    def type(self, symtab: SymbolTable) -> Type:
        etype = self.expression.type(symtab)
        if etype.kind == TypeKind.BITS:
            return etype
        if etype.kind == TypeKind.BITFIELD:
            return Type(TypeKind.BITS, width=etype.width, qualifiers=frozenset({Qualifier.KNOWN}))
        if etype.kind == TypeKind.ENUM_REF:
            assert isinstance(etype, Type)
            return Type(
                TypeKind.BITS, width=etype.enum_class.width, qualifiers=frozenset({Qualifier.KNOWN})
            )
        if etype.kind == TypeKind.CSR:
            self.internal_error("not yet supported: $bits cast of CSR")
        self.type_error("$bits cast is only defined for CSRs and Enum references")

    def value(self, symtab: SymbolTable) -> Any:
        etype = self.expression.type(symtab)
        if etype.kind in (TypeKind.BITS, TypeKind.BITFIELD):
            return self.expression.value(symtab)
        if etype.kind == TypeKind.ENUM_REF:
            if isinstance(self.expression, EnumRef):
                return etype.enum_class.value(self.expression.member_name)
            # this is an expression with an EnumRef type
            return self.expression.value(symtab)
        if etype.kind == TypeKind.CSR:
            self.internal_error("not yet supported: $bits cast of CSR")
        self.type_error(f"TODO: Bits cast for {etype.kind}")


@dataclass(frozen=True, slots=True, kw_only=True)
class ArraySize(Node):
    """``$array_size(array)``; Ruby's ``ArraySizeAst``."""

    kind: ClassVar[str] = "array_size_funcall"

    @property
    def array(self) -> Node:
        return self.children[0]

    def to_idl(self) -> str:
        return f"$array_size({self.array.to_idl()})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"array": self.array.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ArraySize:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        array = from_h(data["array"], sources)
        return cls(source=source, start=start, end=end, children=(array,))

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.array.type_check(symtab, strict=strict)
        array_type = self.array.type(symtab)
        if array_type.kind != TypeKind.ARRAY:
            self.type_error(f"{self.array.text} is not an array")
        if not array_type.is_const:
            self.type_error(f"{self.array.text} must be a constant")

    def type(self, symtab: SymbolTable) -> Type:
        array_type = self.array.type(symtab)
        if array_type.width == WIDTH_UNKNOWN:
            return Type(
                TypeKind.BITS, width=WIDTH_UNKNOWN, qualifiers=(Qualifier.CONST, Qualifier.KNOWN)
            )
        length = array_type.width.bit_length() or 1
        return Type(TypeKind.BITS, width=length, qualifiers=(Qualifier.CONST, Qualifier.KNOWN))

    def value(self, symtab: SymbolTable) -> Any:
        w = self.array.type(symtab).width
        if w == WIDTH_UNKNOWN:
            self.value_error("Width of the array is unknown")
        return w


@dataclass(frozen=True, slots=True, kw_only=True)
class EnumSize(Node):
    """``$enum_size(EnumClass)``; Ruby's ``EnumSizeAst``."""

    kind: ClassVar[str] = "enum_size_funcall"

    @property
    def enum_class_name(self) -> UserTypeName:
        return self.children[0]  # type: ignore[return-value]

    def to_idl(self) -> str:
        return f"$enum_size({self.enum_class_name.to_idl()})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"enum_class_name": self.enum_class_name.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> EnumSize:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        enum_class_name = from_h(data["enum_class_name"], sources)
        return cls(source=source, start=start, end=end, children=(enum_class_name,))

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.enum_class_name.type_check(symtab, strict=strict)

    def type(self, symtab: SymbolTable) -> Type:
        enum_type = self.enum_class_name.type(symtab)
        assert isinstance(enum_type, EnumerationType)
        length = len(enum_type.element_names).bit_length()
        return Type(TypeKind.BITS, width=length, qualifiers=(Qualifier.CONST, Qualifier.KNOWN))

    def value(self, symtab: SymbolTable) -> Any:
        enum_type = self.enum_class_name.type(symtab)
        assert isinstance(enum_type, EnumerationType)
        return len(enum_type.element_names)


@dataclass(frozen=True, slots=True, kw_only=True)
class EnumElementSize(Node):
    """``$enum_element_size(EnumClass)``; Ruby's ``EnumElementSizeAst``."""

    kind: ClassVar[str] = "enum_element_size_funcall"

    @property
    def enum_class_name(self) -> UserTypeName:
        return self.children[0]  # type: ignore[return-value]

    def to_idl(self) -> str:
        return f"$enum_element_size({self.enum_class_name.to_idl()})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"enum_class_name": self.enum_class_name.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> EnumElementSize:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        enum_class_name = from_h(data["enum_class_name"], sources)
        return cls(source=source, start=start, end=end, children=(enum_class_name,))

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.enum_class_name.type_check(symtab, strict=strict)

    def type(self, symtab: SymbolTable) -> Type:
        enum_type = self.enum_class_name.type(symtab)
        return Type(
            TypeKind.BITS, width=enum_type.width, qualifiers=(Qualifier.CONST, Qualifier.KNOWN)
        )

    def value(self, symtab: SymbolTable) -> Any:
        return self.enum_class_name.type(symtab).width


@dataclass(frozen=True, slots=True, kw_only=True)
class EnumArrayCast(Node):
    """``$enum_to_a(EnumClass)``; Ruby's ``EnumArrayCastAst``."""

    kind: ClassVar[str] = "enum_to_array_cast"

    @property
    def enum_class_name(self) -> UserTypeName:
        return self.children[0]  # type: ignore[return-value]

    def to_idl(self) -> str:
        return f"$enum_to_a({self.enum_class_name.to_idl()})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"enum_class_name": self.enum_class_name.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> EnumArrayCast:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        enum_class_name = from_h(data["enum_class_name"], sources)
        return cls(source=source, start=start, end=end, children=(enum_class_name,))

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.enum_class_name.type_check(symtab, strict=strict)

    def type(self, symtab: SymbolTable) -> Type:
        enum_type = self.enum_class_name.type(symtab)
        assert isinstance(enum_type, EnumerationType)
        return Type(
            TypeKind.ARRAY,
            width=len(enum_type.element_values),
            sub_type=Type(
                TypeKind.BITS, width=enum_type.width, qualifiers=(Qualifier.CONST, Qualifier.KNOWN)
            ),
            qualifiers=(Qualifier.CONST,),
        )

    def value(self, symtab: SymbolTable) -> Any:
        enum_type = self.enum_class_name.type(symtab)
        assert isinstance(enum_type, EnumerationType)
        return list(enum_type.element_values)


@dataclass(frozen=True, slots=True, kw_only=True)
class EnumCast(Node):
    """``$enum(EnumClass, expr)``; Ruby's ``EnumCastAst``."""

    kind: ClassVar[str] = "bits_to_enum_cast"

    @property
    def enum_class_name(self) -> UserTypeName:
        return self.children[0]  # type: ignore[return-value]

    @property
    def expression(self) -> Node:
        return self.children[1]

    def to_idl(self) -> str:
        return f"$enum({self.enum_class_name.to_idl()}, {self.expression.to_idl()})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"enum_class_name": self.enum_class_name.to_h(), "expr": self.expression.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> EnumCast:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        enum_class_name = from_h(data["enum_class_name"], sources)
        expr = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(enum_class_name, expr))

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.enum_class_name.type_check(symtab, strict=strict)
        self.expression.type_check(symtab, strict=strict)

        if self.expression.type(symtab).kind != TypeKind.BITS:
            self.type_error("Can only cast from Bits<N> to enum")

        enum_def_type = symtab.get(self.enum_class_name.text)
        if enum_def_type is None:
            self.type_error(f"No enum named {self.enum_class_name.text}")
        assert isinstance(enum_def_type, EnumerationType)

        try:
            expr_value = self.expression.value(symtab)
            if expr_value not in enum_def_type.element_values:
                self.type_error(f"{expr_value} is not a value in enum {self.enum_class_name.text}")
        except IdlValueUnknown:
            pass

    def type(self, symtab: SymbolTable) -> Type:
        enum_def_type = symtab.get(self.enum_class_name.text)
        assert isinstance(enum_def_type, EnumerationType)
        return Type(TypeKind.ENUM_REF, enum_class=enum_def_type)

    def value(self, symtab: SymbolTable) -> Any:
        return self.expression.value(symtab)


@dataclass(frozen=True, slots=True, kw_only=True)
class ArrayIncludes(Node):
    """``$array_includes?(array, expr)``; Ruby's ``ArrayIncludesAst``."""

    kind: ClassVar[str] = "array_includes_funcall"

    @property
    def array(self) -> Node:
        return self.children[0]

    @property
    def expression(self) -> Node:
        return self.children[1]

    def to_idl(self) -> str:
        # Ruby emits ``$array_size`` here (python-migration-bugfixes.md entry 19).
        return f"$array_includes?({self.array.to_idl()}, {self.expression.to_idl()})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"array": self.array.to_h(), "expr": self.expression.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ArrayIncludes:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        array = from_h(data["array"], sources)
        expr = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(array, expr))

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.array.type_check(symtab, strict=strict)
        ary_type = self.array.type(symtab)
        if ary_type.kind != TypeKind.ARRAY:
            self.type_error(
                f"First argument of $array_includes? must be an array. Found {ary_type}"
            )

        self.expression.type_check(symtab, strict=strict)
        value_type = self.expression.type(symtab)
        if not (ary_type.width == 0 or value_type.comparable_to(ary_type.sub_type)):
            self.type_error(
                "Second argument of $array_includes? must be comparable to the array "
                f"element type. Found {ary_type.sub_type} and {value_type}"
            )

    def type(self, symtab: SymbolTable) -> Type:
        return BOOL_TYPE

    def value(self, symtab: SymbolTable) -> Any:
        ary_val = self.array.value(symtab)
        expr_val = self.expression.value(symtab)
        return any(v == expr_val for v in ary_val)


@dataclass(frozen=True, slots=True, kw_only=True)
class ImplicationExpression(Node):
    """``antecedent -> consequent``; Ruby's ``ImplicationExpressionAst``."""

    kind: ClassVar[str] = "implication_expr"

    @property
    def antecedent(self) -> Node:
        return self.children[0]

    @property
    def consequent(self) -> Node:
        return self.children[1]

    def to_idl(self) -> str:
        return f"{self.antecedent.to_idl()} -> {self.consequent.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"antecedent": self.antecedent.to_h(), "consequent": self.consequent.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ImplicationExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        antecedent = from_h(data["antecedent"], sources)
        consequent = from_h(data["consequent"], sources)
        return cls(source=source, start=start, end=end, children=(antecedent, consequent))

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if self.antecedent.type(symtab).kind != TypeKind.BOOLEAN:
            self.antecedent.type_error("Antecedent must a boolean")
        if self.consequent.type(symtab).kind != TypeKind.BOOLEAN:
            self.consequent.type_error("Consequent must a boolean")
