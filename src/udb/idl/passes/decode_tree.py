# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Standalone decoder selection, split-field constraints, and C++ emission.

Inputs describe one effective XLEN. Generator adapters supply instruction class
names and implementation guards; this module does not import architecture or
template backends.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import IntEnum


@dataclass(frozen=True)
class DecodeVariable:
    """Decode fields in most-significant-to-least-significant order."""

    name: str
    fields: tuple[range, ...]
    excludes: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.fields or any(
            not bits or bits.step != 1 or bits.start < 0 for bits in self.fields
        ):
            raise ValueError("Decode variables require nonempty ascending bit ranges")
        if any(value < 0 or value >= 1 << self.width for value in self.excludes):
            raise ValueError("Excluded value does not fit the decode variable")

    @property
    def width(self) -> int:
        return sum(len(bits) for bits in self.fields)

    def extract(self, encoding: int) -> int:
        value = 0
        for bits in self.fields:
            value = (value << len(bits)) | ((encoding >> bits.start) & ((1 << len(bits)) - 1))
        return value


@dataclass(frozen=True)
class DecodeEncoding:
    name: str
    format: str
    variables: tuple[DecodeVariable, ...] = ()
    hint_of: str | None = None
    implemented_condition: str | None = None

    def __post_init__(self) -> None:
        if not self.format or any(bit not in "01-" for bit in self.format):
            raise ValueError("Encoding format must contain only opcode bits and '-'")
        if any(bits.stop > self.length for variable in self.variables for bits in variable.fields):
            raise ValueError("Decode variable exceeds the encoding width")

    @property
    def length(self) -> int:
        return len(self.format)

    @property
    def mask(self) -> int:
        return int("".join("0" if bit == "-" else "1" for bit in self.format), 2)

    @property
    def value(self) -> int:
        return int(self.format.replace("-", "0"), 2)

    def matches(self, encoding: int) -> bool:
        return encoding & self.mask == self.value and all(
            variable.extract(encoding) not in variable.excludes for variable in self.variables
        )


class DecodeNodeKind(IntEnum):
    ENDPOINT = 1
    SELECT = 2


@dataclass
class DecodeTreeNode:
    instructions: tuple[DecodeEncoding, ...]
    range: range | None = None
    value: int | None = None
    kind: DecodeNodeKind = DecodeNodeKind.SELECT
    parent: DecodeTreeNode | None = field(default=None, repr=False)
    children: list[DecodeTreeNode] = field(default_factory=list)

    @staticmethod
    def _range_mask(bits: range | None) -> int:
        return 0 if bits is None else ((1 << len(bits)) - 1) << bits.start

    def mask(self, extra_range: range | None = None) -> int:
        return (
            self._range_mask(self.range)
            | self._range_mask(extra_range)
            | (self.parent.mask() if self.parent is not None else 0)
        )

    def mask_overlap(self, test_range: range, extra_range: range | None = None) -> bool:
        return bool(self.mask(extra_range) & self._range_mask(test_range))

    def opcode_bit(self, index: int) -> bool:
        return bool(self.mask() & (1 << index))

    def lowest_non_opcode_bit(self, gte: int = 0) -> int:
        while self.opcode_bit(gte):
            gte += 1
        return gte

    def decode(
        self, encoding: int, *, implemented: Callable[[DecodeEncoding], bool] | None = None
    ) -> DecodeEncoding | None:
        if self.kind == DecodeNodeKind.ENDPOINT:
            return next(
                (
                    instruction
                    for instruction in self.instructions
                    if instruction.matches(encoding)
                    and (implemented is None or implemented(instruction))
                ),
                None,
            )
        for child in self.children:
            bits = child.range
            if (encoding >> bits.start) & ((1 << len(bits)) - 1) == child.value:
                return child.decode(encoding, implemented=implemented)
        return None


def _priority(instructions: tuple[DecodeEncoding, ...]) -> tuple[DecodeEncoding, ...]:
    """Order overlapping hints before their parents, preserving input ties."""

    result: list[DecodeEncoding] = []
    active: set[str] = set()
    done: set[str] = set()

    def add(instruction: DecodeEncoding) -> None:
        if instruction.name in done:
            return
        if instruction.name in active:
            raise ValueError("Cyclic instruction hint relationship")
        active.add(instruction.name)
        for hint in instructions:
            if hint.hint_of == instruction.name:
                add(hint)
        active.remove(instruction.name)
        done.add(instruction.name)
        result.append(instruction)

    for instruction in instructions:
        add(instruction)
    return tuple(result)


