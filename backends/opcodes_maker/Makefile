# Directories
YAML_DIR ?= ../../arch/inst
OUTPUT_DIR := output

# Python scripts
YAML_TO_JSON := yaml_to_json.py
GENERATOR := generator.py

# Generated files
INSTR_DICT := $(OUTPUT_DIR)/instr_dict.json
C_OUT := $(OUTPUT_DIR)/encoding.out.h
CHISEL_OUT := $(OUTPUT_DIR)/inst.chisel
SPINALHDL_OUT := $(OUTPUT_DIR)/inst.spinalhdl
SVERILOG_OUT := $(OUTPUT_DIR)/inst.sverilog
RUST_OUT := $(OUTPUT_DIR)/inst.rs
GO_OUT := $(OUTPUT_DIR)/inst.go
LATEX_OUT := $(OUTPUT_DIR)/instr-table.tex
LATEX_PRIV_OUT := $(OUTPUT_DIR)/priv-instr-table.tex

# Check for required files
REQUIRED_FILES := $(YAML_TO_JSON) $(GENERATOR)
$(foreach file,$(REQUIRED_FILES),\
    $(if $(wildcard $(file)),,$(error Required file $(file) not found)))

# Default target
all: generate

# Create output directory
$(OUTPUT_DIR):
	mkdir -p $(OUTPUT_DIR)

# Convert YAML to JSON
$(INSTR_DICT): $(YAML_TO_JSON) | $(OUTPUT_DIR)
	python3 $(YAML_TO_JSON) $(YAML_DIR) $(OUTPUT_DIR)

# Generate all outputs
generate: $(INSTR_DICT)
	python3 $(GENERATOR) $(INSTR_DICT) -c -chisel -spinalhdl -sverilog -rust -go -latex || \
		{ echo "Error generating riscv-opcodes outputs. Likely, you don't have updated riscv-opcodes submodules. Please do:"; \
		  echo "git submodule update --init --recursive"; \
		  echo "git submodule update --remote ext/riscv-opcodes"; \
		  exit 1; }
	mv encoding.out.h inst.chisel inst.spinalhdl inst.sverilog inst.rs inst.go \
	   instr-table.tex priv-instr-table.tex $(OUTPUT_DIR)/ 2>/dev/null || true
	python3 sorter.py
# Clean generated files
clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all generate clean
