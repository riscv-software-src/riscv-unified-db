"""
GNU Assembler Test Generator for RISC-V

Generates GNU Assembler test files (.s, .d, .l) from RISC-V unified database.

Generated Test Files:
- Assembly source files (.s) containing assembly instructions
- Dump files (.d) containing expected disassembly patterns
- Error files (.l) for negative tests
- Fail test sets (-fail.s, -fail.d, -fail.l)
- Architecture-specific tests (currently only rv64)
The generator automatically discovers extension patterns from the unified database
and generates tests that should integrate seamlessly with the existing gas test suite.
"""

import os
import sys
import argparse
import logging
import yaml
import glob
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generator import (parse_extension_requirements, load_csrs, calculate_location_width)



def extract_instruction_constraints(name: str, data: dict) -> dict:
    """Extract constraints from instruction YAML data."""
    constraints = {}
    
    encoding = data.get('encoding', {})
    variables = encoding.get('variables', [])
    
    register_constraints = {}
    immediate_constraints = {}
    
    for var in variables:
        var_name = var.get('name', '')
        location = var.get('location', '')
        not_value = var.get('not')
        left_shift = var.get('left_shift', 0)
        sign_extend = var.get('sign_extend', False)
        
        if not var_name or not location:
            continue
        
        width = calculate_location_width(location)
        
        # Determine if this is a register or immediate field
        if var_name in ['xd', 'xs1', 'xs2', 'xs3', 'rd', 'rs1', 'rs2', 'rs3']:
            register_constraints[var_name] = {
                'width': width,
                'not_value': not_value,
                'location': location
            }
        elif var_name in ['imm', 'simm'] or var_name.startswith('zimm') or var_name.startswith('simm'):
            # Calculate the logical immediate range
            # Determine if signed or unsigned immediate
            is_signed = (sign_extend or 
                        var_name.startswith('simm') or
                        (width == 12 and var_name == 'imm'))  # I-type pattern
            
            if is_signed:
                if width > 0:
                    max_val = (1 << (width - 1)) - 1
                    min_val = -(1 << (width - 1))
                else:
                    max_val, min_val = 2047, -2048 
            else:
                # Unsigned immediate - use full width
                if width > 0:
                    max_val = (1 << width) - 1
                    min_val = 0
                else:
                    max_val, min_val = 4095, 0
            
            immediate_constraints[var_name] = {
                'range': (min_val, max_val),
                'not_value': not_value,
                'left_shift': left_shift,
                'sign_extend': sign_extend,
                'width': width
            }

    if register_constraints or immediate_constraints:
        constraints['registers'] = register_constraints
        constraints['immediates'] = immediate_constraints

    base = data.get('base')
    if base:
        constraints['architecture'] = base

    if name.startswith('c.'):
        constraints['compressed'] = True
        if 'rs1\'' in str(data) or 'rd\'' in str(data):
            constraints['limited_registers'] = True
    
    return constraints


def sanitize_extension_name(name: str) -> str:
    """Sanitize extension name to be a valid filename."""
    sanitized = name.lower()
    sanitized = re.sub(r'[{}\[\]\'",\s:]+', '-', sanitized)
    sanitized = sanitized.strip('-')[:20]
    return sanitized if sanitized else 'unknown'


# RISC-V ABI register definitions
# TODO: Move to UDB specs
RISCV_ABI_REGISTERS = {
    'gpr': {
        'arg_ret': ["a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7"],
        'temp': ["t0", "t1", "t2", "t3", "t4", "t5", "t6"],
        'saved': ["s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10", "s11"],
        'special': ["zero", "ra", "sp", "gp", "tp"]
    },
    'fpr': {
        'arg_ret': ["fa0", "fa1", "fa2", "fa3", "fa4", "fa5", "fa6", "fa7"], 
        'temp': ["ft0", "ft1", "ft2", "ft3", "ft4", "ft5", "ft6", "ft7", "ft8", "ft9", "ft10", "ft11"],
        'saved': ["fs0", "fs1", "fs2", "fs3", "fs4", "fs5", "fs6", "fs7", "fs8", "fs9", "fs10", "fs11"]
    },
    'vpr': {
        'general': ["v0", "v1", "v2", "v3", "v4", "v8", "v12", "v16", "v20", "v24", "v28"]
    }
}

RISCV_FP_ROUNDING_MODES = ["rne", "rtz", "rdn", "rup", "rmm"]
RISCV_FENCE_ORDERING = ["rw", "r", "w", "iorw", "ior", "iow"]

logging.basicConfig(level=logging.INFO, format="%(levelname)s:: %(message)s")


class TestInstructionGroup:
    """Represents a group of related instructions for test generation."""
    
    def __init__(self, extension: str, base_arch: str = "rv32i"):
        self.extension = extension
        self.base_arch = base_arch
        self.instructions = []
        self.aliases = []
        self.compressed_variants = []
        self.error_cases = []
        self.arch_specific = {"rv32": [], "rv64": []}
    
    def add_instruction(self, name: str, info: dict):
        """Add an instruction to this group."""
        self.instructions.append((name, info))
        
        if name.startswith('c.'):
            self.compressed_variants.append((name, info))
        
        base = info.get('base')
        if base == 32:
            self.arch_specific["rv32"].append((name, info))
        elif base == 64:
            self.arch_specific["rv64"].append((name, info))
    
    def add_alias(self, name: str, base_name: str, info: dict):
        """Add an instruction alias."""
        self.aliases.append((name, base_name, info))
    
    def add_error_case(self, instruction: str, invalid_assembly: str, error_msg: str):
        """Add a negative test case."""
        self.error_cases.append((instruction, invalid_assembly, error_msg))


