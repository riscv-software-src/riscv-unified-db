# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Fixed-bit instruction matching, not an operand or pseudoinstruction disassembler."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ..architecture import ConfiguredArchitecture, QueryPresence
from ..conditions import XlenTerm, all_of, implies
from ..configuration import Configuration, ConfigurationKind
from ..database import Database, DatabaseObject
from ..errors import DataError, ObjectNotFoundError
from ..idl_condition_binding import IdlConditionBinding
from ..instruction_fields import DecodeField, InstructionFieldBuilder, InstructionFields


class MatchingError(DataError, ValueError):
    """Malformed encoding or an unsupported matching request."""


class InstructionSelection(StrEnum):
    """Catalog is the real legacy CLI policy; possible/mandatory are explicit queries."""

    CATALOG = "catalog"
    POSSIBLE = "possible"
    MANDATORY = "mandatory"


def parse_encoding(encoding: str | int) -> int:
    if isinstance(encoding, str):
        if not re.fullmatch(r"(?:0[xX])?[a-fA-F0-9]+", encoding):
            raise MatchingError("encoding must be a hex string")
        return int(encoding, 16)
    if type(encoding) is not int or encoding < 0:
        raise MatchingError("encoding must be a nonnegative integer or a hex string")
    return encoding


def possible_xlens(architecture: ConfiguredArchitecture) -> tuple[int, ...]:
    """Legacy effective-mode XLENs, rather than just the machine-mode MXLEN."""
    params = architecture.configuration.params
    mxlen = params.get("MXLEN")
    if mxlen is None:
        return (32, 64)
    if type(mxlen) is not int or mxlen not in (32, 64):
        raise MatchingError("MXLEN must be 32 or 64")
    if mxlen == 32:
        return (32,)
    if architecture.kind is ConfigurationKind.UNCONFIGURED:
        return (32, 64)
    for extension, parameter in (("S", "SXLEN"), ("U", "UXLEN"), ("H", "VSXLEN"), ("H", "VUXLEN")):
        try:
            presence = architecture.extension_presence(extension)
        except ObjectNotFoundError:
            # A small explicitly supplied database need not contain privilege extensions.
            continue
        if presence is QueryPresence.DEFERRED:
            raise MatchingError(f"effective XLEN is undecidable for extension {extension}")
        if presence is QueryPresence.ABSENT:
            continue
        if architecture.kind is ConfigurationKind.PARTIAL and (
            presence is not QueryPresence.MANDATORY or parameter not in params
        ):
            return (32, 64)
        values = params.get(parameter)
        if not isinstance(values, tuple):
            raise MatchingError(
                f"{parameter} must be supplied as an array for extension {extension}"
            )
        if len(values) > 1:
            return (32, 64)
    return (64,)


@dataclass(frozen=True, slots=True)
class DecodedVariable:
    name: str
    encoded_value: int
    value: int
    width: int
    sign_extend: bool
    left_shift: int
    alias: str | None
    excluded: bool


def decode_variable(field: DecodeField, encoding: int) -> DecodedVariable:
    """Concatenate declared ranges in order, then shift and sign-extend."""
    value = 0
    for part in field.ranges:
        value = (value << part.width) | ((encoding >> part.low) & ((1 << part.width) - 1))
    encoded = value
    value <<= field.left_shift
    if field.sign_extend and value & (1 << (field.width - 1)):
        value -= 1 << field.width
    return DecodedVariable(
        field.name,
        encoded,
        value,
        field.width,
        field.sign_extend,
        field.left_shift,
        field.alias,
        encoded in field.exclusions,
    )


@dataclass(frozen=True, slots=True)
class InstructionMatch:
    name: str
    xlen: int
    length: int
    mask: int
    fixed_value: int
    assembly: str | None
    variables: tuple[DecodedVariable, ...]

    @property
    def constraint_violations(self) -> tuple[str, ...]:
        return tuple(variable.name for variable in self.variables if variable.excluded)


@dataclass(frozen=True, slots=True)
class XlenMatches:
    xlen: int
    matches: tuple[InstructionMatch, ...]

    @property
    def illegal(self) -> bool:
        return not self.matches

    @property
    def ambiguous(self) -> bool:
        return len(self.matches) > 1


@dataclass(frozen=True, slots=True)
class DisassemblyReport:
    encoding: int
    width: int | None
    selection: InstructionSelection
    results: tuple[XlenMatches, ...]

    def render(self) -> str:
        return "".join(
            f"RV{result.xlen}:\n"
            + (
                "".join(f"  {match.name}\n" for match in result.matches)
                if result.matches
                else "  Illegal Instruction\n"
            )
            for result in self.results
        )


