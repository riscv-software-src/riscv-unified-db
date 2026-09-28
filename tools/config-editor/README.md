<!--
Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# RISC-V Configuration Editor

A standalone HTML tool for creating and editing RISC-V architecture configuration files.

## Features

- **Fully Client-Side**: No server required - runs entirely in your browser
- **Extension Management**: Add/remove RISC-V extensions with version selection
- **Dynamic Parameters**: Parameters automatically appear/disappear based on selected extensions
- **Smart Input Types**: Dropdowns for enums, checkboxes for booleans, number inputs with validation
- **Import/Export**: Load existing YAML configs and export new ones
- **Real-time Validation**: Immediate feedback on configuration validity
- **Autocomplete**: Search and filter extensions as you type

## Usage

### Opening the Tool

Simply open `gui.html` in any modern web browser:

```bash
# From the repository root
open tools/config-editor/gui.html

# Or with a specific browser
firefox tools/config-editor/gui.html
chrome tools/config-editor/gui.html
```

### Creating a New Configuration

1. **Enter Metadata**:
   - Fill in the configuration name (e.g., "my-rv64-config")
   - Add a description

2. **Add Extensions**:
   - Type in the search box to find extensions (e.g., "I", "M", "Zicsr")
   - Click "Add" to add the extension
   - Select the desired version from the dropdown
   - Remove extensions with the "Remove" button

3. **Configure Parameters**:
   - Parameters appear automatically based on selected extensions
   - Fill in required parameters (e.g., MXLEN, endianness settings)
   - Parameters with dependencies only show when their conditions are met

4. **Export**:
   - Click "Export YAML" to download your configuration
   - The file will be saved as `<config-name>.yaml`

### Importing Existing Configurations

1. Click "Import YAML"
2. Select a YAML configuration file from your system
3. The tool will load all extensions and parameters
4. Edit as needed and export again

### Validation

The tool provides real-time validation:
- **Red errors**: Required fields missing or invalid values
- **Yellow warnings**: Non-critical issues (e.g., no extensions added)
- **Green success**: Configuration is valid

## Supported Configuration Types

Currently supports **fully configured** architectures only. The tool generates configs with:
- `type: "fully configured"`
- `implemented_extensions`: List of [name, version] pairs
- `params`: Key-value parameter map

## Embedded Database

The tool includes an embedded database with:
- **40+ standard RISC-V extensions** (I, M, A, F, D, C, V, H, S, U, Zicsr, Zifencei, etc.)
- **60+ configuration parameters** with schemas and dependencies
- **Dynamic parameter visibility** based on `definedBy` conditions

## Parameter Dependencies

Parameters automatically show/hide based on:
- **Extension dependencies**: Parameter appears when specific extension is added
- **Parameter dependencies**: Parameter appears when another parameter has a specific value

Examples:
- `ARCH_ID_VALUE` only appears when `MARCHID_IMPLEMENTED` is `true`
- `TRAP_ON_ECALL_FROM_S` only appears when S-mode extension is added
- `VLEN` only appears when V (Vector) extension is added

## Limitations

- **Array parameters**: Some complex array parameters (like `COUNTINHIBIT_EN`) show a note to edit in YAML
- **Custom extensions**: Only standard extensions are included in the embedded database
- **Partial configs**: Tool only supports fully configured type (not partially configured or unconfigured)
- **Advanced validation**: Some cross-parameter constraints may not be validated

## Technical Details

- **Single file**: Entirely self-contained HTML with embedded CSS and JavaScript
- **Dependencies**: Uses js-yaml library from CDN for YAML parsing/generation
- **Browser compatibility**: Works in all modern browsers (Chrome, Firefox, Safari, Edge)
- **No build step**: No compilation or bundling required

## Example Workflow

```bash
# 1. Open the tool
open tools/config-editor/gui.html

# 2. Create a simple RV32I configuration:
#    - Name: "simple-rv32"
#    - Add extensions: I (2.1.0), Sm (1.12.0), Zicsr (2.0.0)
#    - Set MXLEN: 32
#    - Set M_MODE_ENDIANNESS: little
#    - Set TRAP_ON_EBREAK: true

# 3. Export to YAML
#    - Click "Export YAML"
#    - File saved as "simple-rv32.yaml"

# 4. Use the configuration
cp ~/Downloads/simple-rv32.yaml cfgs/
```

## Future Enhancements

Potential improvements for future versions:
- Support for partially configured and unconfigured types
- Custom extension support
- More sophisticated array parameter editors
- Configuration templates/presets
- Diff view between configurations
- Export to JSON format
- Offline mode (embed js-yaml library)

## Troubleshooting

**Extensions not showing in autocomplete**:
- Make sure you're typing the exact extension name (case-sensitive)
- Try typing just the first letter (e.g., "Z" for Zicsr)

**Parameters not appearing**:
- Check that the required extension is added
- For dependent parameters, ensure the parent parameter is set correctly

**Export not working**:
- Ensure your browser allows downloads
- Check that name and description fields are filled in

**Import fails**:
- Verify the YAML file is valid
- Check that it follows the config schema format
- Ensure extension names match those in the embedded database

## Support

For issues or questions:
- Check existing configuration examples in `cfgs/` directory
- Review the config schema in `spec/schemas/config_schema.json`
- Consult parameter definitions in `spec/std/isa/param/`
