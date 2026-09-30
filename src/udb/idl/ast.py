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

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

from .source import IdlSource

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


# ---------------------------------------------------------------------------
# Base node
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class Node:
    """Base class for every IDL syntax tree node.

    Mirrors Ruby's ``Idl::AstNode``: an immutable node with a source
    reference, a half-open ``(start, end)`` interval into that source's text,
    a tuple of child nodes, and a parent link (set once, at construction).
    """

    kind: ClassVar[str] = ""

    source: IdlSource
    start: int
    end: int
    children: tuple[Node, ...] = ()
    parent: Node | None = field(default=None, compare=False, repr=False)
    _cache: dict[str, Any] = field(default_factory=dict, compare=False, repr=False, hash=False)

    def __post_init__(self) -> None:
        for child in self.children:
            object.__setattr__(child, "parent", self)

    @property
    def text(self) -> str:
        """The exact source text spanned by this node (Ruby's ``text_value``)."""
        return self.source.text[self.start : self.end]

    @property
    def lineno(self) -> int:
        """1-based line number this node starts on."""
        return self.source.lineno(self.start)

    @property
    def column(self) -> int:
        """1-based column number this node starts on."""
        return self.source.column(self.start)

    def _to_h_fields(self) -> dict[str, Any]:
        """Subclass-specific ``to_h`` keys (everything but ``kind``/``source``)."""
        return {}

    def to_h(self) -> dict[str, Any]:
        """Dict serialization matching Ruby's ``AstNode#to_h`` exactly."""
        result: dict[str, Any] = {"kind": self.kind}
        result.update(self._to_h_fields())
        result["source"] = self.source.source_dict(self.start, self.end)
        return result

    def to_idl(self) -> str:  # pragma: no cover - overridden by every concrete subclass
        raise NotImplementedError(f"{type(self).__name__}.to_idl")

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.text!r})"


def _source_and_span(
    data: Mapping[str, Any], sources: Mapping[str, str]
) -> tuple[IdlSource, int, int]:
    """Build an :class:`IdlSource`/``(start, end)`` triple from a ``to_h`` ``"source"`` dict."""
    src = data["source"]
    label = src["file"]
    source = IdlSource(text=sources[label], label=label)
    return source, src["begin"], src["end"]


def _check_kind(data: Mapping[str, Any], kind: str) -> None:
    if data.get("kind") != kind:
        raise ValueError(f"Bad YAML: expected kind {kind!r}, got {data.get('kind')!r}")


def _idl_join(nodes: tuple[Node, ...], sep: str = ", ") -> str:
    return sep.join(n.to_idl() for n in nodes)


# ---------------------------------------------------------------------------
# Leaf nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class Id(Node):
    """An identifier reference (``kind = "id"``); Ruby's ``IdAst``."""

    kind: ClassVar[str] = "id"

    name: str

    @property
    def text(self) -> str:
        return self.name

    @property
    def const(self) -> bool:
        """Whether this identifier names a compile-time constant (starts with an uppercase letter)."""
        return bool(self.name) and self.name[0].isupper()

    def to_idl(self) -> str:
        return self.name

    def _to_h_fields(self) -> dict[str, Any]:
        return {"name": self.name}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> Id:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end, name=data["name"])


@dataclass(frozen=True, slots=True, kw_only=True)
class UnknownLiteral:
    """A value with some bits known and others left as Verilog ``x``/``X`` ("unknown") bits.

    Mirrors Ruby's plain (non-``AstNode``) ``Idl::UnknownLiteral`` helper class,
    which :class:`IntLiteral` uses as its ``unsigned_value``/``value`` when the
    literal's digit text contains ``x``/``X`` (e.g. ``4'b10x1``).

    This case is never exercised by real IDL source in the database (verified
    against the full corpus). ``IntLiteral.to_h()`` serializes it as its
    ``str()`` form (``__str__`` mirrors Ruby's ``UnknownLiteral#to_s``
    exactly), matching what the Ruby oracle's ``JSON.generate`` actually
    produces: ``UnknownLiteral`` defines no ``to_json`` of its own, so Ruby's
    ``json`` stdlib falls back to its default ``Object#to_json``, which calls
    ``#to_s``. ``from_h`` does not support reconstructing this value (see
    :meth:`IntLiteral.from_h`), since the string form is lossy for round-trip
    purposes and Ruby has no matching ``from_h`` support for it either.
    """

    known_value: int
    unknown_mask: int

    def bit_length(self) -> int:
        return max(self.known_value.bit_length(), self.unknown_mask.bit_length())

    def __str__(self) -> str:
        known_bits = bin(self.known_value)[2:][::-1]
        mask_bits = bin(self.unknown_mask)[2:][::-1]
        n = max(len(known_bits), len(mask_bits))
        chars = []
        for i in range(n):
            is_unknown = i < len(mask_bits) and mask_bits[i] == "1"
            if is_unknown:
                chars.append("x")
            else:
                chars.append(known_bits[i] if i < len(known_bits) else "0")
        return f"{n}'b{''.join(reversed(chars))}"


_VERILOG_INT_RE = re.compile(r"^((MXLEN)|([0-9]+))?'(s?)([bodh]?)(.*)$")
_CPP_INT_RE = re.compile(r"^0([bdx]?)([0-9a-fA-F]*)(s?)$")
_DECIMAL_INT_RE = re.compile(r"^([0-9]*)(s?)$")
_RADIX_TO_VERILOG = {2: "b", 8: "o", 10: "d", 16: "h"}


def _ruby_str_to_i(text: str, base: int) -> int:
    """Mirror Ruby's tolerant ``String#to_i(base)``: empty text parses as ``0``."""
    return int(text, base) if text else 0


def _int_to_s(value: int, radix: int) -> str:
    """Mirror Ruby's ``Integer#to_s(radix)`` (lowercase digits, no prefix)."""
    if radix == 2:
        return format(value, "b")
    if radix == 8:
        return format(value, "o")
    if radix == 16:
        return format(value, "x")
    return str(value)


