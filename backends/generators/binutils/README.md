# Binutils RISC-V Generator

This generator creates binutils-compatible opcode table entries from RISC-V UDB instruction definitions, following the format used in `binutils-gdb/opcodes/riscv-opc.c`.

## Generated Files

The generator produces two files for every run:

### 1. Opcode Table (`.c` file)
- **Format**: `{output_name}.c` 
- **Purpose**: Contains the `riscv_opcodes[]` array with instruction definitions
- **Structure**: Each entry follows binutils format: `{name, xlen, insn_class, operands, MATCH, MASK, match_func, pinfo}`
- **Example**: `{"add", 0, INSN_CLASS_I, "d,s,t", MATCH_ADD, MASK_ADD, match_opcode, 0}`

### 2. Header File (`.h` file)
- **Format**: `{output_name}.h`
- **Purpose**: Contains `#define` constants and custom instruction class definitions
- **Contents**:
  - `MATCH_*` constants for instruction matching
  - `MASK_*` constants for instruction masking
  - Custom `INSN_CLASS_*` definitions (commented out for manual addition to binutils)

## Architecture

### Single Source of Truth
All instruction class mappings are centralized in `insn_class_config.py`:

- **`BUILTIN_CLASSES`**: Maps extensions to existing binutils instruction classes
- **`BUILTIN_COMBINATIONS`**: Maps complex extension combinations to binutils classes
- **`is_builtin_class()`**: Determines if a class already exists in binutils

### Extension Mapping
The `ExtensionMapper` class handles UDB `definedBy` specifications:

- **Simple extensions**: Direct 1:1 mapping (e.g., `Zba` → `INSN_CLASS_ZBA`)
- **Complex combinations**: 
  - `anyOf` → `*_OR_*` classes (e.g., `[Zbb, Zbkb]` → `INSN_CLASS_ZBB_OR_ZBKB`)
  - `allOf` → `*_AND_*` classes (e.g., `[Zcb, Zba]` → `INSN_CLASS_ZCB_AND_ZBA`)
- **Custom extensions**: Auto-generates class names (e.g., `Zfoo` → `INSN_CLASS_ZFOO`)

### Operand Mapping
The `OperandMapper` class converts UDB assembly format to binutils operand strings:

- Maps register operands (e.g., `xd` → `d`, `xs1` → `s`)
- Handles immediate operands (e.g., `imm` → `j`)
- Marks unknown patterns as `NON_DEFINED_*`

## Usage

### Basic Usage
```bash
python3 binutils_generator.py --extensions=I,M,Zba,Zbb --output=my_opcodes.c
```

### Command Line Options
- `--inst-dir`: Directory containing instruction YAML files (default: `../../../spec/std/isa/inst/`)
- `--output`: Output C file name (corresponding .h file generated automatically)
- `--extensions`: Comma-separated list of enabled extensions
- `--arch`: Target architecture (`RV32`, `RV64`, `BOTH`)
- `--include-all` / `-a`: Include all instructions, ignoring extension filtering
- `--verbose` / `-v`: Enable verbose logging

### Examples
```bash
# Generate for specific extensions
python3 binutils_generator.py --extensions=I,M,A,F,D --output=rv64_core.c

# Generate all instructions
python3 binutils_generator.py --include-all --output=complete_riscv.c

# Custom extension
python3 binutils_generator.py --extensions=I,MyCustomExt --output=custom.c
```

## Integration with Binutils

### Adding Custom Instruction Classes

1. **Review generated header file**: Check the "Custom instruction class definitions" section
2. **Add to binutils enum**: Edit `binutils-gdb/include/opcode/riscv.h`
   ```c
   enum riscv_insn_class
   {
     // ... existing classes ...
     INSN_CLASS_ZFOO,           // Add your custom classes here
     INSN_CLASS_I_OR_ZILSD,
     // ...
   };
   ```

3. **Add subset support**: Edit `binutils-gdb/bfd/elfxx-riscv.c` to handle extension requirements
   ```c
   static bool
   riscv_multi_subset_supports (riscv_parse_subset_t *rps,
                                enum riscv_insn_class insn_class)
   {
     switch (insn_class)
     {
       // ... existing cases ...
       case INSN_CLASS_ZFOO:
         return riscv_subset_supports (rps, "zfoo");
       // ...
     }
   }
   ```

### Adding Generated Opcodes

1. **Include header**: Add `#include "my_opcodes.h"` to your opcode file
2. **Merge opcode arrays**: 
   - Option A: Replace existing `riscv_opcodes[]` in `opcodes/riscv-opc.c`
   - Option B: Create separate opcode table and modify binutils to use it
   - Option C: Append entries to existing table

### File Locations in Binutils
- **Instruction classes**: `include/opcode/riscv.h` (enum `riscv_insn_class`)
- **Opcode tables**: `opcodes/riscv-opc.c` (`riscv_opcodes[]` array)
- **Extension support**: `bfd/elfxx-riscv.c` (`riscv_multi_subset_supports()`)
- **Operand parsing**: `opcodes/riscv-dis.c` and `gas/config/tc-riscv.c`

## Extending the Generator

### Adding New Extensions
```python
from extension_mapper import ExtensionMapper

mapper = ExtensionMapper()
mapper.add_simple_mapping('Zfoo', 'INSN_CLASS_ZFOO')
mapper.add_complex_mapping('anyOf', ['Zfoo', 'Zbar'], 'INSN_CLASS_ZFOO_OR_ZBAR')
```

### Custom Operand Mappings
Edit `operand_mapper.py` to add support for new operand patterns.

### Configuration
Edit `insn_class_config.py` to modify built-in extension mappings.

## Output Statistics

The generator provides detailed statistics:
- **Total instructions**: Number of instructions processed
- **Successfully processed**: Instructions with complete mappings
- **Non-defined operands**: Instructions with unknown operand patterns
- **Non-defined extensions**: Instructions with unknown extensions (should be 0 with current design)
- **Custom classes**: Number of custom instruction classes generated

## Validation

Use `validate_output.py` to compare generated output against reference binutils opcodes:
```bash
python3 validate_output.py reference.c generated.c
```

The validator provides detailed comparison including instruction class, operands, and MATCH/MASK values.