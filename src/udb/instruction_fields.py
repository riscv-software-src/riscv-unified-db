# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Validated builder outputs and typed instruction fields for native generators."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, NoReturn

from .architecture import ConfiguredArchitecture, QueryPresence
from .conditions import XlenTerm, all_of
from .configuration import Configuration
from .database import Database, Instruction, ResolvedDatabase
from .errors import DataError, ObjectNotFoundError
from .idl_condition_binding import IdlConditionBinding
from .reference import DataReference, ResolvedNode
from .source import SourceSpan

type ArchitectureSource = Database | ConfiguredArchitecture
type FieldPath = tuple[str | int, ...]
_METADATA = {"$child_of", "$parent_of"}


class InstructionFieldError(DataError):
    """An instruction contains unsupported or malformed encoding data."""


@dataclass(frozen=True, slots=True)
class BitRange:
    """One contiguous range, with inclusive endpoints."""

    high: int
    low: int

    @property
    def width(self) -> int:
        return self.high - self.low + 1


@dataclass(frozen=True, slots=True)
class OpcodeField:
    bits: str
    location: BitRange
    source: SourceSpan | None = None

    @property
    def value(self) -> int:
        return int(self.bits, 2)


@dataclass(frozen=True, slots=True)
class DecodeField:
    name: str
    location: str
    ranges: tuple[BitRange, ...]
    sign_extend: bool = False
    left_shift: int = 0
    exclusions: tuple[int, ...] = ()
    alias: str | None = None
    source: SourceSpan | None = None

    @property
    def encoded_width(self) -> int:
        return sum(part.width for part in self.ranges)

    @property
    def width(self) -> int:
        return self.encoded_width + self.left_shift

    @property
    def bits(self) -> tuple[int, ...]:
        """Instruction positions in extraction (most-significant-first) order."""
        return tuple(bit for part in self.ranges for bit in range(part.high, part.low - 1, -1))


@dataclass(frozen=True, slots=True)
class EncodingFields:
    xlen: int
    match: str
    opcodes: tuple[OpcodeField, ...]
    variables: tuple[DecodeField, ...]

    @property
    def length(self) -> int:
        return len(self.match)


@dataclass(frozen=True, slots=True)
class InstructionFields:
    """A typed descriptor; use the builder to validate its extraction semantics."""

    instruction: Instruction
    assembly: str | None
    encodings: tuple[EncodingFields, ...]

    @property
    def name(self) -> str:
        return self.instruction.name

    def encoding(self, xlen: int) -> EncodingFields | None:
        if type(xlen) is not int or xlen not in (32, 64):
            raise ValueError("XLEN must be 32 or 64")
        return next((encoding for encoding in self.encodings if encoding.xlen == xlen), None)


