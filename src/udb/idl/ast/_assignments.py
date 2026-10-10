# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Assignment nodes: PC, variable, array-element/range, field, and multi-variable."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from ._base import Node, _check_kind, _idl_join, _source_and_span, from_h


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
