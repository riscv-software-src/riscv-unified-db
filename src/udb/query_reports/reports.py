# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Configured report queries with immutable outputs and faithful human renderers."""

from __future__ import annotations

import io
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from ruamel.yaml import YAML

from ..architecture import ConfiguredArchitecture, QueryPresence
from ..conditions import ExtensionTerm, all_of, any_of, implies, parse_condition
from ..configuration import Configuration, ConfigurationKind
from ..database import Database, DatabaseObject, Extension
from ..errors import ObjectNotFoundError
from ..idl_condition_binding import IdlConditionBinding
from ..versions import parse_version_requirements
from .formatting import ReportError, ascii_table, condition_text, schema_text
from .matching import catalog_order


def catalog_names(database: Database, kind: str) -> tuple[str, ...]:
    """Query the supplied raw/resolved catalog without configuring or resolving it."""
    if not isinstance(database, Database):
        raise TypeError("catalog_names requires a Database")
    return tuple(record.name for record in catalog_order(database.objects(kind)))


@dataclass(frozen=True, slots=True)
class ExtensionReport:
    name: str
    long_name: str
    versions: tuple[str, ...]
    instruction_count: int

    def render(self) -> str:
        text = (
            f"{self.name} Extension\n  {self.long_name}\n\nVersions:\n"
            + "\n".join(f"  * {version}" for version in self.versions)
            + "\n\n"
        )
        if self.instruction_count:
            text += f"Includes {self.instruction_count} instructions\n"
        return text


@dataclass(frozen=True, slots=True)
class ParameterRow:
    name: str
    exts: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "exts": self.exts, "description": self.description}


@dataclass(frozen=True, slots=True)
class ParameterReport:
    name: str
    defined_by: str
    defined_by_pretty: str
    description: str
    schema_description: str
    has_configured_value: bool
    configured_value: Any

    def render(self) -> str:
        description = self.description.replace("\n", "\n    ")
        return (
            f"{self.name}\n\n  Defined by:\n  {self.defined_by_pretty}\n\n"
            f"  Description:\n    {description}\n\n  Value:\n    {self.schema_description}\n"
        )


@dataclass(frozen=True, slots=True)
class ParameterListReport:
    rows: tuple[ParameterRow, ...]

    def to_data(self) -> list[dict[str, str]]:
        return [row.to_dict() for row in self.rows]

    def render(self, output_format: str = "ascii") -> str:
        if output_format == "ascii":
            return ascii_table([(row.name, row.exts, row.description) for row in self.rows])
        if output_format == "json":
            return json.dumps(self.to_data(), ensure_ascii=False, separators=(",", ":")) + "\n"
        if output_format == "yaml":
            yaml = YAML(typ="safe", pure=True)
            yaml.explicit_start = True
            yaml.default_flow_style = False
            yaml.sort_base_mapping_type_on_output = False
            stream = io.StringIO()
            yaml.dump(self.to_data(), stream)
            return stream.getvalue()
        raise ReportError("parameter output format must be ascii, yaml or json")


