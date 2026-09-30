# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Leaf nodes: identifiers, literals, and other childless expressions."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from ..errors import IdlValueUnknown
from ..source import IdlSource
from ..symbols import SymbolTable, Var
from ..types import (
    BITS32_TYPE,
    BITS64_TYPE,
    BOOL_TYPE,
    STRING_TYPE,
    WIDTH_UNKNOWN,
    EnumerationType,
    Qualifier,
    Type,
    TypeKind,
)
from ._base import RESERVED_WORDS, Node, _check_kind, _source_and_span, from_h


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

    def const_eval(self, symtab: SymbolTable) -> bool:
        if self.const:
            return True
        var = symtab.get(self.name)
        assert isinstance(var, Var)
        return var.const_eval

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if self.name in RESERVED_WORDS:
            self.type_error(f"Cannot use reserved word '{self.name}' as variable name")
        if symtab.get(self.name) is None:
            self.type_error(f"no symbol named '{self.name}'")

    def type(self, symtab: SymbolTable) -> Type:
        # Not memoized: the same AST can be evaluated under different scopes.
        sym = symtab.get(self.name)
        if sym is None:
            self.type_error(f"Symbol '{self.name}' not found")
        if isinstance(sym, Type):
            return sym
        if isinstance(sym, Var):
            return sym.type
        self.internal_error("Unexpected object on the symbol table")

    def value(self, symtab: SymbolTable) -> Any:
        var = symtab.get(self.name)
        if var is None:
            self.type_error(f"Variable '{self.name}' was not found")
        if not isinstance(var, Var):
            self.internal_error("Unexpected object on the symbol table")
        if var.value is None:
            self.value_error(f"Value of '{self.name}' not known")
        return var.value

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

    def is_zero(self) -> bool:
        """Mirrors Ruby's ``UnknownLiteral#zero?`` (always ``False``)."""
        return False

    def __and__(self, other: int | UnknownLiteral) -> int | UnknownLiteral:
        if isinstance(other, UnknownLiteral):
            new_known = self.known_value & other.known_value
            new_mask = (
                (self.unknown_mask | other.unknown_mask)
                & ~(~self.known_value & ~self.unknown_mask)
                & ~(~other.known_value & ~other.unknown_mask)
            )
        else:
            new_known = self.known_value & other
            new_mask = self.unknown_mask & other
        return (
            new_known
            if new_mask == 0
            else UnknownLiteral(known_value=new_known, unknown_mask=new_mask)
        )

    def __or__(self, other: int | UnknownLiteral) -> int | UnknownLiteral:
        if isinstance(other, UnknownLiteral):
            new_known = self.known_value | other.known_value
            new_mask = (
                (self.unknown_mask | other.unknown_mask)
                & ~(self.known_value & ~self.unknown_mask)
                & ~(other.known_value & ~other.unknown_mask)
            )
        else:
            new_known = self.known_value | other
            new_mask = self.unknown_mask & ~other
        return (
            new_known
            if new_mask == 0
            else UnknownLiteral(known_value=new_known, unknown_mask=new_mask)
        )

    def __lshift__(self, shamt: int) -> UnknownLiteral:
        return UnknownLiteral(
            known_value=self.known_value << shamt, unknown_mask=self.unknown_mask << shamt
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, UnknownLiteral):
            return (
                self.known_value & ~self.unknown_mask == other.known_value & ~other.unknown_mask
                and self.unknown_mask == other.unknown_mask
            )
        if isinstance(other, int):
            return self.known_value == other and self.unknown_mask == 0
        return NotImplemented

    def __le__(self, other: int | UnknownLiteral) -> bool:
        if self.unknown_mask != 0:
            raise IdlValueUnknown("unknown value")
        if isinstance(other, UnknownLiteral):
            if other.unknown_mask != 0:
                raise IdlValueUnknown("unknown value")
            return self.known_value <= other.known_value
        return self.known_value <= other


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

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

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

    def _width_for(self, symtab: SymbolTable | None) -> int | object:
        """Ruby's ``IntLiteralAst#width(symtab)``: the symtab-aware bit width.

        Distinct from the no-argument :meth:`width` (used by ``to_h``): this
        falls back to :data:`~udb.idl.types.WIDTH_UNKNOWN` when there is no
        explicit width and no known ``symtab.mxlen`` (``width()`` falls back
        to the string ``"unknown"`` for the same case; both are ports of two
        separately-written, intentionally-not-unified Ruby code paths).
        """
        cached = self._cache.get("_width_symtab")
        if cached is not None:
            return cached
        style, m = self._match()
        if style == "verilog":
            w = m.group(1)
            if w is None or w == "MXLEN":
                width: int | object = (
                    WIDTH_UNKNOWN if symtab is None or symtab.mxlen is None else symtab.mxlen
                )
            else:
                width = int(w)
        else:
            v = self.unsigned_value()
            assert isinstance(v, int)
            bit_length = v.bit_length() + 1 if self.signed() else v.bit_length()
            width = 1 if bit_length == 0 else bit_length
        self._cache["_width_symtab"] = width
        return width

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        style, m = self._match()
        if style != "verilog":
            return
        width_text = m.group(1)
        value_text = m.group(6)
        if width_text is None or width_text == "MXLEN":
            width = 32 if symtab.mxlen is None else symtab.mxlen
        else:
            width = int(width_text)
        uv = self.unsigned_value()
        if uv.bit_length() > width:
            self.type_error(f"{value_text} cannot be represented in {width} bits")

    def type(self, symtab: SymbolTable) -> Type:
        cached = self._cache.get("_type_symtab")
        if cached is not None:
            return cached
        style, m = self._match()
        if style == "verilog":
            signed = m.group(4) == "s"
            value_text = m.group(6)
            width = self._width_for(symtab)
            if width != WIDTH_UNKNOWN and not (isinstance(width, int) and width > 0):
                self.type_error(f"integer width must be positive (is {width})")
            qualifiers = [Qualifier.SIGNED, Qualifier.CONST] if signed else [Qualifier.CONST]
            # Ruby only checks lowercase ``x`` here (a confirmed bug, see
            # doc/python-migration-bugfixes.md); Python checks both cases,
            # matching ``unsigned_value``'s own case-insensitive handling.
            if "x" not in value_text.lower():
                qualifiers.append(Qualifier.KNOWN)
            if width == WIDTH_UNKNOWN:
                result = Type(TypeKind.BITS, width=width, max_width=64, qualifiers=qualifiers)
            else:
                result = Type(TypeKind.BITS, width=width, qualifiers=qualifiers)
        else:
            signed = (m.group(3) if style == "cpp" else m.group(2)) == "s"
            qualifiers = (
                [Qualifier.SIGNED, Qualifier.CONST, Qualifier.KNOWN]
                if signed
                else [Qualifier.CONST, Qualifier.KNOWN]
            )
            result = Type(TypeKind.BITS, width=self._width_for(symtab), qualifiers=qualifiers)
        self._cache["_type_symtab"] = result
        return result

    def value(self, symtab: SymbolTable) -> int | UnknownLiteral:
        cached = self._cache.get("_value_symtab")
        if cached is not None:
            return cached
        style, _m = self._match()
        uv = self.unsigned_value()
        if style != "verilog":
            self._cache["_value_symtab"] = uv
            return uv
        signed = self.signed()
        width = self._width_for(symtab)
        if width == WIDTH_UNKNOWN:
            # Ruby crashes here (``NoMethodError: undefined method '>'``) if
            # ``uv`` is an ``UnknownLiteral`` -- an unsized literal with x/X
            # bits (confirmed Ruby bug; see doc/python-migration-bugfixes.md).
            # Comparing against ``bit_length()`` gives an identical result
            # for plain integers and also works for ``UnknownLiteral``.
            bit_length = uv.bit_length()
            if signed:
                if bit_length > 31:
                    self.value_error("Don't know if value will be negative")
                if bit_length > 32:
                    self.value_error("Don't know if value will fit in literal")
            else:
                if bit_length > 32:
                    self.value_error("Don't know if value will fit in literal")
            v: int | UnknownLiteral = uv
        else:
            assert isinstance(width, int)
            if uv.bit_length() > width:
                self.value_error("Value does not fit in literal")
            if signed and isinstance(uv, int) and ((uv >> (width - 1)) & 1) == 1:
                # Ruby also checks ``unsigned_value.bit_length > (width - 1)``
                # here, but that is *always* true whenever the sign bit is
                # set (given the ``bit_length <= width`` guard just above),
                # so Ruby's ``value()`` never actually returns a negative
                # value for an explicit-width signed literal -- a confirmed
                # Ruby bug; Python computes the correct negative value.
                v = -(2**width - uv)
            elif signed and isinstance(uv, UnknownLiteral):
                # Ruby crashes here too (``>>`` undefined on ``UnknownLiteral``);
                # the sign bit genuinely can't be determined in general.
                self.value_error("Value is not fully known")
            else:
                v = uv
        self._cache["_value_symtab"] = v
        return v

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

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        pass

    def type(self, symtab: SymbolTable) -> Type:
        cached = self._cache.get("_type_symtab")
        if cached is not None:
            return cached
        result = Type(TypeKind.STRING, width=len(self.value(symtab)), qualifiers=(Qualifier.CONST,))
        self._cache["_type_symtab"] = result
        return result

    def value(self, symtab: SymbolTable) -> str:
        return self.content

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

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        pass

    def type(self, symtab: SymbolTable) -> Type:
        return BOOL_TYPE

    def value(self, symtab: SymbolTable) -> bool:
        return True

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

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        pass

    def type(self, symtab: SymbolTable) -> Type:
        return BOOL_TYPE

    def value(self, symtab: SymbolTable) -> bool:
        return False

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

    def const_eval(self, symtab: SymbolTable) -> bool:
        if self.name == "$encoding":
            return True
        if self.name == "$pc":
            return False
        self.internal_error("TODO")

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if self.name not in ("$pc", "$encoding"):
            self.type_error("Not a builtin variable")

    def type(self, symtab: SymbolTable) -> Type:
        if self.name == "$encoding":
            sz = symtab.get("__instruction_encoding_size")
            if sz is None:
                self.internal_error("Forgot to set __instruction_encoding_size")
            return Type(
                TypeKind.BITS,
                width=sz.value,
                qualifiers=frozenset({Qualifier.CONST, Qualifier.KNOWN}),
            )
        if self.name == "$pc":
            return Type(TypeKind.BITS, width=32 if symtab.mxlen == 32 else 64)
        self.internal_error(f"unhandled builtin variable {self.name}")

    def value(self, symtab: SymbolTable) -> Any:
        self.value_error("Cannot know the value of pc or encoding")

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

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if self.name in RESERVED_WORDS:
            self.type_error(f"Cannot use reserved word '{self.name}' as user-defined type name")
        t = self.type(symtab)
        if not isinstance(t, Type):
            self.type_error(f"{self.name} is not a type")

    def type(self, symtab: SymbolTable) -> Type:
        t = symtab.get(self.name)
        if t is None:
            self.type_error(f"Undefined user type: '{self.name}'")
        assert isinstance(t, Type)
        return t

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

    def const_eval(self, symtab: SymbolTable) -> bool:
        # Ruby's `const_eval?` compares `@type_name == "bits"` (lowercase), but
        # `@type_name` is always the grammar-cased "Bits"/"XReg"/etc., so that
        # comparison is always false and Ruby always returns `True` here, even
        # for `Bits<...>` with a non-const width expression. Unreachable in
        # the frozen corpus (no call site actually invokes this), so this
        # implements the evidently-intended behavior instead of the dead
        # comparison.
        if self.type_name == "Bits":
            assert self.bits_expression is not None
            return self.bits_expression.const_eval(symtab)
        return True

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if self.type_name == "Bits":
            assert self.bits_expression is not None
            self.bits_expression.type_check(symtab, strict=strict)
            try:
                if not self.bits_expression.value(symtab) > 0:
                    self.type_error(
                        f"Bits width ({self.bits_expression.value(symtab)}) must be positive"
                    )
            except IdlValueUnknown:
                pass
            if not self.bits_expression.type(symtab).is_const:
                self.type_error(f"Bits width ({self.bits_expression.text}) must be const")
        if self.type_name not in _BUILTIN_TYPE_NAMES:
            self.type_error(f"Unimplemented builtin type {self.text}")

    def bits_type(self, symtab: SymbolTable) -> Type:
        assert self.bits_expression is not None
        try:
            return Type(TypeKind.BITS, width=self.bits_expression.value(symtab))
        except IdlValueUnknown:
            return Type(TypeKind.BITS, width=WIDTH_UNKNOWN, width_ast=self.bits_expression)

    def type(self, symtab: SymbolTable) -> Type:
        if self.type_name == "XReg":
            if symtab.mxlen == 32:
                return BITS32_TYPE
            if symtab.mxlen == 64:
                return BITS64_TYPE
            return Type(TypeKind.BITS, width=WIDTH_UNKNOWN, max_width=64)
        if self.type_name == "Boolean":
            return BOOL_TYPE
        if self.type_name == "U32":
            return BITS32_TYPE
        if self.type_name == "U64":
            return BITS64_TYPE
        if self.type_name == "String":
            return STRING_TYPE
        if self.type_name == "Bits":
            return self.bits_type(symtab)
        self.internal_error(f"TODO: {self.text}")


