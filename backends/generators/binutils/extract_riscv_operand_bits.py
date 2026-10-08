"""
Extract RISC-V operand tokens and bit positions (JSON/Markdown).

Thin wrapper that reuses helpers in binutils_parser.py (single source of truth).
"""

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path


def parse_op_fields(riscv_h: str):
    """Parse OP_SH_* and OP_MASK_* into a field->bits map."""
    sh_re = re.compile(r"#define\s+OP_SH_([A-Z0-9_]+)\s+(\d+)")
    mask_re = re.compile(r"#define\s+OP_MASK_([A-Z0-9_]+)\s+((?:0x[0-9A-Fa-f]+|\d+)[Uu]?)")

    shifts = {}
    masks = {}
    for m in sh_re.finditer(riscv_h):
        shifts[m.group(1)] = int(m.group(2))
    for m in mask_re.finditer(riscv_h):
        raw = m.group(2)
        if raw.endswith(("U", "u")):
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
    """Parse ENCODE_* macros to compute bit destinations for immediates."""
    define_re = re.compile(r"^#define\s+ENCODE_([A-Z0-9_]+)\(x\)\s+(.*)$", re.M)
    lines = riscv_h.splitlines()
    macros = {}
    for m in define_re.finditer(riscv_h):
        name = m.group(1)
        start_pos = m.start()
        start_line = riscv_h.count("\n", 0, start_pos)
        body_lines = []
        i = start_line
        while i < len(lines):
            body_lines.append(lines[i])
            if not lines[i].rstrip().endswith("\\"):
                break
            i += 1
        body = " ".join([bl.rstrip(" \\") for bl in body_lines])
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
insert_re = re.compile(r"INSERT_OPERAND\s*\(\s*([A-Z0-9_]+)")
extract_any_re = re.compile(r"\bEXTRACT_([A-Z0-9_]+)\s*\(")
encode_any_re = re.compile(r"\bENCODE_([A-Z0-9_]+)\s*\(")


def parse_operand_switch(lines, start_idx=0):
    """Parse switch(*oparg) capturing top-level and nested C/V/X/W cases."""
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
            ch, cmt = m.group(1), (m.group(2) or "").strip()
            if ch in ("C", "V", "X", "W"):
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
                    if "{" in l2 or "}" in l2:
                        depth += l2.count("{") - l2.count("}")
                        if l2.count("{"):
                            seen_brace = True
                        if seen_brace and depth < 0:
                            break
                        if seen_brace and depth == 0:
                            k += 1
                            break
                    mm = case_re.match(l2)
                    if mm and (not seen_brace or depth > 0):
                        subch, subcmt = mm.group(1), (mm.group(2) or "").strip()
                        key = f"{ch}.{subch}"
                        inserts, extracts, encodes = set(), set(), set()
                        la = 0
                        kk = k + 1
                        local_depth = 0
                        while kk < n and la < 30:
                            if case_re.match(lines[kk]) and local_depth == 0:
                                break
                            local_depth += lines[kk].count("{") - lines[kk].count("}")
                            inserts.update(insert_re.findall(lines[kk]))
                            extracts.update(extract_any_re.findall(lines[kk]))
                            encodes.update(encode_any_re.findall(lines[kk]))
                            kk += 1
                            la += 1
                        entries.append(
                            (
                                key,
                                subcmt,
                                sorted(inserts),
                                sorted(extracts),
                                sorted(encodes),
                            )
                        )
                    k += 1
                i = k
                continue

            key = ch
            inserts, extracts, encodes = set(), set(), set()
            la = 0
            j = i + 1
            local_depth = 0
            while j < n and la < 30:
                if case_re.match(lines[j]) and local_depth == 0:
                    break
                local_depth += lines[j].count("{") - lines[j].count("}")
                inserts.update(insert_re.findall(lines[j]))
                extracts.update(extract_any_re.findall(lines[j]))
                encodes.update(encode_any_re.findall(lines[j]))
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
            if "The operand string defined in the riscv_opcodes" in ln:
                return idx
        for idx, ln in enumerate(lines):
            if "switch (*oparg)" in ln:
                return idx
        return 0

    asm_entries = parse_operand_switch(asm_lines, start_idx(asm_lines))
    dis_entries = parse_operand_switch(dis_lines, start_idx(dis_lines))

    merged = OrderedDict()
    for key, cmt, ins, _ex, en in asm_entries:
        merged[key] = {
            "asm": {"comment": cmt, "inserts": ins, "encodes": en},
            "dis": {"comment": "", "extracts": []},
        }
    for key, cmt, _ins, ex, _en in dis_entries:
        d = merged.setdefault(
            key,
            {
                "asm": {"comment": "", "inserts": [], "encodes": []},
                "dis": {"comment": "", "extracts": []},
            },
        )
        d["dis"]["comment"] = cmt
        d["dis"]["extracts"] = ex
    return merged


