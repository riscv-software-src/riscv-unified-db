# Instructions Repository

This repository contains definitions for instructions following the standardized JSON schema provided by UDB (Universal Design Base). Each instruction is specified within its own YAML file.

## Structure

Instructions are organized under the following path:

```
arch/
  inst/
    <extension_name>/ # Typically alphabetical order of extensions defining instructions; however, this is not mandatory.
      <instruction_name>.yaml
```

## Creating an Instruction Definition

Each instruction definition should conform to the provided schema (`inst_schema.json`). Below is a detailed template and explanation for creating a new instruction YAML file.

### YAML Template

```yaml
$schema: "inst_schema.json#"
kind: instruction
name: <instruction_mnemonic>
long_name: <Brief description of the instruction>
description: |
  Detailed explanation of what the instruction does.
  Use clear and precise asciidoc-formatted text.
definedBy: <Extension defining this instruction>
assembly: <assembly_format>
encoding:
  match: <binary encoding using 0, 1, and ->
  variables:
    - name: <variable_name>
      location: <bit range, e.g., 24-20>
access:
  s: always | sometimes | never
  u: always | sometimes | never
  vs: always | sometimes | never
  vu: always | sometimes | never
data_independent_timing: true | false
operation(): |
  # Optional IDL operation
  leave empty if not provided

sail(): |
  # Optional Sail operation
  leave empty if not provided
```

### Explanation of Fields

- **`name`**: The mnemonic of the instruction (lowercase, alphanumeric and periods only).
- **`long_name`**: Short, human-readable description.
- **`description`**: Full, detailed description of the instruction behavior (asciidoc format).
- **`definedBy`**: Specifies the extension defining this instruction.
- **`assembly`**: Instruction format in assembly language, including operands.
- **`encoding.match`**: Binary encoding of the instruction with fixed bits defined by `0` or `1` and variable bits indicated by `-`.
- **`encoding.variables`**: Defines fields in the instruction encoding, including their location.
  - **`name`**: Name of the field (e.g., `rs1`, `rs2`).
  - **`location`**: Bit positions of the field in the instruction encoding.
- **`access`**: Specifies the privilege mode access for the instruction (`always`, `sometimes`, or `never`).
- **`data_independent_timing`**: Indicates whether the execution timing is data-independent.
- **`operation()` & `sail()`**: Optional fields for IDL or Sail descriptions. Leave empty if unused.

## JSON Schema

All instruction definitions must adhere strictly to the provided JSON schema:

[`inst_schema.json`](schemas/inst_schema.json)

Ensure compliance with schema validation to facilitate integration and usage within UDB.
