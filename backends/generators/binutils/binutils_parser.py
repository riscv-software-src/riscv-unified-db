"""
Binutils Source Parser for RISC-V Operand Definitions

Houses both:
- A small API (BinutilsParser) used by the generator to discover operand tokens
  and their bit positions; and
- The underlying extractor helpers (parse_op_fields, parse_encode_macros,
  extract_operand_mapping, derive_bits_for_token) so logic lives in one place.

This keeps behavior identical while reducing duplication, and allows other
tools (like the standalone extractor script) to import the same helpers.
"""

import os
import logging
import re
from pathlib import Path
from collections import OrderedDict
from typing import Dict, List, Tuple, Optional, NamedTuple


# ----------------------------
# Extractor helper functions
# ----------------------------

def parse_op_fields(riscv_h: str):
    """Parse OP_SH_* and OP_MASK_* into a field->bits map.

    Returns dict FIELD -> {shift, mask, width, bits:[int...]}
    """
    sh_re = re.compile(r"#define\s+OP_SH_([A-Z0-9_]+)\s+(\d+)")
    mask_re = re.compile(r"#define\s+OP_MASK_([A-Z0-9_]+)\s+((?:0x[0-9A-Fa-f]+|\d+)[Uu]?)")

    shifts = {}
    masks = {}
    for m in sh_re.finditer(riscv_h):
        shifts[m.group(1)] = int(m.group(2))
    for m in mask_re.finditer(riscv_h):
        raw = m.group(2)
        if raw.endswith(('U', 'u')):
            raw = raw[:-1]
        masks[m.group(1)] = int(raw, 0)

    fields = {}
    for name, sh in shifts.items():
        if name not in masks:
            continue
        mask = masks[name]
        width = mask.bit_count()
        bits = []
        local = mask
        bit_index = 0
        while local:
            if local & 1:
                bits.append(sh + bit_index)
            local >>= 1
            bit_index += 1
        if width and len(bits) != width:
            bits = sorted(bits)
        elif width:
            bits = list(range(sh, sh + width))
        fields[name] = {
            "shift": sh,
            "mask": mask,
            "width": width,
            "bits": bits,
        }
    return fields


def parse_encode_macros(riscv_h: str):
    """Parse ENCODE_* macros to compute instruction bit destinations for immediates."""
    define_re = re.compile(r"^#define\s+ENCODE_([A-Z0-9_]+)\(x\)\s+(.*)$", re.M)
    lines = riscv_h.splitlines()
    macros = {}
    for m in define_re.finditer(riscv_h):
        name = m.group(1)
        start_pos = m.start()
        start_line = riscv_h.count('\n', 0, start_pos)
        body_lines = []
        i = start_line
        while i < len(lines):
            body_lines.append(lines[i])
            if not lines[i].rstrip().endswith('\\'):
                break
            i += 1
        body = " ".join([bl.rstrip(' \\') for bl in body_lines])
        segs = []
        for sm in re.finditer(r"RV_X\(x,\s*(\d+),\s*(\d+)\)\s*<<\s*(\d+)", body):
            src_start = int(sm.group(1))
            width = int(sm.group(2))
            dst_start = int(sm.group(3))
            segs.append({"src_start": src_start, "width": width, "dst_start": dst_start})
        if not segs:
            continue
        bits = []
        for seg in segs:
            bits.extend(range(seg["dst_start"], seg["dst_start"] + seg["width"]))
        macros[name] = {"segments": segs, "bits": sorted(set(bits))}
    return macros


case_re = re.compile(r"^\s*case\s*'(.?)':\s*(?:/\*\s*(.*?)\s*\*/)?")
switch_start_re = re.compile(r"^\s*switch\s*\(\*[+]*oparg\)\s*")
INSERT_RE = re.compile(r"INSERT_OPERAND\s*\(\s*([A-Z0-9_]+)")
EXTRACT_ANY_RE = re.compile(r"\bEXTRACT_([A-Z0-9_]+)\s*\(")
ENCODE_ANY_RE = re.compile(r"\bENCODE_([A-Z0-9_]+)\s*\(")


