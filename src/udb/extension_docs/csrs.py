# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Retained CSR attributes, formats, field semantics and read/write behavior."""

from __future__ import annotations

import json
from collections.abc import Sequence

from ..architecture import ConfiguredArchitecture, QueryPresence
from ..conditions import ExtensionTerm
from ..database import Csr
from ..idl.errors import IdlValueUnknown
from ..idl.passes import prune, reachable_functions, to_adoc, to_option_adoc
from ..idl_architecture import ArchitectureCompiler
from ..idl_environment import _multi_xlen_in_mode, possible_xlens
from ..versions import VersionRequirement
from .instructions import CHECK, diagram
from .links import anchors, identifier, link
from .model import (
    DocumentOptions,
    ExtensionDocumentError,
    ExtensionSelection,
    SelectionQueries,
    condition_adoc,
    defined_by,
    extension_terms,
    prose_text,
)

_XLEN_FIELD = {
    "M": "CSR[misa].MXL",
    "D": "CSR[misa].MXL",
    "S": "CSR[mstatus].SXL",
    "U": "CSR[mstatus].UXL",
    "VS": "CSR[hstatus].VSXL",
    "VU": "CSR[vsstatus].UXL",
}
_MODES = {
    "M": ("M",),
    "D": ("M", "D"),
    "S": ("M", "S", "VS"),
    "VS": ("M", "S", "VS"),
    "U": ("M", "S", "U", "VS", "VU"),
}


def csr_summary(
    csrs: Sequence[Csr],
    selections: Sequence[ExtensionSelection],
    queries: SelectionQueries,
    compiler: ArchitectureCompiler,
) -> str:
    descriptors = compiler.global_symbol_table.csr_hash
    lines = ["[.portrait]", "<<<", "== CSR summary", ""]
    for selection in selections:
        rows = [
            csr
            for csr in csrs
            if any(
                queries.implies(
                    ExtensionTerm(selection.name, (VersionRequirement.exact(v.version),)),
                    defined_by(csr),
                )
                for v in selection.versions
            )
        ]
        if not rows:
            continue
        if len(selections) > 1:
            lines.extend((f"=== {selection.name}", ""))
        lines.extend(
            (
                f"The following {len(rows)} CSRs are affected by this extension.",
                "",
                "[%autowidth]",
                "|===",
                "| RV32 | RV64 | CSR | Name"
                + (
                    "| " + " | ".join("v" + v.canonical for v in selection.versions)
                    if len(selection.versions) > 1
                    else ""
                ),
                "",
            )
        )
        for csr in rows:
            descriptor = descriptors[csr.name]
            lines.extend(
                (
                    "| " + (CHECK if descriptor.defined_in_base(32) else ""),
                    "| " + (CHECK if descriptor.defined_in_base(64) else ""),
                    "| " + link("csr", csr.name),
                    "| " + csr.data.get("long_name", csr.name),
                )
            )
            if len(selection.versions) > 1:
                lines.append(
                    "| "
                    + " | ".join(
                        CHECK
                        if queries.implies(
                            ExtensionTerm(selection.name, (VersionRequirement.exact(v.version),)),
                            defined_by(csr),
                        )
                        else ""
                        for v in selection.versions
                    )
                )
        lines.extend(("", "|===", ""))
    return "\n".join(lines) + "\n"


