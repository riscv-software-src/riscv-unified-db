# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Binary, unary, and ternary operator expressions, and parenthesized expressions."""

from __future__ import annotations

import operator
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from ..errors import IdlValueUnknown
from ..symbols import SymbolTable
from ..types import (
    BOOL_TYPE,
    CONST_BOOL_TYPE,
    WIDTH_UNKNOWN,
    Qualifier,
    Type,
    TypeKind,
)
from ._base import (
    Node,
    _check_kind,
    _ruby_shl,
    _ruby_shr,
    _source_and_span,
    _try_value,
    _values_disjoint,
    from_h,
)
from ._leaves import UnknownLiteral


@dataclass(frozen=True, slots=True, kw_only=True)
class BinaryExpression(Node):
    """A binary operator expression; Ruby's ``BinaryExpressionAst``.

    ``children = (lhs, rhs)``. Left-associative chains of the same precedence
    level are folded left-to-right by the parser (mirroring
    ``BinaryExpressionRightSyntaxNode#to_ast``), so this node is never
    n-ary -- only ever exactly two operands.
    """

    kind: ClassVar[str] = "binary_operator_expr"

    op: str

    OPS: ClassVar[tuple[str, ...]] = (
        "==",
        "!=",
        ">",
        "<",
        ">=",
        "<=",
        "&&",
        "||",
        "+",
        "-",
        "/",
        "*",
        "%",
        "<<",
        ">>",
        ">>>",
        "`+",
        "`-",
        "`*",
        "`<<",
        "&",
        "|",
        "^",
    )

    def __post_init__(self) -> None:
        # NOTE: call the parent implementation explicitly rather than via a
        # zero-arg ``super()``: CPython < 3.13 has a bug where
        # ``@dataclass(slots=True)`` recreates the class object, which can
        # leave the implicit ``__class__`` closure cell used by a zero-arg
        # ``super()`` pointing at a stale class and raise
        # ``TypeError: super(type, obj): obj must be an instance or
        # subtype of type`` (fixed upstream in Python 3.13).
        Node.__post_init__(self)
        if self.op not in self.OPS:
            raise ValueError(f"Bad binary operator: {self.op!r}")

    @property
    def lhs(self) -> Node:
        return self.children[0]

    @property
    def rhs(self) -> Node:
        return self.children[1]

    def to_idl(self) -> str:
        return f"({self.lhs.to_idl()} {self.op} {self.rhs.to_idl()})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"op": self.op, "lhs": self.lhs.to_h(), "rhs": self.rhs.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> BinaryExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        lhs = from_h(data["lhs"], sources)
        rhs = from_h(data["rhs"], sources)
        return cls(source=source, start=start, end=end, children=(lhs, rhs), op=data["op"])

    LOGICAL_OPS: ClassVar[tuple[str, ...]] = ("==", "!=", ">", "<", ">=", "<=", "&&", "||")

    def type(self, symtab: SymbolTable) -> Type:
        op = self.op
        if op in ("||", "&&"):
            # See if we can short circuit.
            lhs_value = _try_value(self.lhs, symtab)
            rhs_value = _try_value(self.rhs, symtab)
            if isinstance(lhs_value, bool) and isinstance(rhs_value, bool):
                return CONST_BOOL_TYPE
            if lhs_value is False and op == "||":
                return CONST_BOOL_TYPE if self.rhs.type(symtab).is_const else BOOL_TYPE
            if lhs_value is True and op == "||":
                return CONST_BOOL_TYPE
            if lhs_value is True and op == "&&":
                return CONST_BOOL_TYPE if self.rhs.type(symtab).is_const else BOOL_TYPE
            if lhs_value is False and op == "&&":
                return CONST_BOOL_TYPE
            if rhs_value is False and op == "||":
                return CONST_BOOL_TYPE if self.lhs.type(symtab).is_const else BOOL_TYPE
            if rhs_value is True and op == "||":
                return CONST_BOOL_TYPE
            if rhs_value is True and op == "&&":
                return CONST_BOOL_TYPE if self.lhs.type(symtab).is_const else BOOL_TYPE
            if rhs_value is False and op == "&&":
                return CONST_BOOL_TYPE

        lhs_type = self.lhs.type(symtab)
        rhs_type = self.rhs.type(symtab)

        qualifiers: list[Qualifier] = []
        if lhs_type.is_const and rhs_type.is_const:
            qualifiers.append(Qualifier.CONST)

        if op in self.LOGICAL_OPS:
            return CONST_BOOL_TYPE if Qualifier.CONST in qualifiers else BOOL_TYPE
        if op in ("<<", ">>", ">>>"):
            # Type of a non-widening shift is the type of the left-hand side.
            return lhs_type
        if op == "`<<":
            if lhs_type.is_known and rhs_type.is_known:
                qualifiers.append(Qualifier.KNOWN)
            try:
                if lhs_type.width == WIDTH_UNKNOWN:
                    self.value_error("lhs width unknown")
                # If the shift amount is known, the result width is increased
                # by the shift; otherwise it is the width of the lhs.
                return Type(
                    TypeKind.BITS,
                    width=lhs_type.width + self.rhs.value(symtab),
                    qualifiers=tuple(qualifiers),
                )
            except IdlValueUnknown:
                return Type(TypeKind.BITS, width=lhs_type.width, qualifiers=tuple(qualifiers))
        if op in ("`+", "`-"):
            # +/- raises an exception if either lhs or rhs has undefined state.
            qualifiers.append(Qualifier.KNOWN)
            # Widening addition/subtraction: result is 1 more bit than the
            # largest operand, to capture the carry.
            try:
                if lhs_type.width == WIDTH_UNKNOWN:
                    self.value_error("lhs width is unknown")
                if rhs_type.width == WIDTH_UNKNOWN:
                    self.value_error("rhs width is unknown")
                return Type(
                    TypeKind.BITS,
                    width=max(lhs_type.width, rhs_type.width) + 1,
                    qualifiers=tuple(qualifiers),
                )
            except IdlValueUnknown:
                return Type(TypeKind.BITS, width=WIDTH_UNKNOWN, qualifiers=tuple(qualifiers))
        if op == "`*":
            if lhs_type.is_known and rhs_type.is_known:
                qualifiers.append(Qualifier.KNOWN)
            # Widening multiply: result width is the sum of the operand widths.
            try:
                if lhs_type.width == WIDTH_UNKNOWN:
                    self.value_error("lhs width is unknown")
                if rhs_type.width == WIDTH_UNKNOWN:
                    self.value_error("rhs width is unknown")
                return Type(
                    TypeKind.BITS,
                    width=lhs_type.width + rhs_type.width,
                    qualifiers=tuple(qualifiers),
                )
            except IdlValueUnknown:
                return Type(TypeKind.BITS, width=WIDTH_UNKNOWN, qualifiers=tuple(qualifiers))

        if lhs_type.is_signed and rhs_type.is_signed:
            qualifiers.append(Qualifier.SIGNED)
        if lhs_type.is_known and rhs_type.is_known:
            qualifiers.append(Qualifier.KNOWN)
        if lhs_type.width == WIDTH_UNKNOWN or rhs_type.width == WIDTH_UNKNOWN:
            return Type(TypeKind.BITS, width=WIDTH_UNKNOWN, qualifiers=tuple(qualifiers))
        return Type(
            TypeKind.BITS, width=max(lhs_type.width, rhs_type.width), qualifiers=tuple(qualifiers)
        )

    def const_eval(self, symtab: SymbolTable) -> bool:
        # Ruby's comment: can't check for short-circuit here unless we also
        # evaluate values during the const_eval pass; conservatively assume
        # no short-circuiting.
        return self.lhs.const_eval(symtab) and self.rhs.const_eval(symtab)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        op = self.op
        lhs_short_circuit = False
        rhs_short_circuit = False
        if op in ("||", "&&"):
            lhs_value = _try_value(self.lhs, symtab)
            rhs_value = _try_value(self.rhs, symtab)
            if isinstance(lhs_value, bool) and isinstance(rhs_value, bool):
                return
            if lhs_value is False and op == "||":
                self.rhs.type_check(symtab, strict=strict)
            elif lhs_value is True and op == "||":
                rhs_short_circuit = True
            elif lhs_value is True and op == "&&":
                self.rhs.type_check(symtab, strict=strict)
            elif lhs_value is False and op == "&&":
                rhs_short_circuit = True
            elif rhs_value is False and op == "||":
                self.lhs.type_check(symtab, strict=strict)
            elif rhs_value is True and op == "||":
                lhs_short_circuit = True
            elif rhs_value is True and op == "&&":
                self.lhs.type_check(symtab, strict=strict)
            elif rhs_value is False and op == "&&":
                lhs_short_circuit = True

        if op in ("<=", ">=", "<", ">", "!=", "=="):
            rhs_type = self.rhs.type(symtab)
            lhs_type = self.lhs.type(symtab)
            if not rhs_type.comparable_to(lhs_type):
                self.type_error(
                    f"{self.lhs.text} (type = {lhs_type}) and {self.rhs.text} "
                    f"(type = {rhs_type}) are not comparable"
                )
        elif op in ("&&", "||"):
            if not lhs_short_circuit:
                lhs_type = self.lhs.type(symtab)
                if not lhs_type.convertable_to(TypeKind.BOOLEAN):
                    self.type_error(
                        f"left-hand side of {op} needs to be boolean (is {lhs_type}) ({self.text})"
                    )
            if not rhs_short_circuit:
                rhs_type = self.rhs.type(symtab)
                if not rhs_type.convertable_to(TypeKind.BOOLEAN):
                    self.type_error(
                        f"right-hand side of {op} needs to be boolean (is {rhs_type}) ({self.text})"
                    )
        elif op == "<<":
            rhs_type = self.rhs.type(symtab)
            lhs_type = self.lhs.type(symtab)
            if lhs_type.kind != TypeKind.BITS:
                self.type_error(f"Unsupported type for left shift: {lhs_type}")
            if rhs_type.kind != TypeKind.BITS:
                self.type_error(f"Unsupported shift for left shift: {rhs_type}")
        elif op == "`<<":
            rhs_type = self.rhs.type(symtab)
            lhs_type = self.lhs.type(symtab)
            if lhs_type.kind != TypeKind.BITS:
                self.type_error(f"Unsupported type for left shift: {lhs_type}")
            if rhs_type.kind != TypeKind.BITS:
                self.type_error(f"Unsupported shift for left shift: {rhs_type}")
            if not rhs_type.is_const:
                self.type_error(
                    "Widening shift amount must be constant (if it's not, the width of "
                    "the result is unknowable)."
                )
        elif op in (">>", ">>>"):
            rhs_type = self.rhs.type(symtab)
            lhs_type = self.lhs.type(symtab)
            if lhs_type.kind != TypeKind.BITS:
                self.type_error(f"Unsupported type for right shift: {lhs_type}")
            if rhs_type.kind != TypeKind.BITS:
                self.type_error(f"Unsupported shift for right shift: {rhs_type}")
        elif op in ("*", "`*", "/", "%"):
            rhs_type = self.rhs.type(symtab)
            lhs_type = self.lhs.type(symtab)
            if not (lhs_type.is_integral and rhs_type.is_integral):
                self.type_error(
                    "Multiplication/division is only defined for integral types. "
                    "Maybe you forgot a $bits cast?"
                )
        elif op in ("+", "-", "`+", "`-"):
            rhs_type = self.rhs.type(symtab)
            lhs_type = self.lhs.type(symtab)
            if not (lhs_type.is_integral and rhs_type.is_integral):
                self.type_error(
                    "Addition/subtraction is only defined for integral types. "
                    "Maybe you forgot a $bits cast?"
                )
        elif op in ("&", "|", "^"):
            rhs_type = self.rhs.type(symtab)
            lhs_type = self.lhs.type(symtab)
            if not (lhs_type.is_integral and rhs_type.is_integral):
                self.type_error(
                    "Bitwise operation is only defined for integral types. "
                    "Maybe you forgot a $bits cast?"
                )
        else:
            self.internal_error(f"Unhandled op '{op}'")

    def value(self, symtab: SymbolTable) -> Any:
        try:
            return self._value(symtab)
        except TypeError:
            # Ruby crashes on most operators with a partially-unknown (``x``-bit)
            # operand (a confirmed Ruby bug; see doc/python-migration-bugfixes.md).
            # The result is not knowable at compile time.
            if any(
                isinstance(_try_value(side, symtab), UnknownLiteral)
                for side in (self.lhs, self.rhs)
            ):
                self.value_error(f"Cannot evaluate '{self.op}' on a value with unknown bits")
            raise

    def _value(self, symtab: SymbolTable) -> Any:
        op = self.op
        if op == ">>>":
            lhs_value = self.lhs.value(symtab)
            lhs_width = self.lhs.type(symtab).width
            if (lhs_value & (1 << (lhs_width - 1))) == 0:
                shamt = self.rhs.value(symtab)
                return lhs_value if shamt == 0 else _ruby_shr(lhs_value, shamt)
            shift_amount = self.rhs.value(symtab)
            if shift_amount == 0:
                return lhs_value
            shifted_value = _ruby_shr(lhs_value, shift_amount)
            mask_len = min(lhs_width, shift_amount)
            mask = (_ruby_shl(1, mask_len) - 1) << max(lhs_width - shift_amount, 0)
            return shifted_value | mask

        if op in ("&&", "||"):
            # These can short circuit, so we might only need the lhs.
            lhs_value = self.lhs.value(symtab)
            if op == "&&" and lhs_value is False:
                return False
            if op == "||" and lhs_value is True:
                return True
            # Otherwise lhs_value is True (for "&&") or False (for "||"), so the
            # result is exactly rhs's value; mirrors Ruby's
            # ``lhs_value && rhs.value(symtab)`` / ``lhs_value || rhs.value(symtab)``.
            return self.rhs.value(symtab)

        if op in ("==", "!="):
            try:
                lhs_val = self.lhs.value(symtab)
                rhs_val = self.rhs.value(symtab)
                return lhs_val == rhs_val if op == "==" else lhs_val != rhs_val
            except IdlValueUnknown:
                # Even without knowing the exact lhs/rhs values, disjoint
                # possible-value sets are enough to resolve == / !=.
                if _values_disjoint(self.lhs.values(symtab), self.rhs.values(symtab)):
                    return op == "!="
                self.value_error("There is overlap in the lhs/rhs return values")

        if op in ("<=", ">=", "<", ">"):
            cmp = {
                "<=": operator.le,
                ">=": operator.ge,
                "<": operator.lt,
                ">": operator.gt,
            }[op]
            try:
                return cmp(self.lhs.value(symtab), self.rhs.value(symtab))
            except IdlValueUnknown:
                rhs_values = self.rhs.values(symtab)
                if all(cmp(lv, rv) for lv in self.lhs.values(symtab) for rv in rhs_values):
                    return True
                self.value_error(f"Some value of lhs is not {op} some value of rhs")

        if op == "&":
            # If one side is zero, we don't need to know the other side.
            lhs_val = None
            try:
                lhs_val = self.lhs.value(symtab)
                if lhs_val == 0:
                    return 0
            except IdlValueUnknown:
                pass
            rhs_val = self.rhs.value(symtab)
            if rhs_val == 0:
                return 0
            if lhs_val is None:
                self.value_error("lhs value not known")
            return lhs_val & rhs_val

        if op == "|":
            # If one side is all ones, we don't need to know the other side.
            rhs_type = self.rhs.type(symtab)
            if rhs_type.width == WIDTH_UNKNOWN:
                self.value_error("Unknown width")
            lhs_type = self.lhs.type(symtab)
            if lhs_type.width == WIDTH_UNKNOWN:
                self.value_error("unknown width")

            rhs_val = None
            try:
                rhs_mask = (1 << rhs_type.width) - 1
                rhs_val = self.rhs.value(symtab)
                if rhs_val == rhs_mask and lhs_type.width <= rhs_type.width:
                    return rhs_mask
            except IdlValueUnknown:
                pass
            lhs_mask = (1 << lhs_type.width) - 1
            lhs_val = None
            try:
                lhs_val = self.lhs.value(symtab)
                if lhs_val == lhs_mask and rhs_type.width <= lhs_type.width:
                    return lhs_mask
            except IdlValueUnknown:
                pass
            if lhs_val is None:
                self.value_error("lhs value not known")
            if rhs_val is None:
                self.value_error("rhs value not known")
            return lhs_val | rhs_val

        lhs_val = self.lhs.value(symtab)
        rhs_val = self.rhs.value(symtab)
        if op in ("+", "`+"):
            v = lhs_val + rhs_val
        elif op in ("-", "`-"):
            v = lhs_val - rhs_val
        elif op in ("*", "`*"):
            v = lhs_val * rhs_val
        elif op == "/":
            if rhs_val == 0:
                # Ruby crashes here with an uncaught ZeroDivisionError (a
                # confirmed Ruby bug; see doc/python-migration-bugfixes.md).
                # A zero divisor genuinely makes the compile-time value
                # unknowable, so this is a value error, not a crash.
                self.value_error("Division by zero")
            v = lhs_val // rhs_val
        elif op == "%":
            if rhs_val == 0:
                self.value_error("Division by zero")
            v = lhs_val % rhs_val
        elif op == "^":
            v = lhs_val ^ rhs_val
        elif op == ">>":
            v = _ruby_shr(lhs_val, rhs_val)
        elif op in ("<<", "`<<"):
            v = _ruby_shl(lhs_val, rhs_val)
        else:
            self.internal_error(f"Unhandled binary op {op!r}")

        expr_type = self.type(symtab)
        if expr_type.width == WIDTH_UNKNOWN:
            self.value_error("Cannot know value of Bits with unknown width")
        v_trunc = v if "`" in op else self.truncate(v, expr_type.width, expr_type.is_signed)
        if v != v_trunc:
            self.truncation_warn(
                f"The value of '{self.text}' is truncated from {v} to {v_trunc} "
                f"because the result is only {expr_type.width} bits"
            )
        return v_trunc