def derive_bits_for_token(token, macro_use, fields_map, enc_map):
    """Compute bit positions for a token from asm/dis macro usage."""
    bits = set()
    notes = []
    inserts = macro_use.get("asm", {}).get("inserts", [])
    encodes = macro_use.get("asm", {}).get("encodes", [])
    extracts = macro_use.get("dis", {}).get("extracts", [])

    for fld in inserts:
        if fld in fields_map:
            bits.update(fields_map[fld]["bits"])

    for enc in encodes:
        if enc in enc_map:
            bits.update(enc_map[enc]["bits"])

    if not bits and extracts:
        for ex in extracts:
            if ex in fields_map:
                bits.update(fields_map[ex]["bits"])
                continue
            alias = None
            if ex.endswith("_IMM") or (
                ex.startswith("RVV_V")
                or ex.startswith("ZCB")
                or ex.startswith("ZCM")
                or ex.startswith("CV_")
                or ex.startswith("MIPS_")
            ):
                alias = ex.replace("EXTRACT_", "ENCODE_")
            if alias and alias in enc_map:
                bits.update(enc_map[alias]["bits"])

    if not bits:
        fallback = {
            "d": "RD",
            "s": "RS1",
            "t": "RS2",
            "r": "RS3",
            "m": "RM",
            "E": "CSR",
            "P": "PRED",
            "Q": "SUCC",
            ">": "SHAMT",
            "<": "SHAMTW",
            "Z": "RS1",
            "C.s": "CRS1S",
            "C.t": "CRS2S",
            "C.V": "CRS2",
            "V.d": "VD",
            "V.s": "VS1",
            "V.t": "VS2",
            "V.m": "VMASK",
            "V.i": "VIMM",
            "V.j": "VIMM",
        }
        fld = fallback.get(token)
        if fld and fld in fields_map:
            bits.update(fields_map[fld]["bits"])

    if token == "0":
        notes.append("constant-zero; bits reported when context provides an immediate encoder")

    return sorted(bits), notes


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
    tokens = out_obj.get("tokens", {})
    fp.write("RISC-V Operand Bit Positions (from binutils)\n")
    fp.write("\n")
    fp.write("- Bit indices are instruction bit positions with LSB = 0.\n")
    fp.write("- Fields come from OP_MASK_*/OP_SH_*; immediates from ENCODE_* macros.\n")
    fp.write("\n")

    def grp(tok):
        if tok.startswith("C."):
            return (1, tok)
        if tok.startswith("V."):
            return (2, tok)
        if tok.startswith("X.") or tok.startswith("W."):
            return (3, tok)
        return (0, tok)

    for tok in sorted(tokens.keys(), key=grp):
        data = tokens[tok]
        bits = data.get("bits", [])
        ranges = _bit_ranges(bits)
        fields = data.get("asm_inserts", [])
        encs = data.get("asm_encodes", [])
        exts = data.get("dis_extracts", [])
        fp.write(f"- {tok}\n")
        fp.write(f"  - bits: {', '.join(ranges) if ranges else '(none)'}\n")
        if fields:
            fp.write(f"  - fields: {', '.join(fields)}\n")
        if encs:
            fp.write(f"  - encodes: {', '.join(encs)}\n")
        if exts:
            fp.write(f"  - extracts: {', '.join(exts)}\n")
        notes = data.get("notes") or []
        if notes:
            fp.write(f"  - notes: {'; '.join(notes)}\n")
        fp.write("\n")


def main():
    ap = argparse.ArgumentParser(
        description="Extract RISC-V operand bit positions from binutils sources"
    )
    ap.add_argument(
        "--format",
        "-f",
        choices=["json", "markdown", "md", "text"],
        default="json",
        help="Output format (default: json)",
    )
    ap.add_argument("--out", "-o", default="-", help="Output file path or - for stdout")
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
            "bits": bits,
            "asm_inserts": macro_use.get("asm", {}).get("inserts", []),
            "asm_encodes": macro_use.get("asm", {}).get("encodes", []),
            "dis_extracts": macro_use.get("dis", {}).get("extracts", []),
            "notes": notes,
        }

    # Enrich with a simple dictionary of OP fields and ENCODE immediates for reference
    ref = {
        "op_fields": {
            k: {
                "bits": v["bits"],
                "shift": v["shift"],
                "mask": v["mask"],
                "width": v["width"],
            }
            for k, v in sorted(fields_map.items())
        },
        "encode_immediates": {
            k: {"bits": v["bits"], "segments": v["segments"]} for k, v in sorted(enc_map.items())
        },
    }

    out = {
        "tokens": results,
        "reference": ref,
    }

    # Emit in the requested format
    out_path = args.out
    fmt = args.format

    def _emit(fp):
        if fmt in ("markdown", "md", "text"):
            _emit_markdown(out, fp)
        else:
            json.dump(out, fp, indent=2, sort_keys=False)
            fp.write("\n")

    if out_path == "-":
        _emit(sys.stdout)
    else:
        with open(out_path, "w", encoding="utf-8") as fp:
            _emit(fp)


if __name__ == "__main__":
    main()
