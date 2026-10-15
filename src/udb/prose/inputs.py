# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Captured, immutable configured-prose inputs; no renderer or solver."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from ..conditions import (
    AllOf,
    AnyOf,
    Condition,
    EvaluationContext,
    ExactlyOne,
    ExtensionTerm,
    Implies,
    NoneOf,
    Not,
    ParameterTerm,
    TruthValue,
    XlenTerm,
    parse_condition,
)
from ..configuration import Configuration, ConfigurationKind, Presence
from ..database import DatabaseObject, ResolvedDatabase, _freeze
from ..errors import DataError
from ..source import SourceSpan
from ..versions import ExtensionVersion, ExtensionVersionSet, Version, parse_version_requirements

if TYPE_CHECKING:
    from ..architecture import ConfiguredArchitecture


class ParameterState(Enum):
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class CapturedFailure:
    """An upstream query failed; retain its exact class and message."""

    error_class: str
    message: str


@dataclass(frozen=True, slots=True)
class CodeRecord:
    num: int
    name: str
    var: str = ""
    extensions: tuple[str, ...] = ()
    display_name: str | None = None
    name_source: CapturedProse | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if type(self.num) is not int or self.num < 0 or not isinstance(self.name, str):
            raise DataError("Prose code records require a nonnegative integer and string name")
        if not isinstance(self.var, str) or not all(
            isinstance(name, str) for name in self.extensions
        ):
            raise DataError("Code identifiers and defining extensions must be strings")
        object.__setattr__(self, "extensions", tuple(self.extensions))
        if not self.var:
            object.__setattr__(self, "var", self.name)


@dataclass(frozen=True, slots=True)
class CapturedProse:
    """A scalar and original provenance, never a filename to reopen."""

    text: str
    source: str = "<prose>"
    path: tuple[str | int, ...] = ()
    span: SourceSpan | None = None
    source_text: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not isinstance(self.source, str):
            raise DataError("Captured prose text and source must be strings")
        if not all(type(item) in (str, int) for item in self.path):
            raise DataError("Captured prose field paths contain strings or integers")
        object.__setattr__(self, "path", tuple(self.path))

    @classmethod
    def from_record(
        cls, database: ResolvedDatabase, record: DatabaseObject, *path: str | int
    ) -> CapturedProse:
        value: object = record.data
        try:
            for item in path:
                if type(item) not in (str, int) or (
                    not isinstance(value, Mapping)
                    and not (isinstance(value, tuple) and type(item) is int and item >= 0)
                ):
                    raise KeyError(item)
                value = value[item]
        except (KeyError, IndexError, TypeError) as error:
            raise DataError(f"{record.path}: invalid prose field path {path!r}") from error
        if not isinstance(value, str):
            raise DataError(f"{record.path}: prose field {path!r} is not a string")
        span = record.source_at(*path)
        original = None
        if span is not None:
            try:
                original = database.source_text(span.source, layer=span.layer)
            except DataError as error:
                raise DataError(
                    f"{span.label}: cannot capture prose field {path!r}: {error}"
                ) from error
        return cls(value, str(record.path), path, span, original)

    @property
    def label(self) -> str:
        origin = self.span.label if self.span is not None else self.source
        pointer = "/".join(str(item).replace("~", "~0").replace("/", "~1") for item in self.path)
        return origin + (f"#/{pointer}" if pointer else "")


