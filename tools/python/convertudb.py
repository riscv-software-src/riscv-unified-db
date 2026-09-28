# Copyright (c) HMC Qualcomm Clinic Team (Isabel Godoy, Nina Luo, Brayden Mendoza, Lughnasa Miller, Madeline Seifert, Ben Wiedermann)
# SPDX-License-Identifier: CC0-1.0

"""
Script to convert .udb files to .yml files and vice versa.

NOTE: doesn't handle in-line comments, assumes that all comments exist
      on their own line (TODO: add support for in-line comments)
"""

import re
import sys

# String fields that should always have quotes around them
QUOTED_FIELDS = [
    "version",
]

# String fields that don't have to have quotes around them in YAML
STRING_FIELDS = [
    # General fields
    "$schema",
    "name",
    "long_name",
    "display_name",
    "description",
    "$source",
    "id",
    "url",
    "text_url",
    "email",
    "introduction",
    # CSR fields
    "alias",
    "requires",
    # Instruction fields
    "assembly",
    "operation_ast",
    "access_detail",
    "match",
    "$child_of",
    # Extension fields
    "rvi_jira_issue",
    "branch",
    "ratification_date",
    "company",
    # Profile fields
    "text",
    "note",
    "$parent_of",
    "marketing_name",
    # Register file fields
    "register_class",
    # Manual fields
    "marketing_version",
    # Manual version fields
    "title",
    "isa_manual_tree",
    # Profile family fields
    "naming_scheme",
    # Config fields
    "arch_overlay",
    # Non-isa fields
    "content",
    # IDL fields
    "sw_read()",
    "reset_value()",
    "sw_write(csr_value)",
    "legal?(csr_value)",
    "type()",
    "operation()",
    "arch_read()",
    "arch_write(value)",
    "when()",
    "idl()",
    # Conditions
    "reason",
]

# Fields that aren't strings, but have strings in them
# e.g. release: { $ref: "releaseAddress" }
HAS_STRINGS = [
    "opcode",
    "release",
    "not",
    "manual",
]

# Fields that are yaml arrays of strings
YAML_ARRAY_STRING_FIELDS = [
    "doc_links",
    "items",  # for alias in csr
    "changes",
    "chapters",
]

# Fields that are yaml arrays of values that contain strings
# e.g. an element in "hints" looks like
#    - { $ref: "inst/Zihintntl/c.ntl.p1.yaml#" }
YAML_ARRAY_HAS_STRINGS = [
    "hints",
]

# Fields that are YAML arrays of arrays of strings
# e.g. elements would look like: - ["A", "B", "C"]
YAML_ARRAY_ARRAY_STRINGS = [
    "implemented_extensions",
]

# Fields that are arrays of strings, but without the '-' prefixing every element
YAML_LIST_STRING_FIELDS = [
    "fields",
    "opcodes",
    "extensions",
]

# Fields that can be EITHER a yaml array of strings or just a string
YAML_ARRAY_OR_STRING_FIELDS = [
    "$inherits",
    "$remove",
]

# Fields that are arrays of strings (i.e., denoted with square brackets)
ARRAY_STRING_FIELDS = [
    "abi_mnemonics",
    "pseudoinstructions",
]

# Fields that are either a string or an array
# e.g. affectedBy could be "F" or ["F", "D", "V"]
ARRAY_OR_STRING_FIELDS = [
    "affectedBy",
    "parent_of",
]

# Some fields (especialy in conditions), might be a string, as they could take on
# other values as well
MAYBE_STRING = [
    "equal",
    "notEqual",
    "includes",
]

KEYWORDS = (
    STRING_FIELDS
    + YAML_ARRAY_STRING_FIELDS
    + HAS_STRINGS
    + YAML_ARRAY_OR_STRING_FIELDS
    + YAML_LIST_STRING_FIELDS
    + YAML_ARRAY_HAS_STRINGS
    + MAYBE_STRING
)


def add_quotes(s):
    """Add quotes to string s if it doesn't already have them"""
    if not (s.startswith('"') and s.endswith('"')):
        return f'"{s}"' if s else s
    return s