@dataclass(frozen=True, slots=True, kw_only=True)
class IntLiteral(Node):
    """An integer literal (``kind = "bits_literal"``); Ruby's ``IntLiteralAst``.

    Supports all three literal forms from the grammar: Verilog-style
    (``[width]'[s][bodh]digits``, digits may contain ``x``/``X`` unknown
    bits), C++-style (``0[bdx]digits``, a bare ``0...`` prefix means octal),
    and plain decimal (``digits[s]``).
    """

    kind: ClassVar[str] = "bits_literal"

    raw_text: str

    @property
    def text(self) -> str:
        return self.raw_text

    def to_idl(self) -> str:
        return self.raw_text

    def _match(self) -> tuple[str, re.Match[str]]:
        cached = self._cache.get("_int_match")
        if cached is not None:
            return cached
        t = self.raw_text.replace("_", "")
        for style, pattern in (
            ("verilog", _VERILOG_INT_RE),
            ("cpp", _CPP_INT_RE),
            ("decimal", _DECIMAL_INT_RE),
        ):
            m = pattern.fullmatch(t)
            if m is not None:
                self._cache["_int_match"] = (style, m)
                return style, m
        raise ValueError(f"Unhandled int literal: {self.raw_text!r}")

    def signed(self) -> bool:
        style, m = self._match()
        if style == "verilog":
            return m.group(4) != ""
        if style == "cpp":
            return m.group(3) != ""
        return m.group(2) != ""

    def radix(self) -> int:
        style, m = self._match()
        if style == "verilog":
            return {"": 10, "b": 2, "o": 8, "d": 10, "h": 16}[m.group(5)]
        if style == "cpp":
            return {"": 10, "b": 2, "d": 10, "x": 16}[m.group(1)]
        return 10

    def unsigned_value(self) -> int | UnknownLiteral:
        style, m = self._match()
        if style == "verilog":
            radix_id = m.group(5) or "d"
            value_text = m.group(6)
            base = {"b": 2, "o": 8, "d": 10, "h": 16}[radix_id]
            if "x" not in value_text and "X" not in value_text:
                return _ruby_str_to_i(value_text, base)
            if radix_id == "d":
                raise ValueError("impossible: decimal literal cannot have unknown bits")
            zero_pattern = {"b": "1", "o": "[0-7]", "h": "[0-9a-fA-F]"}[radix_id]
            fill = {"b": "1", "o": "7", "h": "f"}[radix_id]
            known_value = _ruby_str_to_i(re.sub("[xX]", "0", value_text), base)
            unknown_mask = _ruby_str_to_i(
                re.sub("[xX]", fill, re.sub(zero_pattern, "0", value_text)), base
            )
            return UnknownLiteral(known_value=known_value, unknown_mask=unknown_mask)
        if style == "cpp":
            radix_id = m.group(1) or "o"
            base = {"b": 2, "o": 8, "d": 10, "x": 16}[radix_id]
            return _ruby_str_to_i(m.group(2), base)
        return _ruby_str_to_i(m.group(1), 10)

    def width(self) -> int | str:
        """The literal's bit width, or the sentinel ``"unknown"``.

        Mirrors ``IntLiteralAst#width(nil)`` (called with no symbol table, as
        ``to_h`` does): a Verilog-style literal with no explicit width and no
        symbol table has unknown width; the other two forms always have a
        computed width.
        """
        style, m = self._match()
        if style == "verilog":
            w = m.group(1)
            if w is None or w == "MXLEN":
                return "unknown"
            return int(w)
        value = self.unsigned_value()
        bit_length = value.bit_length()
        # Ruby's basic-decimal branch reads the wrong capture group and drops
        # the sign bit for literals such as ``63s`` (python-migration-bugfixes.md
        # entry 18). Python gives every signed form the extra bit.
        computed = bit_length + 1 if self.signed() else bit_length
        return 1 if computed == 0 else computed

    def _to_h_fields(self) -> dict[str, Any]:
        w = self.width()
        value = self.unsigned_value()
        # Ruby's ``to_h`` embeds whatever ``value(symtab)`` returns directly
        # in the Hash; when that is an ``UnknownLiteral`` (an x/X don't-care
        # bits literal), the *oracle's* ``JSON.generate`` call serializes it
        # via Ruby's default ``Object#to_json`` fallback, which stringifies
        # via ``#to_s`` (``UnknownLiteral`` defines no ``to_json`` of its
        # own). Mirror that exact string form here rather than embedding the
        # object, matching the oracle's real JSON output byte for byte.
        if isinstance(value, UnknownLiteral):
            value = str(value)
        return {
            "width": "MXLEN" if w == "unknown" else str(w),
            "value": value,
            "signed": self.signed(),
            "radix": self.radix(),
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> IntLiteral:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        radix = data["radix"]
        value = data["value"]
        # ``to_h`` serializes unknown-bit (x/X) values as strings; see ``_to_h_fields``.
        if isinstance(value, (str, UnknownLiteral)):
            raise NotImplementedError("from_h does not support unknown-bit literal values")
        text = f"{data['width']}'{'s' if data['signed'] else ''}{_RADIX_TO_VERILOG[radix]}{_int_to_s(value, radix)}"
        return cls(source=source, start=start, end=end, raw_text=text)


@dataclass(frozen=True, slots=True, kw_only=True)
class StringLiteral(Node):
    """A string literal (``kind = "string_literal"``); Ruby's ``StringLiteralAst``.

    ``raw_text`` includes the surrounding quotes (matching Ruby's
    ``text_value``); ``to_h``'s ``"text"`` strips them.
    """

    kind: ClassVar[str] = "string_literal"

    raw_text: str

    @property
    def text(self) -> str:
        return self.raw_text

    @property
    def content(self) -> str:
        return self.raw_text.replace('"', "")

    def to_idl(self) -> str:
        return self.raw_text

    def _to_h_fields(self) -> dict[str, Any]:
        return {"text": self.content}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> StringLiteral:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end, raw_text=f'"{data["text"]}"')


@dataclass(frozen=True, slots=True, kw_only=True)
class TrueExpression(Node):
    """The ``true`` literal; Ruby's ``TrueExpressionAst``."""

    kind: ClassVar[str] = "true"

    def to_idl(self) -> str:
        return "true"

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> TrueExpression:
        _check_kind(data, cls.kind)
        if data.get("source") is None:
            return cls(source=IdlSource(text="true", label="<synthetic>"), start=0, end=4)
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end)


@dataclass(frozen=True, slots=True, kw_only=True)
class FalseExpression(Node):
    """The ``false`` literal; Ruby's ``FalseExpressionAst``."""

    kind: ClassVar[str] = "false"

    def to_idl(self) -> str:
        return "false"

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> FalseExpression:
        _check_kind(data, cls.kind)
        if data.get("source") is None:
            return cls(source=IdlSource(text="false", label="<synthetic>"), start=0, end=5)
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end)


@dataclass(frozen=True, slots=True, kw_only=True)
class Comment(Node):
    """A ``#``-to-end-of-line comment; Ruby's ``CommentAst``.

    Comments are absorbed by the grammar's ``space`` rule and never produced
    as real nodes by the parser, so this class exists only for structural
    completeness (matching Ruby, where it likewise is unreachable from a real
    parse but still defined). Note Ruby's ``CommentAst.from_h`` itself has a
    latent bug -- it reads ``yaml.fetch("content")`` but ``to_h`` only emits
    key ``"text"`` -- which is why it is unreachable in practice; Python's
    :meth:`from_h` reads the correct key.
    """

    kind: ClassVar[str] = "comment"

    raw_text: str

    @property
    def text(self) -> str:
        return self.raw_text

    @property
    def content(self) -> str:
        return self.raw_text[1:].strip()

    def to_idl(self) -> str:
        return f"# {self.content}\n"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"text": self.content}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> Comment:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end, raw_text=data["text"])


