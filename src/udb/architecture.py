# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Configured architecture queries over YAML and compiled symbolic IDL conditions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self

from .conditions import (
    Condition,
    EvaluationContext,
    ExtensionTerm,
    ParameterOperator,
    ParameterTerm,
    XlenTerm,
    all_of,
    implies,
    negate,
    parse_condition,
)
from .configuration import Configuration, ConfigurationKind, Presence
from .database import Csr, DatabaseObject, Extension, Instruction, ResolvedDatabase, _freeze
from .domains import DomainError, ParameterDomain
from .errors import DataError, ObjectNotFoundError
from .idl.errors import IdlError
from .idl_condition_binding import IdlConditionBinding
from .schema import SchemaStore
from .solver import (
    ConditionModel,
    ConditionSolver,
    SolverContext,
    SolverError,
    SolverStatus,
    SolverUnknownError,
)
from .source import SourceMap
from .versions import ExtensionVersion, VersionRequirement, parse_version_requirements

if TYPE_CHECKING:
    from .idl_architecture import CompiledIdl


class ArchitectureError(DataError):
    """A configured query cannot be performed on the supplied architecture."""


class ArchitectureCheckStatus(StrEnum):
    VALID = "valid"
    UNSAT = "unsat"
    DEFERRED = "deferred"


class QueryPresence(StrEnum):
    """Proof status for a record or extension under a configuration."""

    MANDATORY = "mandatory"
    POSSIBLE = "possible"
    ABSENT = "absent"
    DEFERRED = "deferred"


@dataclass(frozen=True, slots=True)
class ArchitectureDiagnostic:
    code: str
    message: str
    label: str | None = None
    source: str | None = None


@dataclass(frozen=True, slots=True)
class ArchitectureCheck:
    status: ArchitectureCheckStatus
    diagnostics: tuple[ArchitectureDiagnostic, ...] = ()
    model: ConditionModel | None = None
    conflict: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return self.status is ArchitectureCheckStatus.VALID


@dataclass(frozen=True, slots=True)
class DeferredQuery:
    """An explicit Stage 4 boundary for a query that needs IDL semantics."""

    operation: str
    reason: str
    source: str | None = None


@dataclass(frozen=True, slots=True)
class CsrField:
    """An immutable CSR-field view with its effective presence condition."""

    csr: Csr
    name: str
    data: Mapping[str, Any] = field(repr=False)
    condition: Condition = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", _freeze(self.data))


