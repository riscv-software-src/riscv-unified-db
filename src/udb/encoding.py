# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Data-only instruction-encoding and CSR-address overlap checks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from .conditions import XlenTerm, all_of
from .database import Csr, Instruction
from .errors import DataError

if TYPE_CHECKING:
    from .architecture import ConfiguredArchitecture


class OverlapKind(StrEnum):
    CONFLICT = "conflict"
    ALIAS = "alias"
    DEFERRED = "deferred"


@dataclass(frozen=True, slots=True)
class InstructionEncoding:
    instruction: Instruction
    xlen: int
    length: int
    mask: int
    value: int
    exclusions: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class InstructionOverlap:
    left: Instruction
    right: Instruction
    xlen: int
    kind: OverlapKind


@dataclass(frozen=True, slots=True)
class CsrAddressKey:
    space: str
    address: int
    slot: int | None = None
    privilege: str | None = None


@dataclass(frozen=True, slots=True)
class CsrAddressOverlap:
    left: Csr
    right: Csr
    xlen: int
    key: CsrAddressKey
    kind: OverlapKind


def instruction_encodings(
    architecture: ConfiguredArchitecture, instruction: Instruction
) -> tuple[InstructionEncoding, ...]:
    """Normalize legacy and resolved format encodings for both XLENs."""

    if "encoding" in instruction.data:
        raw = instruction.data["encoding"]
        if not isinstance(raw, Mapping):
            raise DataError(f"{instruction.path}#/encoding must be a mapping")
        if "match" in raw:
            return tuple(_legacy_encoding(instruction, raw, xlen) for xlen in (32, 64))
        result = []
        for key, xlen in (("RV32", 32), ("RV64", 64)):
            encoding = raw.get(key)
            if isinstance(encoding, Mapping):
                result.append(_legacy_encoding(instruction, encoding, xlen))
        return tuple(result)

    raw_format = instruction.data.get("format")
    if not isinstance(raw_format, Mapping):
        return ()
    length = _format_length(architecture, raw_format)
    mask = 0
    value = 0
    opcodes = raw_format.get("opcodes", {})
    if not isinstance(opcodes, Mapping):
        raise DataError(f"{instruction.path}#/format/opcodes must be a mapping")
    for name, opcode in opcodes.items():
        if not isinstance(opcode, Mapping):
            raise DataError(f"{instruction.path}#/format/opcodes/{name} must be a mapping")
        field_mask, positions = _location_mask(opcode.get("location"))
        opcode_value = _opcode_value(architecture, opcode.get("value"))
        encoded = _place_value(opcode_value, positions)
        if mask & field_mask and ((value ^ encoded) & (mask & field_mask)):
            raise DataError(f"{instruction.path} has contradictory format opcode bits")
        mask |= field_mask
        value |= encoded

    exclusions = _format_exclusions(raw_format)
    return tuple(
        InstructionEncoding(instruction, xlen, length, mask, value, exclusions) for xlen in (32, 64)
    )


def instruction_overlaps(
    architecture: ConfiguredArchitecture,
    instructions: Iterable[Instruction],
) -> tuple[InstructionOverlap, ...]:
    from .architecture import QueryPresence

    encoded = {
        instruction.name: instruction_encodings(architecture, instruction)
        for instruction in instructions
    }
    records = {instruction.name: instruction for instruction in instructions}
    result: list[InstructionOverlap] = []
    for left_name, right_name in combinations(sorted(records), 2):
        left = records[left_name]
        right = records[right_name]
        if _is_hint_pair(left, right):
            continue
        xlens = set()
        for left_encoding in encoded[left_name]:
            for right_encoding in encoded[right_name]:
                if left_encoding.xlen != right_encoding.xlen:
                    continue
                if not _encodings_overlap(left_encoding, right_encoding):
                    continue
                xlens.add(left_encoding.xlen)
        for xlen in sorted(xlens):
            presence = architecture.condition_presence(
                all_of(
                    architecture._defined_by(left),
                    architecture._defined_by(right),
                    XlenTerm(xlen),
                )
            )
            if presence is QueryPresence.ABSENT:
                kind = OverlapKind.ALIAS
            elif presence is QueryPresence.DEFERRED:
                kind = OverlapKind.DEFERRED
            else:
                kind = OverlapKind.CONFLICT
            result.append(InstructionOverlap(left, right, xlen, kind))
    return tuple(result)


