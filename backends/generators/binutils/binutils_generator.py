#!/usr/bin/env python3
"""
Binutils RISC-V Generator

Generates binutils-compatible opcode table entries from RISC-V UDB instruction definitions.
Follows the format used in binutils-gdb/opcodes/riscv-opc.c
"""

import os
import sys
import argparse
import logging

# Add parent directory to path to find generator.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generator import (
    parse_match,
    parse_extension_requirements,
    load_full_instructions,
)
from naming_config import USER_DEFINED_INSN_NAMES, USER_DEFINED_OPERAND_PREFERENCES, is_user_defined_class
import re

logging.basicConfig(level=logging.INFO, format="%(levelname)s:: %(message)s")


# Inline minimal mappers to keep only three files in this toolchain

class ExtensionMapper:
    def __init__(self) -> None:
        self._defaults_used = []  # list[(ext, class_name)]
        self._records = []        # list[(ext, class_name)]

    def map_extension(self, defined_by, instruction_name: str = "") -> str:
        if isinstance(defined_by, str):
            ext = defined_by
            if ext in USER_DEFINED_INSN_NAMES:
                class_name = USER_DEFINED_INSN_NAMES[ext]
            else:
                class_name = f"INSN_CLASS_{ext.upper()}"
                self._defaults_used.append((ext, class_name))
            self._records.append((ext, class_name))
            return class_name
        if isinstance(defined_by, dict):
            base = instruction_name or "custom"
            class_name = f"INSN_CLASS_{base.upper()}"
            self._defaults_used.append((base, class_name))
            self._records.append((base, class_name))
            return class_name
        class_name = "INSN_CLASS_I"
        self._records.append(("I", class_name))
        return class_name

    def get_defaults_warning(self) -> str:
        if not self._records:
            return ""
        lines = []
        lines.append("\n============================================================")
        lines.append("WARNING: Default instruction class names were generated")
        lines.append("============================================================")
        lines.append("The following extensions used auto-generated names:\n")
        for ext, cls in self._records:
            lines.append(f"  • Extension '{ext}' -> {cls}")
        lines.append("\nTo define custom names, add them to USER_DEFINED_INSN_NAMES in naming_config.py")
        lines.append("============================================================")
        return "\n".join(lines)


class OperandMatch:
    def __init__(self, binutils_char, info, score, reasons):
        self.binutils_char = binutils_char
        self.binutils_info = info
        self.score = score
        self.match_reasons = reasons


class OperandMatcher:
    def __init__(self, binutils_parser):
        self.parser = binutils_parser
        self.match_suggestions = {}

    def _parse_bit_range(self, location_str):
        m = re.match(r'^(\d+)-(\d+)$', location_str)
        if m:
            high = int(m.group(1)); low = int(m.group(2))
            return (low, high)
        ranges = []
        for part in location_str.split(','):
            if '-' in part:
                m = re.match(r'^(\d+)-(\d+)$', part)
                if m:
                    endb = int(m.group(1)); startb = int(m.group(2))
                    ranges.append((startb, endb))
            else:
                b = int(part)
                ranges.append((b, b))
        if ranges:
            ranges.sort(key=lambda x: x[1]-x[0], reverse=True)
            return ranges[0]
        return (0, 31)

    def find_matches(self, name, location_str):
        if not self.parser.parsed:
            return []
        low, high = self._parse_bit_range(location_str)
        matches = []
        for char, info in self.parser.get_all_operands().items():
            if info.bit_start == low and info.bit_end == high:
                matches.append(OperandMatch(char, info, 1.0, [f"Exact bit match ({low}-{high})"]))
        return matches

    def suggest_operand_mapping(self, operand_name, location_str):
        key = (operand_name, location_str)
        if key in USER_DEFINED_OPERAND_PREFERENCES:
            return USER_DEFINED_OPERAND_PREFERENCES[key]
        cache_key = f"{operand_name}({location_str})"
        if cache_key in self.match_suggestions:
            return None
        matches = self.find_matches(operand_name, location_str)
        if not matches:
            suggestion = f"no_match_{operand_name}_{location_str.replace('-', '_').replace(',', '_')}"
            logging.warning(f"No exact bit match found for UDB '{operand_name}({location_str})' → using '{suggestion}'")
            self.match_suggestions[cache_key] = suggestion
            return suggestion
        if len(matches) == 1:
            m = matches[0]
            logging.info(f"Auto-mapped UDB '{operand_name}({location_str})' → binutils '{m.binutils_char}' (exact bit match)")
            self.match_suggestions[cache_key] = m.binutils_char
            return m.binutils_char
        # Multiple matches: prefer user config; otherwise first
        preferred = USER_DEFINED_OPERAND_PREFERENCES.get(key)
        choice = preferred or matches[0].binutils_char
        return choice