@dataclass(frozen=True, slots=True, kw_only=True)
class BuiltinVariable(Node):
    """A ``$``-prefixed builtin variable reference (e.g. ``$pc``, ``$encoding``).

    Ruby's ``BuiltinVariableAst``.
    """

    kind: ClassVar[str] = "builtin_var_expr"

    name: str

    @property
    def text(self) -> str:
        return self.name

    def to_idl(self) -> str:
        return self.name

    def _to_h_fields(self) -> dict[str, Any]:
        return {"name": self.name}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> BuiltinVariable:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end, name=data["name"])


@dataclass(frozen=True, slots=True, kw_only=True)
class UserTypeName(Node):
    """A user-defined type name reference (enum/bitfield/struct name); Ruby's ``UserTypeNameAst``."""

    kind: ClassVar[str] = "user_type_reference"

    name: str

    @property
    def text(self) -> str:
        return self.name

    def to_idl(self) -> str:
        return self.name

    def _to_h_fields(self) -> dict[str, Any]:
        return {"name": self.name}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> UserTypeName:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end, name=data["name"])


_BUILTIN_TYPE_NAMES = ("XReg", "Bits", "Boolean", "String", "U32", "U64")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuiltinTypeName(Node):
    """A builtin type name (``XReg``, ``Bits<...>``, ``Boolean``, ``String``, ``U32``, ``U64``).

    Ruby's ``BuiltinTypeNameAst``. ``kind`` is ``"bits_type"`` for ``Bits<...>``
    (whose single child is the width expression) and ``"builtin_type"`` for
    every other builtin type name (no children).

    This is also the Python stand-in for Ruby's ``TypeNameAst`` Sorbet type
    alias (``T.any(UserTypeNameAst, BuiltinTypeNameAst)``): code needing
    "either kind of type name" should annotate with ``UserTypeName | BuiltinTypeName``.
    """

    kind: ClassVar[str] = "builtin_type"

    type_name: str

    @property
    def bits_expression(self) -> Node | None:
        return self.children[0] if self.children else None

    def to_idl(self) -> str:
        if self.type_name == "Bits":
            assert self.bits_expression is not None
            return f"Bits<{self.bits_expression.to_idl()}>"
        return self.type_name

    def to_h(self) -> dict[str, Any]:
        if self.type_name == "Bits":
            assert self.bits_expression is not None
            return {
                "kind": "bits_type",
                "width_expr": self.bits_expression.to_h(),
                "source": self.source.source_dict(self.start, self.end),
            }
        return {
            "kind": "builtin_type",
            "type": self.type_name,
            "source": self.source.source_dict(self.start, self.end),
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> BuiltinTypeName:
        kind = data.get("kind")
        if kind == "bits_type":
            source, start, end = _source_and_span(data, sources)
            width_expr = from_h(data["width_expr"], sources)
            return cls(
                source=source, start=start, end=end, children=(width_expr,), type_name="Bits"
            )
        if kind == "builtin_type":
            source, start, end = _source_and_span(data, sources)
            return cls(source=source, start=start, end=end, type_name=data["type"])
        raise ValueError(f"Bad YAML: expected kind 'bits_type' or 'builtin_type', got {kind!r}")


@dataclass(frozen=True, slots=True, kw_only=True)
class DontCareReturn(Node):
    """The ``-`` "don't care" return-value placeholder; Ruby's ``DontCareReturnAst``."""

    kind: ClassVar[str] = "dont_care"

    def to_idl(self) -> str:
        return "-"

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> DontCareReturn:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end)


@dataclass(frozen=True, slots=True, kw_only=True)
class DontCareLvalue(Node):
    """The ``-`` "don't care" assignment-target placeholder; Ruby's ``DontCareLvalueAst``."""

    kind: ClassVar[str] = "dont_care_lval"

    def to_idl(self) -> str:
        return "-"

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> DontCareLvalue:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end)


@dataclass(frozen=True, slots=True, kw_only=True)
class EnumRef(Node):
    """An ``EnumClass::member`` reference; Ruby's ``EnumRefAst``."""

    kind: ClassVar[str] = "enum_reference_expr"

    class_name: str
    member_name: str

    def to_idl(self) -> str:
        return f"{self.class_name}::{self.member_name}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"enum_class": self.class_name, "member_name": self.member_name}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> EnumRef:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return cls(
            source=source,
            start=start,
            end=end,
            class_name=data["enum_class"],
            member_name=data["member_name"],
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Noop(Node):
    """A synthetic empty expression; Ruby's ``NoopAst``.

    Never produced by parsing real source (it is a synthetic placeholder used
    internally by lowering); ``from_h`` ignores everything but the kind and
    always returns a fresh synthetic instance, matching Ruby.
    """

    kind: ClassVar[str] = "noop_expr"

    def to_idl(self) -> str:
        return ""

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> Noop:
        _check_kind(data, cls.kind)
        return cls(source=IdlSource(text="", label="<synthetic>"), start=0, end=0)


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# CSR expressions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class CsrReadExpression(Node):
    """A ``CSR[name]`` read expression; Ruby's ``CsrReadExpressionAst``."""

    kind: ClassVar[str] = "csr_read_expr"

    csr_name: str

    def to_idl(self) -> str:
        return f"CSR[{self.csr_name}]"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"csr_name": self.csr_name}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> CsrReadExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end, csr_name=data["csr_name"])


@dataclass(frozen=True, slots=True, kw_only=True)
class CsrWrite(Node):
    """A ``CSR[name_or_address_expr]`` write-target expression; Ruby's ``CsrWriteAst``."""

    kind: ClassVar[str] = "csr_access_expr"

    @property
    def idx(self) -> Node:
        return self.children[0]

    def to_idl(self) -> str:
        return f"CSR[{self.idx.text}]"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"csr_name_or_address_expr": self.idx.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> CsrWrite:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        idx = from_h(data["csr_name_or_address_expr"], sources)
        return cls(source=source, start=start, end=end, children=(idx,))