def csr_address_overlaps(
    architecture: ConfiguredArchitecture,
    csrs: Iterable[Csr],
) -> tuple[CsrAddressOverlap, ...]:
    from .architecture import QueryPresence

    by_key: dict[CsrAddressKey, list[Csr]] = {}
    for csr in csrs:
        for key in _csr_keys(csr):
            by_key.setdefault(key, []).append(csr)

    result: list[CsrAddressOverlap] = []
    for key in sorted(
        by_key, key=lambda item: (item.space, item.privilege or "", item.address, item.slot or 0)
    ):
        for left, right in combinations(sorted(by_key[key], key=lambda item: item.name), 2):
            for xlen in (32, 64):
                presence = architecture.condition_presence(
                    all_of(
                        architecture._defined_by(left),
                        architecture._defined_by(right),
                        XlenTerm(xlen),
                    )
                )
                if presence is QueryPresence.ABSENT:
                    kind = OverlapKind.ALIAS
                elif presence is QueryPresence.DEFERRED:
                    kind = OverlapKind.DEFERRED
                else:
                    kind = OverlapKind.CONFLICT
                result.append(CsrAddressOverlap(left, right, xlen, key, kind))
    return tuple(result)


def _legacy_encoding(
    instruction: Instruction, encoding: Mapping[str, Any], xlen: int
) -> InstructionEncoding:
    match = encoding.get("match")
    if not isinstance(match, str) or not match or any(bit not in "01-" for bit in match):
        raise DataError(f"{instruction.path} has an invalid encoding match")
    mask = 0
    value = 0
    for bit, character in enumerate(reversed(match)):
        if character != "-":
            mask |= 1 << bit
            if character == "1":
                value |= 1 << bit
    exclusions: list[tuple[int, int]] = []
    variables = encoding.get("variables", ())
    if isinstance(variables, Sequence) and not isinstance(variables, (str, bytes)):
        for variable in variables:
            if not isinstance(variable, Mapping) or "not" not in variable:
                continue
            variable_mask, positions = _location_mask(variable.get("location"))
            rejected = variable["not"]
            values = (
                rejected
                if isinstance(rejected, Sequence) and not isinstance(rejected, str)
                else (rejected,)
            )
            left_shift = variable.get("left_shift", 0)
            if not isinstance(left_shift, int) or isinstance(left_shift, bool) or left_shift < 0:
                raise DataError(f"{instruction.path} has an invalid encoding left_shift")
            for item in values:
                if not isinstance(item, int) or isinstance(item, bool):
                    raise DataError(f"{instruction.path} has a non-integer encoding exclusion")
                encoded = _excluded_value(item, positions, left_shift)
                if encoded is not None:
                    exclusions.append((variable_mask, encoded))
    return InstructionEncoding(instruction, xlen, len(match), mask, value, tuple(exclusions))


def _format_length(architecture: ConfiguredArchitecture, raw_format: Mapping[str, Any]) -> int:
    type_ref = raw_format.get("type")
    if isinstance(type_ref, Mapping) and isinstance(type_ref.get("$ref"), str):
        path = type_ref["$ref"].split("#", 1)[0]
        name = PurePosixPath(path).stem
        try:
            value = architecture.database.get("instruction_type", name).data.get("length")
            if isinstance(value, int) and not isinstance(value, bool):
                return value
        except DataError:
            pass
    maximum = 31
    for group_name in ("opcodes", "variables"):
        group = raw_format.get(group_name, {})
        if not isinstance(group, Mapping):
            continue
        for item in group.values():
            if isinstance(item, Mapping):
                _, positions = _location_mask(item.get("location"))
                if positions:
                    maximum = max(maximum, *positions)
    return maximum + 1


def _opcode_value(architecture: ConfiguredArchitecture, value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, Mapping) and isinstance(value.get("$ref"), str):
        path = value["$ref"].split("#", 1)[0]
        name = PurePosixPath(path).stem
        record = architecture.database.get("instruction_opcode", name)
        resolved = record.data.get("data", {}).get("value")
        if isinstance(resolved, int) and not isinstance(resolved, bool):
            return resolved
    raise DataError(f"cannot resolve instruction opcode value {value!r}")


def _format_exclusions(raw_format: Mapping[str, Any]) -> tuple[tuple[int, int], ...]:
    result = []
    variables = raw_format.get("variables", {})
    if not isinstance(variables, Mapping):
        return ()
    for variable in variables.values():
        if not isinstance(variable, Mapping) or "not" not in variable:
            continue
        mask, positions = _location_mask(variable.get("location"))
        rejected = variable["not"]
        values = (
            rejected
            if isinstance(rejected, Sequence) and not isinstance(rejected, str)
            else (rejected,)
        )
        left_shift = variable.get("left_shift", 0)
        if not isinstance(left_shift, int) or isinstance(left_shift, bool) or left_shift < 0:
            raise DataError("format variable has an invalid encoding left_shift")
        for value in values:
            if isinstance(value, int) and not isinstance(value, bool):
                encoded = _excluded_value(value, positions, left_shift)
                if encoded is not None:
                    result.append((mask, encoded))
    return tuple(result)