class OperandMapper:
    def __init__(self, binutils_path: str | None = None):
        self.variable_map = {
            ('xd', '11-7'): 'd', ('xs1', '19-15'): 's', ('xs2', '24-20'): 't',
            ('fd', '11-7'): 'D', ('fs1', '19-15'): 'S', ('fs2', '24-20'): 'T',
            ('imm', '31-20'): 'j', ('imm', '31-25,11-7'): 'o', ('imm', '31,7,30-25,11-8'): 'p', ('imm', '31,19-12,20,30-21'): 'a',
            ('shamt', '25-20'): '>', ('shamt', '24-20'): '<',
        }
        self.binutils_parser = None
        self.operand_matcher = None
        if binutils_path:
            from binutils_parser import BinutilsParser
            self.binutils_parser = BinutilsParser(binutils_path)
            if self.binutils_parser.parse_operand_definitions():
                self.operand_matcher = OperandMatcher(self.binutils_parser)
                logging.info("Dynamic operand matching enabled with binutils source")
            else:
                logging.warning("Could not parse binutils source, using static mappings only")
        else:
            logging.info("No binutils path provided, using static mappings only")

    def map_assembly(self, assembly_str, instr_info):
        if not assembly_str or not assembly_str.strip():
            return ""
        variables = self._extract_variables(instr_info)
        parts = self._parse_assembly(assembly_str)
        out = []
        for comp in parts:
            out.append(self._map_single_operand(comp, variables, instr_info))
        return ",".join(out)

    def _extract_variables(self, instr_info):
        variables = {}
        encoding = instr_info.get("encoding", {})
        if isinstance(encoding, dict):
            var_list = encoding.get("variables", [])
            if not var_list and "RV64" in encoding:
                rv64 = encoding.get("RV64", {})
                if isinstance(rv64, dict):
                    var_list = rv64.get("variables", [])
            elif not var_list and "RV32" in encoding:
                rv32 = encoding.get("RV32", {})
                if isinstance(rv32, dict):
                    var_list = rv32.get("variables", [])
            for var in var_list:
                if isinstance(var, dict):
                    name = var.get("name"); location = var.get("location"); not_c = var.get("not")
                    if name and location:
                        variables[name] = {'location': str(location), 'not': not_c}
        return variables

    def _parse_assembly(self, assembly_str):
        comps = [c.strip() for c in assembly_str.split(',')]
        parsed = []
        for comp in comps:
            if '(' in comp and ')' in comp:
                m = re.match(r'([^(]+)\(([^)]+)\)', comp)
                if m:
                    offset, base = m.groups(); parsed.extend([offset.strip(), base.strip()])
                else:
                    parsed.append(comp)
            else:
                parsed.append(comp)
        return parsed

    def _map_single_operand(self, operand, variables, instr_info):
        operand = operand.strip()
        if operand in ("rm", "csr"):
            return ""
        if operand in variables:
            var = variables[operand]; location = var['location']; not_c = var.get('not')
            is_compressed = instr_info.get("name", "").startswith("c.")
            mapping_keys = [ (operand, location), (operand, location, 'compressed') if is_compressed else None, (operand, location, 'x8-x15') if not_c == 0 else None ]
            for key in mapping_keys:
                if key and key in self.variable_map:
                    res = self.variable_map[key]
                    if res:
                        return res
            if self.operand_matcher:
                suggestion = self.operand_matcher.suggest_operand_mapping(operand, location)
                if suggestion:
                    return suggestion
            if self.operand_matcher:
                return self.operand_matcher.get_fallback_operand(operand, location)
            else:
                return f"NON_DEFINED_{operand}_{location}"
        return f"NON_DEFINED_{operand}"