@dataclass(frozen=True, slots=True, kw_only=True)
class CsrFieldReadExpression(Node):
    """A ``CSR[name].field`` read expression; Ruby's ``CsrFieldReadExpressionAst``."""

    kind: ClassVar[str] = "csr_field_read_expr"

    field_name: str

    @property
    def csr(self) -> CsrReadExpression:
        return self.children[0]  # type: ignore[return-value]

    def to_idl(self) -> str:
        return f"{self.csr.to_idl()}.{self.field_name}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"csr": self.csr.to_h(), "field_name": self.field_name}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> CsrFieldReadExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        csr = from_h(data["csr"], sources)
        return cls(
            source=source, start=start, end=end, children=(csr,), field_name=data["field_name"]
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class CsrSoftwareWrite(Node):
    """A ``CSR[name].sw_write(value)`` expression; Ruby's ``CsrSoftwareWriteAst``."""

    kind: ClassVar[str] = "csr_sw_write_expr"

    @property
    def csr(self) -> Node:
        return self.children[0]

    @property
    def expression(self) -> Node:
        return self.children[1]

    def to_idl(self) -> str:
        return f"{self.csr.to_idl()}.sw_write({self.expression.to_idl()})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"csr": self.csr.to_h(), "value": self.expression.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> CsrSoftwareWrite:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        csr = from_h(data["csr"], sources)
        expr = from_h(data["value"], sources)
        return cls(source=source, start=start, end=end, children=(csr, expr))


@dataclass(frozen=True, slots=True, kw_only=True)
class CsrFunctionCall(Node):
    """A ``CSR[name].function(args)`` expression; Ruby's ``CsrFunctionCallAst``."""

    kind: ClassVar[str] = "csr_funcall_expr"

    function_name: str

    @property
    def csr(self) -> Node:
        return self.children[0]

    @property
    def args(self) -> tuple[Node, ...]:
        return self.children[1:]

    def to_idl(self) -> str:
        return f"{self.csr.to_idl()}.{self.function_name}({_idl_join(self.args)})"

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "csr": self.csr.to_h(),
            "function_name": self.function_name,
            "arguments": [a.to_h() for a in self.args],
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> CsrFunctionCall:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        csr = from_h(data["csr"], sources)
        args = tuple(from_h(a, sources) for a in data["arguments"])
        return cls(
            source=source,
            start=start,
            end=end,
            children=(csr, *args),
            function_name=data["function_name"],
        )


# ---------------------------------------------------------------------------
# ``$``-builtin expressions
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class Statement(Node):
    """An unconditional statement (``action;``); Ruby's ``StatementAst``.

    Shares ``kind = "stmt"`` with :class:`ReturnStatement`; the module-level
    :func:`from_h` disambiguates by inspecting the nested ``"expr"``'s kind.
    """

    kind: ClassVar[str] = "stmt"

    @property
    def action(self) -> Node:
        return self.children[0]

    def to_idl(self) -> str:
        return f"{self.action.to_idl()};"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"expr": self.action.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> Statement:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        action = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(action,))


@dataclass(frozen=True, slots=True, kw_only=True)
class ConditionalStatement(Node):
    """A conditionally-executed statement (``action if (condition);``).

    Ruby's ``ConditionalStatementAst``; shares ``kind = "conditional_stmt"``
    with :class:`ConditionalReturnStatement`, disambiguated the same way as
    :class:`Statement`/:class:`ReturnStatement`.
    """

    kind: ClassVar[str] = "conditional_stmt"

    @property
    def action(self) -> Node:
        return self.children[0]

    @property
    def condition(self) -> Node:
        return self.children[1]

    def to_idl(self) -> str:
        return f"{self.action.to_idl()} if ({self.condition.to_idl()});"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"condition": self.condition.to_h(), "expr": self.action.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ConditionalStatement:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        action = from_h(data["expr"], sources)
        condition = from_h(data["condition"], sources)
        return cls(source=source, start=start, end=end, children=(action, condition))


@dataclass(frozen=True, slots=True, kw_only=True)
class ReturnExpression(Node):
    """The (possibly multi-valued) expression list of a ``return``; Ruby's ``ReturnExpressionAst``."""

    kind: ClassVar[str] = "return_expr"

    @property
    def return_value_nodes(self) -> tuple[Node, ...]:
        return self.children

    def to_idl(self) -> str:
        return f"return {_idl_join(self.children, sep=',')}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"exprs": [c.to_h() for c in self.children]}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ReturnExpression:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        exprs = tuple(from_h(e, sources) for e in data["exprs"])
        return cls(source=source, start=start, end=end, children=exprs)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReturnStatement(Node):
    """A ``return ...;`` statement; Ruby's ``ReturnStatementAst``.

    Shares ``kind = "stmt"`` with :class:`Statement`.
    """

    kind: ClassVar[str] = "stmt"

    @property
    def return_expression(self) -> ReturnExpression:
        return self.children[0]  # type: ignore[return-value]

    def to_idl(self) -> str:
        return f"{self.return_expression.to_idl()};"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"expr": self.return_expression.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ReturnStatement:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return_expression = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(return_expression,))


@dataclass(frozen=True, slots=True, kw_only=True)
class ConditionalReturnStatement(Node):
    """A conditionally-executed ``return`` (``return ... if (condition);``).

    Ruby's ``ConditionalReturnStatementAst``; shares ``kind = "conditional_stmt"``
    with :class:`ConditionalStatement`.
    """

    kind: ClassVar[str] = "conditional_stmt"

    @property
    def return_expression(self) -> ReturnExpression:
        return self.children[0]  # type: ignore[return-value]

    @property
    def condition(self) -> Node:
        return self.children[1]

    def to_idl(self) -> str:
        return f"{self.return_expression.to_idl()} if ({self.condition.to_idl()});"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"condition": self.condition.to_h(), "expr": self.return_expression.to_h()}

    @classmethod
    def from_h(
        cls, data: Mapping[str, Any], sources: Mapping[str, str]
    ) -> ConditionalReturnStatement:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return_expression = from_h(data["expr"], sources)
        condition = from_h(data["condition"], sources)
        return cls(source=source, start=start, end=end, children=(return_expression, condition))


@dataclass(frozen=True, slots=True, kw_only=True)
class ImplicationStatement(Node):
    """A top-level implication statement inside a ``constraint_body``.

    Ruby's ``ImplicationStatementAst``. Note: Ruby's own ``from_h`` for this
    class checks for ``kind == "implication_expr"``, but real ``to_h`` output
    always has ``kind == "implication_stmt"`` -- so Ruby's ``from_h`` can
    never actually succeed on real output (it always raises immediately).
    Python's :meth:`from_h` is not buggy: it correctly reconstructs this node
    from ``kind == "implication_stmt"``.
    """

    kind: ClassVar[str] = "implication_stmt"

    @property
    def expression(self) -> ImplicationExpression:
        return self.children[0]  # type: ignore[return-value]

    def to_idl(self) -> str:
        return f"{self.expression.to_idl()};"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"expr": self.expression.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ImplicationStatement:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        expression = from_h(data["expr"], sources)
        return cls(source=source, start=start, end=end, children=(expression,))


