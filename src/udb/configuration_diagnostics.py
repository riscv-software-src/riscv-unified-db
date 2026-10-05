# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Presentation of configuration conflicts using immutable captured inputs.

This module does not solve constraints, interpret IDL, or reopen source files.
Core labels remain the identity of each entry, including unknown labels.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from .architecture import ArchitectureCheck, ArchitectureCheckStatus, ConfiguredArchitecture
from .configuration import ConfigurationKind, Presence
from .source import SourceMap, SourceSpan, ValuePath

_MAX_TEXT = 240
_MAX_ARRAY_INDICES = 8
_MAX_DETAILS = 12


@dataclass(frozen=True, slots=True)
class ConflictDetail:
    message: str
    source: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class ConflictExplanation:
    """One core member, retaining its exact label independently of presentation."""

    label: str
    summary: str
    details: tuple[ConflictDetail, ...] = ()
    source: SourceSpan | None = None
    raw: bool = False


def _bounded(text: str, limit: int = _MAX_TEXT) -> str:
    """Truncate captured text without normalizing its literal content."""

    if len(text) <= limit:
        return text
    return text[:limit] + "... [truncated]"


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return _bounded(repr(value))


def summarize_value(value: Any) -> str:
    """Describe flat configuration values without an unbounded array dump.

    The most frequent typed value is summarized by count; other indices are
    observational facts, not a claim that those entries caused the conflict.
    Boolean and integer values are deliberately counted separately.
    """

    if not isinstance(value, (list, tuple)):
        return _scalar(value)
    if not value:
        return "array of 0 entries"
    counts = Counter((type(item), item) for item in value)
    dominant, count = counts.most_common(1)[0]
    summary = f"array of {len(value)} entries; {count} entries are {_scalar(dominant[1])}"
    if count == len(value):
        return summary
    differing = []
    for index, item in enumerate(value):
        if (type(item), item) != dominant:
            differing.append(f"[{index}]={_scalar(item)}")
            if len(differing) == _MAX_ARRAY_INDICES:
                break
    summary += "; other entries: " + ", ".join(differing)
    omitted = len(value) - count - _MAX_ARRAY_INDICES
    if omitted > 0:
        summary += f"; {omitted} more other entries omitted"
    return summary


def _location(sources: SourceMap | None, path: ValuePath) -> SourceSpan | None:
    return None if sources is None else sources.nearest(*path)


def _rule(raw: Any, *, context: Literal["extension", "param"] | None = None) -> str:
    """Render captured syntax, without evaluating or revalidating it."""

    if isinstance(raw, bool):
        return _scalar(raw)
    if context == "extension" and isinstance(raw, str):
        return f"extension {raw}"
    if not isinstance(raw, Mapping):
        return _bounded(repr(raw))
    if context == "extension" and "name" in raw:
        version = raw.get("version")
        return f"extension {raw['name']}" + (
            f" ({summarize_value(version)})" if version is not None else ""
        )
    if context == "param" and "name" in raw:
        name = raw["name"]
        if "index" in raw:
            name += f"[{raw['index']}]"
        elif raw.get("size"):
            name = f"size({name})"
        elif "range" in raw:
            name += f"[{raw['range']}]"
        for key, operator in (
            ("equal", "="),
            ("notEqual", "!="),
            ("lessThan", "<"),
            ("lessThanOrEqual", "<="),
            ("greaterThan", ">"),
            ("greaterThanOrEqual", ">="),
            ("includes", "includes"),
            ("oneOf", "is one of"),
        ):
            if key in raw:
                return _bounded(f"{name} {operator} {summarize_value(raw[key])}")
    if "idl()" in raw:
        return "IDL: " + _bounded(raw["idl()"])
    for key, joiner in (("allOf", " AND "), ("anyOf", " OR ")):
        if key in raw:
            return _bounded(
                "(" + joiner.join(_rule(child, context=context) for child in raw[key]) + ")"
            )
    for key, description in (("oneOf", "exactly one of"), ("noneOf", "none of")):
        if key in raw:
            return _bounded(
                description
                + " ("
                + ", ".join(_rule(child, context=context) for child in raw[key])
                + ")"
            )
    if "not" in raw:
        return _bounded("NOT (" + _rule(raw["not"], context=context) + ")")
    if "if" in raw and "then" in raw:
        return _bounded(
            "(" + _rule(raw["if"]) + ") implies (" + _rule(raw["then"], context=context) + ")"
        )
    if "extension" in raw:
        return _rule(raw["extension"], context="extension")
    if "param" in raw:
        return _rule(raw["param"], context="param")
    if "xlen" in raw:
        return f"XLEN = {raw['xlen']}"
    return _bounded(repr(raw))