class InstructionFieldBuilder:
    """Reuse one public, unconfigured architecture for structural XLEN queries.

    Configured machine values intentionally do not restrict instruction layouts.
    The supplied configuration still determines the resolved database context.
    Record arguments must belong to the input or effective resolved database;
    name arguments explicitly select a record in the effective database.
    """

    def __init__(self, source: ArchitectureSource) -> None:
        database = source.database if isinstance(source, ConfiguredArchitecture) else source
        self._source_database = database
        self.database = database if isinstance(database, ResolvedDatabase) else database.resolve()
        self._structural: ConfiguredArchitecture | None = None
        self._bases: dict[str, tuple[int, ...]] = {}
        self._binding = IdlConditionBinding(self.database, Configuration.builtin("_"))

    def describe(self, instruction: Instruction | str) -> InstructionFields:
        if isinstance(instruction, str):
            record = self.database.instruction(instruction)
        elif isinstance(instruction, Instruction):
            try:
                original = self._source_database.instruction(instruction.name)
                record = self.database.instruction(instruction.name)
            except ObjectNotFoundError:
                _foreign_instruction(instruction)
            if instruction is not original and instruction is not record:
                _foreign_instruction(instruction)
        else:
            raise TypeError("instruction must be a name or an Instruction")
        owner = ResolvedNode(str(record.path), (), self.database)
        if any(
            char.isspace() or not char.isprintable() or char in "#=|~!<>" for char in record.name
        ):
            _fail(owner, ("name",), "instruction name is ambiguous in an instruction-table row")
        if "encoding" in record and "format" in record:
            _fail(owner, (), "encoding and format cannot both be present")
        assembly = record.get("assembly")
        if assembly is not None and not isinstance(assembly, str):
            _fail(owner, ("assembly",), "assembly must be a string")
        encodings = []
        bases = self._supported_bases(record)
        key = "format" if "format" in record else "encoding"
        raw = _mapping(owner, (key,), record.get(key))
        split = "RV32" in raw or "RV64" in raw
        if split:
            _keys(owner, (key,), raw, {"RV32", "RV64"})
            # Validate both declared branches, even when one is structurally absent.
            for branch in raw:
                if branch not in _METADATA:
                    self._encoding(owner, (key, branch), raw[branch], int(branch[2:]), key)
        for xlen in bases:
            path = (key, f"RV{xlen}") if split else (key,)
            value = raw.get(f"RV{xlen}") if split else raw
            encodings.append(self._encoding(owner, path, value, xlen, key))
        return InstructionFields(record, assembly, tuple(encodings))

    def _supported_bases(self, record: Instruction) -> tuple[int, ...]:
        raw = record.get("definedBy", True)
        if isinstance(raw, str):
            raw = {"extension": {"name": raw}}
        condition = self._binding.resolve_record(raw, record, ("definedBy",))
        key = repr(condition)
        if key not in self._bases:
            if self._structural is None:
                self._structural = self.database.configure(Configuration.builtin("_"))
            presence = tuple(
                self._structural.condition_presence(all_of(condition, XlenTerm(xlen)))
                for xlen in (32, 64)
            )
            if QueryPresence.DEFERRED in presence:
                _fail(
                    ResolvedNode(str(record.path), (), self.database),
                    ("definedBy",),
                    "structural XLEN support is undecidable",
                )
            supported = tuple(
                xlen
                for xlen, status in zip((32, 64), presence, strict=True)
                if status is not QueryPresence.ABSENT
            )
            # Ruby infers a restriction only when exactly one XLEN is satisfiable.
            self._bases[key] = supported if len(supported) == 1 else (32, 64)
        return self._bases[key]

    def _encoding(
        self, owner: ResolvedNode, path: FieldPath, value: Any, xlen: int, kind: str
    ) -> EncodingFields:
        raw = _mapping(owner, path, value)
        if kind == "format":
            return self._format(owner, path, raw, xlen)
        _keys(owner, path, raw, {"match", "variables"})
        match = raw.get("match")
        if not isinstance(match, str) or not re.fullmatch(r"[01-]+", match):
            _fail(owner, (*path, "match"), "match must be a nonempty string of 0, 1 and -")
        variables = raw.get("variables", ())
        if not isinstance(variables, Sequence) or isinstance(variables, (str, bytes)):
            _fail(owner, (*path, "variables"), "variables must be a sequence")
        fields = tuple(
            _variable(owner, (*path, "variables", index), value, len(match))
            for index, value in enumerate(variables)
        )
        return _finish(owner, path, match, fields, xlen)

    def _format(
        self, owner: ResolvedNode, path: FieldPath, raw: Mapping, xlen: int
    ) -> EncodingFields:
        _keys(owner, path, raw, {"type", "subtype", "opcodes", "variables"})
        type_node = _target(owner, (*path, "type"))
        length = _mapping(type_node, (), type_node.value).get("length")
        if type(length) is not int or length <= 0:
            _fail(type_node, ("length",), "instruction type length must be a positive integer")
        match = ["-"] * length
        opcodes = _mapping(owner, (*path, "opcodes"), raw.get("opcodes"))
        for name, opcode in opcodes.items():
            if name in _METADATA:
                continue
            opcode_path = (*path, "opcodes", name)
            _name(owner, opcode_path, name)
            opcode = _mapping(owner, opcode_path, opcode)
            _keys(owner, opcode_path, opcode, {"location", "display_name", "value"})
            if "display_name" in opcode and not isinstance(opcode["display_name"], str):
                _fail(owner, (*opcode_path, "display_name"), "display_name must be a string")
            _, ranges = _location(owner, (*opcode_path, "location"), opcode.get("location"), length)
            if len(ranges) != 1:
                _fail(owner, (*opcode_path, "location"), "opcode fields must be contiguous")
            part = ranges[0]
            value = opcode.get("value")
            if isinstance(value, Mapping):
                target = _target(owner, (*opcode_path, "value"))
                target_value = _mapping(target, (), target.value)
                if "data" in target_value:
                    target_value = _mapping(target, ("data",), target_value["data"])
                value = target_value.get("value")
            if type(value) is not int or value < 0 or value >= 1 << part.width:
                _fail(owner, (*opcode_path, "value"), "opcode value does not fit its field")
            for bit, text in zip(
                range(part.high, part.low - 1, -1), f"{value:0{part.width}b}", strict=True
            ):
                if match[length - bit - 1] != "-":
                    _fail(owner, opcode_path, "opcode fields overlap")
                match[length - bit - 1] = text
        # Ruby format encodings obtain ordered variables from the subtype.
        subtype = _target(owner, (*path, "subtype"))
        subtype_data = _mapping(subtype, (), subtype.value)
        variables_owner = subtype.child("data") if "data" in subtype_data else subtype
        variables = _mapping(
            variables_owner, ("variables",), variables_owner.value.get("variables", {})
        )
        fields = tuple(
            _variable(variables_owner, ("variables", name), variable, length, name=name)
            for name, variable in variables.items()
            if name not in _METADATA
        )
        # Format-local variables are annotations in legacy Ruby; verify rather than
        # silently discard conflicting extraction semantics.
        if "variables" in raw:
            local = _mapping(owner, (*path, "variables"), raw["variables"])
            for name, variable in local.items():
                if name in _METADATA:
                    continue
                candidate = _variable(
                    owner, (*path, "variables", name), variable, length, name=name
                )
                expected = next((field for field in fields if field.name == name), None)
                if expected is None or _semantics(candidate) != _semantics(expected):
                    _fail(owner, (*path, "variables", name), "variable disagrees with its subtype")
        return _finish(owner, path, "".join(match), fields, xlen)


