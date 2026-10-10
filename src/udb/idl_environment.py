# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Adapter: build an ``udb.idl`` :class:`~udb.idl.symbols.IdlEnvironment` from a
:class:`~udb.architecture.ConfiguredArchitecture`.

Per ``doc/stage4-idl.md``, ``udb.idl`` is not allowed to import ``udb.architecture``:
the architecture reaches the IDL compiler through an explicit protocol
(:class:`~udb.idl.symbols.IdlEnvironment`). This module is the "Stage 4
integration" adapter that builds that protocol value, and lives *outside*
``udb.idl`` for exactly that reason.

Ruby -> Python mapping
-----------------------

======================================  =========================================
Ruby (``udb/cfg_arch.rb``)              Python (this module)
======================================  =========================================
``ConfiguredArchitecture#create_symtab`` ``idl_environment()`` / ``symbol_table()``
``ConfiguredArchitecture#symtab_callbacks`` ``_builtin_funcs()``
``ConfiguredArchitecture#symtab_enums``  ``_builtin_enums()``
``ConfiguredArchitecture#mxlen``          ``cfg_arch.configuration.mxlen`` (reused as-is)
``ConfiguredArchitecture#possible_xlens`` ``possible_xlens()``
``ConfiguredArchitecture#multi_xlen?``    ``multi_xlen()``
``ConfiguredArchitecture#multi_xlen_in_mode?`` ``_multi_xlen_in_mode()``
``ConfiguredArchitecture#ext?``           ``_ext_literal()``
``ConfiguredArchitecture#prohibited_ext?`` ``_ext_prohibited()``
``Udb::Parameter#idl_type``               ``_ParameterAdapter.idl_type``
``Udb::Schema``                           ``_SchemaAdapter``
``Udb::Csr``                              ``_CsrAdapter`` (see deviations below)
``Udb::RegisterFile``                     ``_RegisterFileAdapter``
======================================  =========================================

Deviations / explicit extension points (not silently wrong)
-------------------------------------------------------------

1. **Genuine globals and includes.** Runtime and register-width bootstrap tables
   load captured ``isa/globals.isa`` and included sources through
   :mod:`udb.idl_global_environment`, then delegate registration to the ordinary
   compiler. Missing/cyclic sources and compiler errors are explicit. No repository
   paths are reopened and no bundled files replace custom sources. An optional
   post-registration hook remains available for additional caller bindings.