def generate_binutils_opcodes(instr_dict, output_file="riscv-opc.c", extension_mapper=None, binutils_path=None):
    operand_mapper = OperandMapper(binutils_path)
    if extension_mapper is None:
        extension_mapper = ExtensionMapper()
    args = " ".join(sys.argv)

    opcode_entries = []
    stats = {'total': 0, 'success': 0, 'non_defined_operands': 0, 'non_defined_extensions': 0, 'errors': 0}

    for name, info in sorted(instr_dict.items(), key=lambda x: x[0].upper()):
        stats['total'] += 1
        try:
            encoding = info.get("encoding", {})
            match_str = encoding.get("match", "")
            if not match_str:
                logging.warning(f"No match string found for {name}")
                continue
            defined_by = info.get("definedBy", "I")
            assembly = info.get("assembly", "")
            enc_match = parse_match(match_str)
            enc_mask = int(''.join('1' if c != '-' else '0' for c in match_str), 2)
            insn_class = extension_mapper.map_extension(defined_by, instruction_name=name)
            if "NON_DEFINED" in insn_class:
                stats['non_defined_extensions'] += 1
                logging.warning(f"Non-defined extension for {name}: {defined_by} -> {insn_class}")
            if insn_class.startswith('INSN_CLASS_') and not is_user_defined_class(insn_class):
                if not hasattr(generate_binutils_opcodes, 'custom_classes'):
                    generate_binutils_opcodes.custom_classes = set()
                generate_binutils_opcodes.custom_classes.add(insn_class)
            operand_format = operand_mapper.map_assembly(assembly, info)
            if "NON_DEFINED" in operand_format:
                stats['non_defined_operands'] += 1
                logging.warning(f"Non-defined operands for {name}: {assembly} -> {operand_format}")
            match_const = f"MATCH_{name.upper().replace('.', '_')}"
            mask_const = f"MASK_{name.upper().replace('.', '_')}"
            entry = f'  {{"{name}", 0, {insn_class}, "{operand_format}", {match_const}, {mask_const}, match_opcode, 0}}'
            opcode_entries.append(entry)
            if not hasattr(generate_binutils_opcodes, 'constants'):
                generate_binutils_opcodes.constants = []
            generate_binutils_opcodes.constants.append({
                'name': name,
                'match_const': match_const,
                'mask_const': mask_const,
                'match_value': f"0x{enc_match:x}",
                'mask_value': f"0x{enc_mask:x}"
            })
            if insn_class.startswith('INSN_CLASS_') and not is_user_defined_class(insn_class):
                if not hasattr(generate_binutils_opcodes, 'custom_class_extensions'):
                    generate_binutils_opcodes.custom_class_extensions = {}
                generate_binutils_opcodes.custom_class_extensions[insn_class] = defined_by
            stats['success'] += 1
        except Exception as e:
            stats['errors'] += 1
            logging.error(f"Error processing {name}: {e}")
            continue

    prelude = f"/* Code generated by {args}; DO NOT EDIT. */\n"
    prelude += "/* This file should be placed at: binutils-gdb/opcodes/riscv-opc.c */\n\n"
    prelude += """#include "opcode/riscv.h"

const struct riscv_opcode riscv_opcodes[] = {
"""
    opcodes_str = ",\n".join(opcode_entries)
    postlude = "\n};\n"
    full_output = prelude + opcodes_str + postlude
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(full_output)

    generate_header_file(output_file, args)
    generate_subset_support(output_file, args)

    header_file = output_file.replace('.c', '.h')
    support_file = 'elfxx-riscv.c'
    logging.info(f"Generated files:")
    logging.info(f"  Opcode table:    {output_file}")
    logging.info(f"  Header file:     {header_file}")
    if hasattr(generate_binutils_opcodes, 'custom_class_extensions') and generate_binutils_opcodes.custom_class_extensions:
        logging.info(f"  Subset support:  {support_file}")
    logging.info(f"Statistics:")
    logging.info(f"  Total instructions: {stats['total']}")
    logging.info(f"  Successfully processed: {stats['success']}")
    logging.info(f"  Non-defined operands: {stats['non_defined_operands']}")
    logging.info(f"  Non-defined extensions: {stats['non_defined_extensions']}")
    logging.info(f"  Errors: {stats['errors']}")