@dataclass(frozen=True, slots=True)
class ConfiguredArchitecture:
    """An immutable configured view of one resolved database.

    Each instance owns one incremental solver.  No results or symbolic state
    are shared between configured architectures.
    """

    database: ResolvedDatabase
    configuration: Configuration
    parameter_domains: Mapping[str, ParameterDomain] = field(init=False, repr=False)
    _catalog: Mapping[str, Any] = field(init=False, repr=False, compare=False)
    _solver: ConditionSolver | None = field(init=False, repr=False, compare=False)
    _base_status: SolverStatus | None = field(init=False, repr=False, compare=False)
    _constraints: tuple[tuple[Condition, str], ...] = field(init=False, repr=False, compare=False)
    _static_diagnostics: tuple[ArchitectureDiagnostic, ...] = field(
        init=False, repr=False, compare=False
    )
    _condition_binding: IdlConditionBinding = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.database, ResolvedDatabase):
            raise TypeError("ConfiguredArchitecture requires a ResolvedDatabase")
        if not isinstance(self.configuration, Configuration):
            raise TypeError("ConfiguredArchitecture requires an explicit Configuration")
        object.__setattr__(
            self, "_condition_binding", IdlConditionBinding(self.database, self.configuration)
        )

        diagnostics: list[ArchitectureDiagnostic] = []
        catalog = {extension.name: extension.version_set for extension in self.database.extensions}
        domains = self._load_parameter_domains(diagnostics)
        object.__setattr__(self, "parameter_domains", MappingProxyType(domains))
        object.__setattr__(self, "_catalog", MappingProxyType(catalog))
        constraints: list[tuple[Condition, str]] = []
        self._add_architecture_invariants(constraints, diagnostics)
        self._add_configuration_constraints(constraints, diagnostics, catalog, domains)

        solver: ConditionSolver | None = None
        base_status: SolverStatus | None = None
        if not diagnostics:
            try:
                solver = ConditionSolver(
                    SolverContext(extension_versions=catalog, parameter_domains=domains)
                )
                for condition, label in constraints:
                    solver.add(condition, label)
                base_status = solver.check()
            except SolverError as error:
                diagnostics.append(
                    ArchitectureDiagnostic(
                        "solver-error", str(error), source=self.configuration.name
                    )
                )

        object.__setattr__(self, "_constraints", tuple(constraints))
        object.__setattr__(self, "_static_diagnostics", tuple(diagnostics))
        object.__setattr__(self, "_solver", solver)
        object.__setattr__(self, "_base_status", base_status)

    @classmethod
    def create(cls, database: ResolvedDatabase, configuration: Configuration) -> Self:
        return cls(database, configuration)

    @property
    def name(self) -> str:
        return self.configuration.name

    @property
    def kind(self) -> ConfigurationKind:
        return self.configuration.kind

    @property
    def evaluation_context(self) -> EvaluationContext:
        exact: dict[str, str] = {}
        if self.kind is ConfigurationKind.FULL:
            for selection in self.configuration.extensions:
                matching = self._matching_versions(selection.name, selection.requirements)
                if len(matching) == 1:
                    exact[selection.name] = matching[0].canonical
        return EvaluationContext(
            extensions=exact,
            parameters=self.configuration.params,
            xlen=32 if self.configuration.params.get("MXLEN") == 32 else None,
            version_sets=self._catalog,
            closed_world_extensions=self.kind is ConfigurationKind.FULL,
            closed_world_parameters=self.kind is ConfigurationKind.FULL,
        )

    def check(self) -> ArchitectureCheck:
        """Check configuration consistency, including compiled IDL requirements."""

        if self._static_diagnostics:
            return ArchitectureCheck(ArchitectureCheckStatus.UNSAT, self._static_diagnostics)
        solver = self._require_solver()
        status = self._base_status or solver.check()
        if status is SolverStatus.UNSAT:
            conflict = solver.minimal_conflict()
            message = "configuration constraints are mutually unsatisfiable"
            if conflict:
                message += ": " + ", ".join(conflict)
            return ArchitectureCheck(
                ArchitectureCheckStatus.UNSAT,
                (ArchitectureDiagnostic("unsatisfiable", message),),
                conflict=conflict,
            )
        if status is SolverStatus.UNKNOWN:
            return ArchitectureCheck(
                ArchitectureCheckStatus.DEFERRED,
                (ArchitectureDiagnostic("solver-unknown", "the solver could not decide validity"),),
            )

        return _checked_model(solver)

    def condition_presence(self, condition: Condition | bool | Mapping[str, Any]) -> QueryPresence:
        """Classify whether *condition* is necessary, possible, or impossible."""

        self._ensure_queryable()
        parsed = self._resolve_condition(parse_condition(condition))
        solver = self._require_solver()
        possible = solver.check((parsed,))
        if possible is SolverStatus.UNSAT:
            return QueryPresence.ABSENT
        mandatory = solver.check((negate(parsed),))
        if mandatory is SolverStatus.UNSAT:
            return QueryPresence.MANDATORY
        if possible is SolverStatus.UNKNOWN or mandatory is SolverStatus.UNKNOWN:
            return QueryPresence.DEFERRED
        return QueryPresence.POSSIBLE

    def extension_presence(
        self,
        name: str,
        version: str | Sequence[str] | None = None,
    ) -> QueryPresence:
        self._require_extension(name)
        return self.condition_presence(ExtensionTerm(name, parse_version_requirements(version)))

    def possible_extension_versions(self, name: str) -> tuple[ExtensionVersion, ...]:
        return self._extension_versions_with(
            name, {QueryPresence.MANDATORY, QueryPresence.POSSIBLE}
        )

    def mandatory_extension_versions(self, name: str) -> tuple[ExtensionVersion, ...]:
        return self._extension_versions_with(name, {QueryPresence.MANDATORY})

    def absent_extension_versions(self, name: str) -> tuple[ExtensionVersion, ...]:
        return self._extension_versions_with(name, {QueryPresence.ABSENT})

    @property
    def possible_extensions(self) -> tuple[Extension, ...]:
        return tuple(
            extension
            for extension in self.database.extensions
            if self.extension_presence(extension.name)
            in (QueryPresence.MANDATORY, QueryPresence.POSSIBLE)
        )

    @property
    def mandatory_extensions(self) -> tuple[Extension, ...]:
        return tuple(
            extension
            for extension in self.database.extensions
            if self.extension_presence(extension.name) is QueryPresence.MANDATORY
        )

    @property
    def absent_extensions(self) -> tuple[Extension, ...]:
        return tuple(
            extension
            for extension in self.database.extensions
            if self.extension_presence(extension.name) is QueryPresence.ABSENT
        )

    def parameter_domain(self, name: str) -> ParameterDomain:
        try:
            return self.parameter_domains[name]
        except KeyError as error:
            raise ObjectNotFoundError(f"No 'parameter' object named {name!r}") from error

    def validate_parameter_value(self, name: str, value: object) -> bool:
        return self.parameter_domain(name).accepts(value)

    @property
    def parameters_with_values(self) -> tuple[DatabaseObject, ...]:
        return tuple(
            parameter
            for parameter in self.database.objects("parameter")
            if parameter.name in self.configuration.params
        )

    @property
    def parameters_without_values(self) -> tuple[DatabaseObject, ...]:
        return tuple(
            parameter
            for parameter in self.database.objects("parameter")
            if parameter.name not in self.configuration.params
            and self.condition_presence(self._defined_by(parameter))
            in (QueryPresence.MANDATORY, QueryPresence.POSSIBLE)
        )

    @property
    def out_of_scope_parameters(self) -> tuple[DatabaseObject, ...]:
        return tuple(
            parameter
            for parameter in self.database.objects("parameter")
            if self.condition_presence(self._defined_by(parameter)) is QueryPresence.ABSENT
        )

    def object_presence(self, record: DatabaseObject | CsrField) -> QueryPresence:
        condition = record.condition if isinstance(record, CsrField) else self._defined_by(record)
        return self.condition_presence(condition)

    def objects_with_presence(
        self, kind: str, *presences: QueryPresence
    ) -> tuple[DatabaseObject, ...]:
        accepted = set(presences) or {QueryPresence.MANDATORY, QueryPresence.POSSIBLE}
        return tuple(
            record
            for record in self.database.objects(kind)
            if self.object_presence(record) in accepted
        )

    def possible_objects(self, kind: str) -> tuple[DatabaseObject, ...]:
        return self.objects_with_presence(kind, QueryPresence.MANDATORY, QueryPresence.POSSIBLE)

    def mandatory_objects(self, kind: str) -> tuple[DatabaseObject, ...]:
        return self.objects_with_presence(kind, QueryPresence.MANDATORY)

    def absent_objects(self, kind: str) -> tuple[DatabaseObject, ...]:
        return self.objects_with_presence(kind, QueryPresence.ABSENT)

    @property
    def possible_instructions(self) -> tuple[Instruction, ...]:
        return self.possible_objects("instruction")  # type: ignore[return-value]

    @property
    def mandatory_instructions(self) -> tuple[Instruction, ...]:
        return self.mandatory_objects("instruction")  # type: ignore[return-value]

    @property
    def absent_instructions(self) -> tuple[Instruction, ...]:
        return self.absent_objects("instruction")  # type: ignore[return-value]

    @property
    def possible_csrs(self) -> tuple[Csr, ...]:
        return self.possible_objects("csr")  # type: ignore[return-value]

    @property
    def mandatory_csrs(self) -> tuple[Csr, ...]:
        return self.mandatory_objects("csr")  # type: ignore[return-value]

    @property
    def absent_csrs(self) -> tuple[Csr, ...]:
        return self.absent_objects("csr")  # type: ignore[return-value]

    @property
    def possible_exception_codes(self) -> tuple[DatabaseObject, ...]:
        return self.possible_objects("exception_code")

    @property
    def possible_interrupt_codes(self) -> tuple[DatabaseObject, ...]:
        return self.possible_objects("interrupt_code")

    def csr_fields(self, csr: str | Csr) -> tuple[CsrField, ...]:
        record = self.database.csr(csr) if isinstance(csr, str) else csr
        parent = self._defined_by(record)
        fields = record.data.get("fields", {})
        if not isinstance(fields, Mapping):
            return ()
        result: list[CsrField] = []
        for name, data in fields.items():
            if not isinstance(name, str) or not isinstance(data, Mapping):
                continue
            local = self._condition(
                data.get("definedBy", True), record, ("fields", name, "definedBy")
            )
            result.append(CsrField(record, name, data, all_of(parent, local)))
        return tuple(result)

    def possible_csr_fields(self, csr: str | Csr) -> tuple[CsrField, ...]:
        return tuple(
            item
            for item in self.csr_fields(csr)
            if self.object_presence(item) in (QueryPresence.MANDATORY, QueryPresence.POSSIBLE)
        )

    def mandatory_csr_fields(self, csr: str | Csr) -> tuple[CsrField, ...]:
        return tuple(
            item
            for item in self.csr_fields(csr)
            if self.object_presence(item) is QueryPresence.MANDATORY
        )

    def absent_csr_fields(self, csr: str | Csr) -> tuple[CsrField, ...]:
        return tuple(
            item
            for item in self.csr_fields(csr)
            if self.object_presence(item) is QueryPresence.ABSENT
        )

    def direct_objects_for_extension(self, kind: str, extension: str) -> tuple[DatabaseObject, ...]:
        """Return possible records whose declared condition names *extension*."""

        self._require_extension(extension)
        return tuple(
            record
            for record in self.possible_objects(kind)
            if _mentions_extension(self._defined_by(record), extension)
        )

    def implied_objects_for_extension(
        self, kind: str, extension: str
    ) -> tuple[DatabaseObject, ...]:
        """Return records necessarily present whenever *extension* is selected."""

        self._require_extension(extension)
        trigger = ExtensionTerm(extension)
        result = []
        for record in self.database.objects(kind):
            if self._presence_with((trigger,), self._defined_by(record)) is QueryPresence.MANDATORY:
                result.append(record)
        return tuple(result)

    def possible_objects_for_extension(
        self, kind: str, extension: str
    ) -> tuple[DatabaseObject, ...]:
        self._require_extension(extension)
        trigger = ExtensionTerm(extension)
        return tuple(
            record
            for record in self.database.objects(kind)
            if self._presence_with((trigger,), self._defined_by(record))
            in (QueryPresence.MANDATORY, QueryPresence.POSSIBLE)
        )

    def implied_extensions(self, extension: str) -> tuple[Extension, ...]:
        self._require_extension(extension)
        trigger = ExtensionTerm(extension)
        return tuple(
            candidate
            for candidate in self.database.extensions
            if candidate.name != extension
            and self._presence_with((trigger,), ExtensionTerm(candidate.name))
            is QueryPresence.MANDATORY
        )

    def profile_condition(self, profile: str | DatabaseObject) -> Condition:
        record = self.database.profile(profile) if isinstance(profile, str) else profile
        conditions: list[Condition] = []
        base = record.data.get("base")
        if base in (32, 64):
            conditions.append(XlenTerm(base))
        extensions = record.data.get("extensions", {})
        if isinstance(extensions, Mapping):
            for name, declaration in extensions.items():
                if not isinstance(name, str) or not isinstance(declaration, Mapping):
                    continue
                presence = declaration.get("presence")
                requirement = ExtensionTerm(
                    name, parse_version_requirements(declaration.get("version"))
                )
                if presence == "mandatory":
                    conditions.append(requirement)
                elif presence == "prohibited":
                    conditions.append(negate(requirement))
        conditions.append(
            self._condition(record.data.get("requirements", True), record, ("requirements",))
        )
        return all_of(*conditions)

    def profile_presence(self, profile: str | DatabaseObject) -> QueryPresence:
        return self.condition_presence(self.profile_condition(profile))

    def manual_version_extensions(self, manual_version: str) -> tuple[ExtensionVersion, ...]:
        record = self.database.get("manual version", manual_version)
        found: list[ExtensionVersion] = []
        for volume in record.data.get("volumes", ()):
            if not isinstance(volume, Mapping):
                continue
            for declaration in volume.get("extensions", ()):
                if not isinstance(declaration, Mapping):
                    continue
                name = declaration.get("name")
                version = declaration.get("version")
                if not isinstance(name, str) or not isinstance(version, str):
                    continue
                found.append(self.database.extension(name).version(version))
        return tuple(found)

    def manual_versions_for_extension(self, extension: str) -> tuple[DatabaseObject, ...]:
        self._require_extension(extension)
        return tuple(
            record
            for record in self.database.objects("manual version")
            if any(
                item.extension == extension for item in self.manual_version_extensions(record.name)
            )
        )

    def compatible_with(self, other: ConfiguredArchitecture | Configuration) -> ArchitectureCheck:
        """Check two explicit configurations in one fresh solver context."""

        candidate = (
            other if isinstance(other, ConfiguredArchitecture) else self.database.configure(other)
        )
        if candidate.database is not self.database:
            raise ArchitectureError("compatibility requires configurations over the same database")
        if self._static_diagnostics or candidate._static_diagnostics:
            return ArchitectureCheck(
                ArchitectureCheckStatus.UNSAT,
                (*self._static_diagnostics, *candidate._static_diagnostics),
            )
        solver = ConditionSolver(
            SolverContext(
                extension_versions=self._catalog, parameter_domains=self.parameter_domains
            )
        )
        for condition, label in self._architecture_constraints():
            solver.add(condition, label)
        for prefix, architecture in ((self.name, self), (candidate.name, candidate)):
            for condition, label in architecture._configuration_constraints_only():
                solver.add(condition, f"{prefix}: {label}")
        status = solver.check()
        if status is SolverStatus.UNSAT:
            conflict = solver.minimal_conflict()
            return ArchitectureCheck(
                ArchitectureCheckStatus.UNSAT,
                (
                    ArchitectureDiagnostic(
                        "incompatible", "configurations cannot be satisfied together"
                    ),
                ),
                conflict=conflict,
            )
        if status is SolverStatus.UNKNOWN:
            return ArchitectureCheck(
                ArchitectureCheckStatus.DEFERRED,
                (
                    ArchitectureDiagnostic(
                        "solver-unknown",
                        "the solver could not decide compatibility",
                    ),
                ),
            )
        return _checked_model(solver, compatibility=True)

    def instruction_operation(
        self,
        instruction: str,
        *,
        effective_xlen: int,
        type_check: bool = True,
    ) -> CompiledIdl:
        """Compile an instruction operation with explicit effective XLEN and captured source."""

        from .idl_architecture import ArchitectureCompiler

        self._ensure_queryable()
        return ArchitectureCompiler(self).compile_instruction(
            instruction, effective_xlen=effective_xlen, type_check=type_check
        )

    def csr_behavior(
        self,
        csr: str,
        operation: str = "sw_read()",
        *,
        effective_xlen: int | None = None,
        type_check: bool = True,
    ) -> CompiledIdl:
        """Compile a CSR behavior in its owned source, XLEN, and expected-return context."""

        from .idl_architecture import ArchitectureCompiler

        self._ensure_queryable()
        return ArchitectureCompiler(self).compile_csr(
            csr, operation, effective_xlen=effective_xlen, type_check=type_check
        )

    def encoding_overlaps(self, instructions: Iterable[Instruction] | None = None):
        from .encoding import instruction_overlaps

        records = tuple(instructions) if instructions is not None else self.possible_instructions
        return instruction_overlaps(self, records)

    def csr_address_overlaps(self, csrs: Iterable[Csr] | None = None):
        from .encoding import csr_address_overlaps

        records = tuple(csrs) if csrs is not None else self.possible_csrs
        return csr_address_overlaps(self, records)

    def _load_parameter_domains(
        self, diagnostics: list[ArchitectureDiagnostic]
    ) -> dict[str, ParameterDomain]:
        store = (
            SchemaStore(self.database.schemas_root)
            if self.database.schemas_root is not None
            else None
        )
        domains: dict[str, ParameterDomain] = {}
        for parameter in self.database.objects("parameter"):
            schema = parameter.data.get("schema")
            if not isinstance(schema, Mapping):
                diagnostics.append(
                    ArchitectureDiagnostic(
                        "invalid-parameter-schema",
                        f"parameter {parameter.name!r} has no schema mapping",
                        source=str(parameter.path),
                    )
                )
                continue
            try:
                domains[parameter.name] = ParameterDomain.from_schema(
                    schema, schema_store=store, source=f"{parameter.path}#/schema"
                )
            except DomainError as error:
                diagnostics.append(
                    ArchitectureDiagnostic(
                        "invalid-parameter-domain", str(error), source=str(parameter.path)
                    )
                )
        return domains

    def _add_architecture_invariants(
        self,
        constraints: list[tuple[Condition, str]],
        diagnostics: list[ArchitectureDiagnostic],
    ) -> None:
        for extension in self.database.extensions:
            any_version = ExtensionTerm(extension.name)
            self._add_requirement(
                any_version,
                extension.data.get("requirements"),
                f"extension {extension.name} requirements",
                str(extension.path),
                constraints,
                diagnostics,
                sources=extension.sources,
            )
            for version in extension.versions:
                index = next(
                    index
                    for index, declaration in enumerate(extension.data["versions"])
                    if declaration["version"] == version.metadata["version"]
                )
                self._add_requirement(
                    ExtensionTerm(extension.name, _exact(version.canonical)),
                    version.metadata.get("requirements"),
                    f"extension {extension.name}@{version.canonical} requirements",
                    str(extension.path),
                    constraints,
                    diagnostics,
                    sources=extension.sources,
                    path=("versions", index, "requirements"),
                )
        for parameter in self.database.objects("parameter"):
            antecedent = self._defined_by(parameter, diagnostics=diagnostics)
            self._add_requirement(
                antecedent,
                parameter.data.get("requirements"),
                f"parameter {parameter.name} requirements",
                str(parameter.path),
                constraints,
                diagnostics,
                sources=parameter.sources,
            )

    def _add_configuration_constraints(
        self,
        constraints: list[tuple[Condition, str]],
        diagnostics: list[ArchitectureDiagnostic],
        catalog: Mapping[str, Any],
        domains: Mapping[str, ParameterDomain],
    ) -> None:
        known_names = set(catalog)
        listed_names = {selection.name for selection in self.configuration.extensions}
        for selection in self.configuration.extensions:
            if selection.name not in catalog:
                diagnostics.append(
                    ArchitectureDiagnostic(
                        "unknown-extension",
                        f"configuration references unknown extension {selection.name!r}",
                        source=self.configuration.name,
                    )
                )
                continue
            matching = self._matching_versions(selection.name, selection.requirements)
            if not matching:
                requirements = ", ".join(str(item) for item in selection.requirements)
                diagnostics.append(
                    ArchitectureDiagnostic(
                        "unknown-extension-version",
                        f"extension {selection.name!r} has no version matching {requirements}",
                        source=self.configuration.name,
                    )
                )
                continue
            requested = ExtensionTerm(selection.name, selection.requirements)
            any_version = ExtensionTerm(selection.name)
            label = f"configuration {selection.presence.value} extension {selection.name}"
            if selection.presence is Presence.MANDATORY:
                constraints.append((requested, label))
            elif selection.presence is Presence.PROHIBITED:
                constraints.append((negate(requested), label))
            else:
                constraints.append((implies(any_version, requested), label))

        if self.kind is ConfigurationKind.FULL or not self.configuration.additional_extensions:
            for name in sorted(known_names - listed_names):
                constraints.append(
                    (negate(ExtensionTerm(name)), f"configuration excludes extension {name}")
                )

        for name, value in self.configuration.params.items():
            domain = domains.get(name)
            if domain is None:
                diagnostics.append(
                    ArchitectureDiagnostic(
                        "unknown-parameter",
                        f"configuration assigns unknown parameter {name!r}",
                        source=self.configuration.name,
                    )
                )
                continue
            if not domain.accepts(value):
                diagnostics.append(
                    ArchitectureDiagnostic(
                        "parameter-domain",
                        f"parameter {name!r} value {value!r} is outside its declared domain",
                        source=self.configuration.name,
                    )
                )
                continue
            parameter = self.database.get("parameter", name)
            constraints.append(
                (
                    ParameterTerm(name, ParameterOperator.EQUAL, value),
                    f"configuration parameter {name}={value!r}",
                )
            )
            constraints.append(
                (self._defined_by(parameter), f"configuration parameter {name} is defined")
            )

        try:
            requirements = parse_condition(
                self.configuration.requirements,
                source=self.configuration.sources.document,
                path=("requirements",),
            )
            requirements = self._resolve_condition(
                requirements,
                sources=self.configuration.sources,
                source_text=self.configuration.source_text,
            )
            constraints.append((requirements, "configuration requirements"))
        except IdlError as error:
            diagnostics.append(
                ArchitectureDiagnostic(
                    "invalid-idl-condition",
                    str(error),
                    label="configuration requirements",
                    source=self.configuration.sources.document,
                )
            )
        except DataError as error:
            diagnostics.append(
                ArchitectureDiagnostic(
                    "invalid-condition", str(error), source=self.configuration.name
                )
            )

        if self.kind is ConfigurationKind.FULL and not diagnostics:
            # A full implementation supplies a value for every parameter that
            # can exist for its exact extension set and supported XLENs.
            temporary = ConditionSolver(
                SolverContext(extension_versions=catalog, parameter_domains=domains)
            )
            for condition, label in constraints:
                temporary.add(condition, label)
            if temporary.check() is SolverStatus.SAT:
                for parameter in self.database.objects("parameter"):
                    if parameter.name in self.configuration.params:
                        continue
                    if temporary.check((self._defined_by(parameter),)) is not SolverStatus.UNSAT:
                        diagnostics.append(
                            ArchitectureDiagnostic(
                                "missing-parameter",
                                f"fully configured architecture omits defined parameter "
                                f"{parameter.name!r}",
                                source=self.configuration.name,
                            )
                        )

    def _add_requirement(
        self,
        antecedent: Condition,
        raw_requirement: Any,
        label: str,
        source: str,
        constraints: list[tuple[Condition, str]],
        diagnostics: list[ArchitectureDiagnostic],
        *,
        sources: SourceMap | None = None,
        path: Sequence[str | int] = ("requirements",),
    ) -> None:
        if raw_requirement is None:
            return
        try:
            requirement = self._resolve_condition(
                parse_condition(raw_requirement, source=source, path=path), sources=sources
            )
        except IdlError as error:
            diagnostics.append(
                ArchitectureDiagnostic(
                    "invalid-idl-condition", str(error), label=label, source=source
                )
            )
            return
        except DataError as error:
            diagnostics.append(
                ArchitectureDiagnostic("invalid-condition", str(error), source=source)
            )
            return
        constraints.append((implies(antecedent, requirement), label))

    def _defined_by(
        self,
        record: DatabaseObject,
        *,
        diagnostics: list[ArchitectureDiagnostic] | None = None,
    ) -> Condition:
        raw = record.data.get("definedBy", True)
        if isinstance(raw, str):
            raw = {"extension": {"name": raw}}
        try:
            return self._condition(raw, record)
        except (DataError, IdlError) as error:
            if diagnostics is None:
                raise ArchitectureError(str(error)) from error
            diagnostics.append(
                ArchitectureDiagnostic(
                    "invalid-idl-condition" if isinstance(error, IdlError) else "invalid-condition",
                    str(error),
                    source=str(record.path),
                )
            )
            return parse_condition(False)

    def _condition(
        self,
        raw: Any,
        record: DatabaseObject,
        path: Sequence[str | int] = ("definedBy",),
    ) -> Condition:
        return self._condition_binding.resolve_record(raw, record, path)

    def _resolve_condition(
        self,
        condition: Condition,
        *,
        sources: SourceMap | None = None,
        source_text: str | None = None,
    ) -> Condition:
        return self._condition_binding.resolve(condition, sources=sources, source_text=source_text)

    def _matching_versions(
        self, name: str, requirements: Sequence[VersionRequirement]
    ) -> tuple[ExtensionVersion, ...]:
        versions = self._catalog.get(name)
        if versions is None:
            return ()
        return tuple(
            candidate
            for candidate in versions
            if all(
                requirement.matches(candidate.version, versions=versions)
                for requirement in requirements
            )
        )

    def _extension_versions_with(
        self, name: str, accepted: set[QueryPresence]
    ) -> tuple[ExtensionVersion, ...]:
        extension = self._require_extension(name)
        return tuple(
            version
            for version in extension.versions
            if self.condition_presence(ExtensionTerm(name, _exact(version.canonical))) in accepted
        )

    def _require_extension(self, name: str) -> Extension:
        return self.database.extension(name)

    def _ensure_queryable(self) -> None:
        if self._static_diagnostics:
            raise ArchitectureError(
                "; ".join(diagnostic.message for diagnostic in self._static_diagnostics)
            )
        if self._base_status is SolverStatus.UNSAT:
            raise ArchitectureError("configuration constraints are mutually unsatisfiable")

    def _require_solver(self) -> ConditionSolver:
        if self._solver is None:
            raise ArchitectureError("configured architecture has no usable solver")
        return self._solver

    def _presence_with(
        self, assumptions: Sequence[Condition], condition: Condition
    ) -> QueryPresence:
        self._ensure_queryable()
        assumptions = tuple(self._resolve_condition(item) for item in assumptions)
        condition = self._resolve_condition(condition)
        solver = self._require_solver()
        possible = solver.check((*assumptions, condition))
        if possible is SolverStatus.UNSAT:
            return QueryPresence.ABSENT
        mandatory = solver.check((*assumptions, negate(condition)))
        if mandatory is SolverStatus.UNSAT:
            return QueryPresence.MANDATORY
        if possible is SolverStatus.UNKNOWN or mandatory is SolverStatus.UNKNOWN:
            return QueryPresence.DEFERRED
        return QueryPresence.POSSIBLE

    def _architecture_constraints(self) -> tuple[tuple[Condition, str], ...]:
        configuration_labels = {label for _, label in self._configuration_constraints_only()}
        return tuple(item for item in self._constraints if item[1] not in configuration_labels)

    def _configuration_constraints_only(self) -> tuple[tuple[Condition, str], ...]:
        prefixes = ("configuration ",)
        return tuple(item for item in self._constraints if item[1].startswith(prefixes))