def build_decode_tree(instructions: Iterable[DecodeEncoding]) -> DecodeTreeNode:
    """Partition common opcode bits, retaining residual guards and hint priority."""

    encodings = tuple(instructions)
    if len({instruction.name for instruction in encodings}) != len(encodings):
        raise ValueError("Instruction names must be unique")
    root = DecodeTreeNode(_priority(encodings))

    def construct(node: DecodeTreeNode) -> None:
        if not node.instructions:
            node.kind = DecodeNodeKind.ENDPOINT
            return
        common = node.instructions[0].mask
        for instruction in node.instructions[1:]:
            common &= instruction.mask
        common &= ~node.mask()
        if not common:
            node.kind = DecodeNodeKind.ENDPOINT
            return
        start = (common & -common).bit_length() - 1
        stop = start + 1
        while common & (1 << stop):
            stop += 1
        bits = range(start, stop)
        mask = (1 << len(bits)) - 1
        groups: dict[int, list[DecodeEncoding]] = {}
        for instruction in node.instructions:
            groups.setdefault((instruction.value >> start) & mask, []).append(instruction)
        for value, group in groups.items():
            child = DecodeTreeNode(tuple(group), range=bits, value=value, parent=node)
            node.children.append(child)
            construct(child)

    construct(root)
    return root


def extract_decode_variable(variable: DecodeVariable, encoding_var_name: str) -> str:
    offset = 0
    fields = []
    for bits in reversed(variable.fields):
        expression = f"{encoding_var_name}.extract<{bits.stop - 1}, {bits.start}>()"
        if offset:
            expression = f"({expression}.template widening_sll<{offset}>())"
        fields.append(expression)
        offset += len(bits)
    return "(" + " | ".join(fields) + ")"


def decode_variable_allowed_condition(variable: DecodeVariable, encoding_var_name: str) -> str:
    """Choose the shorter allowed/disallowed constraint without large enumeration."""

    expression = extract_decode_variable(variable, encoding_var_name)
    excluded = frozenset(variable.excludes)
    if (1 << variable.width) - len(excluded) <= len(excluded):
        allowed = (value for value in range(1 << variable.width) if value not in excluded)
        tests = [f"({expression} == {value}_b)" for value in allowed]
        return "(" + " || ".join(tests) + ")" if tests else "false"
    tests = [f"({expression} != {value}_b)" for value in sorted(excluded)]
    return "(" + " && ".join(tests) + ")" if tests else "true"


class DecodeGenerator:
    """C++ selection emission with explicit consumer-owned naming/guard inputs."""

    def __init__(
        self,
        *,
        instruction_class: Callable[[str], str] = lambda name: name,
        implementation_condition: Callable[[DecodeEncoding], str | None] | None = None,
    ) -> None:
        self.instruction_class = instruction_class
        self.implementation_condition = implementation_condition

    def generate(
        self,
        instructions: Iterable[DecodeEncoding],
        xlen: int,
        *,
        indent: int = 2,
        encoding_var_name: str = "encoding",
    ) -> str:
        if xlen not in (32, 64):
            raise ValueError("Effective XLEN must be 32 or 64")
        tree = build_decode_tree(instructions)

        def emit(node: DecodeTreeNode, level: int) -> list[str]:
            pad = " " * level
            if node.kind == DecodeNodeKind.SELECT:
                bits = node.children[0].range
                lines = [
                    pad
                    + f"switch({encoding_var_name}.extract<{bits.stop - 1}, {bits.start}>().get()) {{"
                ]
                for child in node.children:
                    lines.append(pad + f"  case 0b{child.value:0{len(bits)}b}:")
                    lines.extend(emit(child, level + 4))
                    lines.append(pad + "    break;")
                lines.append(pad + "}")
                return lines
            lines = []
            for instruction in node.instructions:
                guards = [
                    f"(({encoding_var_name} & 0b{instruction.mask:0{instruction.length}b}_b)"
                    + f" == 0b{instruction.value:0{instruction.length}b}_b)"
                ]
                guards.extend(
                    decode_variable_allowed_condition(variable, encoding_var_name)
                    for variable in instruction.variables
                    if variable.excludes
                )
                implementation = (
                    self.implementation_condition(instruction)
                    if self.implementation_condition is not None
                    else instruction.implemented_condition
                )
                if implementation:
                    guards.append(f"({implementation})")
                name = self.instruction_class(instruction.name)
                lines.extend(
                    [
                        pad + f"if ({' && '.join(guards)}) {{",
                        pad + "  std::construct_at(",
                        pad + f"    reinterpret_cast<{name}<{xlen}, SocType>*>(inst),",
                        pad + f"    this, pc, {encoding_var_name}",
                        pad + "  );",
                        pad + "  return true;",
                        pad + "}",
                    ]
                )
            return lines

        return "\n".join(emit(tree, indent)) + "\n"