def generate_header_file(output_file, args):
    if not hasattr(generate_binutils_opcodes, 'constants'):
        logging.warning("No constants collected for header generation")
        return
    header_file = output_file.replace('.c', '.h')
    args_str = " ".join(sys.argv)
    header_content = f"""/* Code generated by {args_str}; DO NOT EDIT. */
/* This file should be placed at: binutils-gdb/include/opcode/riscv.h (append to existing file) */

#ifndef RISCV_OPC_H
#define RISCV_OPC_H

/* RISC-V opcode constants for {len(generate_binutils_opcodes.constants)} instructions */

"""
    custom_classes = set()
    if hasattr(generate_binutils_opcodes, 'custom_classes'):
        custom_classes = generate_binutils_opcodes.custom_classes
    if custom_classes:
        header_content += "/* Custom instruction class definitions */\n"
        header_content += "/* Add these to your binutils enum riscv_insn_class in include/opcode/riscv.h */\n"
        for class_name in sorted(custom_classes):
            header_content += f"/* {class_name}, */\n"
        header_content += "\n"
    header_content += "/* MATCH constants */\n"
    for const in sorted(generate_binutils_opcodes.constants, key=lambda x: x['name']):
        header_content += f"#define {const['match_const']} {const['match_value']}\n"
    header_content += "\n/* MASK constants */\n"
    for const in sorted(generate_binutils_opcodes.constants, key=lambda x: x['name']):
        header_content += f"#define {const['mask_const']} {const['mask_value']}\n"
    header_content += "\n#endif /* RISCV_OPC_H */\n"
    with open(header_file, "w", encoding="utf-8") as f:
        f.write(header_content)
    stats_msg = f"  MATCH/MASK constants: {len(generate_binutils_opcodes.constants) * 2}"
    if custom_classes:
        stats_msg += f", Custom classes: {len(custom_classes)}"
    logging.info(f"Generated header file: {header_file}")
    logging.info(stats_msg)


def generate_subset_support(output_file, args):
    if not hasattr(generate_binutils_opcodes, 'custom_class_extensions'):
        return
    custom_class_extensions = generate_binutils_opcodes.custom_class_extensions
    if not custom_class_extensions:
        return
    support_file = 'elfxx-riscv.c'
    args_str = " ".join(sys.argv)
    content = f"""/* Code generated by {args_str}; DO NOT EDIT. */
/* This file contains code snippets that should be added to: binutils-gdb/bfd/elfxx-riscv.c */

/* Add these cases to riscv_multi_subset_supports() in bfd/elfxx-riscv.c */

"""
    content += "/* Cases for riscv_multi_subset_supports() switch statement */\n"
    for class_name in sorted(custom_class_extensions.keys()):
        extension_def = custom_class_extensions[class_name]
        case_code = generate_subset_support_case_from_udb(class_name, extension_def)
        content += case_code
    content += "\n/* Cases for riscv_multi_subset_supports_ext() switch statement */\n"
    for class_name in sorted(custom_class_extensions.keys()):
        extension_def = custom_class_extensions[class_name]
        case_code = generate_subset_support_ext_case_from_udb(class_name, extension_def)
        content += case_code
    content += f"""

/* Instructions for integration:
 * 
 * 1. Add the instruction classes to include/opcode/riscv.h:
 *    (Already listed in the generated .h file)
 *
 * 2. Add these cases to the switch statement in bfd/elfxx-riscv.c:
 *    - Find function riscv_multi_subset_supports()
 *    - Add the cases above to the switch statement
 *    - Find function riscv_multi_subset_supports_ext()  
 *    - Add the ext cases above to the switch statement
 *
 * 3. Extension names are converted to lowercase in subset support functions
 */
"""
    with open(support_file, "w", encoding="utf-8") as f:
        f.write(content)
    logging.info(f"Generated subset support file: {support_file}")
    logging.info(f"  Custom classes: {len(custom_class_extensions)}")


