<!--
Copyright (c) Synopsys, Inc.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# RISC-V Unified Database MCP Server

Standalone MCP server for querying pre-generated YAML architecture data in `gen/`.

**Note:** Users must generate data first (e.g., `./do gen:resolved_arch`) before using this server.

## Features

The server provides organized access to:

- **Instructions**: Search and retrieve instruction definitions with advanced filtering
- **CSRs**: Query Control and Status Registers
- **Extensions**: Browse architecture extensions with optional instruction/CSR details
- **IDL Functions**: Search function documentation and find usages
- **Multi-Domain Search**: Search across instructions, CSRs, and extensions simultaneously

### Advanced Search Capabilities

- **Regex Support**: Use regular expressions for powerful pattern matching
- **Fuzzy Matching**: Typo-tolerant searches with adjustable similarity thresholds
- **Field-Specific Search**: Target specific fields (e.g., assembly syntax, encoding patterns)
- **XLEN Filtering**: Filter by 32-bit or 64-bit architecture support
- **Combined Queries**: Search multiple domains at once with unified results

## Prerequisites

- Python 3.10+
- Virtual environment with `mcp[cli]` and `pyyaml` installed
- Pre-generated data in `gen/` directory

## Setup

1. Create venv and install dependencies:

   ```bash
   python3 -m venv .venv_mcp
   . .venv_mcp/bin/activate
   pip install "mcp[cli]" pyyaml
   ```

2. Generate data (if not already done):

   ```bash
   ./do gen:resolved_arch
   ```

3. Run the server:

   ```bash
   # From repo root
   . .venv_mcp/bin/activate && python3 tools/mcp_gen_server/server.py
   ```

4. The server speaks MCP over stdio. Use an MCP-compatible client to connect.

## Available Tools

### Low-Level YAML Access

- **list_gen_yaml**: Lists all YAML files under gen/
- **read_gen_yaml**: Reads and parses a specific YAML file

### Instruction Tools

- **search_instructions**: Advanced search with regex, fuzzy matching, field-specific search, XLEN filtering
  - Args: `term`, `use_regex`, `fuzzy`, `field`, `xlen`, `keys`, `extensions`, `limit`
  - Returns include XLEN info and fuzzy scores

### CSR Tools

- **search_csrs**: Advanced search with same capabilities as instructions
  - Args: `term`, `use_regex`, `fuzzy`, `field`, `xlen`, `keys`, `extensions`, `limit`
  - Returns include XLEN info and fuzzy scores

### Extension Tools

- **search_extensions**: List all or get specific extension details
  - Args: `name`, `include_instructions`, `include_csrs`, `limit`

### Multi-Domain Search

- **search_all**: Search across instructions, CSRs, and extensions simultaneously
  - Args: `term`, `domains`, `use_regex`, `fuzzy`, `extensions`, `xlen`, `limit_per_domain`
  - Returns unified results from multiple domains

### Function/IDL Tools

- **search_functions**: Search IDL function documentation
- **read_function_doc**: Get complete function documentation
- **find_function_usages**: Find where functions are used

## Usage Examples

### Regex Search

```json
{ "term": "^add.*", "use_regex": true }
```

### Fuzzy Search (Typo-Tolerant)

```json
{ "term": "multply", "fuzzy": 0.7 }
```

### Field-Specific Search

```json
{ "term": "rd, rs1", "field": "assembly" }
```

### XLEN Filtering

```json
{ "term": "shift", "xlen": 64 }
```

### Multi-Domain Search

```json
{ "term": "atomic", "domains": ["instructions", "csrs"], "fuzzy": true }
```

## Architecture

1. **Fuzzy Matching**: Levenshtein distance for typo tolerance
2. **Utilities**: Path validation, YAML loading, XLEN detection
3. **Path Iterators**: Domain-specific file discovery
4. **Tool Handlers**: Organized by domain
5. **MCP Server Setup**: Tool registration and routing

## Tool Summary

| Tool                   | Purpose                          |
| ---------------------- | -------------------------------- |
| `list_gen_yaml`        | List all YAML files under gen/   |
| `read_gen_yaml`        | Read specific YAML file          |
| `search_instructions`  | Search instructions with filters |
| `search_csrs`          | Search CSRs with filters         |
| `search_extensions`    | List/query extensions from YAML  |
| `search_all`           | Multi-domain search              |
| `search_functions`     | Search IDL functions             |
| `read_function_doc`    | Get function documentation       |
| `find_function_usages` | Find function usage in code      |
