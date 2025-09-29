# GNU Assembler Test Generator for RISC-V

This tool automatically generates, binutils test files for the GNU Assembler (gas) from the RISC-V unified database. It creates assembly source files (`.s`), dump files (`.d`), and error files (`.l`) using the UDB.

## Overview

The generator attempts to revolutionize RISC-V extension testing by:

- **Automatically discovering** extension patterns from the unified database
- **Matching binutils conventions** with Risc-V architecture
- **Generating realistic assembly examples** with multiple operand combinations
- **Creating comprehensive error cases** for negative testing
- **Eliminating manual test creation** specially for new RISC-V extensions

### Generated Test Files

For each extension, the generator creates:

1. **Assembly Source Files (`.s`)**: Contain actual assembly instructions with various operand combinations
2. **Dump Files (`.d`)**: Define test parameters and expected disassembly output patterns
3. **Error Files (`.l`)**: Expected error messages for negative test cases
4. **Architecture-specific variants**: RV32/RV64 specific tests when applicable

## Usage

### Basic Usage

Generate tests for all instructions in the unified database:

```bash
python3 gas_test_generator.py --include-all --output-dir gas_tests
```

### Generate Tests for Specific Extensions

```bash
python3 gas_test_generator.py --extensions "i,m,a,f,d,zba,zbb"
```

### Custom Output Directory

```bash
python3 gas_test_generator.py --include-all --output-dir gas_tests
```

### Verbose Output

```bash
python3 gas_test_generator.py --include-all --output-dir gas_tests --verbose
```

## Command Line Options

- `--inst-dir`: Directory containing instruction YAML files (default: `../../../spec/std/isa/inst/`)
- `--csr-dir`: Directory containing CSR YAML files (default: `../../../spec/std/isa/csr/`)
- `--output-dir`: Output directory for generated test files (default: `gas_tests`)
- `--extensions`: Comma-separated list of enabled extensions
- `--include-all`: Include all instructions, ignoring extension filtering
- `--verbose`: Enable verbose logging

## Integration with Binutils Test Suite

The generated files follow the same format and conventions as the existing binutils gas test suite and can be directly integrated:

1. Copy generated files to `binutils-gdb/gas/testsuite/gas/riscv/`
2. Update the test Makefile if needed
3. Run tests with `make check`

## Features

### Assembly Generation

- **Multiple Operand Combinations**: Generates realistic assembly examples with different register and immediate combinations
- **Constraint-Aware Generation**: Respects instruction-specific constraints from encoding definitions
- **Edge Case Testing**: Creates boundary value tests for immediate operands
- **Memory Operand Variants**: Handles `offset(base)` memory operands with various offsets
- **Register Type Awareness**: Uses appropriate register names (x/a/t/s for GPR, f/fa/ft/fs for FPR)
- **Compressed Instruction Support**: Handles C extension register constraints properly

### Error Case Generation

- **Invalid Registers**: Tests with out-of-range register numbers
- **Invalid Immediates**: Tests with out-of-bounds immediate values
- **Malformed Assembly**: Common syntax error cases

### Test Organization

- **Extension Grouping**: Groups related instructions by defining extension
- **Consistent Naming**: Follows existing binutils test naming conventions
- **Regex Patterns**: Generates robust regex patterns for disassembly matching

## Architecture

The generator uses a clean, modular architecture with three main components:

### TestInstructionGroup
Groups related instructions by extension and categorizes them:
- Main instructions (architecture-neutral)
- Compressed variants (C extension)
- Architecture-specific instructions (RV32/RV64 only)
- Error cases for negative testing

### AssemblyExampleGenerator
Creates realistic assembly examples using data-driven approach:
- Loads and classifies all extensions from unified database
- Parses assembly format strings from YAML definitions
- Generates constraint-aware operand combinations
- Creates realistic immediate values respecting encoding constraints
- Handles different operand types (registers, immediates, memory, CSRs)
- Manages compressed instruction register constraints

### GasTestGenerator
Main orchestrator implementing binutils conventions:
- Loads instructions
- Groups instructions by extension
- Generates RV32-default tests matching binutils patterns
- Creates architecture-specific variants when needed
- Builds march strings
- Manages binutils-compatible output directory structure

## Extending the Generator

### Adding New Operand Types

To support new operand types, extend the `_parse_assembly_operands` method in `AssemblyExampleGenerator`:

```python
elif part == "new_operand_type":
    operand_info["type"] = "new_type"
```

### Custom Error Cases

Add extension-specific error cases by overriding `_generate_common_error_cases`:

```python
def _generate_custom_error_cases(self, group: TestInstructionGroup):
    # Add custom error scenarios
    group.add_error_case("instruction", "invalid_assembly", "error_message")
```

### Architecture-specific Logic

Modify `_determine_march` to handle new architecture requirements:

```python
def _determine_march(self, group: TestInstructionGroup) -> str:
    # Custom march string logic
    return f"rv32i_{extension}"
```
