# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Normative parameter records and constraints, reusing accepted conditions."""

from __future__ import annotations

import json

from ..conditions import ConstantCondition, parse_condition
from ..database import DatabaseObject
from .links import anchors, link
from .model import (
    DocumentOptions,
    ExtensionSelection,
    SelectionQueries,
    condition_adoc,
    defined_by,
    extension_terms,
    prose_text,
)


def parameters_for(selection: ExtensionSelection, queries: SelectionQueries):
    result = []
    for record in queries.architecture.database.objects("parameter"):
        condition = defined_by(record)
        if selection.name not in {term.name for term in extension_terms(condition)}:
            continue
        if not queries.impossible(selection.condition & condition):
            result.append(record)
    return tuple(sorted(result, key=lambda record: record.name))


def render_parameter(
    record: DatabaseObject,
    queries: SelectionQueries,
    options: DocumentOptions,
) -> str:
    architecture = queries.architecture
    lines = [
        anchors("ext_param", record.name),
        f"==== `{record.name}`",
        "",
        record.data.get("long_name", record.name),
        "",
        prose_text(architecture, options, record, "description"),
        "",
        "Defined when: " + condition_adoc(defined_by(record), show_versions=True),
        "",
        "[source,json]",
        "----",
        json.dumps(dict(record.data["schema"]), indent=2, default=dict),
        "----",
        "",
    ]
    if record.name in architecture.configuration.params:
        lines.extend(
            (
                "Configured value::",
                "[source,json]",
                "----",
                json.dumps(architecture.configuration.params[record.name], indent=2, default=dict),
                "----",
                "",
            )
        )
    requirement = parse_condition(record.data.get("requirements", True))
    if not isinstance(requirement, ConstantCondition) or not requirement.value:
        lines.extend(
            (
                "Requirements::",
                condition_adoc(requirement, show_versions=True),
                "",
            )
        )
    return "\n".join(lines) + "\n"


def parameter_sections(
    selections,
    queries: SelectionQueries,
    options: DocumentOptions,
) -> dict[str, str]:
    emitted = set()
    result = {}
    for selection in selections:
        records = parameters_for(selection, queries)
        if not records:
            continue
        lines = ["=== Parameters", ""]
        for record in records:
            if record.name in emitted:
                lines.extend((link("ext_param", record.name, f"`{record.name}`"), ""))
            else:
                lines.append(render_parameter(record, queries, options))
                emitted.add(record.name)
        result[selection.name] = "\n".join(lines) + "\n"
    return result
