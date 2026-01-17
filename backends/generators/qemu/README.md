# QEMU RISC-V Generator

This generator creates QEMU-compatible files from RISC-V Unified Database instruction and CSR definitions. It automates the addition of new RISC-V extensions to QEMU.

## Overview

The generator creates three main types of files:

1. **Instruction Decoder (`insn32.decode`)**: QEMU's instruction decoding format
2. **CSR Table (`cpu_bits.h`)**: Control and Status Register definitions
3. **Disassembler Table (`riscv.c`)**: Disassembler instruction entries

## Motivation

QEMU currently maintains large, hand-maintained instruction maps and CSR tables. New extensions require manual maintenance of:
- `target/riscv/insn32.decode` - instruction decoding tables
- `target/riscv/cpu_bits.h` - CSR definitions
- `disas/riscv.c` - disassembler tables
- `disas/riscv-*.xml` - GDB XML descriptions

This generator helps automate this process by extracting information directly from the unified database.

## Features

### Current Capabilities

- **Instruction Decoding**: Generates QEMU-compatible instruction matching tables from encoding definitions
- **CSR Tables**: Creates CSR address macros for QEMU CPU context
- **Disassembler Stubs**: Generates template entries for the disassembler (requires manual completion of operand formats)
- **Architecture Support**: Handles RV32, RV64, and mixed encoding scenarios
- **Extension Filtering**: Supports selective generation for specific RISC-V extensions

### Future Enhancements

- Complete disassembler table generation with operand format inference
- GDB XML register descriptions (`riscv-*.xml`)
- QEMU TCG translation helper hints
- Automated operand type detection and formatting
- Integration with QEMU's build system

## Usage

### Basic Usage

Generate QEMU files for all standard extensions:

```bash
python3 qemu_generator.py --include-all --output-dir qemu_gen
```

### Generate for Specific Extensions

```bash
python3 qemu_generator.py --extensions=I,M,A,F,D --output-dir qemu_rv64_gen
```

### Custom Paths

```bash
python3 qemu_generator.py \
  --inst-dir=/path/to/spec/inst \
  --csr-dir=/path/to/spec/csr \
  --output-dir=my_qemu_gen \
  --arch=RV64 \
  --verbose
```

## Command Line Options

- `--inst-dir`: Directory containing instruction YAML files (default: `../../../spec/std/isa/inst/`)
- `--csr-dir`: Directory containing CSR YAML files (default: `../../../spec/std/isa/csr/`)
- `--output-dir`: Output directory for generated files (default: `qemu_gen`)
- `--extensions`: Comma-separated list of enabled extensions (default: `I,M,A,F,D,C`)
- `--arch`: Target architecture - `RV32`, `RV64`, or `BOTH` (default: `RV64`)
- `--include-all`, `-a`: Include all instructions, ignoring extension filtering
- `--verbose`, `-v`: Enable verbose logging

## Generated Files

### 1. `insn32_generated.decode`

QEMU instruction decoding table. Contains entries in the format:
```
@insn32_<name> 0x<match> 0x<mask>
```

**Integration**: Append to `qemu/target/riscv/insn32.decode`

### 2. `cpu_bits_generated.h`

CSR address definitions. Contains:
```c
#define CSR_<NAME> 0x<address>
```

**Integration**: Append to `qemu/target/riscv/cpu_bits.h` within the appropriate guarded section.

### 3. `riscv_disas_generated.c`

Disassembler table stubs. These are templates that require:
- Operand format specification
- Register mapping
- Immediate encoding details

**Integration**: Requires manual completion and merging into `qemu/disas/riscv.c`

## Architecture

### QemuInstructionDecoder

Processes instruction encoding definitions:
- Parses match strings from encoding definitions
- Extracts mask and match values
- Handles both RV32 and RV64 variants
- Sorts entries by specificity (most specific masks first)

### QemuCsrTable

Generates CSR definitions:
- Maps CSR addresses to names
- Creates QEMU-compatible macro format
- Includes documentation comments

### QemuDisassemblerTable

Generates disassembler entries (currently as templates):
- Creates entry stubs for all instructions
- Includes assembly format reference
- Marked for manual completion of operand formats

