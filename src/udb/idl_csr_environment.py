# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Architecture-backed CSR descriptors and unpinned structural base inference."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from .conditions import Condition, XlenTerm, parse_condition
from .idl.errors import IdlInternalError, IdlValueUnknown
from .solver import ConditionSolver, SolverContext, SolverStatus

if TYPE_CHECKING:
    from .architecture import ConfiguredArchitecture
    from .database import DatabaseObject


class _StructuralBases:
    """One lazy, unpinned solver per environment; no configured value assumptions."""

    def __init__(self, cfg_arch: ConfiguredArchitecture) -> None:
        self._cfg_arch = cfg_arch
        self._solver: ConditionSolver | None = None
        self._cache: dict[str, int | None] = {}
        self._compiler = None

    @property
    def compiler(self):
        if self._compiler is None:
            from .idl_architecture import ArchitectureCompiler

            self._compiler = ArchitectureCompiler(self._cfg_arch)
        return self._compiler

    def base(self, condition: Condition) -> int | None:
        key = repr(condition)
        if key in self._cache:
            return self._cache[key]
        if self._solver is None:
            arch = self._cfg_arch
            self._solver = ConditionSolver(
                SolverContext(
                    extension_versions={
                        extension.name: extension.version_set
                        for extension in arch.database.extensions
                    },
                    parameter_domains=arch.parameter_domains,
                )
            )
            # Stage 3 exposes the database invariants separately from config pins.
            for invariant, label in arch._architecture_constraints():
                self._solver.add(invariant, label)
        rv32 = self._solver.check((condition, XlenTerm(32)))
        rv64 = self._solver.check((condition, XlenTerm(64)))
        if SolverStatus.UNKNOWN in (rv32, rv64):
            raise IdlValueUnknown("CSR base restriction requires unresolved IDL conditions")
        base = (
            32
            if rv32 is SolverStatus.SAT and rv64 is SolverStatus.UNSAT
            else 64
            if rv64 is SolverStatus.SAT and rv32 is SolverStatus.UNSAT
            else None
        )
        self._cache[key] = base
        return base


class _CsrFieldAdapter:
    __slots__ = ("_data", "_field_name", "_parent")

    def __init__(
        self, field_name: str, data: Mapping[str, Any], parent: _CsrAdapter | None = None
    ) -> None:
        self._field_name = field_name
        self._data = data
        self._parent = parent

    @property
    def name(self) -> str:
        return self._field_name

    @property
    def _condition(self) -> Condition:
        if self._parent is None:
            raise IdlInternalError("CSR field presence requires its parent descriptor")
        return self._parent._condition & parse_condition(self._data.get("definedBy", True))

    @property
    def _base(self) -> int | None:
        if self._parent is None:
            raise IdlInternalError("CSR field base inference requires its parent descriptor")
        return self._parent._bases.base(self._condition)

    @property
    def defined_in_all_bases(self) -> bool:
        return self._base is None

    @property
    def defined_in_base32(self) -> bool:
        return self._base != 64

    @property
    def defined_in_base64(self) -> bool:
        return self._base != 32

    def defined_in_base(self, xlen: int) -> bool:
        if xlen not in (32, 64):
            raise ValueError("effective XLEN must be 32 or 64")
        return self._base in (None, xlen)

    @property
    def base64_only(self) -> bool:
        return self._base == 64

    @property
    def base32_only(self) -> bool:
        return self._base == 32

    def _location(self, base: int | None) -> Any:
        if base not in (None, 32, 64):
            raise ValueError("effective XLEN must be 32 or 64")
        if "location" in self._data:
            return self._data["location"]
        if base is None:
            raise ValueError(
                f"The location of {self.name} changes with XLEN; effective XLEN is required"
            )
        return self._data.get(f"location_rv{base}")

    def location(self, base: int | None = None) -> range:
        loc = self._location(base)
        if isinstance(loc, int):
            return range(loc, loc + 1)
        if isinstance(loc, str) and "-" in loc:
            hi, lo = (int(part) for part in loc.split("-", 1))
            if lo <= hi:
                return range(lo, hi + 1)
        raise IdlInternalError(f"Cannot determine field location for {self.name!r}: {loc!r}")

    def width(self, base: int | None) -> int:
        if base is None and "location" not in self._data:
            base = 32
        return len(self.location(base))

    def type(self, base: int | None) -> str | None:
        if "type" in self._data:
            return self._data["type"]
        compiled = self._parent._bases.compiler.compile_field(
            self._parent.name, self.name, "type()", effective_xlen=base
        )
        name = compiled.symtab.get("CsrFieldType").element_name(compiled.return_value())
        return {"ROH": "RO-H", "RWR": "RW-R", "RWH": "RW-H", "RWRH": "RW-RH"}.get(name, name)

    @property
    def exists(self) -> bool:
        from .architecture import QueryPresence

        if self._parent is None:
            raise IdlInternalError("CSR field presence requires its parent descriptor")
        presence = self._parent._cfg_arch.condition_presence(self._condition)
        if presence is QueryPresence.DEFERRED:
            raise IdlValueUnknown(f"Presence of CSR field {self.name} requires IDL conditions")
        return presence is not QueryPresence.ABSENT

    @property
    def reset_value(self) -> object:
        if "reset_value" in self._data:
            return self._data["reset_value"]
        from .idl.ast import Id

        compiled = self._parent._bases.compiler.compile_field(
            self._parent.name, self.name, "reset_value()"
        )
        try:
            value = compiled.return_value()
        except IdlValueUnknown as error:
            if isinstance(error.node, Id) and error.node.name in (
                "UNDEFINED_LEGAL",
                "UNDEFINED_LEGAL_DETERMINISTIC",
            ):
                return "UNDEFINED_LEGAL"
            raise
        return "UNDEFINED_LEGAL" if value == 2**64 else value


