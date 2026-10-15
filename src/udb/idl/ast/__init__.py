# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""The IDL syntax tree: node classes, ``to_h``/``to_idl`` serialization, and ``from_h``.

This module is a line-for-line port of the *syntactic* portion of Ruby's
``Idl::AstNode`` hierarchy (``tools/ruby-gems/idlc/lib/idlc/ast.rb``): every
class that can appear in a parsed IDL syntax tree, its ``to_h`` (dict
serialization matching the Ruby oracle byte-for-byte), its ``self.from_h``
counterpart, and ``to_idl`` (re-emit as IDL source, used for round-trip
testing). Semantic methods (``type_check``, ``type``, ``value``, ``execute``,
``prune``, ``gen_adoc``, ...) are out of scope for this slice; they are added
to these same classes in later migration slices.

Ruby class name -> Python class name
-------------------------------------
Every node class below corresponds to a Ruby ``*Ast`` class of the same name
with the ``Ast`` suffix dropped (there is no ambiguity: none of these base
names collide with an unrelated Python builtin or with each other)::

    Id                              <- IdAst
    IntLiteral                      <- IntLiteralAst
    StringLiteral                   <- StringLiteralAst
    TrueExpression                  <- TrueExpressionAst
    FalseExpression                 <- FalseExpressionAst
    Comment                         <- CommentAst
    BuiltinVariable                 <- BuiltinVariableAst
    UserTypeName                    <- UserTypeNameAst
    BuiltinTypeName                 <- BuiltinTypeNameAst
    DontCareReturn                  <- DontCareReturnAst
    DontCareLvalue                  <- DontCareLvalueAst
    EnumRef                         <- EnumRefAst
    Noop                            <- NoopAst
    BinaryExpression                <- BinaryExpressionAst
    UnaryOperatorExpression         <- UnaryOperatorExpressionAst
    TernaryOperatorExpression       <- TernaryOperatorExpressionAst
    ParenExpression                 <- ParenExpressionAst
    ArrayLiteral                    <- ArrayLiteralAst
    ConcatenationExpression         <- ConcatenationExpressionAst
    ReplicationExpression           <- ReplicationExpressionAst
    PostIncrementExpression         <- PostIncrementExpressionAst
    PostDecrementExpression         <- PostDecrementExpressionAst
    FieldAccessExpression           <- FieldAccessExpressionAst
    AryElementAccess                <- AryElementAccessAst
    AryRangeAccess                  <- AryRangeAccessAst
    FunctionCallExpression          <- FunctionCallExpressionAst
    CsrFieldReadExpression          <- CsrFieldReadExpressionAst
    CsrReadExpression               <- CsrReadExpressionAst
    CsrSoftwareWrite                <- CsrSoftwareWriteAst
    CsrFunctionCall                 <- CsrFunctionCallAst
    CsrWrite                        <- CsrWriteAst
    WidthReveal                     <- WidthRevealAst
    SignCast                        <- SignCastAst
    BitsCast                        <- BitsCastAst
    ArraySize                       <- ArraySizeAst
    EnumSize                        <- EnumSizeAst
    EnumElementSize                 <- EnumElementSizeAst
    EnumCast                        <- EnumCastAst
    EnumArrayCast                   <- EnumArrayCastAst
    ArrayIncludes                   <- ArrayIncludesAst
    ImplicationExpression           <- ImplicationExpressionAst
    Statement                       <- StatementAst
    ReturnStatement                 <- ReturnStatementAst
    ConditionalStatement            <- ConditionalStatementAst
    ConditionalReturnStatement      <- ConditionalReturnStatementAst
    ReturnExpression                <- ReturnExpressionAst
    ImplicationStatement            <- ImplicationStatementAst
    ForLoop                         <- ForLoopAst
    IfBody                          <- IfBodyAst
    ElseIf                          <- ElseIfAst
    If                              <- IfAst
    PcAssignment                    <- PcAssignmentAst
    VariableAssignment              <- VariableAssignmentAst
    AryElementAssignment            <- AryElementAssignmentAst
    AryRangeAssignment              <- AryRangeAssignmentAst
    FieldAssignment                 <- FieldAssignmentAst
    CsrFieldAssignment              <- CsrFieldAssignmentAst
    MultiVariableAssignment         <- MultiVariableAssignmentAst
    VariableDeclaration             <- VariableDeclarationAst
    VariableDeclarationWithInitialization <- VariableDeclarationWithInitializationAst
    MultiVariableDeclaration        <- MultiVariableDeclarationAst
    Global                          <- GlobalAst
    GlobalWithInitialization        <- GlobalWithInitializationAst
    FunctionDef                     <- FunctionDefAst
    EnumDefinition                  <- EnumDefinitionAst
    BuiltinEnumDefinition           <- BuiltinEnumDefinitionAst
    BitfieldFieldDefinition         <- BitfieldFieldDefinitionAst
    BitfieldDefinition              <- BitfieldDefinitionAst
    StructDefinition                <- StructDefinitionAst
    FunctionBody                    <- FunctionBodyAst
    ConstraintBody                  <- ConstraintBodyAst
    Fetch                           <- FetchAst
    IncludeStatement                <- IncludeStatementAst
    Isa                             <- IsaAst
    ParseTimeDetectedTypeError      <- ParseTimeDetectedTypeError (unchanged)

