# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Extension-only document assembly; no retired publication framework."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from string import Template
from textwrap import dedent

from ..architecture import ConfiguredArchitecture
from ..conditions import ConstantCondition
from ..idl.ast import FunctionDef
from ..idl.passes import to_adoc
from .compiler import DocumentCompiler
from .instructions import InstructionSections, instruction_summary
from .links import LinkResolver, anchor, anchors
from .model import (
    DocumentOptions,
    ExtensionDocumentError,
    ExtensionSelection,
    SelectionQueries,
    basename_for,
    condition_adoc,
    prose_text,
    select_extensions,
)
from .parameters import parameter_sections, parameters_for
from .prose import configured_prose_provider, needs_configured_prose
from .source_assets import source_asset_closure, write_source_assets

_REVISION = {
    "ratified": (
        "This document is in the http://riscv.org/spec-state[Ratified state] + \\\n"
        "+ \\\nNo changes are allowed. + \\\n"
        "Any desired or needed changes can be the subject of a follow-on new extension. + \\\n"
        "Ratified extensions are never revised. + \\\n"
    ),
    "frozen": (
        "This document is in the http://riscv.org/spec-state[Frozen state]. + \\\n"
        "+ \\\nChange is extremely unlikely. + \\\n"
        "A high threshold will be used, and a change will only occur because of some truly + \\\n"
        "critical issue being identified during the public review cycle. + \\\n"
        "Any other desired or needed changes can be the subject of a follow-on new extension. + \\\n"
    ),
    "development": (
        "This document is in the http://riscv.org/spec-state[Development state]. + \\\n"
        "+ \\\nChange should be expected + \\\n"
    ),
    "nonstandard-released": (
        "This document is the Release State. Changes will result in a new version number. + \\\n"
    ),
}
_PREAMBLES = {
    "ratified": (
        "[WARNING]\n.This document is in the link:http://riscv.org/spec-state[Ratified state]\n"
        "====\nNo changes are allowed. Any desired or needed changes can be the subject of a\n"
        "follow-on new extension. Ratified extensions are never revised\n====\n"
    ),
    "frozen": (
        "[WARNING]\nThis document is in the http://riscv.org/spec-state[Frozen state].\n"
        "====\nChange is extremely unlikely.\n"
        "A high threshold will be used, and a change will only occur because of some truly\n"
        "critical issue being identified during the public review cycle.\n"
        "Any other desired or needed changes can be the subject of a follow-on new extension.\n"
        "====\n"
    ),
    "development": (
        "[WARNING]\nThis document is in the http://riscv.org/spec-state[Development state].\n"
        "====\nChange should be expected\n====\n"
    ),
    "nonstandard-released": (
        "[WARNING]\nThis document is the Release State.\n"
        "====\nChanges will result in a new version number.\n====\n"
    ),
}


def template(name: str, **values: str) -> str:
    if name not in {"header.adoc", "conventions.adoc"}:
        raise ExtensionDocumentError(f"Unknown packaged document template {name!r}")
    text = files("udb.extension_docs").joinpath("templates", name).read_text(encoding="utf-8")
    return Template(text).substitute(values)