@dataclass(frozen=True, slots=True, kw_only=True)
class UnaryOperatorExpression(Node):
    """A unary operator expression (``~``, ``!``, ``-``); Ruby's ``UnaryOperatorExpressionAst``."""

    kind: ClassVar[str] = "unary_operator_expr"

    op: str

    OPS: ClassVar[tuple[str, ...]] = ("~", "!", "-")

    def __post_init__(self) -> None:
        # See BinaryExpression.__post_init__ for why this avoids super().
        Node.__post_init__(self)
        if self.op not in self.OPS:
            raise ValueError(f"Bad unary operator: {self.op!r}")

    @property
    def expression(self) -> Node:
        return self.children[0]

    def to_idl(self) -> str:
        return f"{self.op}{self.expression.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"op": self.op, "expr": self.expression.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> UnaryOperatorExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        expr = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(expr,), op=data["op"])

    def const_eval(self, symtab: SymbolTable) -> bool:
        return self.expression.const_eval(symtab)

    def type(self, symtab: SymbolTable) -> Type:
        if self.op in ("-", "~"):
            return self.expression.type(symtab)
        if self.op == "!":
            return CONST_BOOL_TYPE if self.expression.type(symtab).is_const else BOOL_TYPE
        self.internal_error(f"unhandled op {self.op}")

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.expression.type_check(symtab, strict=strict)
        exp_type = self.expression.type(symtab)
        if self.op in ("-", "~"):
            if exp_type.kind not in (TypeKind.BITS, TypeKind.BITFIELD):
                self.type_error(f"{exp_type} does not support unary {self.op} operator")
        elif self.op == "!":
            if not exp_type.convertable_to(TypeKind.BOOLEAN):
                if exp_type.kind == TypeKind.BITS:
                    self.type_error(
                        f"{exp_type} does not support unary {self.op} operator. "
                        f"Perhaps you want '{self.expression.text} != 0'?"
                    )
                else:
                    self.type_error(f"{exp_type} does not support unary {self.op} operator")
        else:
            self.internal_error(f"Unhandled op {self.op}")

    def value(self, symtab: SymbolTable) -> Any:
        exp_value = self.expression.value(symtab)
        if self.op == "-":
            val = -exp_value
        elif self.op == "~":
            val = ~exp_value
        elif self.op == "!":
            val = not exp_value
        else:
            self.internal_error(f"Unhandled unary op {self.op}")

        val_trunc = val
        t = self.type(symtab)
        if t.is_integral:
            if t.width == WIDTH_UNKNOWN:
                self.value_error("Unknown width for truncation")
            val_trunc = self.truncate(val, t.width, t.is_signed)

        if self.op != "~" and val_trunc != val:
            self.truncation_warn(
                f"{self.text} is truncated due to insufficient bit width "
                f"(from {val} to {val_trunc})"
            )

        return val_trunc


