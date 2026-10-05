# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""``from_h`` dispatch: reconstructs a node tree from ``to_h`` output."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._aggregates import (
    ArrayLiteral,
    AryElementAccess,
    AryRangeAccess,
    ConcatenationExpression,
    FieldAccessExpression,
    FunctionCallExpression,
    PostDecrementExpression,
    PostIncrementExpression,
    ReplicationExpression,
)
from ._assignments import (
    AryElementAssignment,
    AryRangeAssignment,
    CsrFieldAssignment,
    FieldAssignment,
    MultiVariableAssignment,
    PcAssignment,
    VariableAssignment,
)
from ._base import Node
from ._builtins import (
    ArrayIncludes,
    ArraySize,
    BitsCast,
    EnumArrayCast,
    EnumCast,
    EnumElementSize,
    EnumSize,
    ImplicationExpression,
    SignCast,
    WidthReveal,
)
from ._csr import (
    CsrFieldReadExpression,
    CsrFunctionCall,
    CsrReadExpression,
    CsrSoftwareWrite,
    CsrWrite,
)
from ._declarations import (
    BitfieldDefinition,
    BitfieldFieldDefinition,
    BuiltinEnumDefinition,
    EnumDefinition,
    FunctionBody,
    FunctionDef,
    Global,
    GlobalWithInitialization,
    MultiVariableDeclaration,
    StructDefinition,
    VariableDeclaration,
    VariableDeclarationWithInitialization,
)
from ._leaves import (
    BuiltinTypeName,
    BuiltinVariable,
    Comment,
    DontCareLvalue,
    DontCareReturn,
    EnumRef,
    FalseExpression,
    Id,
    IntLiteral,
    Noop,
    StringLiteral,
    TrueExpression,
    UserTypeName,
)
from ._operators import (
    BinaryExpression,
    ParenExpression,
    TernaryOperatorExpression,
    UnaryOperatorExpression,
)
from ._statements import (
    ConditionalReturnStatement,
    ConditionalStatement,
    ElseIf,
    ForLoop,
    If,
    IfBody,
    ImplicationStatement,
    ReturnExpression,
    ReturnStatement,
    Statement,
)
from ._toplevel import (
    ConstraintBody,
    Fetch,
    IncludeStatement,
    Isa,
    ParseTimeDetectedTypeError,
)

_KIND_TO_CLASS: dict[str, type[Node]] = {
    "id": Id,
    "bits_literal": IntLiteral,
    "string_literal": StringLiteral,
    "true": TrueExpression,
    "false": FalseExpression,
    "comment": Comment,
    "builtin_var_expr": BuiltinVariable,
    "user_type_reference": UserTypeName,
    "builtin_type": BuiltinTypeName,
    "bits_type": BuiltinTypeName,
    "dont_care": DontCareReturn,
    "dont_care_lval": DontCareLvalue,
    "enum_reference_expr": EnumRef,
    "noop_expr": Noop,
    "binary_operator_expr": BinaryExpression,
    "unary_operator_expr": UnaryOperatorExpression,
    "ternary_operator_expr": TernaryOperatorExpression,
    "paren_expr": ParenExpression,
    "array_literal": ArrayLiteral,
    "concat_expr": ConcatenationExpression,
    "repl_expr": ReplicationExpression,
    "post_increment_expr": PostIncrementExpression,
    "post_decrement_expr": PostDecrementExpression,
    "field_access_expr": FieldAccessExpression,
    "array_access": AryElementAccess,
    "array_range_access": AryRangeAccess,
    "funcall_expr": FunctionCallExpression,
    "csr_read_expr": CsrReadExpression,
    "csr_access_expr": CsrWrite,
    "csr_field_read_expr": CsrFieldReadExpression,
    "csr_sw_write_expr": CsrSoftwareWrite,
    "csr_funcall_expr": CsrFunctionCall,
    "bits_width_cast": WidthReveal,
    "sign_cast": SignCast,
    "bits_cast": BitsCast,
    "array_size_funcall": ArraySize,
    "enum_size_funcall": EnumSize,
    "enum_element_size_funcall": EnumElementSize,
    "enum_to_array_cast": EnumArrayCast,
    "bits_to_enum_cast": EnumCast,
    "array_includes_funcall": ArrayIncludes,
    "implication_expr": ImplicationExpression,
    "return_expr": ReturnExpression,
    "implication_stmt": ImplicationStatement,
    "if_body": IfBody,
    "else_if_stmt": ElseIf,
    "if_stmt": If,
    "for_loop_stmt": ForLoop,
    "pc_assignment": PcAssignment,
    "var_assignment": VariableAssignment,
    "array_element_assignment": AryElementAssignment,
    "array_range_assignment": AryRangeAssignment,
    "field_assignment": FieldAssignment,
    "csr_field_assignment": CsrFieldAssignment,
    "multi_var_assignment": MultiVariableAssignment,
    "var_decl": VariableDeclaration,
    "var_decl_init": VariableDeclarationWithInitialization,
    "multi_var_decl": MultiVariableDeclaration,
    "global_var_decl": Global,
    "global_var_decl_with_init": GlobalWithInitialization,
    "function_decl": FunctionDef,
    "enum_decl": EnumDefinition,
    "builtin_enum_decl": BuiltinEnumDefinition,
    "bitfield_field_decl": BitfieldFieldDefinition,
    "bitfield_decl": BitfieldDefinition,
    "struct_decl": StructDefinition,
    "function_body": FunctionBody,
    "constraint_body": ConstraintBody,
    "fetch_decl": Fetch,
    "include": IncludeStatement,
    "isa": Isa,
    "ParseTimeDetectedTypeError": ParseTimeDetectedTypeError,
}


def from_h(data: Mapping[str, Any], sources: Mapping[str, str]) -> Node:
    """Reconstruct a node tree from ``to_h`` output.

    Mirrors Ruby's ``Idl::AstNode.from_h(yaml, source_mapper)`` dispatch,
    including its two kind-sharing special cases:

    * ``"stmt"`` reconstructs a :class:`ReturnStatement` if the nested
      ``"expr"``'s own kind is ``"return_expr"``, else a :class:`Statement`.
    * ``"conditional_stmt"`` reconstructs a :class:`ConditionalReturnStatement`
      under the same condition, else a :class:`ConditionalStatement`.

    Args:
        data: A ``to_h``-shaped dict (as produced by :meth:`Node.to_h`, or by
            the Ruby oracle).
        sources: Maps each ``source["file"]`` label appearing in *data* to
            the full text it should be sliced from (a node's ``(begin, end)``
            interval indexes into this text).
    """
    kind = data.get("kind")
    if kind == "stmt":
        inner_kind = data["expr"].get("kind")
        cls: type[Node] = ReturnStatement if inner_kind == "return_expr" else Statement
        return cls.from_h(data, sources)  # type: ignore[attr-defined]
    if kind == "conditional_stmt":
        inner_kind = data["expr"].get("kind")
        cls = ConditionalReturnStatement if inner_kind == "return_expr" else ConditionalStatement
        return cls.from_h(data, sources)  # type: ignore[attr-defined]
    cls = _KIND_TO_CLASS.get(kind)  # type: ignore[assignment]
    if cls is None:
        raise ValueError(f"Unknown IDL AST kind: {kind!r}")
    return cls.from_h(data, sources)  # type: ignore[attr-defined]
