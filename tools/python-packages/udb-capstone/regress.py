#!/usr/bin/env python3

# Copyright (c) Salil Mittal
# SPDX-License-Identifier: BSD-3-Clause-Clear

import re
import os
import argparse
import yaml
import sys

from capstone import Cs, CS_ARCH_RISCV, CS_MODE_32


# Parse CSRs from the switch case file
def parse_cases(file_path):
    csrs = set()
    with open(file_path, encoding="utf-8") as f:
        case_addr = None
        for line in f:
            m = re.match(r"\s*case\s+(0x[0-9a-fA-F]+):", line)
            if m:
                case_addr = int(m.group(1), 0)  # convert to int
                continue
            if case_addr:
                n = re.match(r'\s*return\s+"([^"]+)";', line)
                if n:
                    csr_name = n.group(1)
                    csrs.add((csr_name, case_addr))
                case_addr = None
    return csrs


# Retrieve CSRs present in the Capstone package
# Adds (CSR name / pseudo-instruction, corresponding address) to result set
def get_capstone_csrs():
    csrs = set()

    md = Cs(CS_ARCH_RISCV, CS_MODE_32)
    for CSR in range(2**12 - 1):
        csrr_hex = f"{CSR:03x}020f3"

        # byte swap
        csrr = (
            csrr_hex[6]
            + csrr_hex[7]
            + csrr_hex[4]
            + csrr_hex[5]
            + csrr_hex[2]
            + csrr_hex[3]
            + csrr_hex[0]
            + csrr_hex[1]
        )
        csrr_bytes = bytes.fromhex(csrr)

        for i in md.disasm(csrr_bytes, 0x1000):
            # Case 1: CSRs having pseudo-instructions
            # Example: rdinstreth ra
            if i.mnemonic != "csrr":
                csrs.add((i.mnemonic, CSR))
                continue

            # Case 2: named CSR operand
            # Example: csrr	ra, sstatus
            csr_name_split = i.op_str.split(",")
            if len(csr_name_split) == 2:
                csr_name = csr_name_split[1].strip()
                if not csr_name.isnumeric():
                    csrs.add((csr_name, CSR))
    return csrs


# Extract CSR address from pseudo-instructions which are in the form:
# xs1 == 0 && csr == <addr>
# Returns the CSR address if the condition is in the above format else None
def extract_csr_addr(cond):
    parts = cond.split("&&")
    if len(parts) != 2:
        return None

    parts = [p.strip() for p in parts]

    xs1_valid = False
    csr_addr = None

    for p in parts:
        if "==" not in p:
            return None

        # split lhs and rhs in equality
        left, right = (x.strip() for x in p.split("==", 1))

        if left == "xs1":
            if right != "0":
                return None
            xs1_valid = True
            continue

        if left == "csr":
            try:
                csr_addr = int(right, 0)  # parse both dec and hex addreses
            except ValueError:
                return None
            continue

        # unknown left-hand identifier
        return None

    if not xs1_valid or csr_addr is None:
        return None

    return csr_addr


# Get pseudo-instructions for `csrrs` to read specific CSRs
def get_pseudo_instr():
    csrrs_path = (
        f"{os.path.dirname(__file__)}/../../../spec/std/isa/inst/Zicsr/csrrs.yaml"
    )

    with open(csrrs_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
        pseudo_instructions = data["pseudoinstructions"]
        res = set()

        for d in pseudo_instructions:
            addr = extract_csr_addr(d["when"])
            if addr != None:
                res.add((addr, d["to"]))
        return res

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Compare CSR switch cases in two C files."
    )
    parser.add_argument(
        "--csr_switch",
        help="Path to C file containing CSR switch case",
        default=f"{os.path.dirname(__file__)}/../../../gen/capstone/csr_switch.c",
    )
    args = parser.parse_args()

    cases_gen = parse_cases(args.csr_switch)  # cases generated using Capstone generator
    capstone_csrs = get_capstone_csrs()

    diff = capstone_csrs - cases_gen

    pseudo_instr_csrs = get_pseudo_instr()

    unhandled_cases = [
        "dscratch",  # defined as dscratch0, dscratch1 in UDB
        # from the removed N extension
        "utvec",
        "sedeleg",
        "uip",
        "uepc",
        "ustatus",
        "ucause",
        "sideleg",
        "uie",
        "utval",
        "uscratch",
    ]

    # remove diff cases handled by pseudo-instructions
    for t in pseudo_instr_csrs:
        addr = t[0]
        for t1 in diff:
            addr1 = t1[1]
            if addr == addr1:
                diff.remove(t1)
                break

    # remove diff cases which are unhandled
    diff_cpy = diff.copy()
    for t in diff_cpy:
        csr = t[0]
        if csr in unhandled_cases:
            diff.remove(t)

    if len(diff) == 0:
        sys.exit(0)  # pass
    else:
        print("CSRs missing in switch statement:", diff)
        sys.exit(1)  # fail


if __name__ == "__main__":
    main()