def _checked_model(solver: ConditionSolver, *, compatibility: bool = False) -> ArchitectureCheck:
    """Recheck after temporary queries before requesting a concrete model."""
    purpose = "compatibility" if compatibility else "validity"
    status = solver.check()
    if status is SolverStatus.UNSAT:
        return ArchitectureCheck(
            ArchitectureCheckStatus.UNSAT,
            (
                ArchitectureDiagnostic(
                    "incompatible" if compatibility else "unsatisfiable",
                    "configuration constraints are mutually unsatisfiable",
                ),
            ),
            conflict=solver.minimal_conflict(),
        )
    if status is SolverStatus.SAT:
        try:
            return ArchitectureCheck(ArchitectureCheckStatus.VALID, model=solver.model())
        except SolverUnknownError as error:
            message = str(error)
    else:
        message = f"the solver could not decide {purpose}"
    return ArchitectureCheck(
        ArchitectureCheckStatus.DEFERRED,
        (ArchitectureDiagnostic("solver-unknown", message),),
    )


def _exact(version: str) -> tuple[VersionRequirement, ...]:
    return parse_version_requirements(f"= {version}")


def _mentions_extension(condition: Condition, name: str) -> bool:
    from .conditions import AllOf, AnyOf, ExactlyOne, Implies, NoneOf, Not

    if isinstance(condition, ExtensionTerm):
        return condition.name == name
    if isinstance(condition, (AllOf, AnyOf, ExactlyOne, NoneOf)):
        return any(_mentions_extension(child, name) for child in condition.children)
    if isinstance(condition, Not):
        return _mentions_extension(condition.child, name)
    if isinstance(condition, Implies):
        return _mentions_extension(condition.antecedent, name) or _mentions_extension(
            condition.consequent, name
        )
    return False


__all__ = [
    "ArchitectureCheck",
    "ArchitectureCheckStatus",
    "ArchitectureDiagnostic",
    "ArchitectureError",
    "ConfiguredArchitecture",
    "CsrField",
    "DeferredQuery",
    "QueryPresence",
]