class CsrSections:
    def __init__(
        self,
        architecture: ConfiguredArchitecture,
        compiler: ArchitectureCompiler,
        queries: SelectionQueries,
        options: DocumentOptions,
    ) -> None:
        self.architecture = architecture
        self.compiler = compiler
        self.queries = queries
        self.options = options
        self.descriptors = compiler.global_symbol_table.csr_hash
        self.functions = {}
        self.cache = {}

    def length_condition(self, csr: Csr, base: int) -> str:
        encoding = {32: 0, 64: 1}[base]
        length = csr.data["length"]
        modes = {"MXLEN": "M", "SXLEN": "S", "VSXLEN": "VS"}
        if length in modes:
            return f"{_XLEN_FIELD[modes[length]]} == {encoding}"
        if length == "XLEN":
            modes = [
                mode
                for mode in _MODES[csr.data["priv_mode"]]
                if _multi_xlen_in_mode(self.architecture, mode)
            ]
            if not modes:
                raise ExtensionDocumentError(f"{csr.name}: no dynamic mode selects XLEN")
            return " || ".join(
                f"(priv_mode() == PrivilegeMode::{mode} && {_XLEN_FIELD[mode]} == {encoding})"
                for mode in modes
            )
        raise ExtensionDocumentError(f"{csr.name}: unexpected dynamic length {length!r}")

    def length_pretty(self, csr: Csr, descriptor) -> str:
        if descriptor.dynamic_length():
            return "\n".join(
                f"* {descriptor.length(base)} when {self.length_condition(csr, base)}"
                for base in (32, 64)
            )
        length = descriptor.length(descriptor._base or self.architecture.configuration.mxlen)
        return f"{length}-bit"

    def location_pretty(self, csr: Csr, field) -> str:
        def text(base):
            location = field.location(base)
            return (
                str(location.start)
                if len(location) == 1
                else f"{location.stop - 1}:{location.start}"
            )

        if self.dynamic_location(csr, field):
            mode = csr.data["priv_mode"]
            return (
                "\n".join(
                    f"* {text(base)} when {_XLEN_FIELD[mode]} == {index}"
                    for index, base in enumerate((32, 64))
                )
                + "\n"
            )
        return text(self.architecture.configuration.mxlen)

    def dynamic_location(self, csr: Csr, field) -> bool:
        return "location" not in field._data and any(
            _multi_xlen_in_mode(self.architecture, mode) for mode in _MODES[csr.data["priv_mode"]]
        )

    def field_type(self, csr: Csr, field) -> str:
        try:
            value = field.type(None)
            if value is not None:
                return value
        except IdlValueUnknown:
            pass
        compiled = self.compiler.compile_field(csr.name, field.name, "type()")
        return to_option_adoc(compiled.ast)

    def field_reset(self, csr: Csr, field) -> str:
        try:
            return str(field.reset_value)
        except IdlValueUnknown:
            compiled = self.compiler.compile_field(csr.name, field.name, "reset_value()")
            return to_option_adoc(compiled.ast)

    def waveform(self, csr: Csr, descriptor, base: int) -> str:
        fields = sorted(
            (field for field in descriptor.fields if field.defined_in_base(base)),
            key=lambda field: field.location(base).start,
        )
        rows = []
        last = -1
        length = descriptor.length(base)
        if not isinstance(length, int):
            raise ExtensionDocumentError(f"{csr.name}: unresolved RV{base} format length")
        for field in fields:
            location = field.location(base)
            if location.start > last + 1:
                rows.append({"bits": location.start - last - 1, "type": 1})
            if location.start <= last or location.stop > length:
                raise ExtensionDocumentError(
                    f"{csr.name}.{field.name}: overlapping/out-of-range field"
                )
            presence = self.queries.configured_presence(field._condition)
            optional = (
                self.architecture.configuration.kind.value == "partially configured"
                and presence is QueryPresence.POSSIBLE
            )
            rows.append({"bits": len(location), "name": field.name, "type": 2 if optional else 3})
            last = location.stop - 1
        if fields and last != length - 1:
            rows.append({"bits": length - 1 - last, "type": 1})
        return json.dumps(
            {"reg": rows, "config": {"bits": length, "lanes": length // 16}},
            separators=(",", ":"),
        )

    def discover(self, csr: Csr, descriptor) -> None:
        for base in possible_xlens(self.architecture):
            if not descriptor.defined_in_base(base):
                continue
            bodies = []
            if csr.data.get("sw_read()"):
                bodies.append(self.compiler.compile_csr(csr.name, effective_xlen=base))
            for field in descriptor.fields:
                if not field.defined_in_base(base):
                    continue
                for behavior in ("type()", "reset_value()", "sw_write(csr_value)"):
                    if field._data.get(behavior):
                        bodies.append(
                            self.compiler.compile_field(
                                csr.name, field.name, behavior, effective_xlen=base
                            )
                        )
            for compiled in bodies:
                tree = prune(compiled.ast, compiled.symtab)
                for function in reachable_functions(tree, compiled.symtab, cache=self.cache):
                    self.functions[function.name] = function

    def render(self, csr: Csr) -> str:
        descriptor = self.descriptors[csr.name]
        fields = descriptor.fields
        lines = [
            anchors("csr", csr.name),
            "= " + csr.name,
            "",
            "*" + csr.data.get("long_name", csr.name) + "*",
            "",
            prose_text(self.architecture, self.options, csr, "description"),
            "",
            "== Attributes",
            '[%autowidth,separator="^"]',
            "|===",
            "h^ Requirement a^ " + condition_adoc(defined_by(csr)),
            "h^ Defining extensions",
            "a^",
            "",
            "!===",
        ]
        names = sorted(
            name
            for name in {term.name for term in extension_terms(defined_by(csr))}
            if any(
                self.queries.implies(
                    ExtensionTerm(name, (VersionRequirement.exact(version.version),)),
                    defined_by(csr),
                )
                for version in self.architecture.database.extension(name).versions
            )
        )
        for name in names:
            ext = self.architecture.database.extension(name)
            lines.append(f"h! {name} ! {ext.data.get('long_name', name)}")
        lines.extend(("!===", "", f"h^ CSR Address    ^ 0x{csr.data.get('address', 0):x}"))
        if csr.data["priv_mode"] == "VS":
            lines.append(f"h^ Virtual CSR Address    ^ 0x{csr.data['virtual_address']:x}")
        lines.extend(
            (
                "h^ Length         ^ " + self.length_pretty(csr, descriptor),
                "h^ Privilege Mode ^ " + csr.data["priv_mode"],
                "|===",
                "",
                "== Format",
            )
        )
        dynamic = descriptor.dynamic_length() or any(
            self.dynamic_location(csr, field) for field in fields
        )
        if dynamic:
            lines.append("This CSR format changes dynamically.")
            for base in (32, 64):
                lines.extend(
                    (
                        f".{csr.name} Format when {self.length_condition(csr, base)}",
                        diagram(self.waveform(csr, descriptor, base)),
                    )
                )
        else:
            base = descriptor._base or self.architecture.configuration.mxlen or 64
            lines.extend((f".{csr.name} format", diagram(self.waveform(csr, descriptor, base))))
        lines.extend(
            (
                "== Field Summary",
                "",
                (
                    '[%autowidth,separator=@,float="center",align="center",cols="^,<,<,<",'
                    'options="header",role="stretch"]'
                ),
                "|===",
                "@Name @ Location @ Type @ Reset Value",
                "",
            )
        )
        details = []
        for field in fields:
            location = self.location_pretty(csr, field)
            type_text = self.field_type(csr, field)
            reset = self.field_reset(csr, field)
            name = csr.name + "*" + field.name
            if self.options.include_csr_field_descriptions:
                label = link("csr_field", name, csr.name + "." + field.name)
            else:
                label = f"[[{identifier('csr_field', name)}]]{field.name}"
            lines.extend(("@ " + label, "@ " + location, "@ " + type_text, "@ " + reset, ""))
            if not self.options.include_csr_field_descriptions:
                continue
            details.extend(
                (
                    anchors("csr_field", name),
                    f"=== `{field.name}`",
                    "",
                    "[example]",
                    "--",
                    "Location::",
                    location,
                    "",
                    "Description::",
                    prose_text(
                        self.architecture, self.options, csr, "fields", field.name, "description"
                    ),
                    "",
                    "Type::",
                    type_text,
                    "",
                    "Reset value::",
                    reset,
                    "",
                    "--",
                    "",
                )
            )
        lines.extend(("|===", ""))
        if self.options.include_csr_field_descriptions:
            lines.extend(("== Fields", ""))
            if not fields:
                lines.append(
                    "This CSR has no fields. However, it must still exist (not cause an "
                    "`Illegal Instruction` trap) and always return zero on a read."
                )
            lines.extend(details)
        if any(field._data.get("sw_write(csr_value)") for field in fields):
            lines.extend(
                (
                    "== Software write",
                    "",
                    "This CSR may store a value that is different from what software attempts to write.",
                    "",
                    "When a software write occurs (_e.g._, through `csrrw`), the following determines the",
                    "written value:",
                    "",
                    "[source,idl]",
                    "----",
                )
            )
            for field in fields:
                body = field._data.get("sw_write(csr_value)")
                lines.append(f"{field.name} = {body if body else 'csr_value.' + field.name}")
            lines.extend(("----", ""))
        if csr.data.get("sw_read()"):
            compiled = self.compiler.compile_csr(csr.name, type_check=False)
            lines.extend(
                (
                    "== Software read",
                    "",
                    "This CSR may return a value that is different from what is stored in hardware.",
                    "",
                    '[source,idl,subs="specialchars,macros"]',
                    "----",
                    to_adoc(compiled.ast),
                    "----",
                    "",
                )
            )
        self.discover(csr, descriptor)
        return "\n".join(lines) + "\n"