def parse_operand_switch(lines, start_idx=0):
    """Parse the switch(*oparg) table capturing top-level cases and nested C/V/X/W."""
    entries = []
    i = start_idx
    n = len(lines)
    while i < n and not switch_start_re.search(lines[i]):
        i += 1
    if i >= n:
        return entries
    i += 1
    while i < n:
        line = lines[i]
        m = case_re.match(line)
        if m:
            ch, cmt = m.group(1), (m.group(2) or '').strip()
            if ch in ('C', 'V', 'X', 'W'):
                j = i + 1
                while j < n and not switch_start_re.search(lines[j]):
                    if case_re.match(lines[j]):
                        break
                    j += 1
                if j >= n or not switch_start_re.search(lines[j]):
                    i += 1
                    continue
                depth = 0
                seen_brace = False
                k = j + 1
                while k < n:
                    l2 = lines[k]
                    if '{' in l2 or '}' in l2:
                        depth += l2.count('{') - l2.count('}')
                        if l2.count('{'):
                            seen_brace = True
                        if seen_brace and depth < 0:
                            break
                        if seen_brace and depth == 0:
                            k += 1
                            break
                    mm = case_re.match(l2)
                    if mm and (not seen_brace or depth > 0):
                        subch, subcmt = mm.group(1), (mm.group(2) or '').strip()
                        key = f"{ch}.{subch}"
                        inserts, extracts, encodes = set(), set(), set()
                        la = 0
                        kk = k + 1
                        local_depth = 0
                        while kk < n and la < 30:
                            if case_re.match(lines[kk]) and local_depth == 0:
                                break
                            local_depth += lines[kk].count('{') - lines[kk].count('}')
                            inserts.update(INSERT_RE.findall(lines[kk]))
                            extracts.update(EXTRACT_ANY_RE.findall(lines[kk]))
                            encodes.update(ENCODE_ANY_RE.findall(lines[kk]))
                            kk += 1
                            la += 1
                        entries.append((key, subcmt, sorted(inserts), sorted(extracts), sorted(encodes)))
                    k += 1
                i = k
                continue
            else:
                key = ch
                inserts, extracts, encodes = set(), set(), set()
                la = 0
                j = i + 1
                local_depth = 0
                while j < n and la < 30:
                    if case_re.match(lines[j]) and local_depth == 0:
                        break
                    local_depth += lines[j].count('{') - lines[j].count('}')
                    inserts.update(INSERT_RE.findall(lines[j]))
                    extracts.update(EXTRACT_ANY_RE.findall(lines[j]))
                    encodes.update(ENCODE_ANY_RE.findall(lines[j]))
                    j += 1
                    la += 1
                entries.append((key, cmt, sorted(inserts), sorted(extracts), sorted(encodes)))
        i += 1
    return entries


def extract_operand_mapping(tc_riscv_c: str, riscv_dis_c: str):
    """Return an ordered mapping of operand token -> macro usage from asm+dis."""
    asm_lines = tc_riscv_c.splitlines()
    dis_lines = riscv_dis_c.splitlines()
    def start_idx(lines):
        for idx, ln in enumerate(lines):
            if 'The operand string defined in the riscv_opcodes' in ln:
                return idx
        for idx, ln in enumerate(lines):
            if 'switch (*oparg)' in ln:
                return idx
        return 0
    asm_entries = parse_operand_switch(asm_lines, start_idx(asm_lines))
    dis_entries = parse_operand_switch(dis_lines, start_idx(dis_lines))

    merged = OrderedDict()
    for key, cmt, ins, ex, en in asm_entries:
        merged[key] = {
            'asm': {'comment': cmt, 'inserts': ins, 'encodes': en},
            'dis': {'comment': '', 'extracts': []},
        }
    for key, cmt, ins, ex, en in dis_entries:
        d = merged.setdefault(key, {'asm': {'comment': '', 'inserts': [], 'encodes': []},
                                    'dis': {'comment': '', 'extracts': []}})
        d['dis']['comment'] = cmt
        d['dis']['extracts'] = ex
    return merged


def derive_bits_for_token(token, macro_use, fields_map, enc_map):
    """Given a token's asm/dis macro usage, compute bit positions and notes."""
    bits = set()
    notes = []
    inserts = macro_use.get('asm', {}).get('inserts', [])
    encodes = macro_use.get('asm', {}).get('encodes', [])
    extracts = macro_use.get('dis', {}).get('extracts', [])

    for fld in inserts:
        if fld in fields_map:
            bits.update(fields_map[fld]['bits'])

    for enc in encodes:
        if enc in enc_map:
            bits.update(enc_map[enc]['bits'])

    if not bits and extracts:
        for ex in extracts:
            if ex in fields_map:
                bits.update(fields_map[ex]['bits'])
                continue
            alias = None
            if ex.endswith('_IMM'):
                alias = ex.replace('EXTRACT_', 'ENCODE_')
            elif ex.startswith('RVV_V') or ex.startswith('ZCB') or ex.startswith('ZCM') or ex.startswith('CV_') or ex.startswith('MIPS_'):
                alias = ex.replace('EXTRACT_', 'ENCODE_')
            if alias and alias in enc_map:
                bits.update(enc_map[alias]['bits'])

    if not bits:
        fallback = {
            'd': 'RD', 's': 'RS1', 't': 'RS2', 'r': 'RS3',
            'm': 'RM', 'E': 'CSR', 'P': 'PRED', 'Q': 'SUCC',
            '>': 'SHAMT', '<': 'SHAMTW', 'Z': 'RS1',
            'C.s': 'CRS1S', 'C.t': 'CRS2S', 'C.V': 'CRS2',
            'V.d': 'VD', 'V.s': 'VS1', 'V.t': 'VS2', 'V.m': 'VMASK', 'V.i': 'VIMM', 'V.j': 'VIMM',
        }
        fld = fallback.get(token)
        if fld and fld in fields_map:
            bits.update(fields_map[fld]['bits'])

    if token == '0':
        notes.append('constant-zero; bits reported when context provides an immediate encoder')

    return sorted(bits), notes

