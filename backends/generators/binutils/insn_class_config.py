"""
User configuration for instruction class names.

Define custom names for extensions here, e.g.:
  USER_DEFINED_INSN_NAMES = { 'Zbb': 'INSN_CLASS_ZBB' }
"""

USER_DEFINED_INSN_NAMES = {}


def is_user_defined_class(class_name: str) -> bool:
    return class_name in set(USER_DEFINED_INSN_NAMES.values())