@dataclass(frozen=True, slots=True, kw_only=True)
class IfBody(Node):
    """The statement list of an ``if``/``else if``/``else`` block body.

    Ruby's ``IfBodyAst``. When empty, this is always a synthetic zero-width
    node (Ruby forces ``super("", 0...0, [])`` in that case), matching the
    convention used by :class:`Noop`.
    """

    kind: ClassVar[str] = "if_body"

    @property
    def stmts(self) -> tuple[Node, ...]:
        return self.children

    def to_idl(self) -> str:
        return "".join(s.to_idl() for s in self.children)

    def _to_h_fields(self) -> dict[str, Any]:
        return {"stmts": [c.to_h() for c in self.children]}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> IfBody:
        _check_kind(data, cls.kind)
        stmts = tuple(from_h(s, sources) for s in data["stmts"])
        if not stmts:
            return cls(source=IdlSource(text="", label="<synthetic>"), start=0, end=0, children=())
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end, children=stmts)


@dataclass(frozen=True, slots=True, kw_only=True)
class ElseIf(Node):
    """An ``else if (condition) { body }`` clause; Ruby's ``ElseIfAst``."""

    kind: ClassVar[str] = "else_if_stmt"

    @property
    def condition(self) -> Node:
        return self.children[0]

    @property
    def body(self) -> IfBody:
        return self.children[1]  # type: ignore[return-value]

    def to_idl(self) -> str:
        return f" else if ({self.condition.to_idl()}) {{ {self.body.to_idl()} }}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"condition": self.condition.to_h(), "body": self.body.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ElseIf:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        condition = from_h(data["condition"], sources)
        body = from_h(data["body"], sources)
        return cls(source=source, start=start, end=end, children=(condition, body))


