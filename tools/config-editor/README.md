<!--
Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# RISC-V Configuration Editor

A standalone HTML tool for creating and editing RISC-V architecture configuration files.

The front-end (`gui.html.template`) is plain HTML/CSS/JavaScript. `generate.py`
embeds the resolved extension/parameter database into it and writes a
self-contained `gui.html`.

## Features

- **Fully Client-Side**: No server required - the generated HTML runs entirely in your browser
- **Extension Management**: Add/remove RISC-V extensions with version selection
- **Dynamic Parameters**: Parameters automatically appear/disappear based on selected extensions
- **Smart Input Types**: Dropdowns for enums, checkboxes for booleans, number inputs with validation
- **Import/Export**: Load existing YAML configs and export new ones
- **Real-time Validation**: Immediate feedback on configuration validity
- **Autocomplete**: Search and filter extensions as you type

## Generating the Tool

The editor embeds a database built from the resolved spec, so generate it first:

```bash
# 1. Create the resolved spec (if not already present)
./bin/generate

# 2. Generate the config editor HTML
python3 tools/config-editor/generate.py
```

This writes the self-contained editor to `gen/config-editor/gui.html`.

Requirements: Python 3.10+ and `ruamel.yaml` (already a UDB Python dependency).

## Opening the Tool

Open the generated file in any modern web browser:

```bash
open gen/config-editor/gui.html

# Or with a specific browser
firefox gen/config-editor/gui.html
chrome gen/config-editor/gui.html
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

The generated tool includes an embedded database with:
- All standard RISC-V extensions from the resolved spec
- Configuration parameters with schemas and dependencies
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
- **Partial configs**: Tool only supports fully configured type (not partially configured or unconfigured)
- **Advanced validation**: Some cross-parameter constraints may not be validated

## Technical Details

- **Generator**: `generate.py` (Python, uses `ruamel.yaml`)
- **Template**: `gui.html.template` - self-contained HTML with embedded CSS and JavaScript
- **Dependencies**: Uses js-yaml and Asciidoctor.js from CDN for YAML parsing and description rendering
- **Browser compatibility**: Works in all modern browsers (Chrome, Firefox, Safari, Edge)

## Future Enhancements

Potential improvements for future versions:
- Support for partially configured and unconfigured types
- Custom extension support
- More sophisticated array parameter editors
- Configuration templates/presets
- Diff view between configurations
- Offline mode (embed js-yaml and Asciidoctor libraries)

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