def preamble(selections: Sequence[ExtensionSelection], options: DocumentOptions) -> tuple[str, str]:
    primary = selections[0]
    latest = max(primary.versions)
    state = latest.state
    if state not in _REVISION:
        raise ExtensionDocumentError(f"{latest}: unknown publication state {state!r}")
    today = options.today or datetime.now(tz=UTC).astimezone().date()
    company = primary.extension.data.get("company", {}).get("name", "unknown")
    license = primary.extension.data.get("doc_license", {})
    published = (
        latest.release_date
        if state == "nonstandard-released"
        else latest.ratification_date
        if state == "ratified"
        else None
    )
    branding = ""
    if "RISCV" in company:
        branding += (
            ':title-logo-image: image:risc-v_logo.png["RISC-V International Logo",'
            "pdfwidth=3.25in,align=center]\n"
            ":back-cover-image: image:risc-v_logo.svg[opacity=25%]\n"
        )
    if state == "development":
        branding += ":page-background-image: image:draft.png[opacity=20%]\n"
    header = template(
        "header.adoc",
        long_name=primary.extension.data.get("long_name", primary.name),
        ext_name=primary.name,
        revdate=published or today.isoformat(),
        version=latest.canonical,
        revmark=_REVISION[state],
        company=company,
        branding=branding,
    )
    copyright_year = (
        latest.ratification_date.split("-")[0] if latest.ratification_date else str(today.year)
    )
    lines = [
        "// Preamble",
        _PREAMBLES[state],
        "",
        "[preface]",
        "== Copyright and license information",
        (
            f"This document is released under the {license.get('url', 'unknown')}"
            f"[{license.get('name', 'unknown')}]."
        ),
        "",
        f"Copyright {copyright_year} by {company}.",
        "",
        (
            "This document was created using the "
            "http://github.org/riscv/riscv-unified-db[RISC-V Unified Database] "
            f"at commit {options.revision}."
        ),
        "",
        "[preface]",
        "== Acknowledgements",
        "",
    ]
    for selection in selections:
        for version in selection.versions:
            lines.extend(
                (
                    (
                        f"Contributors to version {version.canonical} of the {selection.name} "
                        "specification (in alphabetical order) include: +"
                    ),
                    "",
                )
            )
            contributors = version.metadata.get("contributors", ())
            for person in sorted(contributors, key=lambda person: person["name"].split()[-1]):
                lines.extend(
                    (
                        (
                            f"  * {person['name']} <{person.get('email', '')}> "
                            f"({person.get('company', '')})"
                        ),
                        "",
                    )
                )
    lines.extend(
        (
            "We express our gratitude to everyone that contributed to, reviewed or",
            "improved this specification through their comments and questions.",
            "",
            "[preface]",
            "== Versions",
            "",
        )
    )
    versions = [version for selection in selections for version in selection.versions]
    if len(versions) > 1:
        lines.extend(("This specification documents the following extension versions:", ""))
        lines.extend(f"* {version}" for version in versions)
    else:
        lines.append(
            f"This specification documents version {versions[0].canonical} of {primary.name}."
        )
    lines.extend(("", "=== Version History", ""))
    for selection in selections:
        lines.extend(
            ('[frame="none",grid="none",cols="1,4"]', "|===", f"2+^| {selection.name}", "")
        )
        for version in reversed(selection.extension.versions):
            if version.version > max(selection.versions).version:
                continue
            lines.extend(
                (
                    f"h| {version.canonical}",
                    "a|",
                    "",
                    '[frame="none",grid="none",cols="1,4"]',
                    "!===",
                    "",
                    f"h! State ! {version.state}",
                )
            )
            if version.state == "ratified" and version.ratification_date:
                lines.append("h! Ratification date ! " + version.ratification_date)
            if version.changes:
                lines.extend(("h! Changes a!", ""))
                lines.extend("    * " + change for change in version.changes)
                lines.append("")
            if version.metadata.get("url"):
                lines.append("h! Ratification document ! " + version.metadata["url"])
            lines.extend(("", "!===", ""))
        lines.extend(("|===", ""))
    return header, "\n".join(lines) + "\n"


def descriptions(
    architecture: ConfiguredArchitecture,
    selections: Sequence[ExtensionSelection],
    options: DocumentOptions,
    queries: SelectionQueries,
) -> str:
    lines = ["<<<", "== Extension description", ""]
    parameters = parameter_sections(selections, queries, options)
    for selection in selections:
        lines.extend(
            (
                anchors("ext", selection.name),
                ":leveloffset: +2",
                prose_text(architecture, options, selection.extension, "description"),
                ":leveloffset: -2",
                "",
            )
        )
        # Metadata requirements are normative, even though the old helper's
        # defining_extension_requirements method currently returns [].
        for version in selection.versions:
            condition = selection.requirements_condition(version)
            if not isinstance(condition, ConstantCondition) or not condition.value:
                lines.extend(
                    (
                        "=== Requirements",
                        "",
                        f".{selection.name} {version.canonical} requirements",
                        "[example]",
                        "--",
                        condition_adoc(condition, show_versions=True),
                        "--",
                        "",
                    )
                )
        if selection.name in parameters:
            lines.append(parameters[selection.name])
    return "\n".join(lines) + "\n"