### QemuExtensionMapper

Maps UDB extension definitions to QEMU naming:
- Simple extensions: Uppercase (e.g., `Zba` → `ZBA`)
- Complex combinations: Underscore-joined (e.g., `allOf: [I, M]` → `I_AND_M`)

## Integration with QEMU

### Step 1: Run the Generator

```bash
python3 qemu_generator.py --include-all --output-dir /tmp/qemu_gen
```

### Step 2: Review Generated Files

Check the output files for completeness:
- `insn32_generated.decode` - Review instruction count
- `cpu_bits_generated.h` - Verify CSR addresses
- `riscv_disas_generated.c` - Note TODO markers for manual work

### Step 3: Integrate Instruction Decoder

Append `insn32_generated.decode` to `qemu/target/riscv/insn32.decode`:

```bash
cat /tmp/qemu_gen/insn32_generated.decode >> qemu/target/riscv/insn32.decode
```

### Step 4: Integrate CSR Definitions

Add CSR macros to `qemu/target/riscv/cpu_bits.h`:

```bash
# Extract the relevant #define lines and add to cpu_bits.h
```

### Step 5: Complete Disassembler (Manual)

For `riscv_disas_generated.c`:
1. Review generated entry stubs
2. For each instruction, complete the operand format
3. Add to `qemu/disas/riscv.c` `riscv_opcodes` table

## Limitations and Known Issues

### Current Limitations

1. **Disassembler Format**: Operand format specification requires manual completion
2. **Immediate Encoding**: Complex immediate encoding schemes not yet fully supported
3. **Register Constraints**: Compressed instruction register constraints partially supported
4. **Extension Dependencies**: No validation of extension interdependencies

### Information Missing from UDB

Some QEMU-specific information is not yet captured in the UDB:
- Register type information (GPR, FPR, VR, etc.)
- Operand format strings (QEMU requires specific formats like "d,s,t")
- Instruction encoding translations for QEMU's helper functions
- GDB register numbering and descriptions

### Workarounds

Until the UDB is enhanced:
1. Use this generator for instruction matching tables (safe, directly from UDB)
2. Generate CSR tables (direct mapping, reliable)
3. Review and manually complete disassembler entries
4. Use existing QEMU patterns as templates for new extensions

## Extending the Generator

### Adding New Output Format

Create a new generator class:

```python
class QemuNewFormat:
    def __init__(self):
        self.entries = []

    def add_entry(self, name: str, info: dict):
        # Process and add entry
        pass

    def generate_file(self, output_file: str):
        # Write output
        pass
```

### Customizing Extension Mapping

Modify `QemuExtensionMapper.map_extension()` to handle custom extensions:

```python
def map_extension(self, defined_by) -> str:
    if isinstance(defined_by, str):
        if defined_by == "CustomExt":
            return "CUSTOM_EXT"
    return super().map_extension(defined_by)
```

## Statistics and Reporting

The generator provides statistics for each run:
- Instructions processed vs. successfully generated
- Errors and filtering reasons
- CSR count
- Output file sizes and locations

Example output:
```
============================================================
QEMU Generation Summary
============================================================
Instructions processed:  245
  Successfully generated: 243
  Errors:                 0
  No match string:        2
CSRs generated:          65
Disassembly entries:     243

Output files:
  qemu_gen/insn32_generated.decode
  qemu_gen/cpu_bits_generated.h
  qemu_gen/riscv_disas_generated.c
============================================================
```

## Contributing

To improve this generator:

1. **Enhance UDB Schema**: Add missing operand format information
2. **Extend Generator**: Add support for new QEMU file formats
3. **Add Tests**: Create test cases for various extension combinations
4. **Document Patterns**: Record common patterns for manual completion

## Related Resources

- [QEMU RISC-V Documentation](https://qemu.weilnetz.de/doc/html/system/target-riscv.html)
- [RISC-V ISA Specification](https://riscv.org/technical/specifications/)
- [RISC-V Unified Database](https://github.com/riscv-software-src/riscv-unified-db)
- QEMU source: `target/riscv/`, `disas/riscv.c`, `disas/riscv-*.xml`