2. **Register-file max widths.** Ruby's ``create_symtab`` computes
   ``register_file_max_widths`` by parsing ``register_length()``, *compiling*
   it against a throwaway bootstrap symbol table, and calling ``max_value`` on
   the resulting AST. This module ports that for real:
   :func:`_register_file_max_widths` builds an analogous bootstrap
   ``SymbolTable`` (:func:`_bootstrap_builtin_funcs` -- a tri-state
   ``implemented?``/``implemented_version?`` that matches Ruby's
   ``fully_configured?``-before-``constructing_symtab?`` branch order
   exactly, *not* an unconditional "explore both branches"), parses each
   register file's body with the real parser, and evaluates it with
   :mod:`udb.idl.value_bounds` (a new, standalone port of Ruby's
   ``AstNode#max_value``/``#min_value``, kept outside ``udb.idl.ast`` itself).
   Generated predicates use ordinary registered function symbols and native
   function-call semantics. No untyped predicate-evaluation bridge remains.
   Unsupported expressions and unknown maxima raise rather than guessing;
   callers may also pass an explicit ``register_file_max_widths`` override to
   :func:`idl_environment`. Verified against the three register files that
   exist in ``spec/std/isa/register_file`` today (``X``: ``MXLEN``; ``F``:
   nested ``implemented?`` ternaries; ``V``: a parameter reference, ``VLEN``)
   across ``_``, ``rv32``, ``rv64``, and ``qc_iu``.

3. **CSR descriptors** live in :mod:`udb.idl_csr_environment`. Parent and own
   conditions govern field existence; structural base restrictions use an
   unpinned solver with database invariants, never the configured machine width.
   Lengths and static field values follow Ruby. Dynamic ``type()`` and
   ``reset_value()`` bodies use :mod:`udb.idl_architecture` and ordinary evaluation;
   unresolved values and missing source/type prerequisites remain explicit.

4. ``implemented_csr`` **callback: Ruby bug, not mirrored.** See the
   module-level docstring of :func:`_implemented_csr_callback`.

5. **Parameter-level ``requirements: idl(): ...`` invariants are not yet
   solver-visible.** Extension callbacks query the requested condition through
   :meth:`ConfiguredArchitecture.condition_presence`, but the Stage 3
   solver it calls into can only fold in *structural* (schema/extension/xlen)
   conditions today -- a parameter's own ``requirements: idl(): ...`` field
   (e.g. ``spec/std/isa/param/SXLEN.yaml``'s
   ``MXLEN == 32 -> !$array_includes?(SXLEN, 64);``) needs IDL
   statement/expression evaluation to fold into that parameter's
   :class:`~udb.domains.ParameterDomain`, which is out of scope here (same
   "needs a later slice" category as points 1-2 above, just discovered while
   verifying this module against the Ruby oracle rather than being a
   documented extension point from the start). Concretely, this means
   extensions that are *only* prohibited via such a cross-parameter
   constraint (``Sv39``/``Sv48``/``Sv57``/``Svnapot``/``Svpbmt``/
   ``Svrsw60t59b``/``Svukte`` under ``rv32``, all transitively gated by
   ``Sv39``'s ``param: SXLEN includes 64`` requirement) report ``None``
   ("unknown") where Ruby's IDL-backed solver reports ``False``
   ("prohibited") -- never the wrong answer, just a currently-undecidable
   one. No workaround is implemented here; fixing it belongs in
   ``src/udb/architecture.py``/``domains.py`` once parameter ``idl()``
   requirements can be evaluated.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from . import idl_csr_environment as _csr_environment
from .conditions import AnyOf, ExtensionTerm, parse_condition
from .configuration import ConfigurationKind, Presence
from .idl import value_bounds
from .idl.ast import ReturnStatement
from .idl.errors import IdlInternalError
from .idl.parser import parse_function_body
from .idl.symbols import (
    BuiltinFunctionCallbacks,
    EnumDef,
    IdlEnvironment,
    SymbolTable,
    Var,
)
from .idl.types import Type, TypeKind
from .idl_csr_environment import _CsrAdapter, _StructuralBases
from .versions import VersionRequirement

if TYPE_CHECKING:
    from .architecture import ConfiguredArchitecture
    from .configuration import ExtensionSelection
    from .database import DatabaseObject, ResolvedDatabase

__all__ = [
    "condition_symbol_table",
    "idl_environment",
    "symbol_table",
]

_CsrFieldAdapter = _csr_environment._CsrFieldAdapter

_MODES = ("S", "U", "VS", "VU")
_MODE_EXTENSION = {"S": "S", "U": "U", "VS": "H", "VU": "H"}
_MODE_PARAM = {"S": "SXLEN", "U": "UXLEN", "VS": "VSXLEN", "VU": "VUXLEN"}


# ---------------------------------------------------------------------------
# Schema / parameter adapters (SchemaLike / RuntimeParamLike)
# ---------------------------------------------------------------------------


class _SchemaAdapter:
    """Structural port of ``Udb::Schema`` (``udb/schema.rb``). Implements ``SchemaLike``."""

    __slots__ = ("_schema",)

    def __init__(self, schema: Mapping[str, Any]) -> None:
        self._schema = schema

    @property
    def to_idl_type(self) -> Type:
        idl_type = Type.from_json_schema(self._schema)
        if idl_type is None:
            raise IdlInternalError(f"Cannot convert schema {self._schema!r} to an IDL type")
        return idl_type

    @property
    def max_val_known(self) -> bool:
        return self.to_idl_type.kind is TypeKind.BITS and (
            "const" in self._schema or "maximum" in self._schema or "enum" in self._schema
        )

    @property
    def max_val(self) -> int:
        if "const" in self._schema:
            return self._schema["const"]
        if "enum" in self._schema:
            return max(self._schema["enum"])
        if "maximum" in self._schema:
            return self._schema["maximum"]
        raise IdlInternalError("Schema max_val is not known")

    @property
    def min_val_known(self) -> bool:
        return self.to_idl_type.kind is TypeKind.BITS and (
            "const" in self._schema or "minimum" in self._schema or "enum" in self._schema
        )

    @property
    def min_val(self) -> int:
        if "const" in self._schema:
            return self._schema["const"]
        if "enum" in self._schema:
            return min(self._schema["enum"])
        if "minimum" in self._schema:
            return self._schema["minimum"]
        raise IdlInternalError("Schema min_val is not known")


_UNSET = object()


class _ParameterAdapter:
    """Structural port of ``Udb::Parameter``/``Udb::ParameterWithValue``. Implements ``RuntimeParamLike``."""

    __slots__ = ("_record", "_value")

    def __init__(self, record: DatabaseObject, value: object = _UNSET) -> None:
        self._record = record
        self._value = value

    @property
    def name(self) -> str:
        return self._record.name

    @property
    def description(self) -> str:
        return self._record.data.get("description", "")

    @property
    def schema(self) -> _SchemaAdapter:
        return _SchemaAdapter(self._record.data["schema"])

    @property
    def value_known(self) -> bool:
        return self._value is not _UNSET

    @property
    def value(self) -> object:
        return None if self._value is _UNSET else self._value

    @property
    def idl_type(self) -> Type:
        # Mirrors `Parameter#idl_type = schema.to_idl_type.make_const.freeze`.
        return self.schema.to_idl_type.make_const()


def _all_params(cfg_arch: ConfiguredArchitecture) -> list[_ParameterAdapter]:
    """Port of ``create_symtab``'s ``all_params``: every DB param, with or without a config value.

    Unlike ``ConfiguredArchitecture.parameters_without_values``/``out_of_scope_parameters``
    (which filter by solver-derived presence), Ruby's ``all_params`` does *no* such
    filtering -- it is every parameter in the database, partitioned only by whether the
    configuration happens to declare a value for it. This mirrors that exactly.
    """
    config_params = cfg_arch.configuration.params
    records = cfg_arch.database.objects("parameter")
    by_name = {record.name: record for record in records}

    result: list[_ParameterAdapter] = []
    for name, value in config_params.items():
        record = by_name.get(name)
        if record is not None:
            result.append(_ParameterAdapter(record, value))
    result.extend(
        _ParameterAdapter(record) for record in records if record.name not in config_params
    )
    return result


def _param_var(param: _ParameterAdapter) -> Var:
    idl_type = param.idl_type
    if param.value_known:
        return Var(param.name, idl_type, param.value, param=True)
    return Var(param.name, idl_type, param=True)


# ---------------------------------------------------------------------------
# Builtin enums
# ---------------------------------------------------------------------------


def _builtin_enums(database: ResolvedDatabase) -> tuple[EnumDef, ...]:
    """Port of ``symtab_enums``: ``ExtensionName``, ``ExceptionCode``, ``InterruptCode``.

    All three are built from the *entire* unfiltered database (not just what's
    possible/mandatory under this configuration), exactly like Ruby.
    """
    extensions = database.extensions
    extension_name = EnumDef(
        name="ExtensionName",
        element_values=tuple(range(1, len(extensions) + 1)),
        element_names=tuple(extension.name for extension in extensions),
    )

    exception_codes = database.objects("exception_code")
    exception_code = EnumDef(
        name="ExceptionCode",
        element_values=tuple(record.data["num"] for record in exception_codes),
        element_names=tuple(record.name for record in exception_codes),
    )

    interrupt_codes = database.objects("interrupt_code")
    interrupt_code = EnumDef(
        name="InterruptCode",
        element_values=tuple(record.data["num"] for record in interrupt_codes),
        element_names=tuple(record.name for record in interrupt_codes),
    )
    return (extension_name, exception_code, interrupt_code)


# ---------------------------------------------------------------------------
# implemented? / implemented_version? / implemented_csr? callbacks
# ---------------------------------------------------------------------------


def _selection_matches(
    cfg_arch: ConfiguredArchitecture,
    selection: ExtensionSelection,
    name: str,
    version: str | None,
) -> bool:
    """Whether config *selection* covers extension *name* at *version* (or any version).

    *version*, when given, is a **version requirement string** (e.g.
    ``"<= 1.9.1"``, matching how real IDL calls ``implemented_version?()`` --
    see e.g. ``spec/std/isa/isa/interrupts.idl``) -- not a bare version.

    Faithful, literal (non-solver) port of the version-matching half of
    Ruby's ``ext?``: when *version* is given, Ruby checks that *every*
    version satisfying the selection's own requirement also satisfies the
    query (``e.satisfying_versions.all? { requirement.satisfied_by?(it) }``
    for partial configs; an exact ``=`` pin for full configs, which reduces
    to the same check since a pinned selection's own "satisfying versions"
    is always exactly that one version). Reusing the extension's real
    version set keeps this exact rather than approximate.
    """
    if selection.name != name:
        return False
    if version is None:
        return True
    extension = cfg_arch.database.extension(name)
    query = VersionRequirement.parse(version)
    satisfying = [
        v
        for v in extension.versions
        if all(req.matches(v.version) for req in selection.requirements)
    ]
    return bool(satisfying) and all(query.matches(v.version) for v in satisfying)


def _ext_literal(cfg_arch: ConfiguredArchitecture, name: str, version: str | None = None) -> bool:
    """Port of ``ConfiguredArchitecture#ext?``: a literal (non-solver) closed-world lookup."""
    config = cfg_arch.configuration
    if config.kind is ConfigurationKind.FULL:
        return any(_selection_matches(cfg_arch, sel, name, version) for sel in config.extensions)
    if config.kind is ConfigurationKind.PARTIAL:
        return any(
            _selection_matches(cfg_arch, sel, name, version)
            for sel in config.extensions
            if sel.presence is Presence.MANDATORY
        )
    return False


def _ext_prohibited(cfg_arch: ConfiguredArchitecture, name: str) -> bool:
    """An extension is prohibited only when its entire requested condition is absent."""
    from .architecture import QueryPresence

    if not any(extension.name == name for extension in cfg_arch.database.extensions):
        return True
    return cfg_arch.condition_presence(ExtensionTerm(name)) is QueryPresence.ABSENT


def _implemented(cfg_arch: ConfiguredArchitecture) -> Callable[[str], bool | None]:
    def callback(name: str) -> bool | None:
        return _presence_value(cfg_arch.condition_presence(ExtensionTerm(name)))

    return callback


def _implemented_version(cfg_arch: ConfiguredArchitecture) -> Callable[[str, str], bool | None]:
    """``version`` is a version *requirement* string (e.g. ``"<= 1.9.1"``), matching how
    real IDL calls ``implemented_version?()`` -- not a bare version.
    """

    def callback(name: str, version: str) -> bool | None:
        condition = ExtensionTerm(name, (VersionRequirement.parse(version),))
        return _presence_value(cfg_arch.condition_presence(condition))

    return callback


def _presence_value(presence: Any) -> bool | None:
    from .architecture import QueryPresence

    if presence is QueryPresence.MANDATORY:
        return True
    if presence is QueryPresence.ABSENT:
        return False
    return None


def _implemented_csr_callback(cfg_arch: ConfiguredArchitecture) -> Callable[[int], bool | None]:
    """Port of ``symtab_callbacks``'s ``implemented_csr:`` -- with a confirmed Ruby bug fixed.

    Ruby's version (``cfg_arch.rb``, ``symtab_callbacks``)::

        implemented_csr: (
          Idl::SymbolTable.make_implemented_csr_callback do |csr_addr|
            if fully_configured?
              if implemented_csrs.any? { |c| c.address == csr_addr }
                true
              end
            else
              if not_prohibited_csrs.none? { |c| c.address == csr_addr }
                false
              end
            end
          end
        )

    Both branches are missing an ``else``: for a *fully configured* arch this
    can only ever return ``true`` or ``nil`` (never ``false``, even though a
    closed-world config should be able to say "definitely not implemented");
    for a *partially configured* arch it can only ever return ``false`` or
    ``nil`` (never ``true``, even though ``csrs_that_must_be_implemented``
    exists and mirrors the ``implemented``/``implemented_version`` pattern
    used everywhere else in this same method). This is not mirrored: Python
    uses ``ConfiguredArchitecture.object_presence`` (already solver-backed,
    and exactly what ``defined_by_condition.satisfied_by_cfg_arch?``/
    ``satisfiable_by_cfg_arch?`` compute in Ruby) symmetrically for both
    config kinds, so both ``true`` and ``false`` are reachable whenever the
    presence is actually decidable.
    """
    csrs_by_address: dict[int, list[DatabaseObject]] = {}
    for record in cfg_arch.database.objects("csr"):
        address = record.data.get("address")
        if isinstance(address, int):
            csrs_by_address.setdefault(address, []).append(record)

    def callback(csr_addr: int) -> bool | None:
        records = csrs_by_address.get(csr_addr, ())
        if not records:
            return False
        condition = AnyOf(
            tuple(parse_condition(record.data.get("definedBy", True)) for record in records)
        )
        return _presence_value(cfg_arch.condition_presence(condition))

    return callback


def _builtin_funcs(cfg_arch: ConfiguredArchitecture) -> BuiltinFunctionCallbacks:
    return BuiltinFunctionCallbacks(
        implemented=_implemented(cfg_arch),
        implemented_version=_implemented_version(cfg_arch),
        implemented_csr=_implemented_csr_callback(cfg_arch),
    )


# ---------------------------------------------------------------------------
# mxlen / possible_xlens
# ---------------------------------------------------------------------------


def _param_size(cfg_arch: ConfiguredArchitecture, name: str) -> int:
    value = cfg_arch.configuration.params.get(name)
    if value is None:
        return 0
    if isinstance(value, (list, tuple)):
        return len(value)
    return 1


def _multi_xlen_in_mode(cfg_arch: ConfiguredArchitecture, mode: str) -> bool:
    """Port of ``ConfiguredArchitecture#multi_xlen_in_mode?``."""
    config = cfg_arch.configuration
    mxlen = config.mxlen
    if mxlen == 32:
        return False
    if mode in ("M", "D"):
        return mxlen is None

    extension = _MODE_EXTENSION[mode]
    param = _MODE_PARAM[mode]

    if mode == "S":
        if config.kind is ConfigurationKind.UNCONFIGURED:
            return True
        if config.kind is ConfigurationKind.FULL:
            return _ext_literal(cfg_arch, extension) and _param_size(cfg_arch, param) > 1
        if _ext_prohibited(cfg_arch, extension):
            return False
        if not _ext_literal(cfg_arch, extension):
            return True
        if param not in config.params:
            return True
        return _param_size(cfg_arch, param) > 1

    # U, VS, VU: the prohibited-extension check happens *before* the
    # unconfigured check (matches Ruby's ordering exactly; the asymmetry
    # with the "S" branch above is in Ruby too, not a porting mistake).
    if _ext_prohibited(cfg_arch, extension):
        return False
    if config.kind is ConfigurationKind.UNCONFIGURED:
        return True
    if config.kind is ConfigurationKind.FULL:
        return _ext_literal(cfg_arch, extension) and _param_size(cfg_arch, param) > 1
    if not _ext_literal(cfg_arch, extension):
        return True
    if param not in config.params:
        return True
    return _param_size(cfg_arch, param) > 1


def multi_xlen(cfg_arch: ConfiguredArchitecture) -> bool:
    """Port of ``ConfiguredArchitecture#multi_xlen?``."""
    if cfg_arch.configuration.mxlen is None:
        return True
    return any(_multi_xlen_in_mode(cfg_arch, mode) for mode in _MODES)


def possible_xlens(cfg_arch: ConfiguredArchitecture) -> tuple[int, ...]:
    """Port of ``ConfiguredArchitecture#possible_xlens``."""
    if multi_xlen(cfg_arch):
        return (32, 64)
    mxlen = cfg_arch.configuration.mxlen
    assert mxlen is not None  # multi_xlen() is True whenever mxlen is None
    return (mxlen,)


# ---------------------------------------------------------------------------
# Register files
# ---------------------------------------------------------------------------


class _RegisterFileAdapter:
    """Structural port of ``Udb::RegisterFile``. Implements ``RegisterFileLike``."""

    __slots__ = ("_record",)

    def __init__(self, record: DatabaseObject) -> None:
        self._record = record

    @property
    def name(self) -> str:
        return self._record.name

    @property
    def register_length(self) -> str:
        return self._record.data["register_length()"]

    @property
    def registers(self) -> Sequence[object]:
        return self._record.data.get("registers", [])


def _bootstrap_builtin_funcs(cfg_arch: ConfiguredArchitecture) -> BuiltinFunctionCallbacks:
    """``implemented?``/``implemented_version?`` as ``create_symtab``'s *bootstrap* symtab
    sees them while computing ``register_file_max_widths`` -- a **different** tri-state
    than the real, steady-state :func:`_builtin_funcs` used everywhere else.

    Ruby's ``symtab_callbacks`` (cfg_arch.rb ~502-544) branches on
    ``fully_configured?`` *before* ever consulting ``constructing_symtab?``: for a fully
    configured arch, ``implemented?()`` is exactly as deterministic during bootstrap as
    at steady state (``ext?(ext_name)``, no ``nil``). Only for a *partially configured or
    unconfigured* arch does ``constructing_symtab?`` force ``nil`` (unknown) -- and only
    when ``ext?`` is already ``false`` (``elsif constructing_symtab?`` comes *after* the
    ``if ext?(ext_name) then true`` check, and *before* ``prohibited_ext?`` would
    otherwise be consulted). This is why, e.g., a fully configured arch's register file
    can have a *smaller* max width than a partially configured one's: bootstrap forces
    the "explore both ternary branches" worst case only for the latter.

    ``implemented_csr?`` needs no bootstrap variant: Ruby's callback for it never checks
    ``constructing_symtab?`` at all, so :func:`_implemented_csr_callback` (steady state)
    is reused unchanged.
    """

    def implemented(name: str) -> bool | None:
        if cfg_arch.configuration.kind is ConfigurationKind.FULL:
            return _ext_literal(cfg_arch, name)
        return True if _ext_literal(cfg_arch, name) else None

    def implemented_version(name: str, version: str) -> bool | None:
        if cfg_arch.configuration.kind is ConfigurationKind.FULL:
            return _ext_literal(cfg_arch, name, version)
        return True if _ext_literal(cfg_arch, name, version) else None

    return BuiltinFunctionCallbacks(
        implemented=implemented,
        implemented_version=implemented_version,
        implemented_csr=_implemented_csr_callback(cfg_arch),
    )


def _register_length_expression(rf: _RegisterFileAdapter) -> Any:
    """Parse ``rf``'s ``register_length()`` IDL function body (real parser) and return
    its single ``return`` expression. Mirrors the shape ``create_symtab`` compiles.
    """
    body = parse_function_body(rf.register_length)
    if len(body.stmts) != 1 or not isinstance(body.stmts[0], ReturnStatement):
        raise IdlInternalError(
            f"register_length() body for {rf.name!r} is not a single return statement: "
            f"{rf.register_length!r}"
        )
    (expr,) = body.stmts[0].return_expression.return_value_nodes
    return expr


def _register_file_max_width(rf: _RegisterFileAdapter, bootstrap_symtab: SymbolTable) -> int:
    """Port of ``create_symtab``'s per-register-file ``rf_max_widths`` computation:
    parse the real ``register_length()`` body, type-check it, and take
    :func:`value_bounds.max_value` against a *bootstrap* symbol table (see
    :func:`_bootstrap_builtin_funcs`).

    Function signatures must be registered normally; unsupported compiler paths
    and unknown widths are not suppressed.
    """
    expr = _register_length_expression(rf)
    expr.type_check(bootstrap_symtab)
    max_width = value_bounds.max_value(expr, bootstrap_symtab)
    if max_width == value_bounds.UNKNOWN:
        raise IdlInternalError(
            f"Cannot determine max width for register file {rf.name!r} "
            f"(register_length() body: {rf.register_length!r})"
        )
    if not isinstance(max_width, int):
        raise IdlInternalError(f"Unexpected max_value result for {rf.name!r}: {max_width!r}")
    return max_width


def _register_file_max_widths(
    cfg_arch: ConfiguredArchitecture,
    register_files: Sequence[_RegisterFileAdapter],
    params: Sequence[_ParameterAdapter],
    mxlen: int | None,
    overrides: Mapping[str, int] | None,
) -> dict[str, int]:
    """Port of ``create_symtab``'s ``rf_max_widths`` local (cfg_arch.rb ~615-638): builds
    a throwaway bootstrap ``SymbolTable`` (params, mxlen, enums, and the bootstrap-tri-state
    builtin callbacks from :func:`_bootstrap_builtin_funcs` -- *not* the real environment's),
    then compiles and evaluates each register file's ``register_length()`` against it.
    """
    if all(rf.name in (overrides or {}) for rf in register_files):
        return dict(overrides or {})

    bootstrap_env = IdlEnvironment(
        mxlen=mxlen,
        possible_xlens_cb=lambda: possible_xlens(cfg_arch),
        builtin_global_vars=tuple(_param_var(param) for param in params),
        builtin_enums=_builtin_enums(cfg_arch.database),
        builtin_funcs=_bootstrap_builtin_funcs(cfg_arch),
        csrs=(),
        params=tuple(params),
        name=f"{cfg_arch.name}/bootstrap",
        register_files=(),
        register_file_max_widths={},
    )
    bootstrap_symtab = SymbolTable(bootstrap_env)
    from .idl_condition_environment import add_predicate_signatures
    from .idl_global_environment import global_ast

    globals_ast = global_ast(cfg_arch.database)
    if globals_ast is None:
        add_predicate_signatures(bootstrap_symtab)
    else:
        globals_ast.add_global_symbols(bootstrap_symtab)

    widths: dict[str, int] = dict(overrides or {})
    for rf in register_files:
        if rf.name in widths:
            continue
        widths[rf.name] = _register_file_max_width(rf, bootstrap_symtab)
    return widths


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def idl_environment(
    cfg_arch: ConfiguredArchitecture,
    *,
    register_file_max_widths: Mapping[str, int] | None = None,
) -> IdlEnvironment:
    """Build an :class:`~udb.idl.symbols.IdlEnvironment` for *cfg_arch*.

    Port of ``ConfiguredArchitecture#create_symtab``. See the module
    docstring for what is deliberately left as an extension point.

    Args:
        cfg_arch: The configured architecture to build an environment for.
        register_file_max_widths: Optional override/pre-seed for register files
            whose IDL body requires unavailable compiler semantics. Takes priority
            over the parsed expression's max_value result.
    """
    params = _all_params(cfg_arch)
    builtin_global_vars = tuple(_param_var(param) for param in params)

    register_files = tuple(
        _RegisterFileAdapter(record) for record in cfg_arch.database.objects("register_file")
    )
    mxlen = cfg_arch.configuration.mxlen
    max_widths = _register_file_max_widths(
        cfg_arch, register_files, params, mxlen, register_file_max_widths
    )

    bases = _StructuralBases(cfg_arch)
    csrs = tuple(
        _CsrAdapter(cfg_arch, record, bases) for record in cfg_arch.database.objects("csr")
    )

    return IdlEnvironment(
        mxlen=mxlen,
        possible_xlens_cb=lambda: possible_xlens(cfg_arch),
        builtin_global_vars=builtin_global_vars,
        builtin_enums=_builtin_enums(cfg_arch.database),
        builtin_funcs=_builtin_funcs(cfg_arch),
        csrs=csrs,
        params=tuple(params),
        name=cfg_arch.name,
        register_files=register_files,
        register_file_max_widths=max_widths,
    )


def condition_symbol_table(resolved_database: ResolvedDatabase) -> SymbolTable:
    """Build an isolated symbolic table for condition translation.

    No configuration, solver, register files, CSR evaluation or specialized globals
    are accessed. Generated predicate signatures use normal ``FunctionType`` symbols;
    parsing/type-checking/calls remain the responsibility of the IDL compiler.
    """
    from .idl_condition_environment import add_encoding_size_constant, add_predicate_signatures

    if not resolved_database.is_resolved:
        raise TypeError("condition_symbol_table requires a resolved database")
    params = tuple(_ParameterAdapter(record) for record in resolved_database.objects("parameter"))
    callbacks = BuiltinFunctionCallbacks(
        implemented=lambda name: None,
        implemented_version=lambda name, version: None,
        implemented_csr=lambda address: None,
    )
    env = IdlEnvironment(
        builtin_global_vars=tuple(_param_var(param) for param in params),
        builtin_enums=_builtin_enums(resolved_database),
        builtin_funcs=callbacks,
        params=params,
        name="conditions",
    )
    symtab = SymbolTable(env)
    add_predicate_signatures(symtab)
    add_encoding_size_constant(resolved_database, symtab)
    return symtab


def symbol_table(
    cfg_arch: ConfiguredArchitecture,
    *,
    register_file_max_widths: Mapping[str, int] | None = None,
    add_global_symbols: Callable[[SymbolTable], None] | None = None,
) -> SymbolTable:
    """Build a :class:`~udb.idl.symbols.SymbolTable` for *cfg_arch*.

    Args:
        cfg_arch: The configured architecture to build a symbol table for.
        register_file_max_widths: See :func:`idl_environment`.
        add_global_symbols: Optional additional post-construction hook, after
            genuine captured globals and includes have been registered.
    """
    from .idl_condition_environment import add_predicate_signatures
    from .idl_global_environment import global_ast

    env = idl_environment(cfg_arch, register_file_max_widths=register_file_max_widths)
    symtab = SymbolTable(env)
    globals_ast = global_ast(cfg_arch.database)
    if globals_ast is None:
        add_predicate_signatures(symtab)
    else:
        globals_ast.add_global_symbols(symtab)
    if add_global_symbols is not None:
        add_global_symbols(symtab)
    return symtab
