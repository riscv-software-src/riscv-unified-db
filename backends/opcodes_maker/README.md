# RISC-V Instruction Format Generator

This tool converts RISC-V instruction YAML definitions into various output formats including C headers, Chisel, Rust, Go, and LaTeX documentation.

## Prerequisites

- Python 3
- YAML Python package (`pip install pyyaml`)
- Make

## Directory Structure

```
.
├── yaml_to_json.py    # Converts YAML instruction definitions to JSON
├── generator.py       # Generates various output formats from JSON
├── output/           # Generated files directory
└── Makefile         # Build system configuration
```

## Input/Output Format

### Input
- YAML files containing RISC-V instruction definitions
- Default input directory: `../../arch/inst`
- Can be customized using `YAML_DIR` variable

### Output
All outputs are generated in the `output` directory:
- `encoding.out.h` - C header definitions
- `inst.chisel` - Chisel implementation
- `inst.spinalhdl` - SpinalHDL implementation
- `inst.sverilog` - SystemVerilog implementation
- `inst.rs` - Rust implementation
- `inst.go` - Go implementation
- `instr-table.tex` - LaTeX instruction table
- `priv-instr-table.tex` - LaTeX privileged instruction table
- `instr_dict.json` - Intermediate JSON representation
- `processed_instr_dict.json` - Final processed JSON

## Usage

### Basic Usage
```bash
make                        # Use default YAML directory
make YAML_DIR=/custom/path  # Use custom YAML directory
make clean                  # Remove all generated files
make help                   # Show help message
```

### Pipeline Steps
1. YAML to JSON conversion (`yaml_to_json.py`)
   - Reads YAML instruction definitions
   - Creates intermediate JSON representation

2. Output Generation (`generator.py`)
   - Takes JSON input
   - Generates all output formats
   - Places results in output directory

### Customization
- Input directory can be changed:
  ```bash
  make YAML_DIR=/path/to/yaml/files
  ```
- Default paths in Makefile:
  ```makefile
  YAML_DIR ?= ../../arch/inst
  OPCODES_DIR := ../riscv-opcodes
  OUTPUT_DIR := output
  ```

## Error Handling
- Checks for required Python scripts before execution
- Verifies input directory exists
- Creates output directory if missing
- Shows helpful error messages for missing files/directories

## Cleaning Up
```bash
make clean  # Removes all generated files and output directory
```

## Dependencies
- Requires access to RISC-V opcodes repository (expected at `../riscv-opcodes`)
- Python scripts use standard libraries plus PyYAML

## Note
Make sure your input YAML files follow the expected RISC-V instruction definition format. For format details, refer to the RISC-V specification or example YAML files in the arch/inst directory.