@dataclass(frozen=True, slots=True)
class ProseInputs:
    """Explicit projection of a configuration for text generation.

    Extension facts distinguish known implementation from symbolic possibility.
    Captured failures are raised only if a template consumes that input.
    """

    configuration: str
    parameters: Mapping[str, object] = field(default_factory=dict)
    extensions: Mapping[str, bool] = field(default_factory=dict)
    possible_xlens: tuple[int, ...] | CapturedFailure = (32, 64)
    exception_codes: tuple[CodeRecord, ...] | CapturedFailure = ()
    interrupt_codes: tuple[CodeRecord, ...] | CapturedFailure = ()
    selected_versions: Mapping[str, tuple[ExtensionVersion, ...]] = field(default_factory=dict)
    kind: ConfigurationKind = ConfigurationKind.UNCONFIGURED
    configuration_source: str | None = field(default=None, repr=False)
    parameter_sources: Mapping[str, SourceSpan] = field(default_factory=dict, repr=False)
    version_sets: Mapping[str, ExtensionVersionSet] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.configuration, str):
            raise DataError("Prose configuration label must be a string")
        if not all(isinstance(key, str) for key in self.parameters):
            raise DataError("Prose parameter names must be strings")
        for value in self.parameters.values():
            if (
                type(value) not in (str, int, bool, type(None))
                and not isinstance(value, ParameterState)
                and not (
                    isinstance(value, Sequence)
                    and not isinstance(value, str | bytes)
                    and all(type(item) in (str, int, bool) for item in value)
                )
            ):
                raise DataError("Prose parameters must be captured scalars, flat arrays, or states")
        if not all(
            isinstance(key, str) and type(value) is bool for key, value in self.extensions.items()
        ):
            raise DataError("Prose extension facts must be named booleans")
        object.__setattr__(self, "parameters", _freeze(self.parameters))
        object.__setattr__(self, "extensions", _freeze(self.extensions))
        object.__setattr__(self, "selected_versions", _freeze(self.selected_versions))
        object.__setattr__(self, "parameter_sources", _freeze(self.parameter_sources))
        object.__setattr__(self, "version_sets", _freeze(self.version_sets))
        object.__setattr__(self, "kind", ConfigurationKind(self.kind))
        for name in ("exception_codes", "interrupt_codes"):
            value = getattr(self, name)
            if not isinstance(value, CapturedFailure):
                if not isinstance(value, Sequence) or any(
                    not isinstance(code, CodeRecord) for code in value
                ):
                    raise DataError(f"{name} must contain typed CodeRecord inputs")
                if len(value) > 1024:
                    raise DataError(f"{name} exceeds 1024 records")
                object.__setattr__(self, name, tuple(sorted(value, key=lambda code: code.num)))
        if not isinstance(self.possible_xlens, CapturedFailure):
            if not isinstance(self.possible_xlens, Sequence) or any(
                type(width) is not int or width not in (32, 64) for width in self.possible_xlens
            ):
                raise DataError("Possible XLENs must be a sequence of 32 and/or 64")
            object.__setattr__(self, "possible_xlens", tuple(self.possible_xlens))

    def extension(self, name: str, requirement: str | None = None) -> bool:
        key = name + (f"@{requirement}" if requirement else "")
        if key in self.extensions:
            return self.extensions[key]
        versions = self.selected_versions.get(name, ())
        if not versions:
            if requirement is not None and self.extensions.get(name) is True:
                raise DataError(f"Missing captured version predicate {key!r}")
            return False
        if requirement is None:
            return True
        requirements = parse_version_requirements(requirement)
        matches = [
            all(
                req.matches(version.version, versions=self.version_sets.get(name))
                for req in requirements
            )
            for version in versions
        ]
        return all(matches) if self.kind is ConfigurationKind.PARTIAL else any(matches)

    @classmethod
    def from_architecture(cls, architecture: ConfiguredArchitecture) -> ProseInputs:
        """Project declarations, not global satisfiability; prose is not validation."""
        return cls.from_database(architecture.database, architecture.configuration)

    @classmethod
    def from_database(cls, database: ResolvedDatabase, configuration: Configuration) -> ProseInputs:
        """Capture source conditions with existing version/condition machinery.

        Deliberately does not validate architectural consistency or infer additional
        implemented extensions. Call the existing architecture checker separately.
        """
        if configuration.kind is ConfigurationKind.PARTIAL and (
            configuration.requirements is not True
            or not configuration.additional_extensions
            or any(
                selection.presence is Presence.PROHIBITED for selection in configuration.extensions
            )
        ):
            raise DataError(
                "Restricted partial configurations require explicitly captured prose "
                "parameter/code availability; declaration-only projection is insufficient"
            )
        catalog = {extension.name: extension.version_set for extension in database.extensions}
        selected: dict[str, tuple[ExtensionVersion, ...]] = {}
        prohibited: set[str] = set()
        for selection in configuration.extensions:
            if selection.presence is Presence.PROHIBITED:
                prohibited.add(selection.name)
            elif selection.presence is Presence.MANDATORY:
                versions = catalog.get(selection.name)
                if versions is None:
                    raise DataError(f"No extension {selection.name!r} for prose configuration")
                matching = tuple(
                    version
                    for version in versions
                    if all(
                        req.matches(version.version, versions=versions)
                        for req in selection.requirements
                    )
                )
                if not matching or (
                    configuration.kind is ConfigurationKind.FULL and len(matching) != 1
                ):
                    raise DataError(f"Non-concrete prose extension selection {selection.name!r}")
                selected[selection.name] = matching
        full = configuration.kind is ConfigurationKind.FULL
        context = EvaluationContext(
            extensions={
                name: versions[0].version
                for name, versions in selected.items()
                if len(versions) == 1
            },
            parameters=configuration.params,
            version_sets=catalog,
            closed_world_extensions=full,
            closed_world_parameters=full,
            xlen=configuration.mxlen,
        )

        def available(record: DatabaseObject) -> bool:
            condition = parse_condition(record.data.get("definedBy", True))
            if condition.has_unresolved:
                raise DataError(f"{record.path}: unresolved IDL in prose input condition")
            # Existing evaluator handles constants, versions, parameters and XLEN.
            return condition.evaluate(context) is not TruthValue.FALSE

        parameters = {}
        parameter_sources = {}
        for parameter in database.objects("parameter"):
            if parameter.name in configuration.params:
                parameters[parameter.name] = configuration.params[parameter.name]
                span = configuration.sources.at("params", parameter.name)
            else:
                parameters[parameter.name] = (
                    ParameterState.UNKNOWN if available(parameter) else ParameterState.UNAVAILABLE
                )
                span = parameter.source_at("definedBy")
            if span is not None:
                parameter_sources[parameter.name] = span

        def codes(kind: str) -> tuple[CodeRecord, ...]:
            return tuple(
                CodeRecord(
                    record.data["num"],
                    record.name,
                    record.name,
                    _defining_extensions(record.data.get("definedBy", True)),
                    record.data.get("display_name"),
                    CapturedProse.from_record(database, record, "name"),
                )
                for record in database.objects(kind)
                if available(record)
            )

        mxlen = configuration.mxlen
        widths: tuple[int, ...] | CapturedFailure = (32, 64) if mxlen is None else (mxlen,)
        if mxlen == 64:
            for extension, parameter in (
                ("S", "SXLEN"),
                ("U", "UXLEN"),
                ("H", "VSXLEN"),
                ("H", "VUXLEN"),
            ):
                if extension in prohibited or (full and extension not in selected):
                    continue
                if not full and (
                    extension not in selected or parameter not in configuration.params
                ):
                    widths = (32, 64)
                    break
                value = configuration.params.get(parameter)
                if value is None:
                    widths = CapturedFailure("NoMethodError", "undefined method 'size' for nil")
                    break
                if not isinstance(value, Sequence) or isinstance(value, str | bytes):
                    widths = CapturedFailure("TypeError", f"{parameter} must be a width sequence")
                    break
                if len(value) > 1:
                    widths = (32, 64)
                    break
        return cls(
            configuration.name,
            parameters,
            possible_xlens=widths,
            exception_codes=codes("exception_code"),
            interrupt_codes=codes("interrupt_code"),
            selected_versions=selected,
            kind=configuration.kind,
            configuration_source=configuration.source_text,
            parameter_sources=parameter_sources,
            version_sets=catalog,
        )