def _location_mask(location: Any) -> tuple[int, tuple[int, ...]]:
    if isinstance(location, int) and not isinstance(location, bool):
        if location < 0:
            raise DataError(f"negative encoding location {location}")
        return 1 << location, (location,)
    if not isinstance(location, str):
        raise DataError(f"invalid encoding location {location!r}")
    positions: list[int] = []
    for part in reversed(location.split("|")):
        if "-" in part:
            high_text, low_text = part.split("-", 1)
            high, low = int(high_text), int(low_text)
            if high < low:
                raise DataError(f"invalid encoding location {location!r}")
            positions.extend(range(low, high + 1))
        else:
            positions.append(int(part))
    if len(set(positions)) != len(positions):
        raise DataError(f"overlapping encoding location {location!r}")
    mask = sum(1 << bit for bit in positions)
    return mask, tuple(positions)


def _place_value(value: int, positions: Sequence[int]) -> int:
    if value < 0 or value >= 1 << len(positions):
        raise DataError(f"value {value} does not fit in {len(positions)} encoding bits")
    result = 0
    for source_bit, destination_bit in enumerate(positions):
        if value & (1 << source_bit):
            result |= 1 << destination_bit
    return result


def _excluded_value(value: int, positions: Sequence[int], left_shift: int) -> int | None:
    if value < 0:
        raise DataError(f"negative encoding exclusion {value}")
    if left_shift and value & ((1 << left_shift) - 1):
        return None
    return _place_value(value >> left_shift, positions)


def _encodings_overlap(left: InstructionEncoding, right: InstructionEncoding) -> bool:
    if left.length != right.length:
        return False
    shared = left.mask & right.mask
    if (left.value ^ right.value) & shared:
        return False
    fixed_mask = left.mask | right.mask
    fixed_value = (left.value & left.mask) | (right.value & right.mask)
    clauses: list[tuple[tuple[int, bool], ...]] = []
    for mask, value in (*left.exclusions, *right.exclusions):
        clause = []
        satisfied = False
        for bit in range(left.length):
            flag = 1 << bit
            if not mask & flag:
                continue
            excluded_bit = bool(value & flag)
            if fixed_mask & flag:
                if bool(fixed_value & flag) != excluded_bit:
                    satisfied = True
                    break
            else:
                clause.append((bit, not excluded_bit))
        if satisfied:
            continue
        if not clause:
            return False
        clauses.append(tuple(clause))
    return _clauses_satisfiable(tuple(clauses), {})


def _clauses_satisfiable(
    clauses: tuple[tuple[tuple[int, bool], ...], ...], assignment: dict[int, bool]
) -> bool:
    remaining: list[tuple[tuple[int, bool], ...]] = []
    for clause in clauses:
        undecided = []
        for variable, value in clause:
            current = assignment.get(variable)
            if current is None:
                undecided.append((variable, value))
            elif current == value:
                break
        else:
            if not undecided:
                return False
            remaining.append(tuple(undecided))
    if not remaining:
        return True
    variable = min(remaining, key=len)[0][0]
    for value in (False, True):
        assignment[variable] = value
        if _clauses_satisfiable(tuple(remaining), assignment):
            assignment.pop(variable, None)
            return True
    assignment.pop(variable, None)
    return False


def _is_hint_pair(left: Instruction, right: Instruction) -> bool:
    return right.name in _hint_names(left) or left.name in _hint_names(right)


def _hint_names(instruction: Instruction) -> set[str]:
    result = set()
    hints = instruction.data.get("hints", ())
    if not isinstance(hints, Sequence) or isinstance(hints, (str, bytes)):
        return result
    for hint in hints:
        if isinstance(hint, Mapping) and isinstance(hint.get("$ref"), str):
            path = hint["$ref"].split("#", 1)[0]
            result.add(PurePosixPath(path).stem)
    return result


def _csr_keys(csr: Csr) -> tuple[CsrAddressKey, ...]:
    result = []
    address = csr.data.get("address")
    if isinstance(address, int) and not isinstance(address, bool):
        result.append(CsrAddressKey("direct", address))
    virtual = csr.data.get("virtual_address")
    if isinstance(virtual, int) and not isinstance(virtual, bool):
        result.append(CsrAddressKey("virtual", virtual))
    indirect = csr.data.get("indirect_address")
    slot = csr.data.get("indirect_slot")
    if (
        isinstance(indirect, int)
        and not isinstance(indirect, bool)
        and isinstance(slot, int)
        and not isinstance(slot, bool)
    ):
        privilege = csr.data.get("priv_mode")
        result.append(
            CsrAddressKey(
                "indirect", indirect, slot, privilege if isinstance(privilege, str) else None
            )
        )
    return tuple(result)


__all__ = [
    "CsrAddressKey",
    "CsrAddressOverlap",
    "InstructionEncoding",
    "InstructionOverlap",
    "OverlapKind",
    "csr_address_overlaps",
    "instruction_encodings",
    "instruction_overlaps",
]