@dataclass(frozen=True, slots=True, kw_only=True)
class TernaryOperatorExpression(Node):
    """A ``condition ? true_expression : false_expression`` expression.

    Ruby's ``TernaryOperatorExpressionAst``.
    """

    kind: ClassVar[str] = "ternary_operator_expr"

    @property
    def condition(self) -> Node:
        return self.children[0]

    @property
    def true_expression(self) -> Node:
        return self.children[1]

    @property
    def false_expression(self) -> Node:
        return self.children[2]

    def to_idl(self) -> str:
        # Ruby's `TernaryOperatorExpressionAst#to_idl` does *not* wrap
        # itself in parens (unlike `BinaryExpressionAst#to_idl`).
        return f"{self.condition.to_idl()} ? {self.true_expression.to_idl()} : {self.false_expression.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "condition": self.condition.to_h(),
            "true_expression": self.true_expression.to_h(),
            "false_expression": self.false_expression.to_h(),
        }

    @classmethod
    def from_h(
        cls, data: Mapping[str, Any], sources: Mapping[str, str]
    ) -> TernaryOperatorExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        condition = from_h(data["condition"], sources)
        true_expr = from_h(data["true_expression"], sources)
        false_expr = from_h(data["false_expression"], sources)
        return cls(source=source, start=start, end=end, children=(condition, true_expr, false_expr))

    def const_eval(self, symtab: SymbolTable) -> bool:
        return (
            self.condition.const_eval(symtab)
            and self.true_expression.const_eval(symtab)
            and self.false_expression.const_eval(symtab)
        )

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.condition.type_check(symtab, strict=strict)
        cond_type = self.condition.type(symtab)
        if cond_type.kind == TypeKind.BITS:
            self.type_error(
                f"ternary selector must be bool (maybe you meant '{self.condition.text} != 0'?)"
            )
        elif cond_type.kind != TypeKind.BOOLEAN:
            self.type_error("ternary selector must be bool")

        def check_both() -> None:
            self.true_expression.type_check(symtab, strict=strict)
            self.false_expression.type_check(symtab, strict=strict)
            true_type = self.true_expression.type(symtab)
            false_type = self.false_expression.type(symtab)
            if not true_type.equal_to(false_type) and not (
                true_type.kind == TypeKind.BITS and false_type.kind == TypeKind.BITS
            ):
                self.type_error(
                    f"True and false options must be same type (have {true_type} and {false_type})"
                )

        if strict:
            try:
                cond = self.condition.value(symtab)
                # If the condition is compile-time-known, only check the used branch.
                if cond:
                    self.true_expression.type_check(symtab, strict=strict)
                else:
                    self.false_expression.type_check(symtab, strict=strict)
            except IdlValueUnknown:
                check_both()
        else:
            check_both()

    def type(self, symtab: SymbolTable) -> Type:
        cache = self._cache.setdefault("_ternary_type", {})
        key = (symtab.name, symtab.mxlen)
        cached = cache.get(key)
        if cached is not None:
            return cached

        true_type = self.true_expression.type(symtab)
        false_type = self.false_expression.type(symtab)
        if true_type.kind == TypeKind.BITS and false_type.kind == TypeKind.BITS:
            true_width = true_type.width
            false_width = false_type.width
            known = true_type.is_known and false_type.is_known
            if true_width == WIDTH_UNKNOWN or false_width == WIDTH_UNKNOWN:
                if true_width == WIDTH_UNKNOWN and false_width == WIDTH_UNKNOWN:
                    max_width = (
                        None
                        if true_type.max_width is None or false_type.max_width is None
                        else max(true_type.max_width, false_type.max_width)
                    )
                elif true_width == WIDTH_UNKNOWN:
                    max_width = (
                        None
                        if true_type.max_width is None
                        else max(true_type.max_width, false_width)
                    )
                else:
                    max_width = (
                        None
                        if false_type.max_width is None
                        else max(false_type.max_width, true_width)
                    )
                qualifiers = (Qualifier.KNOWN,) if known else ()
                t = Type(
                    TypeKind.BITS, width=WIDTH_UNKNOWN, max_width=max_width, qualifiers=qualifiers
                )
            else:
                qualifiers = (Qualifier.KNOWN,) if known else ()
                t = Type(TypeKind.BITS, width=max(true_width, false_width), qualifiers=qualifiers)
        else:
            t = true_type

        if self.condition.type(symtab).is_const and true_type.is_const and false_type.is_const:
            t = t.make_const()
        cache[key] = t
        return t

    def value(self, symtab: SymbolTable) -> Any:
        return (
            self.true_expression.value(symtab)
            if self.condition.value(symtab)
            else self.false_expression.value(symtab)
        )

    def values(self, symtab: SymbolTable) -> list[Any]:
        try:
            cond = self.condition.value(symtab)
            return (
                self.true_expression.values(symtab)
                if cond
                else self.false_expression.values(symtab)
            )
        except IdlValueUnknown:
            combined = [*self.true_expression.values(symtab), *self.false_expression.values(symtab)]
            deduped: list[Any] = []
            for v in combined:
                if not any(v == existing for existing in deduped):
                    deduped.append(v)
            return deduped


@dataclass(frozen=True, slots=True, kw_only=True)
class ParenExpression(Node):
    """A parenthesized expression; Ruby's ``ParenExpressionAst``."""

    kind: ClassVar[str] = "paren_expr"

    @property
    def expression(self) -> Node:
        return self.children[0]

    def to_idl(self) -> str:
        return f"({self.expression.to_idl()})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"expr": self.expression.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ParenExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        expr = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(expr,))

    def const_eval(self, symtab: SymbolTable) -> bool:
        return self.expression.const_eval(symtab)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.expression.type_check(symtab, strict=strict)

    def type(self, symtab: SymbolTable) -> Type:
        return self.expression.type(symtab)

    def value(self, symtab: SymbolTable) -> Any:
        return self.expression.value(symtab)