def add_nested_quotes(s):
    try:
        nested_field, nested_value = s[1:-1].strip().split(":", 1)
        nested_value = nested_value.strip()
        nested_value = add_quotes(nested_value)
        return f"{{ {nested_field}: {nested_value} }}"

    # 'not' has ambiguity, this handles when 'not' doesn't
    # have any strings that need to be quoted
    except ValueError:
        return s


def add_quotes_to_elements(s):
    elements = [elem.strip() for elem in s.strip("[]").split(",")]
    quoted_elements = [add_quotes(elem) for elem in elements]
    return f"[{', '.join(quoted_elements)}]"


def convert_udb_to_yaml(udb_file):
    """Conversion from YAML to UDB involves removing quotes around string values"""

    with open(udb_file) as file:
        lines = file.readlines()

    output_lines = []
    for line in lines:
        # Don't process comments
        if line.strip().startswith("#"):
            output_lines.append(line)

        else:
            try:
                field, value = line.split(":", 1)

                # Pre-process field string before checking if it's in QUOTED_FIELDS
                clean_field = field.strip()
                if clean_field.startswith("-"):
                    clean_field = clean_field[1:].strip()

                # Don't remove quotes for quoted fields
                if clean_field.strip() in QUOTED_FIELDS:
                    output_lines.append(line)
                else:
                    # Remove quotes unless they're escaped
                    value = re.sub(r'(?<!\\)"', "", value)

                    # Remove '\' from escaped quotes
                    value = value.replace('\\"', '"')

                    # Remove '\' from escaped backslashes
                    value = value.replace("\\\\", "\\")

                    output_lines.append(f"{field}:{value}")

            # Line doesn't have ":"
            except ValueError:
                # Remove quotes unless they're escaped
                line = re.sub(r'(?<!\\)"', "", line)

                # Remove '\' from escaped quotes
                line = line.replace('\\"', '"')

                output_lines.append(line)

    output_file = udb_file.rsplit(".", 1)[0] + ".yaml"
    with open(output_file, "w") as file:
        file.writelines(output_lines)


