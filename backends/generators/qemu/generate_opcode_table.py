#!/usr/bin/env python3
"""Generate QEMU disassembler opcode table entries from the Unified DB."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generator import load_full_instructions  # noqa: E402
from generate_insn32_decode import (  # noqa: E402
    collect_variables,
    determine_format,
    normalize_var_name,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class OffsetOperand(Tuple[str, str]):
    """Typed tuple representing an offset operand like imm(rs1)."""

    __slots__ = ()

    def __new__(cls, offset: str, base: str) -> "OffsetOperand":
        return tuple.__new__(cls, (offset, base))

    @property
    def offset(self) -> str:
        return self[0]

    @property
    def base(self) -> str:
        return self[1]


Operand = Union[str, OffsetOperand]


@dataclass
class OpcodeEntry:
    name: str
    codec: str
    fmt: str

    def render(self, name_width: int = 12) -> str:
        return (
            f"    {{ \"{self.name}\", {self.codec}, {self.fmt}, NULL, 0, 0, 0 }},"
        )


# ---------------------------------------------------------------------------
# Mapping tables / overrides
# ---------------------------------------------------------------------------


FORMAT_TAG_TO_CODEC: Dict[str, str] = {
    "@r": "rv_codec_r",
    "@i": "rv_codec_i",
    "@s": "rv_codec_s",
    "@b": "rv_codec_sb",
    "@u": "rv_codec_u",
    "@j": "rv_codec_uj",
    "@csr": "rv_codec_i_csr",
    "@sh": "rv_codec_i_sh7",
    "@sh5": "rv_codec_i_sh5",
    "@sh6": "rv_codec_i_sh6",
    "@atom_ld": "rv_codec_r_l",
    "@atom_st": "rv_codec_r_a",
    "@sfence_vma": "rv_codec_r",
    "@sfence_vm": "rv_codec_r",
    "@hfence_gvma": "rv_codec_r",
    "@hfence_vvma": "rv_codec_r",
    "@r4_rm": "rv_codec_r4_m",
    "@r_rm": "rv_codec_r_m",
    "@r2_rm": "rv_codec_r_m",
    "@r2": "rv_codec_r",
    "@r2_s": "rv_codec_r",
}

# Some instructions use codecs that cannot be derived from the format tag alone.
NAME_CODEC_OVERRIDES: Dict[str, str] = {
    "fence": "rv_codec_r_f",
    "fence.i": "rv_codec_none",
    "ecall": "rv_codec_none",
    "ebreak": "rv_codec_none",
    "uret": "rv_codec_none",
    "sret": "rv_codec_none",
    "hret": "rv_codec_none",
    "mret": "rv_codec_none",
    "dret": "rv_codec_none",
    "wfi": "rv_codec_none",
}

FORMAT_OVERRIDES: Dict[str, str] = {
    "jal": "rv_fmt_rd_offset",
    "jalr": "rv_fmt_rd_rs1_offset",
    "auipc": "rv_fmt_rd_uoffset",
    "lui": "rv_fmt_rd_uimm",
}

OPERAND_ALIASES: Dict[str, str] = {
    "xs1": "rs1",
    "xs2": "rs2",
    "xs3": "rs3",
    "xd": "rd",
    "xt": "rs",
    "xrd": "rd",
    "xrs1": "rs1",
    "xrs2": "rs2",
    "xrs3": "rs3",
    "shamt": "imm",
    "shamtw": "imm",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_operand_token(token: str) -> str:
    token = token.strip().lower()
    token = token.replace("$", "").replace("`", "")
    token = token.replace("[", "").replace("]", "")
    token = token.replace(" ", "")
    return OPERAND_ALIASES.get(token, normalize_var_name(token))


def parse_operands(assembly: str) -> List[Operand]:
    if not assembly:
        return []
    operands: List[Operand] = []
    for raw in assembly.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if "(" in raw and raw.endswith(")"):
            offset_part, base_part = raw.split("(", 1)
            base_part = base_part[:-1]
            operands.append(
                OffsetOperand(
                    normalize_operand_token(offset_part or "imm"),
                    normalize_operand_token(base_part),
                )
            )
        else:
            operands.append(normalize_operand_token(raw))
    return operands


def classify_imm(variables: Dict[str, Any]) -> str:
    imm_info = variables.get("imm")
    if not imm_info:
        return "imm"
    width = getattr(imm_info, "width", 0)
    left_shift = getattr(imm_info, "left_shift", 0)
    if width == 20 and left_shift >= 12:
        return "uimm"
    return "imm"


def infer_format(
    name: str,
    operands: List[Operand],
    variables: Dict[str, Any],
    format_tag: Optional[str],
) -> Optional[str]:
    override = FORMAT_OVERRIDES.get(name)
    if override:
        return override

    if not operands:
        return "rv_fmt_none"

    if operands == ["pred", "succ"]:
        return "rv_fmt_pred_succ"

    if len(operands) == 1:
        if operands[0] == "rd":
            return "rv_fmt_rd"
        if operands[0] == "imm":
            return "rv_fmt_imm"

    imm_kind = classify_imm(variables)

    # Handle offset forms like imm(rs1)
    if len(operands) == 2 and isinstance(operands[1], OffsetOperand):
        first, offset = operands
        if offset.base == "rs1":
            if first == "rd":
                return "rv_fmt_rd_offset_rs1"
            if first == "rs2":
                return "rv_fmt_rs2_offset_rs1"
            if first == "fd":
                return "rv_fmt_frd_offset_rs1"
            if first == "fs2":
                return "rv_fmt_frs2_offset_rs1"

    if len(operands) == 3 and isinstance(operands[2], OffsetOperand):
        if operands[0] == "rd" and operands[1] == "rs1" and operands[2].base == "rs2":
            return "rv_fmt_rd_rs1_offset"

    signature = tuple(operands)

    if signature == ("rd", "rs1", "rs2"):
        return "rv_fmt_rd_rs1_rs2"
    if signature == ("rd", "rs1", "imm"):
        return "rv_fmt_rd_rs1_imm"
    if signature == ("rd", "rs1", "uimm"):
        return "rv_fmt_rd_uimm"
    if signature == ("rd", "rs1"):
        return "rv_fmt_rd_rs1"
    if signature == ("rd", "rs2"):
        return "rv_fmt_rd_rs2"
    if signature == ("rs1", "rs2", "imm"):
        return "rv_fmt_rs1_rs2_offset"
    if signature == ("rs2", "rs1", "imm"):
        return "rv_fmt_rs2_rs1_offset"
    if signature == ("rs1", "imm"):
        return "rv_fmt_rs1_offset"
    if signature == ("rs2", "imm"):
        return "rv_fmt_rs2_offset"
    if signature == ("rd", "imm"):
        return "rv_fmt_rd_uimm" if imm_kind == "uimm" else "rv_fmt_rd_imm"
    if signature == ("rd", "csr", "rs1"):
        return "rv_fmt_rd_csr_rs1"
    if signature == ("rd", "csr", "imm"):
        return "rv_fmt_rd_csr_zimm"

    # Floating-point helpers
    if signature == ("fd", "fs1", "fs2"):
        return "rv_fmt_frd_frs1_frs2"
    if signature == ("rd", "fs1", "fs2"):
        return "rv_fmt_rd_frs1_frs2"
    if signature == ("fd", "fs1"):
        return "rv_fmt_frd_frs1"
    if signature == ("rd", "fs1"):
        return "rv_fmt_rd_frs1"
    if signature == ("fd", "rs1"):
        return "rv_fmt_frd_rs1"
    if signature == ("rd", "fs1", "fs2", "rm"):
        return "rv_fmt_rm_rd_frs1"
    if signature == ("fd", "fs1", "rm"):
        return "rv_fmt_rm_frd_frs1"
    if signature == ("fd", "fs1", "fs2", "rm"):
        return "rv_fmt_rm_frd_frs1_frs2"
    if signature == ("fd", "fs1", "fs2", "fs3", "rm"):
        return "rv_fmt_rm_frd_frs1_frs2_frs3"

    # Branch offsets from @b format
    if format_tag == "@b" and len(operands) >= 2:
        if len(operands) == 2:
            return "rv_fmt_rs1_offset"
        if len(operands) == 3:
            return "rv_fmt_rs1_rs2_offset"

    logger.debug("Unable to infer format for %s with operands %s", name, operands)
    return None


def infer_codec(name: str, format_tag: Optional[str]) -> Optional[str]:
    if name in NAME_CODEC_OVERRIDES:
        return NAME_CODEC_OVERRIDES[name]
    if not format_tag:
        return "rv_codec_none"
    codec = FORMAT_TAG_TO_CODEC.get(format_tag)
    if not codec:
        logger.debug("No codec mapping for tag %s (%s)", format_tag, name)
    return codec


# ---------------------------------------------------------------------------
# Generator logic
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate rv_opcode_data entries to populate QEMU's disassembler table"
        )
    )
    parser.add_argument(
        "--inst-dir",
        default="../../../spec/std/isa/inst/",
        help="Directory containing instruction YAML files",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Destination file for the generated table snippet ('-' for stdout)",
    )
    parser.add_argument(
        "--extensions",
        default="I,Zicsr",
        help="Comma-separated list of enabled extensions (omit for include-all)",
    )
    parser.add_argument(
        "--include-all",
        action="store_true",
        help="Include all instructions, ignoring extension filtering",
    )
    parser.add_argument(
        "--arch",
        default="RV64",
        choices=["RV32", "RV64", "BOTH"],
        help="Target base architecture",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


def build_entries(
    instructions: Dict[str, dict]
) -> Tuple[List[OpcodeEntry], List[Tuple[str, str]]]:
    entries: List[OpcodeEntry] = []
    skipped: List[Tuple[str, str]] = []

    for name in sorted(instructions.keys()):
        data = instructions[name]
        encoding = data.get("encoding", {})
        if not isinstance(encoding, dict):
            skipped.append((name, "missing encoding"))
            continue

        match = encoding.get("match")
        if not match or len(match) != 32:
            skipped.append((name, "missing 32-bit match"))
            continue

        variables = collect_variables(encoding.get("variables", []))
        format_tag = determine_format(name, variables)
        codec = infer_codec(name, format_tag)
        if not codec:
            skipped.append((name, "codec mapping unavailable"))
            continue

        operands = parse_operands(data.get("assembly", ""))
        fmt = infer_format(name, operands, variables, format_tag)
        if not fmt:
            skipped.append((name, "format mapping unavailable"))
            continue

        entries.append(OpcodeEntry(name=name, codec=codec, fmt=fmt))

    return entries, skipped


def write_output(entries: Iterable[OpcodeEntry], skipped, path: str) -> None:
    header = [
        "/* Auto-generated by generate_opcode_table.py; DO NOT EDIT. */",
        "const rv_opcode_data generated_opcode_data[] = {",
    ]
    body = [entry.render() for entry in entries]
    footer = ["};"]
    if skipped:
        footer.append("")
        footer.append("/* Skipped instructions */")
        for name, reason in skipped:
            footer.append(f"/* - {name}: {reason} */")

    content = "\n".join(header + body + footer) + "\n"

    if path == "-":
        sys.stdout.write(content)
    else:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)


def main() -> None:
    args = parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:: %(message)s")
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    include_all = args.include_all or not args.extensions
    if include_all:
        enabled_extensions: List[str] = []
    else:
        enabled_extensions = [
            ext.strip() for ext in args.extensions.split(",") if ext.strip()
        ]

    instructions = load_full_instructions(
        args.inst_dir,
        enabled_extensions,
        include_all,
        args.arch,
    )

    entries, skipped = build_entries(instructions)
    entries.sort(key=lambda item: item.name)

    write_output(entries, skipped, args.output)


if __name__ == "__main__":  # pragma: no cover
    main()
