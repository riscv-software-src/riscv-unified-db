# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""CSR read/write/field-access expressions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from ._base import Node, _check_kind, _idl_join, _source_and_span, from_h


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