@dataclass(frozen=True, slots=True, kw_only=True)
class If(Node):
    """An ``if``/``else if``/``else`` statement; Ruby's ``IfAst``."""

    kind: ClassVar[str] = "if_stmt"

    @property
    def if_cond(self) -> Node:
        return self.children[0]

    @property
    def if_body(self) -> IfBody:
        return self.children[1]  # type: ignore[return-value]

    @property
    def elseifs(self) -> tuple[ElseIf, ...]:
        return self.children[2:-1]  # type: ignore[return-value]

    @property
    def final_else_body(self) -> IfBody:
        return self.children[-1]  # type: ignore[return-value]

    def to_idl(self) -> str:
        result = f"if ({self.if_cond.to_idl()}) {{ "
        result += self.if_body.to_idl()
        result += "} "
        for elseif in self.elseifs:
            result += elseif.to_idl()
        if self.final_else_body.stmts:
            result += " else { "
            result += self.final_else_body.to_idl()
            result += "} "
        return result

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "condition": self.if_cond.to_h(),
            "taken_body": self.if_body.to_h(),
            "else_ifs": [e.to_h() for e in self.elseifs],
            "else": self.final_else_body.to_h() if self.final_else_body.stmts else None,
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> If:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        if_cond = from_h(data["condition"], sources)
        if_body = from_h(data["taken_body"], sources)
        elseifs = tuple(from_h(e, sources) for e in data["else_ifs"])
        else_data = data["else"]
        final_else_body = (
            from_h(else_data, sources)
            if else_data is not None
            else IfBody(source=IdlSource(text="", label="<synthetic>"), start=0, end=0, children=())
        )
        return cls(
            source=source,
            start=start,
            end=end,
            children=(if_cond, if_body, *elseifs, final_else_body),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ForLoop(Node):
    """A ``for (init; condition; update) { stmts }`` loop; Ruby's ``ForLoopAst``."""

    kind: ClassVar[str] = "for_loop_stmt"

    @property
    def init(self) -> Node:
        return self.children[0]

    @property
    def condition(self) -> Node:
        return self.children[1]

    @property
    def update(self) -> Node:
        return self.children[2]

    @property
    def stmts(self) -> tuple[Node, ...]:
        return self.children[3:]

    def to_idl(self) -> str:
        idl = f"for ({self.init.to_idl()}; {self.condition.to_idl()}; {self.update.to_idl()}) {{"
        idl += "".join(s.to_idl() for s in self.stmts)
        idl += "}"
        return idl

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "init_expr": self.init.to_h(),
            "condition_expr": self.condition.to_h(),
            "update_expr": self.update.to_h(),
            "body": [s.to_h() for s in self.stmts],
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ForLoop:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        init = from_h(data["init_expr"], sources)
        condition = from_h(data["condition_expr"], sources)
        update = from_h(data["update_expr"], sources)
        stmts = tuple(from_h(s, sources) for s in data["body"])
        return cls(source=source, start=start, end=end, children=(init, condition, update, *stmts))


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class PcAssignment(Node):
    """``$pc = value``; Ruby's ``PcAssignmentAst``."""

    kind: ClassVar[str] = "pc_assignment"

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


# ---------------------------------------------------------------------------
# Declarations and definitions
# ---------------------------------------------------------------------------


def _wrap_array_decl_type(type_name: Node, ary_size: Node | None) -> dict[str, Any]:
    if ary_size is None:
        return type_name.to_h()
    return {"kind": "array_decl", "array_size": ary_size.to_h(), "element_type": type_name.to_h()}


def _unwrap_array_decl_type(
    data: Mapping[str, Any], sources: Mapping[str, str]
) -> tuple[Node, Node | None]:
    if data.get("kind") == "array_decl":
        return from_h(data["element_type"], sources), from_h(data["array_size"], sources)
    return from_h(data, sources), None


@dataclass(frozen=True, slots=True, kw_only=True)
class VariableDeclaration(Node):
    """A variable declaration without initialization (``type name;`` or ``type name[size];``).

    Ruby's ``VariableDeclarationAst``.
    """

    kind: ClassVar[str] = "var_decl"

    @property
    def type_name(self) -> Node:
        return self.children[0]

    @property
    def id(self) -> Id:
        return self.children[1]  # type: ignore[return-value]

    @property
    def ary_size(self) -> Node | None:
        return self.children[2] if len(self.children) > 2 else None

    def to_idl(self) -> str:
        if self.ary_size is None:
            return f"{self.type_name.to_idl()} {self.id.to_idl()}"
        return f"{self.type_name.to_idl()} {self.id.to_idl()}[{self.ary_size.to_idl()}]"

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "type": _wrap_array_decl_type(self.type_name, self.ary_size),
            "name": self.id.to_h(),
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> VariableDeclaration:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        type_name, ary_size = _unwrap_array_decl_type(data["type"], sources)
        id_node = from_h(data["name"], sources)
        children = (type_name, id_node) + ((ary_size,) if ary_size is not None else ())
        return cls(source=source, start=start, end=end, children=children)


@dataclass(frozen=True, slots=True, kw_only=True)
class VariableDeclarationWithInitialization(Node):
    """A variable declaration with initialization (``type name = rhs;``).

    Ruby's ``VariableDeclarationWithInitializationAst``. Note the array-size
    child, when present, is the *last* child here (unlike plain
    :class:`VariableDeclaration`, where it is the third).
    """

    kind: ClassVar[str] = "var_decl_init"

    for_iter_var: bool = False

    @property
    def type_name(self) -> Node:
        return self.children[0]

    @property
    def lhs(self) -> Id:
        return self.children[1]  # type: ignore[return-value]

    @property
    def rhs(self) -> Node:
        return self.children[2]

    @property
    def ary_size(self) -> Node | None:
        return self.children[3] if len(self.children) > 3 else None

    def to_idl(self) -> str:
        if self.ary_size is None:
            return f"{self.type_name.to_idl()} {self.lhs.to_idl()} = {self.rhs.to_idl()}"
        return f"{self.type_name.to_idl()} {self.lhs.to_idl()}[{self.ary_size.to_idl()}] = {self.rhs.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "type": _wrap_array_decl_type(self.type_name, self.ary_size),
            "name": self.lhs.to_h(),
            "value": self.rhs.to_h(),
            "in_for_loop": self.for_iter_var,
        }

    @classmethod
    def from_h(
        cls, data: Mapping[str, Any], sources: Mapping[str, str]
    ) -> VariableDeclarationWithInitialization:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        type_name, ary_size = _unwrap_array_decl_type(data["type"], sources)
        lhs = from_h(data["name"], sources)
        rhs = from_h(data["value"], sources)
        children = (type_name, lhs, rhs) + ((ary_size,) if ary_size is not None else ())
        return cls(
            source=source, start=start, end=end, children=children, for_iter_var=data["in_for_loop"]
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class MultiVariableDeclaration(Node):
    """``type name1, name2, ...;`` (declaring several variables of one type at once).

    Ruby's ``MultiVariableDeclarationAst``.
    """

    kind: ClassVar[str] = "multi_var_decl"

    @property
    def type_name(self) -> Node:
        return self.children[0]

    @property
    def var_names(self) -> tuple[Id, ...]:
        return self.children[1:]  # type: ignore[return-value]

    def to_idl(self) -> str:
        return f"{self.type_name.to_idl()} {_idl_join(self.var_names)}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"names": [n.to_h() for n in self.var_names], "type": self.type_name.to_h()}

    @classmethod
    def from_h(
        cls, data: Mapping[str, Any], sources: Mapping[str, str]
    ) -> MultiVariableDeclaration:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        type_name = from_h(data["type"], sources)
        names = tuple(from_h(n, sources) for n in data["names"])
        return cls(source=source, start=start, end=end, children=(type_name, *names))


@dataclass(frozen=True, slots=True, kw_only=True)
class Global(Node):
    """A ``global`` (file-scope) variable declaration; Ruby's ``GlobalAst``."""

    kind: ClassVar[str] = "global_var_decl"

    @property
    def declaration(self) -> VariableDeclaration:
        return self.children[0]  # type: ignore[return-value]

    def to_idl(self) -> str:
        return self.declaration.to_idl()

    def _to_h_fields(self) -> dict[str, Any]:
        return {"decl": self.declaration.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> Global:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        declaration = from_h(data["decl"], sources)
        return cls(source=source, start=start, end=end, children=(declaration,))


@dataclass(frozen=True, slots=True, kw_only=True)
class GlobalWithInitialization(Node):
    """A ``global`` (file-scope) variable declaration with initialization.

    Ruby's ``GlobalWithInitializationAst``.
    """

    kind: ClassVar[str] = "global_var_decl_with_init"

    @property
    def var_decl_with_init(self) -> VariableDeclarationWithInitialization:
        return self.children[0]  # type: ignore[return-value]

    def to_idl(self) -> str:
        return self.var_decl_with_init.to_idl()

    def _to_h_fields(self) -> dict[str, Any]:
        return {"decl": self.var_decl_with_init.to_h()}

    @classmethod
    def from_h(
        cls, data: Mapping[str, Any], sources: Mapping[str, str]
    ) -> GlobalWithInitialization:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        var_decl_with_init = from_h(data["decl"], sources)
        return cls(source=source, start=start, end=end, children=(var_decl_with_init,))


@dataclass(frozen=True, slots=True, kw_only=True)
class FunctionDef(Node):
    """A function definition; Ruby's ``FunctionDefAst``.

    ``qualifier`` is one of ``"normal"``, ``"builtin"``, ``"generated"``,
    ``"external"``. ``children = return_types + arguments (+ [body] if
    present)``; ``num_return_types``/``num_arguments`` record the split
    points (``body`` is builtin-and-generated functions' absence, so it
    cannot be inferred purely from ``len(children)``).
    """

    kind: ClassVar[str] = "function_decl"

    name: str
    qualifier: str
    description: str
    num_return_types: int
    num_arguments: int

    @property
    def return_types(self) -> tuple[Node, ...]:
        return self.children[: self.num_return_types]

    @property
    def arguments(self) -> tuple[Node, ...]:
        end = self.num_return_types + self.num_arguments
        return self.children[self.num_return_types : end]

    @property
    def body(self) -> FunctionBody | None:
        idx = self.num_return_types + self.num_arguments
        return self.children[idx] if len(self.children) > idx else None  # type: ignore[return-value]

    @property
    def builtin(self) -> bool:
        return self.qualifier == "builtin"

    @property
    def generated(self) -> bool:
        return self.qualifier == "generated"

    @property
    def external(self) -> bool:
        return self.qualifier == "external"

    def to_idl(self) -> str:
        returns_idl = f"returns {_idl_join(self.return_types)}" if self.return_types else ""
        args_idl = f"arguments {_idl_join(self.arguments)}" if self.arguments else ""
        qualifier = "" if self.qualifier == "normal" else self.qualifier
        body_idl = "" if self.builtin or self.generated else f"body {{ {self.body.to_idl()} }}"
        return (
            f"{qualifier} function {self.name} {{\n"
            f"  {returns_idl}\n"
            f"  {args_idl}\n"
            f"  description {{ {self.description} }}\n"
            f"  {body_idl}\n"
            "}\n"
        )

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "qualifier": self.qualifier,
            "return_types": [r.to_h() for r in self.return_types],
            "arguments": [a.to_h() for a in self.arguments],
            "description": self.description,
            "body": None if self.body is None else self.body.to_h(),
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> FunctionDef:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return_types = tuple(from_h(r, sources) for r in data["return_types"])
        arguments = tuple(from_h(a, sources) for a in data["arguments"])
        body_data = data["body"]
        body = None if body_data is None else from_h(body_data, sources)
        children = return_types + arguments + ((body,) if body is not None else ())
        return cls(
            source=source,
            start=start,
            end=end,
            children=children,
            name=data["name"],
            qualifier=data["qualifier"],
            description=data["description"],
            num_return_types=len(return_types),
            num_arguments=len(arguments),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EnumDefinition(Node):
    """An ``enum`` definition; Ruby's ``EnumDefinitionAst``.

    ``element_values[i]`` is ``None`` for auto-numbered members (Ruby assigns
    ``next_auto_value`` to those at construction time; :meth:`to_idl` mirrors
    that auto-numbering for round-trip purposes, but this is not part of
    ``to_h``, which just serializes each member's raw AST node or ``None``).
    """

    kind: ClassVar[str] = "enum_decl"

    user_type: UserTypeName
    element_names: tuple[UserTypeName, ...]
    element_values: tuple[IntLiteral | None, ...]

    @property
    def name(self) -> str:
        return self.user_type.name

    def _resolved_values(self) -> tuple[int, ...]:
        values: list[int] = []
        next_auto = 0
        for v in self.element_values:
            resolved = next_auto if v is None else v.unsigned_value()
            assert isinstance(resolved, int)
            values.append(resolved)
            next_auto = resolved + 1
        return tuple(values)

    def to_idl(self) -> str:
        resolved = self._resolved_values()
        members = "".join(f"{n.to_idl()} {v} " for n, v in zip(self.element_names, resolved))
        return f"enum {self.name} {{ {members}}}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "enum_class_name": self.user_type.to_h(),
            "members": [
                {"name": n.to_h(), "value": None if v is None else v.to_h()}
                for n, v in zip(self.element_names, self.element_values)
            ],
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> EnumDefinition:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        user_type = from_h(data["enum_class_name"], sources)
        members = data["members"]
        element_names = tuple(from_h(m["name"], sources) for m in members)
        element_values = tuple(
            from_h(m["value"], sources) if m.get("value") is not None else None for m in members
        )
        children = (user_type, *element_names, *(v for v in element_values if v is not None))
        return cls(
            source=source,
            start=start,
            end=end,
            children=children,
            user_type=user_type,
            element_names=element_names,
            element_values=element_values,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BuiltinEnumDefinition(Node):
    """A ``builtin enum`` definition; Ruby's ``BuiltinEnumDefinitionAst``."""

    kind: ClassVar[str] = "builtin_enum_decl"

    @property
    def user_type(self) -> UserTypeName:
        return self.children[0]  # type: ignore[return-value]

    def to_idl(self) -> str:
        return f"generated enum {self.user_type.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"name": self.user_type.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> BuiltinEnumDefinition:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        user_type = from_h(data["name"], sources)
        return cls(source=source, start=start, end=end, children=(user_type,))


@dataclass(frozen=True, slots=True, kw_only=True)
class BitfieldFieldDefinition(Node):
    """One ``name msb[-lsb]`` field of a ``bitfield`` definition.

    Ruby's ``BitfieldFieldDefinitionAst``.
    """

    kind: ClassVar[str] = "bitfield_field_decl"

    field_name: str

    @property
    def msb(self) -> Node:
        return self.children[0]

    @property
    def lsb(self) -> Node | None:
        return self.children[1] if len(self.children) > 1 else None

    def to_idl(self) -> str:
        if self.lsb is None:
            return f"{self.field_name} {self.msb.to_idl()}"
        return f"{self.field_name} {self.msb.to_idl()}-{self.lsb.to_idl()}"

    def _to_h_fields(self) -> dict[str, Any]:
        lsb_h = self.msb.to_h() if self.lsb is None else self.lsb.to_h()
        return {"name": self.field_name, "range": {"lsb": lsb_h, "msb": self.msb.to_h()}}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> BitfieldFieldDefinition:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        msb = from_h(data["range"]["msb"], sources)
        lsb = from_h(data["range"]["lsb"], sources)
        return cls(
            source=source, start=start, end=end, children=(msb, lsb), field_name=data["name"]
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BitfieldDefinition(Node):
    """A ``bitfield`` definition; Ruby's ``BitfieldDefinitionAst``."""

    kind: ClassVar[str] = "bitfield_decl"

    @property
    def name_node(self) -> UserTypeName | BuiltinTypeName:
        return self.children[0]  # type: ignore[return-value]

    @property
    def size(self) -> IntLiteral:
        return self.children[1]  # type: ignore[return-value]

    @property
    def bitfield_fields(self) -> tuple[BitfieldFieldDefinition, ...]:
        return self.children[2:]  # type: ignore[return-value]

    @property
    def name(self) -> str:
        return self.name_node.text

    def to_idl(self) -> str:
        parts = [f"bitfield ({self.size.to_idl()}) {self.name_node.to_idl()} {{ "]
        parts.extend(f.to_idl() for f in self.bitfield_fields)
        parts.append("}")
        return "\n".join(parts)

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "name": self.name_node.to_h(),
            "size": self.size.to_h(),
            "fields": [f.to_h() for f in self.bitfield_fields],
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> BitfieldDefinition:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        name_node = from_h(data["name"], sources)
        size = from_h(data["size"], sources)
        fields = tuple(from_h(f, sources) for f in data["fields"])
        return cls(source=source, start=start, end=end, children=(name_node, size, *fields))


@dataclass(frozen=True, slots=True, kw_only=True)
class StructDefinition(Node):
    """A ``struct`` definition; Ruby's ``StructDefinitionAst``.

    Unlike every other definition node, ``name`` and each member's name are
    bare Python strings, not child nodes (mirroring Ruby, where they are
    plain ``String`` attributes, not part of ``children``).
    """

    kind: ClassVar[str] = "struct_decl"

    name: str
    member_names: tuple[str, ...]

    @property
    def member_types(self) -> tuple[Node, ...]:
        return self.children

    def to_idl(self) -> str:
        members = "; ".join(
            f"{t.to_idl()} {n}" for t, n in zip(self.member_types, self.member_names)
        )
        return f"struct {self.name} {{ {members}; }}"

    def _to_h_fields(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "members": [
                {"name": n, "type": t.to_h()} for n, t in zip(self.member_names, self.member_types)
            ],
        }

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> StructDefinition:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        members = data["members"]
        member_types = tuple(from_h(m["type"], sources) for m in members)
        member_names = tuple(m["name"] for m in members)
        return cls(
            source=source,
            start=start,
            end=end,
            children=member_types,
            name=data["name"],
            member_names=member_names,
        )


# ---------------------------------------------------------------------------
# Top-level nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class FunctionBody(Node):
    """A function/instruction-operation body (a statement list); Ruby's ``FunctionBodyAst``.

    This is the AST produced by both the ``function_body`` root and the
    ``instruction_operation`` root (Ruby has no separate
    ``InstructionOperationAst`` class -- both grammar rules lower to
    ``FunctionBodyAst``).
    """

    kind: ClassVar[str] = "function_body"

    @property
    def stmts(self) -> tuple[Node, ...]:
        return self.children

    def to_idl(self) -> str:
        return "\n".join(s.to_idl() for s in self.children)

    def _to_h_fields(self) -> dict[str, Any]:
        return {"stmts": [c.to_h() for c in self.children]}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> FunctionBody:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        stmts = tuple(from_h(s, sources) for s in data["stmts"])
        return cls(source=source, start=start, end=end, children=stmts)


@dataclass(frozen=True, slots=True, kw_only=True)
class ConstraintBody(Node):
    """A ``constraint_body`` root's statement list (``ImplicationStatement``/``ForLoop`` mix).

    Ruby's ``ConstraintBodyAst``.
    """

    kind: ClassVar[str] = "constraint_body"

    @property
    def stmts(self) -> tuple[Node, ...]:
        return self.children

    def to_idl(self) -> str:
        return "\n".join(s.to_idl() for s in self.children)

    def _to_h_fields(self) -> dict[str, Any]:
        return {"stmts": [c.to_h() for c in self.children]}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> ConstraintBody:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        stmts = tuple(from_h(s, sources) for s in data["stmts"])
        return cls(source=source, start=start, end=end, children=stmts)


@dataclass(frozen=True, slots=True, kw_only=True)
class Fetch(Node):
    """A top-level ``fetch { ... }`` block; Ruby's ``FetchAst``."""

    kind: ClassVar[str] = "fetch_decl"

    @property
    def body(self) -> FunctionBody:
        return self.children[0]  # type: ignore[return-value]

    def to_idl(self) -> str:
        return f"fetch {{\n  {self.body.to_idl()}\n}}\n"

    def _to_h_fields(self) -> dict[str, Any]:
        return {"function_body": self.body.to_h()}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> Fetch:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        body = from_h(data["function_body"], sources)
        return cls(source=source, start=start, end=end, children=(body,))


@dataclass(frozen=True, slots=True, kw_only=True)
class IncludeStatement(Node):
    """An ``include "filename"`` statement; Ruby's ``IncludeStatementAst``.

    The single child is a full :class:`StringLiteral` (the grammar's
    ``include_statement`` rule reuses the ``string`` sub-rule).

    Ruby's own ``IncludeStatementAst#to_h`` unconditionally raises
    (``"unreachable"``), and ``IsaAst#to_h``/``IsaAst.from_h`` have no
    special-casing or dispatch branch for an ``include`` child at all --
    calling ``to_h`` on any real Ruby ``IsaAst`` containing an ``include``
    statement crashes, and there is no ``from_h`` support for it either.
    Python instead defines a real, bare ``{"kind": "include", "filename":
    ...}`` form (:meth:`to_h` is overridden to omit the usual ``"source"``
    key entirely, matching what independent black-box test fixtures expect),
    with :meth:`from_h` reconstructing a synthetic source on read since there
    is no Ruby contract to mirror.
    """

    kind: ClassVar[str] = "include"

    @property
    def string_literal(self) -> StringLiteral:
        return self.children[0]  # type: ignore[return-value]

    @property
    def filename(self) -> str:
        return self.string_literal.raw_text[1:-1]

    def to_idl(self) -> str:
        return f'include "{self.filename}"'

    def to_h(self) -> dict[str, Any]:
        return {"kind": self.kind, "filename": self.filename}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> IncludeStatement:
        _check_kind(data, cls.kind)
        filename = data["filename"]
        if data.get("source") is None:
            text = f'include "{filename}"'
            source = IdlSource(text=text, label="<synthetic>")
            start, end = 0, len(text)
        else:
            source, start, end = _source_and_span(data, sources)
        string_literal = StringLiteral(
            source=source, start=start, end=end, raw_text=f'"{filename}"'
        )
        return cls(source=source, start=start, end=end, children=(string_literal,))


@dataclass(frozen=True, slots=True, kw_only=True)
class Isa(Node):
    """The top-level ``isa`` root: a whole IDL file's list of definitions.

    Ruby's ``IsaAst``. Whitespace-only definitions are dropped by
    ``IsaSyntaxNode#to_ast`` before construction, so ``children`` here is
    already just the real top-level definitions.
    """

    kind: ClassVar[str] = "isa"

    @property
    def definitions(self) -> tuple[Node, ...]:
        return self.children

    def to_idl(self) -> str:
        globals_ = tuple(
            d for d in self.definitions if isinstance(d, (GlobalWithInitialization, Global))
        )
        enums = tuple(
            d for d in self.definitions if isinstance(d, (EnumDefinition, BuiltinEnumDefinition))
        )
        bitfields = tuple(d for d in self.definitions if isinstance(d, BitfieldDefinition))
        structs = tuple(d for d in self.definitions if isinstance(d, StructDefinition))
        functions = tuple(d for d in self.definitions if isinstance(d, FunctionDef))
        fetch = next(d for d in self.definitions if isinstance(d, Fetch))
        return (
            "%version 1.0\n\n"
            f"{_idl_join(globals_, sep='\n')}\n"
            f"{_idl_join(enums, sep='\n')}\n"
            f"{_idl_join(bitfields, sep='\n')}\n"
            f"{_idl_join(structs, sep='\n')}\n"
            f"{_idl_join(functions, sep='\n')}\n"
            f"{fetch.to_idl()}"
        )

    def _to_h_fields(self) -> dict[str, Any]:
        return {"children": [c.to_h() for c in self.children]}

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> Isa:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        children = tuple(from_h(c, sources) for c in data["children"])
        return cls(source=source, start=start, end=end, children=children)


@dataclass(frozen=True, slots=True, kw_only=True)
class ParseTimeDetectedTypeError(Node):
    """A parse-time-detected ``$``-builtin misuse (bad arg count/type, unknown builtin).

    Ruby's ``ParseTimeDetectedTypeError`` (note: unlike every other node
    class, this one keeps its un-suffixed Ruby name verbatim, since Ruby's
    class is *not* named ``ParseTimeDetectedTypeErrorAst``). Produced by
    lowering in place of e.g. ``WidthReveal``/``EnumSize``/etc. when a
    ``$``-builtin call has the wrong argument count or an invalid argument
    type. Ruby has no ``self.from_h`` entry for this kind at all (it is
    simply absent from the master dispatch table); Python adds one for
    completeness.
    """

    kind: ClassVar[str] = "ParseTimeDetectedTypeError"

    reason: str

    def to_idl(self) -> str:
        return self.text

    def _to_h_fields(self) -> dict[str, Any]:
        return {"reason": self.reason}

    @classmethod
    def from_h(
        cls, data: Mapping[str, Any], sources: Mapping[str, str]
    ) -> ParseTimeDetectedTypeError:
        _check_kind(data, cls.kind)
        source, start, end = _source_and_span(data, sources)
        return cls(source=source, start=start, end=end, reason=data["reason"])


# ---------------------------------------------------------------------------
# ``from_h`` dispatch
# ---------------------------------------------------------------------------

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