def _requirement_details(
    raw: Any,
    sources: SourceMap | None,
    path: ValuePath,
    *,
    prefix: str = "requirement",
) -> tuple[ConflictDetail, ...]:
    details: list[ConflictDetail] = []
    rule_path = (*path, "idl()") if isinstance(raw, Mapping) and "idl()" in raw else path
    details.append(ConflictDetail(f"{prefix}: {_rule(raw)}", _location(sources, rule_path)))
    pending = [(raw, path)]
    while pending and len(details) < _MAX_DETAILS:
        current, current_path = pending.pop()
        if isinstance(current, Mapping):
            if current_path != path and "idl()" in current:
                details.append(
                    ConflictDetail(
                        "captured IDL clause: " + _bounded(current["idl()"]),
                        _location(sources, (*current_path, "idl()")),
                    )
                )
            reason = current.get("reason")
            if isinstance(reason, str):
                details.append(
                    ConflictDetail(
                        "reason: " + _bounded(reason),
                        _location(sources, (*current_path, "reason")),
                    )
                )
            pending.extend(
                (value, (*current_path, key))
                for key, value in reversed(tuple(current.items()))
                if key != "reason" and isinstance(value, (Mapping, list, tuple))
            )
        elif isinstance(current, (list, tuple)):
            pending.extend(
                (value, (*current_path, index))
                for index, value in reversed(tuple(enumerate(current)))
            )
    if pending:
        details.append(ConflictDetail("additional captured reasons omitted"))
    return tuple(details)


