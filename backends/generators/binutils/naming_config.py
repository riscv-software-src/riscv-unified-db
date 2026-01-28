"""
Naming configuration for binutils generation.

- USER_DEFINED_INSN_NAMES: map extension identifiers (e.g., 'Zbb', 'CustomTest')
  to explicit INSN_CLASS_* names. If not set, generator uses INSN_CLASS_<EXT>.

- USER_DEFINED_OPERAND_PREFERENCES: for ambiguous or custom operands, map a
  (operand_name, bit_range_string) pair to a binutils operand token (e.g., 'u').
  Example: { ('imm', '31-12'): 'u' }
"""

USER_DEFINED_INSN_NAMES = {}

# Example preference:
# USER_DEFINED_OPERAND_PREFERENCES = { ('imm', '31-12'): 'u' }
USER_DEFINED_OPERAND_PREFERENCES = {}


def is_user_defined_class(class_name: str) -> bool:
    return class_name in set(USER_DEFINED_INSN_NAMES.values())