def convert_yaml_to_udb(yaml_file):
    """Conversion from YAML to UDB involves adding quotes around string values"""

    with open(yaml_file) as file:
        lines = file.readlines()

    # to keep track if we're currently processing a multi-line string
    inMultiLineString = False

    # to keep track if we're currently processing an array of strings
    inYamlStringArray = False

    # if we're in a YAML array that consists of arrays of strings
    inYamlArrayOfStringArrays = False

    # to keep track if we're currently processing a list of strings
    inYamlStringList = False

    # to keep track if we're currently processing an array that isn't
    #    a list of strings, but has strings in the elements
    inArrayHasStrings = False

    # when we are in a param condition
    inParamCondition = False

    # 'extensions' is handled differently in this case
    inManualVolumes = False

    # when we're an 'extensions' field that's in a 'volumes' field
    inManualVolumesExtensions = False

    # Loop variables that help with handling whitespace
    multiline_indentation = 0
    array_indentation = 0
    manual_volumes_indentation = 0
    param_indentation = 0
    field_indentation = 0

    output_lines = []
    for i, line in enumerate(lines):
        # Don't process comments or empty lines
        stripped = line.strip()
        if stripped.startswith("#") or stripped == "":
            output_lines.append(line)

        else:
            # Check if the line is part of a multi-line string
            if inMultiLineString:
                line_indentation = len(re.search(r"^\s*", line).group())

                if (line_indentation > multiline_indentation) or line.strip() == "":
                    # escape backslashes
                    line = line.replace("\\", "\\\\")

                    # escape quotes
                    line = line.replace('"', '\\"')

                    # edge case for when a multi-line string is at the end of a file
                    if i == len(lines) - 1:
                        line = line + '"\n'

                    output_lines.append(line)
                    continue

                # when we reach a line that has less indentation, we know the
                # multi-line string has ended, so add a closing quote
                else:
                    inMultiLineString = False
                    output_lines.append(" " * multiline_indentation + '"\n')

            # Check if the line is part of a YAML array of strings
            if inYamlStringArray:
                line_indentation = len(re.search(r"^\s*", line).group())
                if line_indentation > array_indentation:
                    prefix, value = line.split("-", 1)

                    # Not every element is a string in this case
                    if inParamCondition:
                        if value.strip().isnumeric():
                            pass
                        else:
                            value = add_quotes(value.strip())

                    # these elements have multiple strings in them, but
                    # aren't strings themselves
                    # e.g: - { name: "string1", version: "string2" }
                    elif inManualVolumesExtensions:
                        left, right = value.strip().split(",")
                        left_field, left_value = left.split(":")
                        right_field, right_value = right.split(":")

                        left_value = add_quotes(left_value.strip())
                        right_value = right_value[:-1]  # exclude the closing brace (})
                        right_value = add_quotes(right_value.strip())

                        value = f"{left_field}: {left_value},{right_field}: {right_value} }}"

                    # some arrays have {} around the portion that's a string
                    elif inArrayHasStrings:
                        value = add_nested_quotes(value.strip())

                    else:
                        # add quotes around the string value
                        value = add_quotes(value.strip())

                    line = f"{prefix}- {value}\n"
                    output_lines.append(line)

                    continue
                else:
                    inYamlStringArray = False
                    inArrayHasStrings = False
                    inManualVolumesExtensions = False

            if inManualVolumes:
                line_indentation = len(re.search(r"^\s*", line).group())
                inManualVolumes = line_indentation > manual_volumes_indentation

            # Check if the line is part of a YAML array that contains arrays of strings
            if inYamlArrayOfStringArrays:
                line_indentation = len(re.search(r"^\s*", line).group())
                if line_indentation > array_indentation:
                    prefix, value = line.split("-", 1)
                    value = add_quotes_to_elements(value.strip())

                    line = f"{prefix}- {value}\n"
                    output_lines.append(line)
                    continue

                else:
                    inYamlArrayOfStringArrays = False

            # Check if line is part of a YAML String list
            if inYamlStringList:
                line_indentation = len(re.search(r"^\s*", line).group())

                # Check that a field isn't already a keyword
                field = line.split(":", 1)[0].strip()
                if field in KEYWORDS:
                    pass

                # Add quotes around fields in the list
                elif (line_indentation == field_indentation) or line.strip() == "":
                    field_name = line.strip().split(":", 1)[0]

                    output_lines.append(" " * field_indentation + f'"{field_name}":\n')
                    continue
                elif line_indentation < field_indentation:
                    inYamlStringList = False

            if inParamCondition:
                line_indentation = len(re.search(r"^\s*", line).group())

                if line_indentation < param_indentation:
                    inParamCondition = False
                    continue

                # 'oneOf' for param conditions is a YAML array that might have strings
                field = line.split(":", 1)[0].strip()
                if field == "oneOf":
                    array_indentation = len(re.search(r"^\s*", line).group())
                    inYamlStringArray = True

            try:
                field, value = line.split(":", 1)
                value = value.strip()

                # Handle multi-line strings
                if value.startswith("|"):
                    inMultiLineString = True

                    # Get indentation level to determine
                    # when the multi-line string ends
                    multiline_indentation = len(re.search(r"^\s*", field).group())

                    output_lines.append(f'{field}: {value} "')

                    # Edge case for when a multiline string is empty and at the end of the file
                    if i == len(lines) - 1:
                        output_lines[-1] += '"'

                    output_lines[-1] += "\n"

                    continue

                # Pre-process field string before checking if it's value needs quotes
                clean_field = field.strip()
                if clean_field.startswith("-"):
                    clean_field = clean_field[1:].strip()

                # 'version' has the most ambiguity, it could be either a plain string,
                # a yaml array of strings, or a normal array of strings
                if clean_field == "version":
                    # YAML array
                    if value == "":
                        array_indentation = len(re.search(r"^\s*", line).group())
                        inYamlStringArray = True

                    # Array of strings
                    elif value.startswith("["):
                        value = add_quotes_to_elements(value)

                    # Plain string
                    else:
                        value = add_quotes(value)

                # 'extensions' handled differently in the 'volumes' field of the manual_verison schema
                elif clean_field == "extensions" and inManualVolumes:
                    array_indentation = len(re.search(r"^\s*", line).group())
                    inYamlStringArray = True
                    inManualVolumesExtensions = True

                # Handle fields that can be either a plain string or an array of strings
                elif clean_field in YAML_ARRAY_OR_STRING_FIELDS:
                    # The value is a YAML array
                    if value == "":
                        array_indentation = len(re.search(r"^\s*", line).group())
                        inYamlStringArray = True

                    # The value is just a string
                    else:
                        value = add_quotes(value)

                # Add quotes around string values if not already quoted
                elif clean_field in STRING_FIELDS:
                    value = add_quotes(value)

                elif clean_field in ARRAY_OR_STRING_FIELDS:
                    # Field is an array of strings
                    if value.startswith("["):
                        value = add_quotes_to_elements(value)

                    # Not an array
                    else:
                        value = add_quotes(value)

                elif clean_field in (YAML_ARRAY_STRING_FIELDS + YAML_ARRAY_HAS_STRINGS):
                    array_indentation = len(re.search(r"^\s*", line).group())
                    inYamlStringArray = True
                    inArrayHasStrings = field.strip() in YAML_ARRAY_HAS_STRINGS

                elif clean_field in YAML_ARRAY_ARRAY_STRINGS:
                    array_indentation = len(re.search(r"^\s*", line).group())
                    inYamlArrayOfStringArrays = True

                elif clean_field in YAML_LIST_STRING_FIELDS and value == "":
                    inYamlStringList = True
                    field_indentation = len(re.search(r"^\s*", lines[i + 1]).group())

                elif clean_field in ARRAY_STRING_FIELDS:
                    # Add quotes around each element in the array
                    value = add_quotes_to_elements(value)

                # Fields that aren't strings, but contain a strings that needs quotes
                elif clean_field in HAS_STRINGS:
                    value = add_nested_quotes(value)

                # equal could be either an int, boolean, or a string
                elif clean_field in MAYBE_STRING:
                    if not (value.isnumeric() or (value.lower() in ("true", "false"))):
                        value = add_quotes(value)

                # Add quotes around quoted fields if they don't already have quotes
                elif clean_field in QUOTED_FIELDS:
                    value = add_quotes(value)

                # Edge case for the param condition, which makes 'anyOf' a YAML array of
                # ints and strings
                elif clean_field == "param":
                    inParamCondition = True
                    param_indentation = len(re.search(r"^\s*", line).group())

                # For 'volumes', 'extensions' is handled different
                elif clean_field == "volumes":
                    inManualVolumes = True
                    manual_volumes_indentation = len(re.search(r"^\s*", line).group())

                output_lines.append(f"{field}: {value}\n")

            except ValueError:
                # When the line doesn't contain a ":"
                output_lines.append(line)

    output_file = yaml_file.rsplit(".", 1)[0] + ".udb"
    with open(output_file, "w") as file:
        file.writelines(output_lines)


def print_usage():
    print("USAGE: python convertudb.py [INPUT]")
    print("where INPUT is either a .udb file or a .yaml file to convert to the other format.\n")
    sys.exit(1)


if __name__ == "__main__":
    # Get CLI arguments
    if len(sys.argv) == 2:
        if sys.argv[1] == "-h" or sys.argv[1] == "--help":
            print("Script for converting between .udb and .yaml files.\n")
            print_usage()

        INPUT_FILE = sys.argv[1]  # .udb file or .yml file to convert
    else:
        print_usage()

    if INPUT_FILE.endswith(".udb"):
        convert_udb_to_yaml(INPUT_FILE)
    elif INPUT_FILE.endswith((".yml", ".yaml")):
        convert_yaml_to_udb(INPUT_FILE)
    else:
        print("INPUT must be either a .udb file or a .yaml file.")
        print_usage()