@dataclass(frozen=True, slots=True, kw_only=True)
class DontCareReturn(Node):
    """The ``-`` "don't care" return-value placeholder; Ruby's ``DontCareReturnAst``."""

    kind: ClassVar[str] = "dont_care"

    def to_idl(self) -> str:
        return "-"

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        pass

    def type(self, symtab: SymbolTable) -> Type:
        return Type(TypeKind.DONTCARE)

    def set_expected_type(self, t: Type) -> None:
        self._cache["_expected_type"] = t

    def value(self, symtab: SymbolTable) -> Any:
        expected_type = self._cache.get("_expected_type")
        if expected_type is None:
            self.internal_error("Must call set_expected_type first")
        if expected_type.kind == TypeKind.BITS:
            return 0
        if expected_type.kind == TypeKind.BOOLEAN:
            return False
        self.internal_error("Unhandled expected type")

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

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        pass

    def type(self, symtab: SymbolTable) -> Type:
        return Type(TypeKind.DONTCARE)

    def value(self, symtab: SymbolTable) -> Any:
        self.internal_error("Why are you calling value for an lval?")

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

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

    def _enum_def_type(self, symtab: SymbolTable) -> Type:
        cache = self._cache.setdefault("_enum_def_type", {})
        if symtab.name not in cache:
            t = symtab.get(self.class_name)
            if t is None or t.kind != TypeKind.ENUM:
                self.type_error(f"{self.class_name} is not a defined Enum")
            cache[symtab.name] = t
        return cache[symtab.name]

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        enum_def_type = self._enum_def_type(symtab)
        if enum_def_type is None:
            self.type_error(f"No symbol {self.class_name} has been defined")
        if not isinstance(enum_def_type, EnumerationType):
            self.type_error(f"{self.class_name} is not an enum type")
        if enum_def_type.value(self.member_name) is None:
            self.type_error(f"{self.class_name} has no member '{self.member_name}'")

    def type(self, symtab: SymbolTable) -> Type:
        enum_def_type = self._enum_def_type(symtab)
        if enum_def_type is None:
            self.type_error(f"No enum named {self.class_name}")
        assert isinstance(enum_def_type, EnumerationType)
        return enum_def_type.ref_type

    def value(self, symtab: SymbolTable) -> Any:
        enum_def_type = self._enum_def_type(symtab)
        assert isinstance(enum_def_type, EnumerationType)
        return enum_def_type.value(self.member_name)

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

    def const_eval(self, symtab: SymbolTable) -> bool:
        return True

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        pass

    def execute(self, symtab: SymbolTable) -> None:
        pass

    @classmethod
    def from_h(cls, data: Mapping[str, Any], sources: Mapping[str, str]) -> Noop:
        _check_kind(data, cls.kind)
        return cls(source=IdlSource(text="", label="<synthetic>"), start=0, end=0)