``BuiltinTypeName`` is the Python stand-in for Ruby's ``TypeNameAst`` Sorbet
type alias (``T.any(UserTypeNameAst, BuiltinTypeNameAst)``); there is no
runtime Ruby class for it, so there is no Python one either -- code that needs
"either kind of type name" should annotate with ``UserTypeName | BuiltinTypeName``.

Design notes
------------
* Every node is an immutable (frozen, ``__slots__``) dataclass. All
  constructor arguments are keyword-only (``kw_only=True``), so subclasses may
  freely add required fields after :class:`Node`'s own defaulted ones.
* ``children`` is always a ``tuple[Node, ...]``; a private, mutable ``_cache``
  dict (excluded from equality/repr) is reserved for later semantic-analysis
  memoization (e.g. a memoized ``type()`` result) -- mutating its *contents*
  does not violate the frozen dataclass, since only attribute *rebinding* is
  blocked.
* ``(start, end)`` is a half-open interval into ``source.text``; ``text``
  defaults to that slice. A handful of leaf classes (:class:`Id`,
  :class:`IntLiteral`, :class:`StringLiteral`, :class:`Comment`,
  :class:`UserTypeName`, :class:`BuiltinVariable`) store an explicit string
  field and override ``text`` to return it instead, mirroring the same
  classes overriding Ruby's ``text_value``.
* Two kind strings are shared by two Python classes each, exactly as in Ruby:
  ``"stmt"`` (:class:`Statement` / :class:`ReturnStatement`) and
  ``"conditional_stmt"`` (:class:`ConditionalStatement` /
  :class:`ConditionalReturnStatement`); the module-level :func:`from_h`
  disambiguates by inspecting the nested ``"expr"``'s own kind
  (``"return_expr"`` selects the *Return* variant), exactly like Ruby's
  ``AstNode.from_h``. Likewise ``"builtin_type"``/``"bits_type"`` both
  reconstruct a :class:`BuiltinTypeName`.
* Ruby's ``IncludeStatementAst#to_h`` unconditionally raises (``"unreachable"``);
  this is why the oracle (``tests/python/ruby_idl_oracle.rb``) special-cases
  both ``IncludeStatementAst`` and ``IsaAst`` (whose ``to_h`` would otherwise
  recurse into that raise) rather than calling ``to_h`` on the whole tree.
  Python's :meth:`IncludeStatement.to_h` deliberately does *not* raise --
  it returns ``{"kind": "include", "filename": ...}`` directly, matching what
  the oracle itself substitutes, so :meth:`Isa.to_h` needs no special-casing
  here.
