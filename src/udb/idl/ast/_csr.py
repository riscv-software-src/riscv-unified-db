# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""CSR read/write/field-access expressions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from ..errors import IdlSemanticError
from ..symbols import SymbolTable
from ..types import WIDTH_UNKNOWN, CsrLike, CsrType, Qualifier, Type, TypeKind
from ._base import Node, _check_kind, _idl_join, _source_and_span, from_h
from ._leaves import IntLiteral


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

    def csr_def(self, symtab: SymbolTable) -> CsrLike | None:
        if "_csr_obj" in self._cache:
            return self._cache["_csr_obj"]
        obj = symtab.csr(self.csr_name)
        self._cache["_csr_obj"] = obj
        return obj

    def csr_known(self, symtab: SymbolTable) -> bool:
        return self.csr_def(symtab) is not None

    def const_eval(self, symtab: SymbolTable) -> bool:
        csr = self.csr_def(symtab)
        return csr is not None and csr.value is not None

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if not symtab.csr_exists(self.csr_name):
            self.type_error(f"CSR '{self.csr_name}' is not defined")

    def type(self, symtab: SymbolTable) -> Type:
        if "_type_symtab" in self._cache:
            return self._cache["_type_symtab"]
        result = CsrType(self.csr_def(symtab))
        self._cache["_type_symtab"] = result
        return result

    def value(self, symtab: SymbolTable) -> Any:
        csr = self.csr_def(symtab)
        v = None if csr is None else csr.value
        if v is None:
            self.value_error("CSR is not defined")
        return v


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

    def const_eval(self, symtab: SymbolTable) -> bool:
        return False

    def csr_def(self, symtab: SymbolTable) -> CsrLike | None:
        if isinstance(self.idx, IntLiteral):
            address = self.idx.value(symtab)
            for csr in symtab.csr_hash.values():
                if csr.address == address:
                    return csr
            return None
        return symtab.csr(self.idx.text)

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        if isinstance(self.idx, IntLiteral):
            address = self.idx.value(symtab)
            found = any(csr.address == address for csr in symtab.csr_hash.values())
            if not found:
                self.type_error(f"No csr number '{address}' was found")
        else:
            if symtab.csr(self.idx.text) is None:
                self.type_error(f"No csr named '{self.idx.text}' was found")

    def type(self, symtab: SymbolTable) -> Type:
        return CsrType(self.csr_def(symtab))

    def name(self, symtab: SymbolTable) -> str:
        csr = self.csr_def(symtab)
        assert csr is not None
        return csr.name

    def execute(self, symtab: SymbolTable) -> Any:
        self.value_error("CSR write")


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

    def csr_obj(self, symtab: SymbolTable) -> CsrLike:
        if "_csr_obj" in self._cache:
            return self._cache["_csr_obj"]
        obj = self.csr.csr_def(symtab)
        if obj is None:
            self.type_error(f"No CSR '{self.csr.text}'")
        self._cache["_csr_obj"] = obj
        return obj

    def csr_name(self) -> str:
        return self.csr.csr_name

    def field_def(self, symtab: SymbolTable) -> Any:
        for f in self.csr_obj(symtab).fields:
            if f.name == self.field_name:
                return f
        self.type_error(f"{self.field_name} is not a field of CSR[{self.csr_name()}]")

    def const_eval(self, symtab: SymbolTable) -> bool:
        try:
            self.value(symtab)
        except IdlSemanticError:
            return False
        return True

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.csr.type_check(symtab, strict=strict)
        obj = self.csr_obj(symtab)
        if not any(f.name == self.field_name for f in obj.fields):
            self.type_error(f"{self.field_name} is not a field of CSR[{self.csr_name()}]")
        if strict:
            fd = self.field_def(symtab)
            if symtab.mxlen == 32 and not fd.defined_in_base32:
                self.type_error(f"CSR[{self.csr_name()}].{self.field_name} is not defined in RV32")
            if symtab.mxlen == 64 and not fd.defined_in_base64:
                self.type_error(f"CSR[{self.csr_name()}].{self.field_name} is not defined in RV64")

    def type(self, symtab: SymbolTable) -> Type:
        if "_type_symtab" in self._cache:
            return self._cache["_type_symtab"]
        fd = self.field_def(symtab)
        if fd.defined_in_all_bases:
            width = max(fd.width(xlen) for xlen in symtab.possible_xlens)
            result = Type(TypeKind.BITS, width=width)
        elif fd.base64_only:
            result = Type(TypeKind.BITS, width=fd.width(64))
        elif fd.base32_only:
            result = Type(TypeKind.BITS, width=fd.width(32))
        else:
            self.internal_error("unexpected field base")
        self._cache["_type_symtab"] = result
        return result

    def value(self, symtab: SymbolTable) -> Any:
        fd = self.field_def(symtab)
        if not fd.exists:
            return 0
        bases = {32: fd.defined_in_base32, 64: fd.defined_in_base64}
        applicable_xlens = tuple(xlen for xlen in symtab.possible_xlens if bases[xlen])
        if not applicable_xlens:
            self.value_error(f"'{self.csr_name()}.{self.field_name}' has no applicable XLEN")
        for effective_xlen in applicable_xlens:
            if fd.type(effective_xlen) != "RO":
                self.value_error(f"'{self.csr_name()}.{self.field_name}' is not RO")
        v = fd.reset_value
        if v is None or v == "UNDEFINED_LEGAL":
            self.value_error(f"'{self.csr_name()}.{self.field_name}' is not RO")
        return v


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

    def const_eval(self, symtab: SymbolTable) -> bool:
        return False

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.csr.type_check(symtab, strict=strict)
        self.expression.type_check(symtab, strict=strict)
        e_type = self.expression.type(symtab)
        if e_type.kind == TypeKind.BITS and (
            e_type.width == WIDTH_UNKNOWN or symtab.mxlen is None or e_type.width == symtab.mxlen
        ):
            return
        self.type_error("CSR value must be an XReg")

    def value(self, symtab: SymbolTable) -> Any:
        self.value_error("CSR writes are global")

    def execute(self, symtab: SymbolTable) -> Any:
        self.value_error("CSR writes are global")


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

    def csr_known(self, symtab: SymbolTable) -> bool:
        return self.csr.csr_known(symtab)

    def csr_name(self) -> str:
        return self.csr.csr_name

    def csr_def(self, symtab: SymbolTable) -> CsrLike | None:
        return self.csr.csr_def(symtab)

    def const_eval(self, symtab: SymbolTable) -> bool:
        return self.csr_known(symtab) and self.function_name == "address"

    def type_check(self, symtab: SymbolTable, *, strict: bool = False) -> None:
        self.csr.type_check(symtab, strict=strict)
        if self.function_name in ("sw_read", "address"):
            if self.args:
                self.type_error("unexpected argument(s)")
        else:
            self.type_error(f"'{self.function_name}' is not a supported CSR function call")

    def type(self, symtab: SymbolTable) -> Type:
        if self.function_name == "sw_read":
            if self.csr_known(symtab):
                length = symtab.csr(self.csr_name()).length(None)
                return Type(TypeKind.BITS, width=WIDTH_UNKNOWN if length is None else length)
            width = WIDTH_UNKNOWN if symtab.mxlen is None else symtab.mxlen
            return Type(TypeKind.BITS, width=width)
        if self.function_name == "address":
            return Type(TypeKind.BITS, width=12, qualifiers=(Qualifier.CONST, Qualifier.KNOWN))
        self.internal_error(f"No function '{self.function_name}' for CSR. call type check first!")

    def value(self, symtab: SymbolTable) -> Any:
        if self.function_name == "sw_read":
            if not self.csr_known(symtab):
                self.value_error("CSR not knowable")
            cd = self.csr_def(symtab)
            assert cd is not None
            for f in cd.fields:
                if f.type(None) != "RO":
                    self.value_error(f"{self.csr_name()}.{f.name} not RO")
            self.value_error("TODO: CSRs with sw_read function")
        if self.function_name == "address":
            if not self.csr_known(symtab):
                self.value_error("CSR not knowable")
            cd = self.csr_def(symtab)
            assert cd is not None
            return cd.address
        self.internal_error(f"TODO: {self.function_name}")
