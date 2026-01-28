#!/usr/bin/env python3
"""
Extract RISC-V operand tokens and bit positions (JSON/Markdown).

Thin wrapper that reuses helpers in binutils_parser.py (single source of truth).
"""

import json
import argparse
import sys
from pathlib import Path
from collections import OrderedDict

from binutils_parser import (
    parse_op_fields,
    parse_encode_macros,
    extract_operand_mapping,
    derive_bits_for_token,
)

ROOT = (Path(__file__).resolve().parents[1] / "binutils-gdb").resolve()
RISCV_H = ROOT / "include" / "opcode" / "riscv.h"
ASM = ROOT / "gas" / "config" / "tc-riscv.c"
DIS = ROOT / "opcodes" / "riscv-dis.c"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _bit_ranges(bits):
    if not bits:
        return []
    bits = sorted(bits)
    ranges = []
    start = prev = bits[0]
    for b in bits[1:]:
        if b == prev + 1:
            prev = b
            continue
        ranges.append((start, prev))
        start = prev = b
    ranges.append((start, prev))
    return [f"{a}" if a == b else f"{a}..{b}" for a, b in ranges]


def _emit_markdown(out_obj, fp):
    tokens = out_obj.get('tokens', {})
    fp.write("RISC-V Operand Bit Positions (from binutils)\n")
    fp.write("\n")
    fp.write("- Bit indices are instruction bit positions with LSB = 0.\n")
    fp.write("- Fields come from OP_MASK_*/OP_SH_*; immediates from ENCODE_* macros.\n")
    fp.write("\n")

    def grp(tok):
        if tok.startswith('C.'):
            return (1, tok)
        if tok.startswith('V.'):
            return (2, tok)
        if tok.startswith('X.') or tok.startswith('W.'):
            return (3, tok)
        return (0, tok)

    for tok in sorted(tokens.keys(), key=grp):
        data = tokens[tok]
        bits = data.get('bits', [])
        ranges = _bit_ranges(bits)
        fields = data.get('asm_inserts', [])
        encs = data.get('asm_encodes', [])
        exts = data.get('dis_extracts', [])
        fp.write(f"- {tok}\n")
        fp.write(f"  - bits: {', '.join(ranges) if ranges else '(none)'}\n")
        if fields:
            fp.write(f"  - fields: {', '.join(fields)}\n")
        if encs:
            fp.write(f"  - encodes: {', '.join(encs)}\n")
        if exts:
            fp.write(f"  - extracts: {', '.join(exts)}\n")
        notes = data.get('notes') or []
        if notes:
            fp.write(f"  - notes: {'; '.join(notes)}\n")
        fp.write("\n")


def main():
    ap = argparse.ArgumentParser(description="Extract RISC-V operand bit positions from binutils sources")
    ap.add_argument('--format', '-f', choices=['json', 'markdown', 'md', 'text'], default='json',
                    help='Output format (default: json)')
    ap.add_argument('--out', '-o', default='-', help='Output file path or - for stdout')
    args = ap.parse_args()
    if not (RISCV_H.exists() and ASM.exists() and DIS.exists()):
        print("error: missing binutils sources next to this script", file=sys.stderr)
        sys.exit(1)

    riscv_h = read(RISCV_H)
    tc_riscv_c = read(ASM)
    riscv_dis_c = read(DIS)

    fields_map = parse_op_fields(riscv_h)
    enc_map = parse_encode_macros(riscv_h)
    op_token_map = extract_operand_mapping(tc_riscv_c, riscv_dis_c)

    results = OrderedDict()
    for token, macro_use in op_token_map.items():
        bits, notes = derive_bits_for_token(token, macro_use, fields_map, enc_map)
        results[token] = {
            'bits': bits,
            'asm_inserts': macro_use.get('asm', {}).get('inserts', []),
            'asm_encodes': macro_use.get('asm', {}).get('encodes', []),
            'dis_extracts': macro_use.get('dis', {}).get('extracts', []),
            'notes': notes,
        }

    # Enrich with a simple dictionary of OP fields and ENCODE immediates for reference
    ref = {
        'op_fields': {k: {'bits': v['bits'], 'shift': v['shift'], 'mask': v['mask'], 'width': v['width']}
                       for k, v in sorted(fields_map.items())},
        'encode_immediates': {k: {'bits': v['bits'], 'segments': v['segments']}
                              for k, v in sorted(enc_map.items())},
    }

    out = {
        'tokens': results,
        'reference': ref,
    }

    # Emit in the requested format
    out_path = args.out
    fmt = args.format
    if out_path == '-':
        fp = sys.stdout
        close_fp = False
    else:
        fp = open(out_path, 'w', encoding='utf-8')
        close_fp = True

    try:
        if fmt in ('markdown', 'md', 'text'):
            _emit_markdown(out, fp)
        else:
            json.dump(out, fp, indent=2, sort_keys=False)
            fp.write('\n')
    finally:
        if close_fp:
            fp.close()


if __name__ == '__main__':
    main()
