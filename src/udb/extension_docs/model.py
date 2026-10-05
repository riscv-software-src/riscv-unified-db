# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Extension-document selection and explicit input contracts, not a semantic engine."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from ..architecture import ConfiguredArchitecture, QueryPresence
from ..conditions import (
    AllOf,
    AnyOf,
    Condition,
    ConstantCondition,
    ExactlyOne,
    ExtensionTerm,
    FreeTerm,
    Implies,
    NoneOf,
    Not,
    ParameterTerm,
    UnresolvedIdlCondition,
    XlenTerm,
    all_of,
    any_of,
    parse_condition,
)
from ..configuration import Configuration, ConfigurationKind
from ..database import DatabaseObject, Extension
from ..errors import DataError
from ..versions import ExtensionVersion, VersionRequirement, parse_version_requirements


class ExtensionDocumentError(DataError):
    """The document cannot be generated without losing required content."""


class ProseProvider(Protocol):
    def __call__(
        self,
        text: str,
        *,
        record: DatabaseObject,
        field_path: tuple[str | int, ...],
        architecture: ConfiguredArchitecture,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class DocumentOptions:
    include_implied: bool = False
    include_csr_field_descriptions: bool = True
    basename: str | None = None
    revision: str = "unknown"
    today: date | None = None
    prose: ProseProvider | None = None
    source_assets: Mapping[str, bytes] | None = None


@dataclass(frozen=True, slots=True)
class ExtensionSelection:
    selector: str
    extension: Extension
    requirements: tuple[VersionRequirement, ...]
    versions: tuple[ExtensionVersion, ...]

    @property
    def name(self) -> str:
        return self.extension.name

    @property
    def condition(self) -> Condition:
        return ExtensionTerm(self.name, self.requirements)

    @property
    def pretty(self) -> str:
        if self.requirements == parse_version_requirements(None):
            return self.name
        return self.name + " " + " and ".join(map(str, self.requirements))

    def requirements_condition(self, version: ExtensionVersion) -> Condition:
        return all_of(
            parse_condition(self.extension.data.get("requirements", True)),
            parse_condition(version.metadata.get("requirements", True)),
        )


def select_extensions(
    architecture: ConfiguredArchitecture, selectors: Sequence[str]
) -> tuple[ExtensionSelection, ...]:
    if not selectors or isinstance(selectors, str):
        raise ExtensionDocumentError("Provide at least one extension selector")
    result = []
    for selector in selectors:
        name, separator, requirement = selector.partition("@")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", name):
            raise ExtensionDocumentError(f"Invalid extension selector {selector!r}")
        extension = architecture.database.extension(name)
        if separator and not requirement:
            raise ExtensionDocumentError(f"Empty version requirement in {selector!r}")
        if requirement == "latest":
            requirements = (VersionRequirement.exact(extension.max_version.version),)
        else:
            try:
                requirements = parse_version_requirements(requirement if separator else None)
            except (TypeError, ValueError) as error:
                raise ExtensionDocumentError(f"Invalid selector {selector!r}: {error}") from error
        versions = tuple(
            version
            for version in extension.versions
            if all(
                req.matches(version.version, versions=extension.version_set) for req in requirements
            )
        )
        if not versions:
            raise ExtensionDocumentError(f"No versions satisfy {selector!r}")
        result.append(ExtensionSelection(selector, extension, requirements, versions))
    return tuple(result)


def basename_for(selections: Sequence[ExtensionSelection], options: DocumentOptions) -> str:
    name = selections[0].selector if options.basename is None else options.basename
    if not name or name in {".", ".."} or any(ch in name for ch in "/\\\0\r\n"):
        raise ExtensionDocumentError(f"Output basename must be a single filename: {name!r}")
    return name


class SelectionQueries:
    """Thin cached calls into the accepted architecture solver."""

    def __init__(self, architecture: ConfiguredArchitecture) -> None:
        self.architecture = architecture
        # Native unsatisfiable_by_arch? intentionally ignores configuration
        # closure. Selection describes the extension, while prose and IDL use
        # the requested configuration. Reuse the accepted unconfigured model.
        self.selection_architecture = (
            architecture
            if architecture.kind is ConfigurationKind.UNCONFIGURED
            else architecture.database.configure(Configuration.builtin("_"))
        )
        self.cache: dict[Condition, QueryPresence] = {}
        self.configured_cache: dict[Condition, QueryPresence] = {}

    def presence(self, condition: Condition) -> QueryPresence:
        if condition not in self.cache:
            presence = self.selection_architecture.condition_presence(condition)
            if presence is QueryPresence.DEFERRED:
                raise ExtensionDocumentError(f"Unresolved document selection: {condition!r}")
            self.cache[condition] = presence
        return self.cache[condition]

    def configured_presence(self, condition: Condition) -> QueryPresence:
        if condition not in self.configured_cache:
            presence = self.architecture.condition_presence(condition)
            if presence is QueryPresence.DEFERRED:
                raise ExtensionDocumentError(f"Unresolved field availability: {condition!r}")
            self.configured_cache[condition] = presence
        return self.configured_cache[condition]

    def impossible(self, condition: Condition) -> bool:
        return self.presence(condition) is QueryPresence.ABSENT

    def implies(self, premise: Condition, conclusion: Condition) -> bool:
        return self.impossible(premise & ~conclusion)

    def records(
        self, kind: str, selections: Sequence[ExtensionSelection]
    ) -> tuple[DatabaseObject, ...]:
        names = any_of(*(ExtensionTerm(selection.name) for selection in selections))
        versions = any_of(*(selection.condition for selection in selections))
        return tuple(
            record
            for record in sorted(
                self.architecture.database.objects(kind), key=lambda record: record.path.as_posix()
            )
            if self.implies(defined_by(record), names)
            and not self.impossible(versions & defined_by(record))
        )


def defined_by(record: DatabaseObject) -> Condition:
    return parse_condition(record.data.get("definedBy", True))


def prose_text(
    architecture: ConfiguredArchitecture,
    options: DocumentOptions,
    record: DatabaseObject,
    *path: str | int,
) -> str:
    value: object = record.data
    for part in path:
        if isinstance(value, Mapping):
            value = value.get(part, "")
        elif isinstance(value, Sequence) and not isinstance(value, str):
            value = value[part] if isinstance(part, int) else ""
        else:
            value = ""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ExtensionDocumentError(f"{record.path}#/{'/'.join(map(str, path))}: expected text")
    if "<%" not in value and "{%" not in value and "{{" not in value:
        return value
    if options.prose is None:
        raise ExtensionDocumentError(
            f"{record.path}#/{'/'.join(map(str, path))}: configured prose provider required"
        )
    result = options.prose(value, record=record, field_path=path, architecture=architecture)
    if not isinstance(result, str) or "<%" in result:
        raise ExtensionDocumentError(f"{record.path}: prose provider returned unresolved text")
    return result


def condition_adoc(condition: Condition, *, show_versions: bool = False) -> str:
    """Presentation of already-parsed conditions; no evaluation or inference."""
    if isinstance(condition, ConstantCondition):
        return "true" if condition.value else "false"
    if isinstance(condition, ExtensionTerm):
        result = f"`{condition.name}`"
        if show_versions and condition.requirements != parse_version_requirements(None):
            result += " (" + " and ".join(map(str, condition.requirements)) + ")"
        return result
    if isinstance(condition, XlenTerm):
        return f"xlen+++()+++ == {condition.value}"
    if isinstance(condition, FreeTerm):
        return condition.name
    if isinstance(condition, UnresolvedIdlCondition):
        return "[source,idl]\n----\n" + condition.text.rstrip() + "\n----"
    if isinstance(condition, ParameterTerm):
        name = condition.name
        if condition.index is not None:
            name += f"[{condition.index}]"
        elif condition.bit_range is not None:
            name += f"[{condition.bit_range[0]}:{condition.bit_range[1]}]"
        elif condition.size:
            name += ".size"
        value = condition.value
        value_text = (
            json.dumps(value, ensure_ascii=False)
            if isinstance(value, (tuple, bool))
            else str(value)
        )
        symbols = {
            "equal": "==",
            "notEqual": "!=",
            "lessThan": "<",
            "greaterThan": ">",
            "lessThanOrEqual": "<=",
            "greaterThanOrEqual": ">=",
        }
        if condition.operator.value in symbols:
            return f"`{name}` {symbols[condition.operator.value]} {value_text}"
        if condition.operator.value == "includes":
            return f"{value_text} in `{name}`"
        if condition.operator.value == "oneOf":
            return f"`{name}` in {value_text}"
        raise ExtensionDocumentError(f"Unsupported parameter condition {condition!r}")
    if isinstance(condition, Not):
        child = condition_adoc(condition.child, show_versions=show_versions)
        if "\n" in child:
            return "[source,json]\n----\n" + json.dumps(condition.to_data(), indent=2) + "\n----"
        return "!" + child
    if isinstance(condition, Implies):
        children = [
            condition_adoc(child, show_versions=show_versions)
            for child in (condition.antecedent, condition.consequent)
        ]
        if any("\n" in child for child in children):
            return "[source,json]\n----\n" + json.dumps(condition.to_data(), indent=2) + "\n----"
        return f"++(++{children[0]} -> {children[1]})"
    operators: dict[type, str] = {
        AllOf: " && ",
        AnyOf: " pass:[||] ",
        ExactlyOne: " &#2295; ",
        NoneOf: " pass:[||] ",
    }
    if type(condition) in operators:
        prefix = "!" if isinstance(condition, NoneOf) else ""
        child_texts = [
            condition_adoc(child, show_versions=show_versions) for child in condition.children
        ]
        if any("\n" in child for child in child_texts):
            return "[source,json]\n----\n" + json.dumps(condition.to_data(), indent=2) + "\n----"
        children = operators[type(condition)].join(child_texts)
        if show_versions and isinstance(condition, ExactlyOne):
            return (
                "exactly-one++(++"
                + ", ".join(
                    condition_adoc(child, show_versions=True) for child in condition.children
                )
                + ")"
            )
        return f"{prefix}++(++{children})"
    raise ExtensionDocumentError(f"Unsupported condition presentation: {condition!r}")


def extension_terms(condition: Condition) -> tuple[ExtensionTerm, ...]:
    if isinstance(condition, ExtensionTerm):
        return (condition,)
    if isinstance(condition, (AllOf, AnyOf, ExactlyOne, NoneOf)):
        return tuple(term for child in condition.children for term in extension_terms(child))
    if isinstance(condition, Not):
        return extension_terms(condition.child)
    if isinstance(condition, Implies):
        return (*extension_terms(condition.antecedent), *extension_terms(condition.consequent))
    return ()


def entities(text: str) -> str:
    for original, replacement in (
        ("&ne;", "≠"),
        ("&pm;", "±"),
        ("-&infin;", "\N{MINUS SIGN}∞"),
        ("+&infin;", "+∞"),
    ):
        text = text.replace(original, replacement)
    return text


type TextTransform = Callable[[str], str]


def version_subset_pretty(extension: Extension, versions: Sequence[ExtensionVersion]) -> str:
    selected = tuple(sorted(set(versions)))
    available = tuple(sorted(extension.versions))
    if selected == available:
        return "any"
    if len(selected) == 1:
        return f"= {selected[0].canonical}"
    low, high = selected[0], selected[-1]
    if selected == tuple(v for v in available if v >= low):
        return f">= {low.canonical}"
    if selected == tuple(v for v in available if v <= high):
        return f"<= {high.canonical}"
    if selected == tuple(v for v in available if low <= v <= high):
        return f">= {low.canonical} and <= {high.canonical}"
    # Native raises TODO for noncontiguous sets. Preserve the complete version
    # set explicitly rather than fabricate a range that includes extra releases.
    return " pass:[||] ".join(f"= {version.canonical}" for version in selected)