def _defining_extensions(value: object) -> tuple[str, ...]:
    names: set[str] = set()

    def visit(item: object) -> None:
        if isinstance(item, Mapping):
            extension = item.get("extension")
            if isinstance(extension, Mapping) and isinstance(extension.get("name"), str):
                names.add(extension["name"])
            for child in item.values():
                visit(child)
        elif isinstance(item, Sequence) and not isinstance(item, str | bytes):
            for child in item:
                visit(child)

    visit(value)
    return tuple(sorted(names))


def all_exception_records(database: ResolvedDatabase) -> tuple[CodeRecord, ...]:
    """All-code, extension-major wrapper selection, independent of configuration.

    Ruby's extension wrapper enumerates expanded condition mentions, including
    requirements of matching extension versions, not just syntactic definedBy.
    This is a dependency projection using the existing condition/version parser,
    not a presence query or an architectural consistency check.
    """
    catalog = {extension.name: extension for extension in database.extensions}
    parameters = {parameter.name: parameter for parameter in database.objects("parameter")}
    symtab = None

    def condition_for(record: DatabaseObject, raw: object, *path: str | int) -> Condition:
        nonlocal symtab
        condition = parse_condition(raw, source=str(record.path), path=path)
        if not condition.has_unresolved:
            return condition
        from ..idl_conditions import resolve_idl_conditions
        from ..idl_environment import condition_symbol_table
        from ..idl_yaml_source import idl_field_source

        if symtab is None:
            # Translation-only, open-world environment: no config, solver,
            # external toolchain, or source reopening.
            symtab = condition_symbol_table(database)

        def source_for(leaf):
            span = record.source_at(*leaf.source_path)
            if span is None or span.start_line is None:
                return leaf.source
            text = database.source_text(span.source, layer=span.layer)
            label = span.source if span.layer == "source" else f"{span.layer}:{span.source}"
            return idl_field_source(text, span, leaf.text, label=label)

        return resolve_idl_conditions(condition, symtab, source_for=source_for)

    def mentions(record: DatabaseObject) -> set[str]:
        names: set[str] = set()
        touched: set[Condition] = set()
        has_xlen = False

        def visit(condition: Condition) -> None:
            nonlocal has_xlen
            if condition in touched:
                return
            touched.add(condition)
            if len(touched) > 10_000:
                raise DataError(f"{record.path}: expanded code condition exceeds 10000 terms")
            if condition.has_unresolved:
                raise DataError(f"{record.path}: unresolved IDL in expanded code condition")
            if isinstance(condition, ExtensionTerm):
                names.add(condition.name)
                extension = catalog.get(condition.name)
                if extension is None:
                    raise DataError(f"{record.path}: no extension {condition.name!r}")
                versions = extension.version_set
                for version in versions:
                    if all(
                        req.matches(version.version, versions=versions)
                        for req in condition.requirements
                    ):
                        visit(
                            condition_for(
                                extension, extension.data.get("requirements", True), "requirements"
                            )
                        )
                        index = next(
                            index
                            for index, metadata in enumerate(extension.data["versions"])
                            if Version.parse(metadata["version"]) == version.version
                        )
                        visit(
                            condition_for(
                                extension,
                                version.metadata.get("requirements", True),
                                "versions",
                                index,
                                "requirements",
                            )
                        )
            elif isinstance(condition, XlenTerm):
                has_xlen = True
            elif isinstance(condition, ParameterTerm):
                name = condition.name
                parameter = parameters.get(name)
                if parameter is None:
                    raise DataError(f"{record.path}: no parameter {name!r}")
                visit(
                    condition_for(
                        parameter, parameter.data.get("requirements", True), "requirements"
                    )
                )
            elif isinstance(condition, (AllOf, AnyOf, ExactlyOne, NoneOf)):
                for child in condition.children:
                    visit(child)
            elif isinstance(condition, Not):
                visit(condition.child)
            elif isinstance(condition, Implies):
                visit(condition.antecedent)
                visit(condition.consequent)

        visit(condition_for(record, record.data.get("definedBy", True), "definedBy"))
        if has_xlen:
            parameter = parameters.get("MXLEN")
            if parameter is None:
                raise DataError(f"{record.path}: no parameter 'MXLEN'")
            # Ruby adds XLEN relations after recursive requirement expansion.
            # Their direct mentions count, but their dependencies are not expanded.
            relation = condition_for(
                parameter, parameter.data.get("requirements", True), "requirements"
            )
            names.update(_defining_extensions(relation.to_data()))
        return names

    codes = database.objects("exception_code")
    expanded = {id(code): mentions(code) for code in codes}
    result = []
    for extension in database.extensions:
        for code in codes:
            if extension.name in expanded[id(code)]:
                result.append(
                    CodeRecord(
                        code.data["num"],
                        code.name,
                        code.name,
                        (extension.name,),
                        code.data.get("display_name"),
                        CapturedProse.from_record(database, code, "name"),
                    )
                )
    return tuple(result)