class _CsrAdapter:
    __slots__ = ("_bases", "_cfg_arch", "_record")

    def __init__(
        self,
        cfg_arch: ConfiguredArchitecture,
        record: DatabaseObject,
        bases: _StructuralBases | None = None,
    ) -> None:
        self._cfg_arch = cfg_arch
        self._record = record
        self._bases = bases if bases is not None else _StructuralBases(cfg_arch)

    @property
    def name(self) -> str:
        return self._record.name

    @property
    def address(self) -> int:
        return self._record.data["address"]

    @property
    def _condition(self) -> Condition:
        return parse_condition(self._record.data.get("definedBy", True))

    @property
    def _base(self) -> int | None:
        return self._bases.base(self._condition)

    def defined_in_base(self, xlen: int) -> bool:
        if xlen not in (32, 64):
            raise ValueError("effective XLEN must be 32 or 64")
        return self._base in (None, xlen)

    @property
    def fields(self) -> Sequence[_CsrFieldAdapter]:
        return tuple(
            _CsrFieldAdapter(name, data, self)
            for name, data in self._record.data.get("fields", {}).items()
        )

    def length(self, base: int | None = None) -> int | None:
        raw = self._record.data.get("length")
        config = self._cfg_arch.configuration
        if isinstance(raw, int):
            return raw
        if raw == "MXLEN":
            return config.mxlen if config.mxlen is not None else self._base or base
        if raw in ("SXLEN", "VSXLEN"):
            values = config.params.get(raw)
            if values is not None:
                return base if len(values) > 1 else values[0]
            return self._base or base
        if raw == "XLEN":
            return base
        raise IdlInternalError(f"Unexpected length field for CSR {self.name!r}: {raw!r}")

    def _extension_possible(self, name: str) -> bool:
        from .architecture import QueryPresence

        if not any(ext.name == name for ext in self._cfg_arch.database.extensions):
            return False
        presence = self._cfg_arch.extension_presence(name)
        if presence is QueryPresence.DEFERRED:
            raise IdlValueUnknown(f"{self.name} maximum length depends on {name} presence")
        return presence is not QueryPresence.ABSENT

    @property
    def max_length(self) -> int:
        base = self._base
        if base is not None:
            return base
        raw = self._record.data.get("length")
        config = self._cfg_arch.configuration
        if isinstance(raw, int):
            return raw
        if raw == "MXLEN":
            return config.mxlen or 64
        if raw in ("SXLEN", "VSXLEN"):
            values = config.params.get(raw)
            return max(values) if values is not None else 64
        if raw == "XLEN":
            if self._extension_possible("Sm"):
                return config.mxlen or 64
            if self._extension_possible("S"):
                return max(config.params.get("SXLEN", (config.mxlen or 64,)))
            if self._extension_possible("H"):
                return max(
                    config.params.get("VSXLEN", config.params.get("SXLEN", (config.mxlen or 64,)))
                )
            return config.mxlen or 64
        raise IdlInternalError(f"Unexpected length field for CSR {self.name!r}: {raw!r}")

    def dynamic_length(self) -> bool:
        from .idl_environment import _multi_xlen_in_mode

        raw = self._record.data.get("length")
        config = self._cfg_arch.configuration
        if isinstance(raw, int) or self._base is not None:
            return False
        if raw == "MXLEN":
            return config.mxlen is None
        if raw in ("SXLEN", "VSXLEN"):
            values = config.params.get(raw)
            return values is None or len(values) > 1
        if raw == "XLEN":
            modes = {
                "M": ("M",),
                "S": ("M", "S", "VS"),
                "U": ("M", "S", "U", "VS", "VU"),
                "VS": ("M", "S", "VS"),
                "D": ("M", "D"),
            }
            privilege = self._record.data.get("priv_mode", "M")
            if privilege not in modes:
                raise IdlInternalError(f"Unexpected CSR privilege mode: {privilege!r}")
            return any(_multi_xlen_in_mode(self._cfg_arch, mode) for mode in modes[privilege])
        raise IdlInternalError(f"Unexpected length field for CSR {self.name!r}: {raw!r}")

    @property
    def value(self) -> int | None:
        fields = self.fields
        if not all(field.type(None) == "RO" for field in fields):
            return None
        total = 0
        for field in fields:
            reset = field.reset_value
            if not isinstance(reset, int):
                return None
            total |= reset << field.location().start
        return total
