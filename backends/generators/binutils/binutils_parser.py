"""
Binutils Source Parser for RISC-V Operand Definitions

Provides the small parser API (BinutilsParser) used by the generator to
discover operand tokens and their bit positions.

Extractor helpers are sourced from extract_riscv_operand_bits.py to keep a
single source of truth.
"""

import logging
import os
from pathlib import Path
from typing import NamedTuple

# Reuse the proven extractor implementation in this directory.
# We import its helpers instead of re-implementing parsing here.
from extract_riscv_operand_bits import (
    derive_bits_for_token,
    extract_operand_mapping,
    parse_encode_macros,
    parse_op_fields,
)


class OperandInfo(NamedTuple):
    """Information about a binutils operand character."""

    char: str
    bit_start: int
    bit_end: int
    operand_type: str  # 'register', 'immediate', 'address', 'special'
    semantic_role: str  # 'destination', 'source1', 'source2', 'immediate', etc.
    description: str
    constraints: str  # Any special constraints or notes


class BinutilsParser:
    """Parses binutils source files to extract RISC-V operand definitions using binutils' own logic."""

    def __init__(self, binutils_path: str):
        self.binutils_path = binutils_path
        self.operand_info: dict[str, OperandInfo] = {}
        self.parsed = False
        # Keep only operand_info; generator/Matcher don't need raw bit lists here

    def validate_binutils_path(self) -> bool:
        """Check if binutils path exists and contains required files."""
        if not os.path.isdir(self.binutils_path):
            return False

        required_files = [
            "gas/config/tc-riscv.c",
            "opcodes/riscv-dis.c",
            "include/opcode/riscv.h",
        ]

        for file_path in required_files:
            full_path = os.path.join(self.binutils_path, file_path)
            if not os.path.isfile(full_path):
                logging.warning(f"Required binutils file not found: {full_path}")
                return False

        return True

    def read_file(self, path: str) -> str:
        """Read file with proper encoding handling."""
        full_path = os.path.join(self.binutils_path, path)
        return Path(full_path).read_text(encoding="utf-8", errors="ignore")

    # All parsing helpers are imported from extract_riscv_operand_bits

    def parse_operand_definitions(self) -> bool:
        """Parse binutils source files to extract operand definitions using binutils' own logic."""
        if not self.validate_binutils_path():
            logging.error(f"Invalid binutils path: {self.binutils_path}")
            return False

        try:
            # Read source files
            riscv_h = self.read_file("include/opcode/riscv.h")
            tc_riscv_c = self.read_file("gas/config/tc-riscv.c")
            riscv_dis_c = self.read_file("opcodes/riscv-dis.c")

            # Parse using the shared extractor helpers
            fields_map = parse_op_fields(riscv_h)
            enc_map = parse_encode_macros(riscv_h)
            op_token_map = extract_operand_mapping(tc_riscv_c, riscv_dis_c)

            # Convert to our operand info format
            for token, macro_use in op_token_map.items():
                bits, _notes = derive_bits_for_token(token, macro_use, fields_map, enc_map)
                if bits:
                    bit_start, bit_end = min(bits), max(bits)
                else:
                    bit_start, bit_end = -1, -1

                # Infer operand type and semantic role
                operand_type = self._infer_operand_type_from_token(token, macro_use)
                semantic_role = self._infer_semantic_role_from_token(token, macro_use)

                self.operand_info[token] = OperandInfo(
                    char=token,
                    bit_start=bit_start,
                    bit_end=bit_end,
                    operand_type=operand_type,
                    semantic_role=semantic_role,
                    description=f"Operand character '{token}'",
                    constraints="",
                )

            self.parsed = True
            logging.info(
                f"Parsed {len(self.operand_info)} operand definitions from binutils using superior parsing"
            )

            # Debug: show what operands we found
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug("Found operand definitions:")
                for char, info in self.operand_info.items():
                    logging.debug(
                        f"  '{char}': bits {info.bit_start}-{info.bit_end}, type={info.operand_type}, role={info.semantic_role}"
                    )

            return True
        except Exception as e:
            logging.error(f"Error parsing binutils source: {e}")
            return False

    def _infer_operand_type_from_token(self, token: str, macro_use: dict) -> str:
        """Infer operand type from token name and macro usage."""
        if token.startswith("V.") or "VD" in str(macro_use) or "VS" in str(macro_use):
            return "vector"
        elif token.startswith("C."):
            return "compressed"
        elif token in ["d", "s", "t", "r", "D", "S", "T", "R"]:
            return "register"
        elif token in ["j", "i", "o", "u", "a", "p", "q"] or "IMM" in str(macro_use):
            return "immediate"
        elif token in [">", "<"]:
            return "shift"
        elif (token in ["P", "Q", "p", "q"] and "PRED" in str(macro_use)) or "SUCC" in str(
            macro_use
        ):
            return "fence"
        elif token in ["E", "m"]:
            return "special"
        else:
            return "unknown"

    def _infer_semantic_role_from_token(self, token: str, macro_use: dict) -> str:
        """Infer semantic role from token name and macro usage."""
        if token in ["d", "D", "V.d"]:
            return "destination"
        elif token in ["s", "S", "V.s"]:
            return "source1"
        elif token in ["t", "T", "V.t"]:
            return "source2"
        elif token in ["r", "R"]:
            return "source3"
        elif token in ["j", "i", "o", "u", "a", "p", "q", ">", "<"]:
            return "immediate"
        elif token in ["P", "Q"]:
            return "fence_pred_succ"
        elif token == "E":
            return "csr"
        elif token == "m":
            return "rounding_mode"
        else:
            return "unknown"

    # Interface methods for compatibility
    def get_operand_info(self, char: str) -> OperandInfo | None:
        """Get information about a specific operand character."""
        return self.operand_info.get(char)

    def get_all_operands(self) -> dict[str, OperandInfo]:
        """Get all parsed operand information."""
        return self.operand_info.copy()

    def find_matching_operands(
        self, bit_start: int, bit_end: int, operand_type: str | None = None
    ) -> list[OperandInfo]:
        """Find operand characters that match given bit positions and type."""
        matches = []

        for info in self.operand_info.values():
            # Check bit position overlap
            if info.bit_start <= bit_end and info.bit_end >= bit_start:
                # Check type compatibility if specified
                if operand_type is None or info.operand_type == operand_type:
                    matches.append(info)

        # Sort by how well the bit positions match
        matches.sort(key=lambda x: abs((x.bit_start + x.bit_end) - (bit_start + bit_end)))
        return matches