def catalog_order(records: Iterable[DatabaseObject]) -> tuple[DatabaseObject, ...]:
    """Ruby Architecture discovers records in recursive, sorted path order."""
    return tuple(sorted(records, key=lambda item: item.path.as_posix()))


class InstructionMatcher:
    """Reusable descriptor-backed matcher with explicit selection/width policies.

    With no width, matching deliberately ignores high bits outside each mask,
    just like ``udb disasm``. Explicit width requires exactly that descriptor
    length and rejects overflowing integers. Decode exclusions are reported,
    not silently used to remove legacy fixed-bit matches.
    """

    def __init__(self, source: Database | ConfiguredArchitecture) -> None:
        if not isinstance(source, (Database, ConfiguredArchitecture)):
            raise TypeError("source must be a Database or ConfiguredArchitecture")
        self.architecture = source if isinstance(source, ConfiguredArchitecture) else None
        self.builder = InstructionFieldBuilder(source)
        self.database = self.builder.database
        self._descriptors: tuple[InstructionFields, ...] | None = None
        configuration = (
            self.architecture.configuration if self.architecture else Configuration.builtin("_")
        )
        self._binding = IdlConditionBinding(self.database, configuration)

    @property
    def descriptors(self) -> tuple[InstructionFields, ...]:
        if self._descriptors is None:
            self._descriptors = tuple(
                self.builder.describe(record)
                for record in catalog_order(self.database.instructions)
            )
        return self._descriptors

    def match(
        self,
        encoding: str | int,
        *,
        width: int | None = None,
        xlen: int | None = None,
        selection: InstructionSelection | str = InstructionSelection.CATALOG,
    ) -> DisassemblyReport:
        value = parse_encoding(encoding)
        selection = InstructionSelection(selection)
        if width is not None and (type(width) is not int or width not in (16, 32)):
            raise MatchingError("instruction width must be 16 or 32")
        if width is not None and value >= 1 << width:
            raise MatchingError(f"encoding does not fit in {width} bits")
        if xlen is not None and (type(xlen) is not int or xlen not in (32, 64)):
            raise MatchingError("XLEN must be 32 or 64")
        if selection is not InstructionSelection.CATALOG and self.architecture is None:
            raise MatchingError("configuration filtering requires a ConfiguredArchitecture")
        xlens = possible_xlens(self.architecture) if self.architecture else (32, 64)
        if xlen is not None:
            if xlen not in xlens:
                raise MatchingError(f"RV{xlen} is not a possible XLEN in this configuration")
            xlens = (xlen,)
        results = []
        for base in xlens:
            matches = []
            for descriptor in self.descriptors:
                layout = descriptor.encoding(base)
                if layout is None or (width is not None and layout.length != width):
                    continue
                mask = int("".join("0" if bit == "-" else "1" for bit in layout.match), 2)
                fixed = int(layout.match.replace("-", "0"), 2)
                if value & mask != fixed:
                    continue
                if not self._selected(descriptor, base, selection):
                    continue
                matches.append(
                    InstructionMatch(
                        descriptor.name,
                        base,
                        layout.length,
                        mask,
                        fixed,
                        descriptor.assembly,
                        tuple(decode_variable(field, value) for field in layout.variables),
                    )
                )
            results.append(XlenMatches(base, tuple(matches)))
        return DisassemblyReport(value, width, selection, tuple(results))

    def _selected(
        self, descriptor: InstructionFields, xlen: int, selection: InstructionSelection
    ) -> bool:
        if selection is InstructionSelection.CATALOG:
            return True
        record = descriptor.instruction
        raw = record.get("definedBy", True)
        if isinstance(raw, str):
            raw = {"extension": {"name": raw}}
        condition = self._binding.resolve_record(raw, record, ("definedBy",))
        presence = self.architecture.condition_presence(
            implies(XlenTerm(xlen), condition)
            if selection is InstructionSelection.MANDATORY
            else all_of(condition, XlenTerm(xlen))
        )
        if presence is QueryPresence.DEFERRED:
            raise MatchingError(f"instruction selection is undecidable for {record.name}")
        return presence is QueryPresence.MANDATORY or (
            selection is InstructionSelection.POSSIBLE and presence is QueryPresence.POSSIBLE
        )