def explain_conflict(
    architecture: ConfiguredArchitecture, result: ArchitectureCheck
) -> tuple[ConflictExplanation, ...]:
    """Attach captured provenance without changing core membership or order.

    Known labels are reconstructed from structured owners, never parsed for
    values. Unrecognized labels explicitly fall back to the exact raw identity.
    Nothing here is evidence of an independently sufficient cause: the entries
    describe the solver's jointly inconsistent core.
    """

    if result.status is not ArchitectureCheckStatus.UNSAT or not result.conflict:
        return ()
    wanted = set(result.conflict)
    entries: dict[str, ConflictExplanation] = {}

    def requirement(
        label: str,
        summary: str,
        raw: Any,
        sources: SourceMap | None,
        path: ValuePath = ("requirements",),
    ) -> None:
        if label in wanted and raw is not None:
            entries[label] = ConflictExplanation(
                label, summary, _requirement_details(raw, sources, path), _location(sources, path)
            )

    for extension in architecture.database.extensions:
        requirement(
            f"extension {extension.name} requirements",
            f"Requirements for extension {extension.name}",
            extension.data.get("requirements"),
            extension.sources,
        )
        for version in extension.versions:
            label = f"extension {extension.name}@{version.canonical} requirements"
            if label not in wanted:
                continue
            index = next(
                index
                for index, declaration in enumerate(extension.data["versions"])
                if declaration["version"] == version.metadata["version"]
            )
            requirement(
                label,
                f"Requirements for extension {extension.name}@{version.canonical}",
                version.metadata.get("requirements"),
                extension.sources,
                ("versions", index, "requirements"),
            )
    parameters = {
        parameter.name: parameter for parameter in architecture.database.objects("parameter")
    }
    for parameter in parameters.values():
        requirement(
            f"parameter {parameter.name} requirements",
            f"Requirements for parameter {parameter.name}",
            parameter.data.get("requirements"),
            parameter.sources,
        )

    configuration = architecture.configuration
    sources = configuration.sources
    data = configuration.to_dict()
    groups = (
        (("implemented_extensions", Presence.MANDATORY),)
        if configuration.kind is ConfigurationKind.FULL
        else (
            ("mandatory_extensions", Presence.MANDATORY),
            ("non_mandatory_extensions", Presence.OPTIONAL),
            ("prohibited_extensions", Presence.PROHIBITED),
        )
    )
    selection_paths = {
        (presence, item["name"]): (group, index)
        for group, presence in groups
        for index, item in enumerate(data.get(group, ()))
    }
    for selection in configuration.extensions:
        label = f"configuration {selection.presence.value} extension {selection.name}"
        if label in wanted:
            path = selection_paths[selection.presence, selection.name]
            entries[label] = ConflictExplanation(
                label,
                f"Configuration {selection.presence.value} extension {selection.name}",
                (
                    ConflictDetail(
                        "requested versions: " + ", ".join(map(str, selection.requirements)),
                        _location(sources, (*path, "version")),
                    ),
                ),
                _location(sources, path),
            )
    listed = {selection.name for selection in configuration.extensions}
    if configuration.kind is ConfigurationKind.FULL or not configuration.additional_extensions:
        for extension in architecture.database.extensions:
            label = f"configuration excludes extension {extension.name}"
            if label in wanted and extension.name not in listed:
                entries[label] = ConflictExplanation(
                    label,
                    f"Configuration excludes unlisted extension {extension.name}",
                    source=_location(sources, ("additional_extensions",)),
                )
    for name, value in configuration.params.items():
        label = f"configuration parameter {name}={value!r}"
        source = _location(sources, ("params", name))
        if label in wanted:
            entries[label] = ConflictExplanation(
                label,
                f"Configuration supplies {name} = {summarize_value(value)}",
                source=source,
            )
        label = f"configuration parameter {name} is defined"
        if label in wanted and name in parameters:
            parameter = parameters[name]
            raw = parameter.data.get("definedBy", True)
            if isinstance(raw, str):
                raw = {"extension": {"name": raw}}
            entries[label] = ConflictExplanation(
                label,
                f"Configuration requires parameter {name} to be defined",
                (
                    ConflictDetail("This asserts existence, not a supplied value."),
                    *_requirement_details(
                        raw, parameter.sources, ("definedBy",), prefix="definition condition"
                    ),
                ),
                source,
            )
    requirement(
        "configuration requirements",
        "Configuration requirements",
        configuration.requirements,
        sources,
    )
    return tuple(
        entries.get(
            label,
            ConflictExplanation(
                label,
                "raw core label: " + _bounded(label),
                (ConflictDetail("No captured explanation is available for this core label."),),
                raw=True,
            ),
        )
        for label in result.conflict
    )


def format_check_diagnostics(
    architecture: ConfiguredArchitecture, result: ArchitectureCheck
) -> tuple[str, ...]:
    """Format stderr lines; non-core and non-UNSAT diagnostics stay unchanged."""

    explanations = explain_conflict(architecture, result)
    lines: list[str] = []
    for diagnostic in result.diagnostics:
        location = diagnostic.source or diagnostic.label
        prefix = f"{location}: " if location else ""
        if diagnostic.code != "unsatisfiable" or not explanations:
            lines.append(f"{prefix}{diagnostic.code}: {diagnostic.message}")
            continue
        lines.append(f"{prefix}unsatisfiable: configuration constraints are mutually unsatisfiable")
        lines.append("  Conflicting constraints (jointly inconsistent):")
        for explanation in explanations:
            location = f" [{explanation.source.label}]" if explanation.source else ""
            lines.append(f"  - {explanation.summary}{location}")
            for detail in explanation.details:
                location = f" [{detail.source.label}]" if detail.source else ""
                lines.append(f"      {detail.message}{location}")
    return tuple(lines)