def functions(functions: Sequence[FunctionDef]) -> str:
    lines = ["<<<", "== IDL Functions", ""]
    for function in sorted(functions, key=lambda function: function.name):
        suffix = " (builtin)" if function.builtin else " (generated)" if function.generated else ""
        description_lines = function.description.splitlines()
        description = (
            description_lines[0] + "\n" + dedent("\n".join(description_lines[1:]))
            if description_lines
            else ""
        )
        return_types = ", ".join(t.to_idl() for t in function.return_types) or "void"
        lines.extend(
            (
                anchor("func", function.name),
                f"=== {function.name}{suffix}",
                "",
                description,
                "",
                '[cols="1,4"]',
                "|===",
                "h| Return Type h| `" + return_types + "`",
                "h| Arguments",
                "a|",
                "",
            )
        )
        if function.arguments:
            lines.extend(('[cols="1,4,4"]', "!===", "! Idx ! Type ! Name", ""))
            for index, argument in enumerate(function.arguments):
                lines.extend(
                    (
                        f"! {index}",
                        "h! `" + to_adoc(argument.type_name) + "`",
                        "! " + to_adoc(argument.id),
                    )
                )
            lines.append("!===")
        else:
            lines.append("None")
        lines.extend(("", "|===", ""))
        if function.body is not None and not (function.builtin or function.generated):
            lines.extend(
                (
                    '[source,idl,subs="specialchars,macros"]',
                    "----",
                    to_adoc(function.body),
                    "----",
                    "",
                )
            )
    return "\n".join(lines) + "\n"


def render_extension_document(
    architecture: ConfiguredArchitecture,
    selectors: Sequence[str],
    *,
    options: DocumentOptions | None = None,
) -> str:
    """Generate complete AsciiDoc in Python; renderer/source checkout not needed."""
    from .csrs import CsrSections, csr_summary

    options = options or DocumentOptions()
    selections = select_extensions(architecture, selectors)
    basename_for(selections, options)
    queries = SelectionQueries(architecture)
    instructions = queries.records("instruction", selections)
    csrs = queries.records("csr", selections)
    if options.prose is None and any(
        needs_configured_prose(record.data)
        for record in (
            *(selection.extension for selection in selections),
            *(record for selection in selections for record in parameters_for(selection, queries)),
            *instructions,
            *csrs,
        )
    ):
        options = replace(options, prose=configured_prose_provider(architecture))
    compiler = DocumentCompiler(architecture)
    inst_sections = InstructionSections(architecture, compiler, selections, queries, options)
    csr_sections = CsrSections(architecture, compiler, queries, options)
    header, introduction = preamble(selections, options)
    parts = [
        header,
        "= " + selections[0].extension.data.get("long_name", selections[0].name),
        introduction,
        template("conventions.adoc"),
        descriptions(architecture, selections, options, queries),
    ]
    if instructions:
        parts.append(instruction_summary(instructions, selections, queries, options))
    if csrs:
        parts.append(csr_summary(csrs, selections, queries, compiler))
        parts.append(
            '<<<\n[#csrs,reftext="CSRs (in alphabetical order)"]\n== Csrs (in alphabetical order)\n'
        )
        for csr in csrs:
            parts.extend(("<<<\n:leveloffset: +2", csr_sections.render(csr), ":leveloffset: -2"))
    if instructions:
        parts.append(
            '[.portrait]\n<<<\n[#insns,reftext="Instructions (in alphabetical order)"]\n'
            "== Instructions (in alphabetical order)\n"
        )
        for instruction in sorted(instructions, key=lambda item: item.name):
            parts.extend(
                (":leveloffset: +2", inst_sections.render(instruction), ":leveloffset: -2\n\n<<<")
            )
    reachable = {
        **compiler.source_functions,
        **inst_sections.functions,
        **csr_sections.functions,
    }
    parts.append(functions(compiler.source_function_closure(reachable)))
    return LinkResolver(architecture).resolve("\n\n".join(parts).rstrip() + "\n")


def generate_extension_document(
    architecture: ConfiguredArchitecture,
    selectors: Sequence[str],
    output_dir: str | Path,
    *,
    options: DocumentOptions | None = None,
) -> Path:
    """Validate and assemble before writing; default basename preserves selector."""
    options = options or DocumentOptions()
    selections = select_extensions(architecture, selectors)
    basename = basename_for(selections, options)
    text = render_extension_document(architecture, selectors, options=options)
    assets = source_asset_closure(text, supplied=options.source_assets)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (basename + ".adoc")
    if target.is_symlink() or not target.resolve().is_relative_to(directory.resolve()):
        raise ExtensionDocumentError(f"AsciiDoc output must not follow a symlink: {target}")
    write_source_assets(assets, directory)
    with target.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    return target