class AssemblyExampleGenerator:
    """Generates assembly examples"""
    
    def __init__(self, csr_dir: str = "../../../spec/std/isa/csr/", inst_dir: str = "../../../spec/std/isa/inst/"):
        self.csr_dir = csr_dir
        self.inst_dir = inst_dir
        
        self._load_operand_definitions()
        self._load_csr_examples()
        self.all_instruction_data, self.instruction_constraints, self.extension_base_requirements = self._load_all_instruction_data()
        self.extension_classification = self._classify_extensions()
    
    def _load_operand_definitions(self):
        """Load operand type definitions from RISC-V ABI and architecture specs."""

        abi_regs = RISCV_ABI_REGISTERS
        
        self.gpr_examples = (
            abi_regs['gpr']['arg_ret'][:4] +
            abi_regs['gpr']['saved'][:4]
        )
        
        # Compressed instruction register set per RISC-V spec
        # 3-bit register fields (rs1', rs2', rd') encode registers x8-x15
        # x8=s0, x9=s1, x10=a0, x11=a1, x12=a2, x13=a3, x14=a4, x15=a5
        self.compressed_gpr_examples = (
            abi_regs['gpr']['saved'][:2] +  # s0, s1 (x8, x9)
            abi_regs['gpr']['arg_ret'][:6]  # a0-a5 (x10-x15)
        )
        
        self.fpr_examples = (
            abi_regs['fpr']['arg_ret'][:4] +
            abi_regs['fpr']['temp'][:3] +
            abi_regs['fpr']['saved'][:2]
        )
        
        self.vpr_examples = abi_regs['vpr']['general']
        
        self.vector_mask_examples = ["", "v0.t"]
        
        self.rounding_mode_examples = RISCV_FP_ROUNDING_MODES
        self.fence_examples = RISCV_FENCE_ORDERING

        self.imm_examples = {
            "small": [0, 1, 2, 4, 8, 16, -1, -2],
            "medium": [100, 255, 512, 1024, -100, -255],
            "large": [2047, -2048, 4095, -4096]
        }
    
    def _load_csr_examples(self):
        """Load CSR examples from the unified database."""
        try:
            csr_dict = load_csrs(self.csr_dir, enabled_extensions=[], include_all=True, target_arch="BOTH")
            self.csr_examples = list(set(name.lower().replace('.rv32', '') for name in csr_dict.values()))[:10]
        except Exception as e:
            logging.warning(f"Failed to load CSRs from {self.csr_dir}: {e}. Using fallback CSR list.")
            self.csr_examples = ["mstatus", "mtvec", "mscratch", "cycle", "time"]
    
    def _load_all_instruction_data(self) -> Tuple[Dict[str, dict], Dict[str, dict], Dict[str, set]]:
        instruction_data = {}
        instruction_constraints = {}
        extension_base_requirements = defaultdict(set)

        yaml_files = glob.glob(os.path.join(self.inst_dir, "**/*.yaml"), recursive=True)
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                if not isinstance(data, dict) or data.get('kind') != 'instruction':
                    continue
                
                name = data.get('name')
                if not name:
                    continue
                
                instruction_data[name] = data
                
                constraints = extract_instruction_constraints(name, data)
                if constraints:
                    instruction_constraints[name] = constraints
                
                defined_by = data.get('definedBy')
                if defined_by:
                    ext_name = self._extract_extension_name(defined_by)
                    base = data.get('base')
                    if base in [32, 64]:
                        extension_base_requirements[ext_name].add(base)
                        
            except Exception as e:
                logging.debug(f"Error loading {yaml_file}: {e}")
                continue
        
        logging.debug(f"Single-pass loaded {len(instruction_data)} instructions, {len(instruction_constraints)} constraints, {len(extension_base_requirements)} extension base requirements")
        return instruction_data, instruction_constraints, extension_base_requirements
    
    def _classify_extensions(self) -> dict:
        """Classify extensions based on actual data from the unified database, not hardcoded patterns."""
        classification = {
            'standard': set(),
            'multi_standard': set(),
            'z_extensions': set(),
            's_extensions': set(),
            'x_extensions': set(),
            'other': set()
        }
        
        all_extensions = set()
        for name, data in self.all_instruction_data.items():
            defined_by = data.get('definedBy')
            if defined_by:
                if isinstance(defined_by, str):
                    all_extensions.add(defined_by.lower())
                elif isinstance(defined_by, dict):
                    self._extract_extensions_from_complex(defined_by, all_extensions)
        
        for ext in all_extensions:
            ext_clean = ext.lower().strip()
            if not ext_clean:
                continue
            if len(ext_clean) == 1 and ext_clean.isalpha():
                classification['standard'].add(ext_clean)
            elif ext_clean.startswith('z'):
                classification['z_extensions'].add(ext_clean)
            elif ext_clean.startswith('s'):
                classification['s_extensions'].add(ext_clean)
            elif ext_clean.startswith('x'):
                classification['x_extensions'].add(ext_clean)
            elif ext_clean.startswith('rv32') or ext_clean.startswith('rv64'):
                base_ext = ext_clean[4:] if len(ext_clean) > 4 else 'i'
                if len(base_ext) == 1:
                    classification['standard'].add(base_ext)
                else:
                    classification['multi_standard'].add(base_ext)
            elif len(ext_clean) > 1:
                classification['multi_standard'].add(ext_clean)
            else:
                classification['other'].add(ext_clean)
        
        return classification
    
    def _extract_extensions_from_complex(self, defined_by: dict, all_extensions: set):
        if 'anyOf' in defined_by:
            for item in defined_by['anyOf']:
                if isinstance(item, str):
                    all_extensions.add(item.lower())
                elif isinstance(item, dict):
                    self._extract_extensions_from_complex(item, all_extensions)
        
        if 'allOf' in defined_by:
            for item in defined_by['allOf']:
                if isinstance(item, str):
                    all_extensions.add(item.lower())
                elif isinstance(item, dict):
                    self._extract_extensions_from_complex(item, all_extensions)
        
        if 'oneOf' in defined_by:
            for item in defined_by['oneOf']:
                if isinstance(item, str):
                    all_extensions.add(item.lower())
                elif isinstance(item, dict):
                    self._extract_extensions_from_complex(item, all_extensions)
    

    

    
    def _get_operand_replacements(self, inst_name: str, assembly: str, variant_index: int) -> Dict[str, str]:
        """Generate operand replacements based on instruction requirements"""
        i = variant_index
        
        constraints = self._get_instruction_constraints(inst_name)
        if constraints.get('uses_compressed_regs') or constraints.get('limited_registers'):
            reg_examples = self.compressed_gpr_examples
        else:
            reg_examples = self.gpr_examples
        
        replacements = {
            # GPR register patterns
            'xd': reg_examples[i % len(reg_examples)],
            'xs1': reg_examples[(i + 1) % len(reg_examples)],
            'xs2': reg_examples[(i + 2) % len(reg_examples)],
            'xs3': reg_examples[(i + 3) % len(reg_examples)],
            'rd': reg_examples[i % len(reg_examples)],
            'rs1': reg_examples[(i + 1) % len(reg_examples)],
            'rs2': reg_examples[(i + 2) % len(reg_examples)],
            'rs3': reg_examples[(i + 3) % len(reg_examples)],
            # FPR register patterns
            'fd': self.fpr_examples[i % len(self.fpr_examples)],
            'fs1': self.fpr_examples[(i + 1) % len(self.fpr_examples)],
            'fs2': self.fpr_examples[(i + 2) % len(self.fpr_examples)],
            'fs3': self.fpr_examples[(i + 3) % len(self.fpr_examples)],
            # Vector register patterns
            'vd': self.vpr_examples[i % len(self.vpr_examples)],
            'vs1': self.vpr_examples[(i + 1) % len(self.vpr_examples)],
            'vs2': self.vpr_examples[(i + 2) % len(self.vpr_examples)],
            'vs3': self.vpr_examples[(i + 3) % len(self.vpr_examples)],
            # Vector mask
            'vm': self.vector_mask_examples[i % len(self.vector_mask_examples)],
            # CSR patterns
            'csr': self.csr_examples[i % len(self.csr_examples)],
            # Immediate patterns
            'imm': str(self._get_safe_immediate(inst_name, self._get_instruction_constraints(inst_name))),
            'simm': str(self._get_safe_immediate(inst_name, self._get_instruction_constraints(inst_name))),
            'zimm': str(abs(self._get_safe_immediate(inst_name, self._get_instruction_constraints(inst_name)))),
            'shamt': str(1 + i),
            'offset': str((i + 1) * 4),
        }
        
        constraints = self._get_instruction_constraints(inst_name)
        
        # Use constraint-based immediate generation for all instructions
        if 'imm_range' in constraints:
            min_val, max_val = constraints['imm_range']
            imm_multiple = constraints.get('imm_multiple', 1)
            imm_not_zero = constraints.get('imm_not_zero', False)
            
            safe_imm = self._get_safe_immediate_from_constraints(min_val, max_val, imm_multiple, imm_not_zero, i)
            
            for key in ['imm', 'simm', 'zimm']:
                if key in replacements:
                    replacements[key] = str(safe_imm)
        
        return replacements
    
    def _get_safe_immediate_from_constraints(self, min_val: int, max_val: int, multiple: int, not_zero: bool, variant: int) -> int:
        """Generate a safe immediate value that satisfies the given constraints."""
        candidates = [1, 2, 4, 8, 16, 32, -1, -2, -4]
        
        candidates = [c + variant for c in candidates] + candidates
        
        for candidate in candidates:
            if (min_val <= candidate <= max_val and 
                candidate % multiple == 0 and 
                (not not_zero or candidate != 0)):
                return candidate
        
        if multiple > 1:
            start = ((min_val + multiple - 1) // multiple) * multiple
            if not_zero and start == 0:
                start = multiple
            if start <= max_val:
                return start
        
        return min_val if not not_zero or min_val != 0 else (min_val + 1 if min_val + 1 <= max_val else max_val)
    
    def generate_examples(self, name: str, assembly: str, encoding_info: dict) -> List[str]:
        """Generate assembly examples using YAML assembly field as the authoritative source."""
        instruction_data = self.all_instruction_data.get(name, {})
        actual_assembly = instruction_data.get('assembly', assembly)
        
        if actual_assembly:
            assembly = actual_assembly
        
        if not assembly or not assembly.strip():
            return []
        
        examples = []
        
        if ',' in assembly or any(reg in assembly for reg in ['rd', 'rs1', 'rs2', 'imm']):
            examples.extend(self._generate_variants(name, assembly))
        else:
            variants = self._generate_variants(name, assembly)
            if variants:
                examples.extend(variants)
            else:
                examples.append(f"{name}")
        
        return examples
    
    def _generate_variants(self, name: str, assembly: str) -> List[str]:
        """Generate multiple assembly variants using the YAML assembly field."""
        variants = []
        
        instruction_data = self.all_instruction_data.get(name, {})
        actual_assembly = instruction_data.get('assembly', assembly)
        
        if actual_assembly and actual_assembly != assembly:
            assembly = actual_assembly
        
        if not assembly or not assembly.strip():
            return []
        
        reg_set = self.compressed_gpr_examples if name.startswith('c.') else self.gpr_examples
        
        for i in range(min(3, len(reg_set) - 1)):
            example = f"{name}\t{assembly}"

            replacements = self._get_operand_replacements(name, assembly, i)
            
            operands = self._parse_assembly_operands(assembly)
            for operand in operands:
                operand_type = operand.get("type")
                operand_raw = operand.get("raw")
                
                if operand_type == "rounding_mode" or operand_raw == "rm":
                    replacements['rm'] = self.rounding_mode_examples[i % len(self.rounding_mode_examples)]
                elif operand_type == "fence_ordering" or operand_raw in ["pred", "succ"]:
                    if operand_raw == "pred":
                        replacements['pred'] = self.fence_examples[i % len(self.fence_examples)]
                    elif operand_raw == "succ":
                        replacements['succ'] = self.fence_examples[(i + 1) % len(self.fence_examples)]
            
            operands = self._parse_assembly_operands(assembly)
            import re
            
            for placeholder, value in replacements.items():
                operand_found = any(op.get("raw") == placeholder or 
                                  op.get("type") in ["csr", "vector_mask"] and placeholder in ["csr", "vm"]
                                  for op in operands)
                
                if not operand_found and placeholder not in assembly:
                    continue
                
                if placeholder == 'csr':
                    example = re.sub(r'\bcsr\b', value, example)
                elif placeholder == 'vm':
                    # Vector mask is special because it's either empty (unmasked) or v0.t (masked)
                    if value:
                        example = re.sub(r'\bvm\b', value, example)
                    else:
                        example = re.sub(r',\s*\bvm\b', '', example)
                        example = re.sub(r'\bvm\b,?\s*', '', example)
                else:
                    example = example.replace(placeholder, value)
            
            for operand in operands:
                if operand.get("type") == "memory":
                    base_placeholder = operand.get("raw")
                    if '(base)' in base_placeholder:
                        base_reg = reg_set[i % len(reg_set)]
                        example = example.replace('(base)', f'({base_reg})')
                elif operand.get("type") == "memory_sp":
                    if '(sp)' in example:
                        continue
                
            variants.append(example)
        
        return variants
    
    def _parse_assembly_operands(self, assembly: str) -> List[Dict]:
        """Parse assembly string to identify operand types."""
        operands = []

        if not assembly or not assembly.strip():
            return []
        parts = [p.strip() for p in assembly.split(',') if p.strip()]
        
        for part in parts:
            operand_info = {"raw": part}
            if '(' in part and ')' in part:
                match = re.match(r'([^(]*)\(([^)]+)\)', part)
                if match:
                    offset, base = match.groups()
                    base_reg = base.strip()
                    
                    if base_reg == "sp":
                        operand_info.update({
                            "type": "memory_sp",
                            "offset": "4"
                        })
                    else:
                        operand_info.update({
                            "type": "memory",
                            "offset": "0",
                            "base": self.gpr_examples[1]
                        })
                else:
                    operand_info["type"] = "unknown"
            elif part in ["imm", "zimm", "simm"]:
                operand_info["type"] = "immediate"
            elif part in ["rd", "rs1", "rs2", "rs3", "xd", "xs1", "xs2", "xs3"]:
                operand_info["type"] = "gpr"
            elif part in ["fd", "fs1", "fs2", "fs3"]:
                operand_info["type"] = "fpr"
            elif part in ["vd", "vs1", "vs2", "vs3"]:
                operand_info["type"] = "vpr"
            elif part == "vm":
                operand_info["type"] = "vector_mask"
            elif part == "csr":
                operand_info["type"] = "csr"
            elif part in ["pred", "succ", "aq", "rl"]:
                operand_info["type"] = "fence_ordering"
            elif part in ["rm"]:
                operand_info["type"] = "rounding_mode"
            elif part in ["shamt", "shamtw"] or part.startswith("shamt"):
                operand_info["type"] = "shift_amount"
            elif part in ["zimm5", "zimm6", "zimm10", "zimm11", "zimm12"] or part.startswith(("zimm", "simm")):
                operand_info["type"] = "immediate"
            else:
                if part.startswith(('x', 'a', 't', 's')):
                    operand_info["type"] = "gpr"
                elif part.startswith(('f', 'fa', 'ft', 'fs')):
                    operand_info["type"] = "fpr"
                elif part.startswith(('v')):
                    operand_info["type"] = "vpr"
                else:
                    operand_info["type"] = "unknown"
            
            operands.append(operand_info)
        
        return operands
    
    def _get_instruction_constraints(self, name: str) -> dict:
        """Get instruction-specific constraints from loaded database."""
        raw_constraints = self.instruction_constraints.get(name, {})
        
        processed_constraints = {}
        
        immediates = raw_constraints.get('immediates', {})
        for imm_name, imm_data in immediates.items():
            if imm_name == 'imm' or imm_name.startswith(('simm', 'zimm')):
                min_val, max_val = imm_data['range']
                processed_constraints['imm_range'] = (min_val, max_val)

                if imm_data.get('not_value') == 0:
                    processed_constraints['imm_not_zero'] = True

                left_shift = imm_data.get('left_shift', 0)
                if left_shift > 0:
                    processed_constraints['imm_multiple'] = 1 << left_shift
                
                break
        
        registers = raw_constraints.get('registers', {})
        if registers:
            processed_constraints['registers'] = registers
            
            for reg_name, reg_data in registers.items():
                if reg_name.endswith("'") or reg_data.get('width') == 3:
                    processed_constraints['uses_compressed_regs'] = True
                    break
        
        if raw_constraints.get('compressed'):
            processed_constraints['compressed'] = True
        
        if raw_constraints.get('limited_registers'):
            processed_constraints['limited_registers'] = True
        
        return processed_constraints
    
 
    def _get_safe_immediate(self, name: str, constraints: dict) -> int:
        """Get a safe immediate value that satisfies instruction constraints."""
        imm_range = constraints.get('imm_range', (-2048, 2047))
        imm_multiple = constraints.get('imm_multiple', 1)
        imm_not_zero = constraints.get('imm_not_zero', False)
        
        min_val, max_val = imm_range
        
        candidates = []
        
        if imm_multiple > 1:
            start = ((min_val + imm_multiple - 1) // imm_multiple) * imm_multiple
            if imm_not_zero and start == 0:
                start = imm_multiple
            
            for i in range(6):
                candidate = start + (i * imm_multiple)
                if candidate <= max_val:
                    candidates.append(candidate)
                neg_candidate = start - ((i + 1) * imm_multiple)
                if neg_candidate >= min_val and neg_candidate != 0:
                    candidates.append(neg_candidate)
        else:
            if min_val >= 0:
                # Unsigned range
                candidates = [min_val, min_val + 1, min_val + 2, min_val + 4, min_val + 8]
                candidates.extend([max_val, max_val - 1, max_val - 2])
            else:
                # Signed range
                candidates = [1, 2, 4, 8, 16, -1, -2, -4, -8]
                candidates.extend([max_val, max_val - 1, min_val, min_val + 1])
        
        candidates = list(set(candidates))
        
        for candidate in candidates:
            if (min_val <= candidate <= max_val and 
                candidate % imm_multiple == 0 and 
                (not imm_not_zero or candidate != 0)):
                return candidate

        if imm_multiple > 1:
            start = ((min_val + imm_multiple - 1) // imm_multiple) * imm_multiple
            if imm_not_zero and start == 0:
                start = imm_multiple
            if start <= max_val:
                return start
        
        return min_val if not imm_not_zero or min_val != 0 else min_val + 1

class GasTestGenerator:
    """Main class for generating GNU Assembler test files."""
    
    def __init__(self, output_dir: str = "gas_tests", csr_dir: str = "../../../spec/std/isa/csr/", inst_dir: str = "../../../spec/std/isa/inst/"):
        self.output_dir = Path(output_dir)
        self.example_generator = AssemblyExampleGenerator(csr_dir, inst_dir)
        self.instruction_groups = {}
        self.output_dir.mkdir(exist_ok=True)
    
    def load_instructions(self, inst_dir: str, enabled_extensions: List[str] = None, 
                         include_all: bool = False) -> Dict[str, dict]:
        """Load instructions from the unified database using precomputed data"""
        if enabled_extensions is None:
            enabled_extensions = []
        
        all_instructions = self.example_generator.all_instruction_data
        
        if include_all:
            logging.info(f"Using all {len(all_instructions)} precomputed instructions")
            return all_instructions
        
        filtered_instructions = {}
        
        for name, data in all_instructions.items():
            defined_by = data.get('definedBy')
            if defined_by:
                try:
                    meets_req = parse_extension_requirements(defined_by)
                    if meets_req(enabled_extensions):
                        filtered_instructions[name] = data
                except Exception:
                    continue
            else:
                filtered_instructions[name] = data
        
        logging.info(f"Filtered to {len(filtered_instructions)} instructions from precomputed data")
        return filtered_instructions
    
    def group_instructions_by_extension(self, instructions: Dict[str, dict]) -> Dict[str, TestInstructionGroup]:
        """Group instructions by their defining extension."""
        groups = {}
        
        for name, info in instructions.items():
            defined_by = info.get('definedBy', 'I')
            ext_name = self._extract_extension_name(defined_by)
            if ext_name not in groups:
                groups[ext_name] = TestInstructionGroup(ext_name)
            
            groups[ext_name].add_instruction(name, info)
        
        return groups
    
    def _extract_extension_name(self, defined_by) -> str:
        """Extract a clean extension name from definedBy field using consistent logic."""
        if isinstance(defined_by, str):
            if defined_by.startswith("RV"):
                if defined_by.startswith("RV32") or defined_by.startswith("RV64"):
                    return defined_by[4:].lower() if len(defined_by) > 4 else "i"
                else:
                    return defined_by[2:].lower() if len(defined_by) > 2 else "i"
            return defined_by.lower()
        elif isinstance(defined_by, dict):
            return self._extract_from_complex_definition(defined_by)
        else:
            return sanitize_extension_name(str(defined_by))
    
    def _extract_from_complex_definition(self, defined_by: dict) -> str:
        """Extract extension name from complex definedBy structures."""
        if 'anyOf' in defined_by:
            any_of_list = defined_by['anyOf']
            if any_of_list and len(any_of_list) > 0:
                first_item = any_of_list[0]
                if isinstance(first_item, str):
                    return first_item.lower()
                elif isinstance(first_item, dict) and 'allOf' in first_item:
                    all_of_list = first_item['allOf']
                    if all_of_list and len(all_of_list) > 0:

                        extensions = [ext.lower() for ext in all_of_list if isinstance(ext, str)]
                        return '-'.join(extensions) if extensions else 'unknown'
                return sanitize_extension_name(str(first_item))
        
        elif 'allOf' in defined_by:
            all_of_list = defined_by['allOf']
            if all_of_list and len(all_of_list) > 0:
                extensions = [ext.lower() for ext in all_of_list if isinstance(ext, str)]
                return '-'.join(extensions) if extensions else 'unknown'
        
        elif 'oneOf' in defined_by:
            one_of_list = defined_by['oneOf']
            if one_of_list and len(one_of_list) > 0:
                first_ext = one_of_list[0]
                if isinstance(first_ext, str):
                    return first_ext.lower()
                return sanitize_extension_name(str(first_ext))

        elif 'name' in defined_by:
            return defined_by['name'].lower()
        
        return sanitize_extension_name(str(defined_by))
    
    def generate_tests_for_group(self, group: TestInstructionGroup) -> None:
        """Generate test files for a group of related instructions."""
        if not group.instructions:
            return

        self._generate_main_tests(group)

        if group.arch_specific["rv64"]:
            self._generate_arch_specific_tests(group, "rv64")

        self._generate_error_tests(group)

        if len(group.instructions) > 5:
            self._generate_no_alias_tests(group)
    
    def _generate_main_tests(self, group: TestInstructionGroup) -> None:
        """Generate the main .s and .d test files for a group."""
        ext_name = self._get_binutils_filename(group.extension)
        
        main_instructions = []
        for name, info in group.instructions:
            base = info.get('base')
            if base is None:
                main_instructions.append((name, info))
        
        # Generate assembly source file
        source_file = self.output_dir / f"{ext_name}.s"
        dump_file = self.output_dir / f"{ext_name}.d"
        
        with open(source_file, 'w') as f:
            f.write("target:\n")
            
            for name, info in main_instructions:
                assembly = info.get('assembly', '')
                examples = self.example_generator.generate_examples(name, assembly, info.get('encoding', {}))
                
                f.write(f"\t# {name} instruction\n")
                
                for example in examples:
                    f.write(f"{example}\n")
                
                f.write("\n")
        
        base_arch = "rv32i"
        march = self._build_march_string(base_arch, group.extension)
        
        with open(dump_file, 'w') as f:
            f.write(f"#as: -march={march}\n")
            f.write(f"#source: {source_file.name}\n")
            f.write("#objdump: -d\n")
            f.write("\n")
            f.write(".*:[ \t]+file format .*\n")
            f.write("\n")
            f.write("\n")
            f.write("Disassembly of section .text:\n")
            f.write("\n")
            f.write("0+000 <target>:\n")
            
            addr = 0
            for name, info in main_instructions:
                assembly = info.get('assembly', '')
                examples = self.example_generator.generate_examples(name, assembly, info.get('encoding', {}))
                
                for example in examples:
                    pattern = self._create_disasm_pattern(addr, name, example)
                    f.write(f"{pattern}\n")
                    addr += 4  # Assume 4-byte instructions
    
    def _generate_arch_specific_tests(self, group: TestInstructionGroup, arch: str) -> None:
        """Generate architecture-specific test files."""
        ext_name = self._get_binutils_filename(group.extension)
        
        source_file = self.output_dir / f"{ext_name}-{arch[2:]}.s"
        dump_file = self.output_dir / f"{ext_name}-{arch[2:]}.d"
        
        arch_instructions = group.arch_specific[arch]
        if not arch_instructions:
            return
        
        with open(source_file, 'w') as f:
            f.write("target:\n")
            
            for name, info in arch_instructions:
                assembly = info.get('assembly', '')
                examples = self.example_generator.generate_examples(name, assembly, info.get('encoding', {}))
                
                f.write(f"\t# {name} instruction ({arch.upper()} only)\n")
                for example in examples:
                    f.write(f"{example}\n")
                f.write("\n")
        
        base_arch = f"{arch}i"
        march = self._build_march_string(base_arch, group.extension)
        
        with open(dump_file, 'w') as f:
            f.write(f"#as: -march={march}\n")
            f.write(f"#source: {source_file.name}\n")
            f.write("#objdump: -d\n")
            f.write("\n")
            f.write(".*:[ \t]+file format .*\n")
            f.write("\n")
            f.write("\n")
            f.write("Disassembly of section .text:\n")
            f.write("\n")
            f.write("0+000 <target>:\n")
            
            addr = 0
            for name, info in arch_instructions:
                assembly = info.get('assembly', '')
                examples = self.example_generator.generate_examples(name, assembly, info.get('encoding', {}))
                
                for example in examples:
                    pattern = self._create_disasm_pattern(addr, name, example)
                    f.write(f"{pattern}\n")
                    addr += 4
    
    def _generate_error_tests(self, group: TestInstructionGroup) -> None:
        """Generate negative test cases for error conditions."""
        ext_name = self._get_binutils_filename(group.extension)
        
        source_file = self.output_dir / f"{ext_name}-fail.s"
        dump_file = self.output_dir / f"{ext_name}-fail.d"
        error_file = self.output_dir / f"{ext_name}-fail.l"
        
        self._generate_common_error_cases(group)
        
        if not group.error_cases:
            logging.debug(f"No error cases generated for extension {group.extension}")
            return
        
        with open(source_file, 'w') as f:
            f.write("target:\n")
            for instruction, invalid_assembly, _ in group.error_cases:
                f.write(f"\t{invalid_assembly}\n")
        
        with open(dump_file, 'w') as f:
            march = self._build_march_string("rv32i", group.extension)
            f.write(f"#as: -march={march}\n")
            f.write(f"#source: {source_file.name}\n")
            f.write(f"#error_output: {error_file.name}\n")
        
        with open(error_file, 'w') as f:
            f.write(".*: Assembler messages:\n")
            for _, invalid_assembly, error_msg in group.error_cases:
                f.write(f".*: Error: {error_msg}\n")
    
    def _generate_no_alias_tests(self, group: TestInstructionGroup) -> None:
        """Generate tests with no-aliases option for detailed disassembly."""
        ext_name = self._get_binutils_filename(group.extension)
        
        dump_file = self.output_dir / f"{ext_name}-na.d"
        source_file = f"{ext_name}.s"
        
        main_instructions = []
        for name, info in group.instructions:
            base = info.get('base')
            if base is None:
                main_instructions.append((name, info))
        
        with open(dump_file, 'w') as f:
            march = self._build_march_string("rv32i", group.extension)
            f.write(f"#as: -march={march}\n")
            f.write(f"#source: {source_file}\n")
            f.write("#objdump: -d -M no-aliases\n")
            f.write("\n")
            f.write(".*:[ \t]+file format .*\n")
            f.write("\n")
            f.write("Disassembly of section .text:\n")
            f.write("\n")
            f.write("0+000 <target>:\n")
            
            addr = 0
            for name, info in main_instructions:
                assembly = info.get('assembly', '')
                examples = self.example_generator.generate_examples(name, assembly, info.get('encoding', {}))
                
                for example in examples:
                    pattern = self._create_disasm_pattern(addr, name, example, no_aliases=True)
                    f.write(f"{pattern}\n")
                    addr += 4
    
    def _generate_common_error_cases(self, group: TestInstructionGroup) -> None:
        """Generate common error cases for instructions that don't have explicit ones."""
        instructions_with_errors = []
        
        for name, info in group.instructions[:5]:
            assembly = info.get('assembly', '')
            
            if assembly:
                examples = self.example_generator.generate_examples(name, assembly, info.get('encoding', {}))
                
                if examples:
                    base_example = examples[0].strip()
                    
                    if '\t' in base_example:
                        inst_name, operands = base_example.split('\t', 1)
                        if operands:

                            if any(reg in operands for reg in ['a0', 'a1', 't0', 't1', 'fa0', 'fs0']):
                                invalid_operands = operands.replace('a0', 'x32').replace('a1', 'x33')
                                invalid_operands = invalid_operands.replace('t0', 'x34').replace('t1', 'x35')
                                invalid_operands = invalid_operands.replace('fa0', 'f32').replace('fs0', 'f33')
                                group.add_error_case(name, f"{inst_name}\t{invalid_operands}", f"illegal operands `{inst_name} {invalid_operands}'")
                                instructions_with_errors.append(name)
                            
    
                            if any(char.isdigit() for char in operands):
                                invalid_operands = re.sub(r'\b\d+\b', '999999', operands)
                                if invalid_operands != operands:
                                    group.add_error_case(name, f"{inst_name}\t{invalid_operands}", f"illegal operands `{inst_name} {invalid_operands}'")
                                    instructions_with_errors.append(name)
                            

                            if name.startswith('c.') and any(char.isdigit() for char in operands):
                                zero_operands = re.sub(r'\b[1-9]\d*\b', '0', operands)
                                if zero_operands != operands:
                                    group.add_error_case(name, f"{inst_name}\t{zero_operands}", f"illegal operands `{inst_name} {zero_operands}'")
                                    instructions_with_errors.append(name)
                
                if 'csr' in assembly.lower():
                    examples = self.example_generator.generate_examples(name, assembly, info.get('encoding', {}))
                    if examples:
                        base_example = examples[0].strip()
                        if '\t' in base_example:
                            inst_name, operands = base_example.split('\t', 1)
                            invalid_operands = operands.replace('mstatus', 'nonexistent').replace('cycle', 'nonexistent')
                            group.add_error_case(name, f"{inst_name}\t{invalid_operands}", "unknown CSR `nonexistent'")
                            instructions_with_errors.append(name)
        
        if not instructions_with_errors and group.instructions:
            name, info = group.instructions[0]
            group.add_error_case(name, f"{name}\tx32, x0", "illegal operands `{name} x32, x0'")
    
    def _get_binutils_filename(self, extension: str) -> str:
        """Get binutils-style filename for extension."""
        ext = extension.lower()
        if '-' in ext:
            ext_parts = ext.split('-')
            classification = self.example_generator.extension_classification
            standard_exts = classification['standard']
            
            if all(part in standard_exts for part in ext_parts):
                return '-'.join(sorted(ext_parts))
            else:
                return ext
        
        return ext
    

    def _build_march_string(self, base_arch: str, extension: str) -> str:
        ext = extension.lower()

        classification = self.example_generator.extension_classification
        standard_exts = classification['standard']

        if '-' in ext:
            ext_parts = ext.split('-')
            
            if all(part in standard_exts for part in ext_parts):
                combined = ''.join(sorted(ext_parts))
                return f"{base_arch}{combined}"
            else:
                std_parts = [p for p in ext_parts if p in standard_exts]
                z_parts = [p for p in ext_parts if p in classification['z_extensions']]
                s_parts = [p for p in ext_parts if p in classification['s_extensions']]
                x_parts = [p for p in ext_parts if p in classification['x_extensions']]
                multi_parts = [p for p in ext_parts if p in classification['multi_standard']]
                other_parts = [p for p in ext_parts if p not in (standard_exts | classification['z_extensions'] | classification['s_extensions'] | classification['x_extensions'] | classification['multi_standard'])]
                
                if std_parts and (z_parts or s_parts or x_parts or multi_parts):
                    std_combined = ''.join(sorted(std_parts))
                    non_std_parts = sorted(z_parts + s_parts + x_parts + multi_parts + other_parts)
                    if non_std_parts:
                        non_std_combined = '_'.join(non_std_parts)
                        return f"{base_arch}{std_combined}_{non_std_combined}"
                    return f"{base_arch}{std_combined}"
                else:
                    return f"{base_arch}_{'_'.join(sorted(ext_parts))}"

        if ext in standard_exts:
            return f"{base_arch}{ext}"
        elif ext in (classification['z_extensions'] | classification['s_extensions'] | classification['x_extensions'] | classification['multi_standard']):
            return f"{base_arch}_{ext}"
        else:
            return f"{base_arch}_{ext}"
    
    def _create_disasm_pattern(self, addr: int, name: str, example: str, no_aliases: bool = False) -> str:
        """Create a regex pattern for expected disassembly output."""
        line = example.strip()
        
        while line.startswith('\t'):
            line = line[1:]
        
        if not line:
            instr = name
            operands = ""
        else:
            parts = re.split(r'\s+', line, maxsplit=1)
            instr = parts[0]
            operands = parts[1] if len(parts) > 1 else ""

        # Format: address: hex_code instruction operands
        pattern = f"[ \t]+[0-9a-f]+:[ \t]+[0-9a-f]+[ \t]+{re.escape(instr)}"
        
        if operands:
            operands_clean = re.sub(r'\s+', ' ', operands.strip())
            operands_pattern = re.escape(operands_clean)
            pattern += f"[ \t]+{operands_pattern}"
        
        return pattern
    
    def generate_all_tests(self, instructions: Dict[str, dict]) -> None:
        groups = self.group_instructions_by_extension(instructions)
        
        logging.info(f"Generating tests for {len(groups)} instruction groups")
        
        for ext_name, group in groups.items():
            logging.info(f"Generating tests for extension: {ext_name}")
            self.generate_tests_for_group(group)
        
        logging.info(f"Test generation complete. Files written to: {self.output_dir}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate GNU Assembler test files from RISC-V unified database"
    )
    parser.add_argument("--inst-dir", default="../../../spec/std/isa/inst/", 
                       help="Directory containing instruction YAML files")
    parser.add_argument("--csr-dir", default="../../../spec/std/isa/csr/", 
                       help="Directory containing CSR YAML files")
    parser.add_argument("--output-dir", default="gas_tests", 
                       help="Output directory for generated test files")
    parser.add_argument("--extensions", 
                       help="Comma-separated list of enabled extensions (default: all)")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose logging")
    parser.add_argument("--include-all", "-a", action="store_true", 
                       help="Include all instructions, ignoring extension filtering")
    
    return parser.parse_args()


def main():
    args = parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.include_all or not args.extensions:
        enabled_extensions = []
        include_all = True
        logging.info("Including all instructions")
    else:
        enabled_extensions = [ext.strip() for ext in args.extensions.split(",") if ext.strip()]
        include_all = False
        logging.info(f"Enabled extensions: {', '.join(enabled_extensions)}")
    
    if not os.path.isdir(args.inst_dir):
        logging.error(f"Instruction directory not found: {args.inst_dir}")
        sys.exit(1)
    
    if not os.path.isdir(args.csr_dir):
        logging.warning(f"CSR directory not found: {args.csr_dir}. Using fallback CSR list.")
    
    generator = GasTestGenerator(args.output_dir, args.csr_dir, args.inst_dir)

    instructions = generator.load_instructions(args.inst_dir, enabled_extensions, include_all)
    
    if not instructions:
        logging.error("No instructions found or all were filtered out.")
        sys.exit(1)

    generator.generate_all_tests(instructions)


if __name__ == "__main__":
    main()