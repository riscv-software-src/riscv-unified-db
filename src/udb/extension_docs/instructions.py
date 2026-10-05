# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Complete retained instruction sections using typed fields and native IDL passes."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from ..architecture import ConfiguredArchitecture
from ..conditions import ExtensionTerm, any_of
from ..database import Instruction
from ..idl.passes import prune, reachable_functions, to_adoc
from ..idl_architecture import ArchitectureCompiler
from ..idl_environment import possible_xlens
from ..instruction_fields import DecodeField, EncodingFields, InstructionFieldBuilder
from ..versions import VersionRequirement
from .links import anchors, link
from .model import (
    DocumentOptions,
    ExtensionSelection,
    SelectionQueries,
    condition_adoc,
    defined_by,
    entities,
    prose_text,
    version_subset_pretty,
)

CHECK = "&#x2713;"


def extract(field: DecodeField) -> str:
    parts = [
        f"$encoding[{part.high}:{part.low}]" if part.width > 1 else f"$encoding[{part.low}]"
        for part in field.ranges
    ]
    if field.left_shift:
        parts.append(f"{field.left_shift}'d0")
    text = parts[0] if len(parts) == 1 else "{" + ", ".join(parts) + "}"
    return f"sext({text}, {field.width})" if field.sign_extend else text


def waveform(encoding: EncodingFields) -> str:
    fields = [
        (
            opcode.location.low,
            {"bits": opcode.location.width, "name": f"0x{opcode.value:x}", "type": 2},
        )
        for opcode in encoding.opcodes
    ]
    for variable in encoding.variables:
        # Adjacent pieces are a single display field, even if extraction has
        # multiple pieces. This matches the native grouped_encoding_fields.
        groups: list[list[int]] = []
        for part in sorted(variable.ranges, key=lambda part: part.low):
            if groups and groups[-1][1] + 1 == part.low:
                groups[-1][1] = part.high
            else:
                groups.append([part.low, part.high])
        pretty = variable.name
        if variable.exclusions:
            constraint = (
                str(variable.exclusions[0])
                if len(variable.exclusions) == 1
                else "{" + ",".join(map(str, variable.exclusions)) + "}"
            )
            pretty += " != " + constraint
        positions = {bit: variable.width - index - 1 for index, bit in enumerate(variable.bits)}
        for low, high in groups:
            name = pretty
            if len(groups) != 1 or high - low + 1 != variable.width:
                ranges = []
                for bit in range(high, low - 1, -1):
                    position = positions[bit]
                    if ranges and ranges[-1][1] - 1 == position:
                        ranges[-1][1] = position
                    else:
                        ranges.append([position, position])
                name += (
                    "["
                    + "|".join(
                        str(start) if start == end else f"{start}:{end}" for start, end in ranges
                    )
                    + "]"
                )
            fields.append((low, {"bits": high - low + 1, "name": name, "type": 4}))
    text = json.dumps({"reg": [field for _, field in sorted(fields)]}, separators=(",", ":"))
    text = re.sub(r'"(0x[0-9a-f]+)"', r"\1", text)
    return text.replace('"name":', '"name": ')


def diagram(text: str) -> str:
    return "[wavedrom, ,svg,subs='attributes',width=\"100%\"]\n....\n" + text + "\n....\n"


def instruction_summary(
    instructions: Sequence[Instruction],
    selections: Sequence[ExtensionSelection],
    queries: SelectionQueries,
    options: DocumentOptions,
) -> str:
    builder = InstructionFieldBuilder(queries.architecture.database)
    lines = ["<<<", "== Instruction list", ""]
    for selection in selections:
        if len(selections) > 1:
            lines.extend((f"=== {selection.name}", ""))
        # Preserve native's direction: records whose definition implies at
        # least one of the selected extension versions.
        direct = [
            item
            for item in instructions
            if any(
                queries.implies(
                    defined_by(item),
                    ExtensionTerm(selection.name, (VersionRequirement.exact(v.version),)),
                )
                for v in selection.versions
            )
        ]
        if direct:
            lines.extend(
                (
                    (
                        f"The following {len(direct)} instructions must be implemented when "
                        f"{selection.name} is implemented:"
                    ),
                    "",
                    f".Instructions defined by {selection.pretty}",
                    '[cols="1,1,5,5"]',
                    "|===",
                    "| RV32 | RV64 | Mnemonic | Instruction"
                    + (
                        " | " + " | ".join("v" + v.canonical for v in selection.versions)
                        if len(selection.versions) > 1
                        else ""
                    ),
                    "",
                )
            )
            for inst in direct:
                descriptor = builder.describe(inst)
                lines.extend(
                    (
                        "| " + (CHECK if descriptor.encoding(32) else ""),
                        "| " + (CHECK if descriptor.encoding(64) else ""),
                        "| `" + (inst.name + " " + inst.data.get("assembly", "")).strip() + "`",
                        "| " + link("inst", inst.name, inst.data.get("long_name", inst.name)),
                    )
                )
                if len(selection.versions) > 1:
                    lines.append(
                        "| "
                        + " | ".join(
                            CHECK
                            if queries.implies(
                                ExtensionTerm(
                                    selection.name, (VersionRequirement.exact(v.version),)
                                ),
                                defined_by(inst),
                            )
                            else ""
                            for v in selection.versions
                        )
                    )
            lines.extend(("|===", ""))
        if options.include_implied:
            implied = [
                inst
                for inst in instructions
                if any(
                    queries.implies(selection.requirements_condition(v), defined_by(inst))
                    for v in selection.versions
                )
            ]
            if implied:
                lines.extend(
                    (
                        (
                            f"{'Additionally, the' if direct else 'The'} following {len(implied)} "
                            "instructions are implied by the requirements"
                        ),
                        "of this extension.",
                        "",
                        f".{selection.pretty} requirements",
                        "--",
                        condition_adoc(
                            any_of(
                                *(selection.requirements_condition(v) for v in selection.versions)
                            )
                        ),
                        "--",
                        "",
                        f".Instructions implied by {selection.pretty}",
                        '[cols="4,4,1",separator="^"]',
                        "|===",
                        "^ Mnemonic ^ Instruction ^ Defined by",
                        "",
                    )
                )
                for inst in sorted(implied, key=lambda item: item.name):
                    lines.extend(
                        (
                            "^ `" + (inst.name + " " + inst.data.get("assembly", "")).strip() + "`",
                            "^ " + link("inst", inst.name, inst.data.get("long_name", inst.name)),
                            "a^ " + condition_adoc(defined_by(inst)),
                        )
                    )
                lines.extend(("|===", ""))
    if len(selections) > 1:
        lines.extend(
            (
                "[.landscape]",
                "<<<",
                "== Instruction Summary",
                "",
                "[%autowidth]",
                "|===",
                "| Mnemonic | " + " | ".join(f"`{s.name}`" for s in selections),
                "",
            )
        )
        for inst in instructions:
            lines.extend(
                (
                    f"| `{inst.name}`",
                    "| "
                    + " | ".join(
                        CHECK if queries.implies(s.condition, defined_by(inst)) else ""
                        for s in selections
                    ),
                )
            )
        lines.extend(("|===", ""))
    return "\n".join(lines) + "\n"