class ReportBuilder:
    """An explicit configured view: raw record inspection remains Database's API.

    Names and disassembly historically use the entire CSR/instruction catalog,
    while extension lists and unfiltered parameters are configuration-sensitive.
    Parameter/extension detail lookup likewise does not require availability.
    """

    def __init__(self, architecture: ConfiguredArchitecture) -> None:
        if not isinstance(architecture, ConfiguredArchitecture):
            raise TypeError(
                "ReportBuilder requires a ConfiguredArchitecture; resolve/configure explicitly"
            )
        self.architecture = architecture
        self.database = architecture.database
        self._structural: ConfiguredArchitecture | None = None
        self._binding = IdlConditionBinding(self.database, Configuration.builtin("_"))
        self._direct: dict[tuple[str, str], tuple[DatabaseObject, ...]] = {}

    @property
    def structural(self) -> ConfiguredArchitecture:
        if self._structural is None:
            self._structural = self.database.configure(Configuration.builtin("_"))
        return self._structural

    def extension(self, name: str) -> ExtensionReport | None:
        try:
            record = self.database.extension(name)
        except ObjectNotFoundError:
            return None
        return ExtensionReport(
            record.name,
            self._text(record, "long_name"),
            tuple(str(version["version"]) for version in record.get("versions", ())),
            len(self._direct_objects("instruction", record)),
        )

    def parameter(self, name: str) -> ParameterReport | None:
        try:
            record = self.database.get("parameter", name)
        except ObjectNotFoundError:
            return None
        schema = record.get("schema")
        if not isinstance(schema, Mapping):
            raise ReportError(f"{record.path}: parameter schema must be a mapping")
        params = self.architecture.configuration.params
        return ParameterReport(
            record.name,
            self._definition_text(record),
            self._definition_text(record, pretty=True),
            self._text(record, "description"),
            schema_text(schema),
            name in params,
            params.get(name),
        )

    def extensions(self) -> tuple[str, ...]:
        possible = {record.name for record in self.architecture.possible_extensions}
        if self.architecture.kind is ConfigurationKind.FULL:
            explicit = [
                entry.name
                for entry in self.architecture.configuration.extensions
                if entry.name in possible
            ]
            remaining = [
                record.name
                for record in catalog_order(self.database.extensions)
                if record.name in possible and record.name not in explicit
            ]
            return tuple(dict.fromkeys([*explicit, *remaining]))
        return tuple(
            record.name
            for record in catalog_order(self.database.extensions)
            if record.name in possible
        )

    def csrs(self, *, selection: str = "catalog") -> tuple[str, ...]:
        if selection == "catalog":
            records = self.database.csrs
        elif selection == "possible":
            records = self.architecture.possible_csrs
        elif selection == "mandatory":
            records = self.architecture.mandatory_csrs
        else:
            raise ReportError("CSR selection must be catalog, possible or mandatory")
        return tuple(record.name for record in catalog_order(records))

    def parameters(self, extensions: Iterable[str] | None = None) -> ParameterListReport:
        if extensions is not None:
            if isinstance(extensions, str):
                raise TypeError("extensions must be an iterable of names, not one string")
            names = set(extensions)
            if any(not isinstance(name, str) for name in names):
                raise TypeError("extension names must be strings")
            records = {}
            for extension in self.architecture.possible_extensions:
                if extension.name in names:
                    records.update(
                        (record.name, record)
                        for record in self._direct_objects("parameter", extension)
                    )
            selected = tuple(records[name] for name in sorted(records))
        else:
            # Ruby preserves the config mapping's insertion order for known values,
            # then catalog order for the remaining applicable parameters.
            selected = []
            for name in self.architecture.configuration.params:
                try:
                    selected.append(self.database.get("parameter", name))
                except ObjectNotFoundError:
                    continue
            selected.extend(catalog_order(self.architecture.parameters_without_values))
        return ParameterListReport(
            tuple(
                ParameterRow(
                    record.name,
                    self._definition_text(record),
                    self._text(record, "description"),
                )
                for record in selected
            )
        )

    def _definition_text(self, record: DatabaseObject, *, pretty: bool = False) -> str:
        raw = record.get("definedBy", True)
        if isinstance(raw, str):
            raw = {"extension": {"name": raw}}
        if parse_condition(raw).has_unresolved:
            raw = self._binding.resolve_record(raw, record, ("definedBy",))
        return condition_text(raw, pretty=pretty)

    def _direct_objects(self, kind: str, extension: Extension) -> tuple[DatabaseObject, ...]:
        key = (kind, extension.name)
        if key in self._direct:
            return self._direct[key]
        requirements = self._requirements(extension)
        selected = []
        for record in self.database.objects(kind):
            raw = record.get("definedBy", True)
            if isinstance(raw, str):
                raw = {"extension": {"name": raw}}
            defined = self._binding.resolve_record(raw, record, ("definedBy",))
            if self._guarantees(ExtensionTerm(extension.name), defined) and not self._guarantees(
                requirements, defined
            ):
                selected.append(record)
        result = tuple(selected)
        self._direct[key] = result
        return result

    def _guarantees(self, trigger, condition) -> bool:
        result = self.structural.condition_presence(implies(trigger, condition))
        if result is QueryPresence.DEFERRED:
            raise ReportError("direct extension membership is undecidable")
        return result is QueryPresence.MANDATORY

    def _requirements(self, extension: Extension):
        general = self._binding.resolve_record(
            extension.get("requirements", True), extension, ("requirements",)
        )
        versions = []
        for index, entry in enumerate(extension.get("versions", ())):
            specific = self._binding.resolve_record(
                entry.get("requirements", True),
                extension,
                ("versions", index, "requirements"),
            )
            requirement = all_of(general, specific)
            if requirement != parse_condition(True):
                versions.append(
                    (
                        ExtensionTerm(
                            extension.name, parse_version_requirements(f"= {entry['version']}")
                        ),
                        requirement,
                    )
                )
        if not versions:
            return parse_condition(True)
        if len(versions) == 1:
            return versions[0][1]
        return all_of(
            any_of(*(requirement for _, requirement in versions)),
            *(implies(version, requirement) for version, requirement in versions),
        )

    @staticmethod
    def _text(record: DatabaseObject, field: str) -> str:
        value = record.get(field, "")
        if not isinstance(value, str):
            raise ReportError(f"{record.path}: {field} must be a string")
        return value


def render_extension(report: ExtensionReport | None, name: str) -> str:
    return report.render() if report else f"Could not find an extension named '{name}'\n"


def render_parameter(report: ParameterReport | None, name: str) -> str:
    return report.render() if report else f"Could not find parameter named {name}\n"


def render_names(names: Iterable[str]) -> str:
    return "".join(f"{name}\n" for name in names)