def instruction_fields(
    source: ArchitectureSource, instruction: Instruction | str
) -> InstructionFields:
    """Describe an instruction; reuse :class:`InstructionFieldBuilder` for batches."""
    return InstructionFieldBuilder(source).describe(instruction)


def _foreign_instruction(instruction: Instruction) -> NoReturn:
    span = instruction.source_at("name")
    origin = span.label if span is not None else str(instruction.path)
    raise InstructionFieldError(
        f"{origin}#/name: instruction belongs to a different database; "
        "pass a name to look it up explicitly in the builder's database"
    )


def _fail(owner: ResolvedNode, path: FieldPath, message: str) -> None:
    span = _source(owner, path)
    pointer = "/".join(
        str(part).replace("~", "~0").replace("/", "~1") for part in (*owner.path, *path)
    )
    origin = span.label if span is not None else owner.document
    raise InstructionFieldError(f"{origin}#/{pointer}: {message}")


def _source(owner: ResolvedNode, path: FieldPath) -> SourceSpan | None:
    node = owner
    try:
        for key in path:
            node = node.child(key)
    except DataError:
        return None
    return node.source


def _mapping(owner: ResolvedNode, path: FieldPath, value: Any) -> Mapping:
    if not isinstance(value, Mapping):
        _fail(owner, path, "must be a mapping")
    return value


def _keys(owner: ResolvedNode, path: FieldPath, value: Mapping, allowed: set[str]) -> None:
    for key in value:
        if key not in allowed | _METADATA:
            _fail(owner, (*path, key), f"unsupported encoding field {key!r}")