class InstructionSections:
    def __init__(
        self,
        architecture: ConfiguredArchitecture,
        compiler: ArchitectureCompiler,
        selections: Sequence[ExtensionSelection],
        queries: SelectionQueries,
        options: DocumentOptions,
    ) -> None:
        self.architecture = architecture
        self.compiler = compiler
        self.selections = selections
        self.queries = queries
        self.options = options
        # Unconfigured descriptors retain both structural encodings, including
        # RV32 diagrams in a configured RV64 document (the native policy).
        self.fields = InstructionFieldBuilder(architecture.database)
        self.functions = {}
        self.cache = {}

    def render(self, inst: Instruction) -> str:
        fields = self.fields.describe(inst)
        raw = inst.data.get("encoding", inst.data.get("format", {}))
        multi = "RV32" in raw
        bases = (32, 64) if multi else (64 if fields.encoding(64) is not None else 32,)
        lines = [
            anchors("inst", inst.name),
            f"= {inst.name}",
            "",
            "Synopsis::",
            inst.data.get("long_name", inst.name),
            "",
            "Mnemonic::",
            "----",
            f"{inst.name} {fields.assembly or ''}",
            "----",
            "",
            "Encoding::",
        ]
        if multi:
            lines.extend(
                ("[NOTE]", "This instruction has different encodings in RV32 and RV64", "")
            )
        for base in bases:
            encoding = fields.encoding(base)
            if encoding is None:
                raise ValueError(f"{inst.name}: missing RV{base} encoding")
            if multi:
                lines.append(f"RV{base}::")
            lines.append(diagram(waveform(encoding)))
        lines.extend(
            (
                "Description::",
                entities(prose_text(self.architecture, self.options, inst, "description")),
                "",
                "Decode Variables::",
                "",
            )
        )
        if not any(fields.encoding(base).variables for base in bases):
            lines.append(f"{inst.name} has no decode variables.")
        else:
            for base in bases:
                if multi:
                    lines.extend((f"RV{base}::", "+", "[source,idl]"))
                else:
                    lines.append('[source,idl,subs="specialchars,macros"]')
                lines.append("----")
                lines.extend(
                    ("signed " if var.sign_extend else "")
                    + f"Bits<{var.width}> {var.name} = {extract(var)};"
                    for var in fields.encoding(base).variables
                )
                lines.extend(("----", ""))
        if inst.data.get("operation()") is not None:
            # Rendering is syntactic and keeps unpruned source. Reachability uses
            # the accepted compiler and pruner in each applicable XLEN context.
            lines.extend(
                (
                    "Operation::",
                    '[source,idl,subs="specialchars,macros"]',
                    "----",
                    entities(to_adoc(self.compiler.instruction_ast(inst.name))),
                    "----",
                    "",
                )
            )
            for base in possible_xlens(self.architecture):
                if fields.encoding(base) is None:
                    continue
                compiled = self.compiler.compile_instruction(inst.name, effective_xlen=base)
                tree = prune(compiled.ast, compiled.symtab)
                for function in reachable_functions(tree, compiled.symtab, cache=self.cache):
                    self.functions[function.name] = function
        lines.extend(
            (
                "Included in::",
                "--",
                f"`{inst.name}` is unconditionally defined by the following:",
                "",
                "|===",
                "| Extension | Version",
                "",
            )
        )
        for selection in self.selections:
            versions = [
                v
                for v in selection.versions
                if self.queries.implies(
                    ExtensionTerm(selection.name, (VersionRequirement.exact(v.version),)),
                    defined_by(inst),
                )
            ]
            if versions:
                lines.extend(
                    (
                        f"| *{selection.name}*",
                        "| " + version_subset_pretty(selection.extension, versions),
                    )
                )
        lines.extend(("|===", "", "--", ""))
        return "\n".join(lines) + "\n"