# Reuse the proven extractor implementation in this directory.
# We import its helpers instead of re-implementing parsing here.
from extract_riscv_operand_bits import (
    parse_op_fields,
    parse_encode_macros,
    extract_operand_mapping,
    derive_bits_for_token,
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
        self.operand_info: Dict[str, OperandInfo] = {}
        self.parsed = False
        # Keep only operand_info; generator/Matcher don't need raw bit lists here
        
    def validate_binutils_path(self) -> bool:
        """Check if binutils path exists and contains required files."""
        if not os.path.isdir(self.binutils_path):
            return False
            
        required_files = [
            "gas/config/tc-riscv.c",
            "opcodes/riscv-dis.c", 
            "include/opcode/riscv.h"
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
                    constraints=""
                )
            
            self.parsed = True
            logging.info(f"Parsed {len(self.operand_info)} operand definitions from binutils using superior parsing")
            
            # Debug: show what operands we found
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug("Found operand definitions:")
                for char, info in self.operand_info.items():
                    logging.debug(f"  '{char}': bits {info.bit_start}-{info.bit_end}, type={info.operand_type}, role={info.semantic_role}")
            
            return True
        except Exception as e:
            logging.error(f"Error parsing binutils source: {e}")
            return False

    def _infer_operand_type_from_token(self, token: str, macro_use: dict) -> str:
        """Infer operand type from token name and macro usage."""
        if token.startswith('V.') or 'VD' in str(macro_use) or 'VS' in str(macro_use):
            return 'vector'
        elif token.startswith('C.'):
            return 'compressed'
        elif token in ['d', 's', 't', 'r', 'D', 'S', 'T', 'R']:
            return 'register'
        elif token in ['j', 'i', 'o', 'u', 'a', 'p', 'q'] or 'IMM' in str(macro_use):
            return 'immediate'
        elif token in ['>', '<']:
            return 'shift'
        elif token in ['P', 'Q', 'p', 'q'] and 'PRED' in str(macro_use) or 'SUCC' in str(macro_use):
            return 'fence'
        elif token in ['E', 'm']:
            return 'special'
        else:
            return 'unknown'

    def _infer_semantic_role_from_token(self, token: str, macro_use: dict) -> str:
        """Infer semantic role from token name and macro usage."""
        if token in ['d', 'D', 'V.d']:
            return 'destination'
        elif token in ['s', 'S', 'V.s']:
            return 'source1'
        elif token in ['t', 'T', 'V.t']:
            return 'source2'
        elif token in ['r', 'R']:
            return 'source3'
        elif token in ['j', 'i', 'o', 'u', 'a', 'p', 'q', '>', '<']:
            return 'immediate'
        elif token in ['P', 'Q']:
            return 'fence_pred_succ'
        elif token == 'E':
            return 'csr'
        elif token == 'm':
            return 'rounding_mode'
        else:
            return 'unknown'
    
    # Interface methods for compatibility
    def get_operand_info(self, char: str) -> Optional[OperandInfo]:
        """Get information about a specific operand character."""
        return self.operand_info.get(char)
    
    def get_all_operands(self) -> Dict[str, OperandInfo]:
        """Get all parsed operand information."""
        return self.operand_info.copy()
    
    def find_matching_operands(self, bit_start: int, bit_end: int, 
                             operand_type: str = None) -> List[OperandInfo]:
        """Find operand characters that match given bit positions and type."""
        matches = []
        
        for info in self.operand_info.values():
            # Check bit position overlap
            if (info.bit_start <= bit_end and info.bit_end >= bit_start):
                # Check type compatibility if specified
                if operand_type is None or info.operand_type == operand_type:
                    matches.append(info)
        
        # Sort by how well the bit positions match
        matches.sort(key=lambda x: abs((x.bit_start + x.bit_end) - (bit_start + bit_end)))
        return matches
