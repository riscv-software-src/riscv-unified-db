#!/usr/bin/env python3

import argparse
import json
import logging
import pprint
import os
import sys
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Any

# Add riscv-opcodes directory to Python path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RISCV_OPCODES_DIR = os.path.join(SCRIPT_DIR, "..", "riscv-opcodes")
sys.path.insert(0, RISCV_OPCODES_DIR)


@contextmanager
def working_directory(path):
    """Context manager for changing the current working directory"""
    prev_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield prev_cwd
    finally:
        os.chdir(prev_cwd)


# Change to riscv-opcodes directory when importing to ensure relative paths work
with working_directory(RISCV_OPCODES_DIR):
    from c_utils import make_c
    from chisel_utils import make_chisel
    from constants import emitted_pseudo_ops
    from go_utils import make_go
    from latex_utils import make_latex_table, make_priv_latex_table
    from rust_utils import make_rust
    from sverilog_utils import make_sverilog

LOG_FORMAT = "%(levelname)s:: %(message)s"
LOG_LEVEL = logging.INFO

pretty_printer = pprint.PrettyPrinter(indent=2)
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)


def load_instruction_dict(json_path: str) -> Dict[str, Any]:
    """
    Load instruction dictionary from a JSON file.
    """
    try:
        with open(json_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Input JSON file not found: {json_path}")
        raise
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON format in file: {json_path}")
        raise


def move_file(src: str, dest_dir: str):
    """
    Move a file to the destination directory if it exists.
    """
    if os.path.exists(src):
        dest = os.path.join(dest_dir, os.path.basename(src))
        shutil.move(src, dest)


def generate_outputs(
    instr_dict: Dict[str, Any],
    include_pseudo: bool,
    c: bool,
    chisel: bool,
    spinalhdl: bool,
    sverilog: bool,
    rust: bool,
    go: bool,
    latex: bool,
):
    """
    Generate output files based on the instruction dictionary.
    """
    # Sort the dictionary for consistent output
    instr_dict = dict(sorted(instr_dict.items()))

    # Save the processed dictionary in current directory
    with open("processed_instr_dict.json", "w", encoding="utf-8") as outfile:
        json.dump(instr_dict, outfile, indent=2)

    # Generate files in riscv-opcodes directory and move them to current directory
    with working_directory(RISCV_OPCODES_DIR) as orig_dir:
        if c:
            # For C output, filter pseudo-ops if needed
            if not include_pseudo:
                c_dict = {
                    k: v for k, v in instr_dict.items() if k not in emitted_pseudo_ops
                }
            else:
                c_dict = instr_dict
            make_c(c_dict)
            move_file("encoding.out.h", orig_dir)
            logging.info("encoding.out.h generated successfully")

        if chisel:
            make_chisel(instr_dict)
            move_file("inst.chisel", orig_dir)
            logging.info("inst.chisel generated successfully")

        if spinalhdl:
            make_chisel(instr_dict, True)
            move_file("inst.spinalhdl", orig_dir)
            logging.info("inst.spinalhdl generated successfully")

        if sverilog:
            make_sverilog(instr_dict)
            move_file("inst.sverilog", orig_dir)
            logging.info("inst.sverilog generated successfully")

        if rust:
            make_rust(instr_dict)
            move_file("inst.rs", orig_dir)
            logging.info("inst.rs generated successfully")

        if go:
            make_go(instr_dict)
            move_file("inst.go", orig_dir)
            logging.info("inst.go generated successfully")

        if latex:
            make_latex_table()
            make_priv_latex_table()
            move_file("instr-table.tex", orig_dir)
            move_file("priv-instr-table.tex", orig_dir)
            logging.info("LaTeX files generated successfully")


def main():
    parser = argparse.ArgumentParser(
        description="Generate RISC-V constants from JSON input"
    )
    parser.add_argument(
        "input_json", help="Path to JSON file containing instruction definitions"
    )
    parser.add_argument(
        "-pseudo", action="store_true", help="Include pseudo-instructions"
    )
    parser.add_argument("-c", action="store_true", help="Generate output for C")
    parser.add_argument(
        "-chisel", action="store_true", help="Generate output for Chisel"
    )
    parser.add_argument(
        "-spinalhdl", action="store_true", help="Generate output for SpinalHDL"
    )
    parser.add_argument(
        "-sverilog", action="store_true", help="Generate output for SystemVerilog"
    )
    parser.add_argument("-rust", action="store_true", help="Generate output for Rust")
    parser.add_argument("-go", action="store_true", help="Generate output for Go")
    parser.add_argument("-latex", action="store_true", help="Generate output for Latex")

    args = parser.parse_args()

    # Load instruction dictionary from JSON
    instr_dict = load_instruction_dict(args.input_json)

    print(f"Loaded instruction dictionary from: {args.input_json}")

    # Generate outputs based on the loaded dictionary
    generate_outputs(
        instr_dict,
        args.pseudo,
        args.c,
        args.chisel,
        args.spinalhdl,
        args.sverilog,
        args.rust,
        args.go,
        args.latex,
    )


if __name__ == "__main__":
    main()
