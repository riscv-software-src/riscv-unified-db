# Directories
YAML_DIR ?= ../../arch/inst
OPCODES_DIR := ../riscv-opcodes
OUTPUT_DIR := output

# Python scripts
YAML_TO_JSON := yaml_to_json.py
GENERATOR := generator.py

# Output files
INSTR_DICT := $(OUTPUT_DIR)/instr_dict.json

# Generated output files
C_OUT := $(OUTPUT_DIR)/encoding.out.h
CHISEL_OUT := $(OUTPUT_DIR)/inst.chisel
SPINALHDL_OUT := $(OUTPUT_DIR)/inst.spinalhdl
SVERILOG_OUT := $(OUTPUT_DIR)/inst.sverilog
RUST_OUT := $(OUTPUT_DIR)/inst.rs
GO_OUT := $(OUTPUT_DIR)/inst.go
LATEX_OUT := $(OUTPUT_DIR)/instr-table.tex
LATEX_PRIV_OUT := $(OUTPUT_DIR)/priv-instr-table.tex
PROCESSED_DICT := $(OUTPUT_DIR)/processed_instr_dict.json

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
	python3 $(GENERATOR) $(INSTR_DICT) -c -chisel -rust -go -latex
	mv encoding.out.h inst.chisel inst.spinalhdl inst.sverilog inst.rs inst.go \
	   instr-table.tex priv-instr-table.tex processed_instr_dict.json \
	   $(OUTPUT_DIR)/ 2>/dev/null || true

# Clean generated files
clean:
	rm -rf $(OUTPUT_DIR)

# Help target
help:
	@echo "Available targets:"
	@echo "  all (default) - Run complete pipeline: YAML -> JSON -> generate"
	@echo "  generate     - Generate all output formats from JSON"
	@echo "  clean        - Remove all generated files"
	@echo ""
	@echo "All output files will be placed in the '$(OUTPUT_DIR)' directory"
	@echo "Use YAML_DIR=/path/to/yaml to specify custom YAML input directory"

.PHONY: all generate clean help