def _name(owner: ResolvedNode, path: FieldPath, value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", value):
        _fail(owner, path, "field name must be a nonempty identifier")
    return value


def _location(
    owner: ResolvedNode, path: FieldPath, value: Any, length: int
) -> tuple[str, tuple[BitRange, ...]]:
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]+(?:-[0-9]+)?(?:\|[0-9]+(?:-[0-9]+)?)*", value
    ):
        _fail(owner, path, "location must contain bit indices or msb-lsb ranges joined by |")
    ranges = []
    seen = set()
    for part in value.split("|"):
        ends = part.split("-")
        high, low = int(ends[0]), int(ends[-1])
        if low > high or high >= length:
            _fail(owner, path, f"location range must descend and fit the {length}-bit encoding")
        bits = set(range(low, high + 1))
        if seen & bits:
            _fail(owner, path, "location repeats an instruction bit")
        seen |= bits
        ranges.append(BitRange(high, low))
    return value, tuple(ranges)


def _variable(
    owner: ResolvedNode, path: FieldPath, value: Any, length: int, *, name: str | None = None
) -> DecodeField:
    raw = _mapping(owner, path, value)
    _keys(
        owner, path, raw, {"name", "location", "sign_extend", "left_shift", "not", "alias", "type"}
    )
    if name is not None and "name" in raw and raw["name"] != name:
        _fail(owner, (*path, "name"), "variable name disagrees with its mapping key")
    name = _name(owner, (*path, "name"), raw.get("name") if name is None else name)
    location, ranges = _location(owner, (*path, "location"), raw.get("location"), length)
    sign = raw.get("sign_extend", False)
    shift = raw.get("left_shift", 0)
    # Explicit null modifiers have the same defaults as Ruby.
    sign = False if sign is None else sign
    shift = 0 if shift is None else shift
    if type(sign) is not bool:
        _fail(owner, (*path, "sign_extend"), "sign_extend must be Boolean")
    if type(shift) is not int or shift < 0:
        _fail(owner, (*path, "left_shift"), "left_shift must be a nonnegative integer")
    excluded = raw.get("not", ())
    if type(excluded) is int:
        excluded = (excluded,)
    if (
        not isinstance(excluded, Sequence)
        or isinstance(excluded, (str, bytes))
        or any(type(item) is not int for item in excluded)
    ):
        _fail(owner, (*path, "not"), "exclusions must be integers or a sequence of integers")
    alias = raw.get("alias")
    if alias is not None:
        _name(owner, (*path, "alias"), alias)
    if "type" in raw:
        target = _target(owner, (*path, "type"))
        _mapping(target, (), target.value)
    return DecodeField(
        name,
        location,
        ranges,
        sign,
        shift,
        tuple(excluded),
        alias,
        _source(owner, path),
    )


def _target(owner: ResolvedNode, path: FieldPath) -> ResolvedNode:
    node = owner
    for key in path:
        node = node.child(key)
    raw = _mapping(node, (), node.value)
    _keys(node, (), raw, {"$ref"})
    reference = node.reference()
    if not isinstance(reference, DataReference):
        _fail(node, (), "expected a data reference")
    return reference.target


def _semantics(field: DecodeField) -> tuple:
    return (field.location, field.sign_extend, field.left_shift, field.exclusions, field.alias)


def _finish(
    owner: ResolvedNode, path: FieldPath, match: str, fields: tuple[DecodeField, ...], xlen: int
) -> EncodingFields:
    names = set()
    occupied = {len(match) - index - 1 for index, bit in enumerate(match) if bit != "-"}
    for field in fields:
        if field.name in names:
            _fail(owner, path, f"duplicate decode variable {field.name!r}")
        names.add(field.name)
        if occupied.intersection(field.bits):
            _fail(owner, path, f"decode variable {field.name!r} overlaps another field")
        occupied.update(field.bits)
    if len(occupied) != len(match):
        _fail(owner, path, "encoding has bits without an opcode or decode variable")
    source = _source(owner, (*path, "match"))
    opcodes = tuple(
        OpcodeField(
            run.group(), BitRange(len(match) - run.start() - 1, len(match) - run.end()), source
        )
        for run in re.finditer(r"[01]+", match)
    )
    return EncodingFields(xlen, match, opcodes, fields)