def generate_subset_support_case_from_udb(class_name, extension_def):
    logic = generate_extension_logic(extension_def)
    return f"""    case {class_name}:
      {logic}
"""


def generate_subset_support_ext_case_from_udb(class_name, extension_def):
    ext_message = generate_extension_error_message(extension_def)
    if isinstance(ext_message, str) and ext_message.startswith('_('):
        return f"""    case {class_name}:
      return {ext_message};
"""
    else:
        return f"""    case {class_name}:
      return \"{ext_message}\";
"""


def generate_extension_logic(extension_def):
    if isinstance(extension_def, str):
        return f'return riscv_subset_supports (rps, "{extension_def.lower()}");'
    elif isinstance(extension_def, dict):
        if "anyOf" in extension_def:
            extensions = extension_def["anyOf"]
            checks = [f'riscv_subset_supports (rps, "{ext.lower()}")' for ext in extensions]
            return f"return ({' || '.join(checks)});"
        elif "allOf" in extension_def:
            extensions = extension_def["allOf"]
            checks = [f'riscv_subset_supports (rps, "{ext.lower()}")' for ext in extensions]
            return f"return ({' && '.join(checks)});"
        else:
            return 'return false; /* TODO: Complex extension logic */'
    else:
        return 'return false; /* TODO: Unknown extension type */'


def generate_extension_error_message(extension_def):
    if isinstance(extension_def, str):
        return extension_def.lower()
    elif isinstance(extension_def, dict):
        if "anyOf" in extension_def:
            extensions = [ext.lower() for ext in extension_def["anyOf"]]
            ext_list = "' or `".join(extensions)
            return f'_("{ext_list}")'
        elif "allOf" in extension_def:
            extensions = [ext.lower() for ext in extension_def["allOf"]]
            ext_list = "' and `".join(extensions)
            return f'_("{ext_list}")'
        else:
            return f'TODO: {extension_def}'
    else:
        return f'TODO: {extension_def}'


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate binutils RISC-V opcode table from UDB instruction definitions"
    )
    parser.add_argument("--inst-dir", default="../../../spec/std/isa/inst/", help="Directory containing instruction YAML files")
    parser.add_argument("--output", default="riscv-opc.c", help="Output C file name (corresponding .h file will be generated automatically)")
    parser.add_argument("--extensions", default="I,M,A,F,D,C,Zba,Zbb,Zbs,Zca", help="Comma-separated list of enabled extensions")
    parser.add_argument("--arch", default="RV64", choices=["RV32", "RV64", "BOTH"], help="Target architecture")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--include-all", "-a", action="store_true", help="Include all instructions, ignoring extension filtering")
    parser.add_argument("--binutils-path", default="../binutils-gdb/", help="Path to binutils-gdb source directory for operand reference")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    include_all = args.include_all or not args.extensions
    if include_all:
        enabled_extensions = []
        logging.info("Including all instructions (extension filtering disabled)")
    else:
        enabled_extensions = [ext.strip() for ext in args.extensions.split(",") if ext.strip()]
        logging.info(f"Enabled extensions: {', '.join(enabled_extensions)}")
    logging.info(f"Target architecture: {args.arch}")
    extension_mapper = ExtensionMapper()
    logging.info("Using user-defined names from insn_class_config.py or auto-generated defaults")
    if not os.path.isdir(args.inst_dir):
        logging.error(f"Instruction directory not found: {args.inst_dir}")
        sys.exit(1)
    instr_dict = load_full_instructions(args.inst_dir, enabled_extensions, include_all, args.arch)
    if not instr_dict:
        logging.error("No instructions found or all were filtered out.")
        sys.exit(1)
    logging.info(f"Loaded {len(instr_dict)} instructions")
    generate_binutils_opcodes(instr_dict, args.output, extension_mapper, args.binutils_path)
    warning = extension_mapper.get_defaults_warning()
    if warning:
        print(warning)


if __name__ == "__main__":
    main()