"""

from __future__ import annotations

import operator as operator
import re as re
import warnings as warnings
from collections.abc import Iterable as Iterable
from collections.abc import Mapping as Mapping
from dataclasses import dataclass as dataclass
from dataclasses import field as field
from typing import Any as Any
from typing import ClassVar as ClassVar
from typing import NoReturn as NoReturn

from ..errors import IdlInternalError as IdlInternalError
from ..errors import IdlTypeError as IdlTypeError
from ..errors import IdlValueUnknown as IdlValueUnknown
from ..source import IdlSource as IdlSource
from ..symbols import SymbolTable as SymbolTable
from ..symbols import Var as Var
from ..types import BITS_UNKNOWN_TYPE as BITS_UNKNOWN_TYPE
from ..types import BOOL_TYPE as BOOL_TYPE
from ..types import CONST_BOOL_TYPE as CONST_BOOL_TYPE
from ..types import POSSIBLY_UNKNOWN_BITS1_TYPE as POSSIBLY_UNKNOWN_BITS1_TYPE
from ..types import WIDTH_UNKNOWN as WIDTH_UNKNOWN
from ..types import BitfieldType as BitfieldType
from ..types import EnumerationType as EnumerationType
from ..types import Qualifier as Qualifier
from ..types import RegFileElementType as RegFileElementType
from ..types import StructType as StructType
from ..types import Type as Type
from ..types import TypeKind as TypeKind
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
from ._base import (
    RESERVED_WORDS as RESERVED_WORDS,
)
from ._base import (
    Node,
)
from ._base import (
    _check_kind as _check_kind,
)
from ._base import (
    _idl_join as _idl_join,
)
from ._base import (
    _source_and_span as _source_and_span,
)
from ._base import (
    _try_value as _try_value,
)
from ._base import (
    _values_disjoint as _values_disjoint,
)
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
    Global,
    GlobalWithInitialization,
    MultiVariableDeclaration,
    StructDefinition,
    VariableDeclaration,
    VariableDeclarationWithInitialization,
)
from ._declarations import (
    _unwrap_array_decl_type as _unwrap_array_decl_type,
)
from ._declarations import (
    _wrap_array_decl_type as _wrap_array_decl_type,
)
from ._functions import FunctionBody, FunctionDef
from ._leaves import (
    _BUILTIN_TYPE_NAMES as _BUILTIN_TYPE_NAMES,
)
from ._leaves import (
    _CPP_INT_RE as _CPP_INT_RE,
)
from ._leaves import (
    _DECIMAL_INT_RE as _DECIMAL_INT_RE,
)
from ._leaves import (
    _RADIX_TO_VERILOG as _RADIX_TO_VERILOG,
)
from ._leaves import (
    _VERILOG_INT_RE as _VERILOG_INT_RE,
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
    UnknownLiteral,
    UserTypeName,
)
from ._leaves import (
    _int_to_s as _int_to_s,
)
from ._leaves import (
    _ruby_str_to_i as _ruby_str_to_i,
)
from ._operators import (
    BinaryExpression,
    ParenExpression,
    TernaryOperatorExpression,
    UnaryOperatorExpression,
)
from ._registry import _KIND_TO_CLASS as _KIND_TO_CLASS
from ._registry import from_h
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

__all__ = [
    "ArrayIncludes",
    "ArrayLiteral",
    "ArraySize",
    "AryElementAccess",
    "AryElementAssignment",
    "AryRangeAccess",
    "AryRangeAssignment",
    "BinaryExpression",
    "BitfieldDefinition",
    "BitfieldFieldDefinition",
    "BitsCast",
    "BuiltinEnumDefinition",
    "BuiltinTypeName",
    "BuiltinVariable",
    "Comment",
    "ConcatenationExpression",
    "ConditionalReturnStatement",
    "ConditionalStatement",
    "ConstraintBody",
    "CsrFieldAssignment",
    "CsrFieldReadExpression",
    "CsrFunctionCall",
    "CsrReadExpression",
    "CsrSoftwareWrite",
    "CsrWrite",
    "DontCareLvalue",
    "DontCareReturn",
    "ElseIf",
    "EnumArrayCast",
    "EnumCast",
    "EnumDefinition",
    "EnumElementSize",
    "EnumRef",
    "EnumSize",
    "FalseExpression",
    "Fetch",
    "FieldAccessExpression",
    "FieldAssignment",
    "ForLoop",
    "FunctionBody",
    "FunctionCallExpression",
    "FunctionDef",
    "Global",
    "GlobalWithInitialization",
    "Id",
    "If",
    "IfBody",
    "ImplicationExpression",
    "ImplicationStatement",
    "IncludeStatement",
    "IntLiteral",
    "Isa",
    "MultiVariableAssignment",
    "MultiVariableDeclaration",
    "Node",
    "Noop",
    "ParenExpression",
    "ParseTimeDetectedTypeError",
    "PcAssignment",
    "PostDecrementExpression",
    "PostIncrementExpression",
    "ReplicationExpression",
    "ReturnExpression",
    "ReturnStatement",
    "SignCast",
    "Statement",
    "StringLiteral",
    "StructDefinition",
    "TernaryOperatorExpression",
    "TrueExpression",
    "UnaryOperatorExpression",
    "UnknownLiteral",
    "UserTypeName",
    "VariableAssignment",
    "VariableDeclaration",
    "VariableDeclarationWithInitialization",
    "WidthReveal",
    "from_h",
]
