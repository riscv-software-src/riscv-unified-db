#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Generate the config editor HTML with an embedded database.

Python port of ``generate.rb``. Reads the resolved extension and parameter
YAML from ``gen/resolved_spec/_`` and embeds it, as JSON, into the
``gui.html.template`` front-end (which is otherwise plain HTML/JS).
"""

import json
import sys
from pathlib import Path

from ruamel.yaml import YAML

_yaml = YAML(typ="safe")

# Sentinel in gui.html.template where the embedded database is injected.
_DB_SENTINEL = "/*__DATABASE_JSON__*/{}"


def load_extensions(ext_dir: Path) -> dict:
    """Load extension definitions keyed by name."""
    extensions = {}
    if not ext_dir.exists():
        return extensions
    for file in sorted(ext_dir.glob("*.yaml")):
        data = _yaml.load(file) or {}
        name = data["name"]
        extensions[name] = {
            "name": name,
            "longName": data.get("long_name") or name,
            "versions": [v["version"] for v in (data.get("versions") or [])],
        }
    return extensions


def load_parameters(param_dir: Path) -> dict:
    """Load parameter definitions keyed by name."""
    parameters = {}
    if not param_dir.exists():
        return parameters
    for file in sorted(param_dir.glob("*.yaml")):
        data = _yaml.load(file) or {}
        name = data["name"]
        parameters[name] = {
            "name": name,
            "description": data.get("description", ""),
            "definedBy": data.get("definedBy") or data.get("defined_by"),
            "schema": data.get("schema") or {},
        }
    return parameters


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    root_dir = script_dir.parent.parent
    spec_dir = root_dir / "gen" / "resolved_spec" / "_"

    if not spec_dir.exists():
        print(f"Error: Resolved spec directory not found at {spec_dir}")
        print("Please run 'bin/generate' first to create the resolved spec")
        sys.exit(1)

    extensions = load_extensions(spec_dir / "ext")
    parameters = load_parameters(spec_dir / "param")
    database = {"extensions": extensions, "parameters": parameters}

    template_path = script_dir / "gui.html.template"
    template = template_path.read_text()
    if _DB_SENTINEL not in template:
        print(f"Error: database sentinel not found in {template_path}")
        sys.exit(1)

    # Single substitution; sorted globs above keep the output deterministic.
    output = template.replace(_DB_SENTINEL, json.dumps(database), 1)

    output_dir = root_dir / "gen" / "config-editor"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "gui.html"
    output_file.write_text(output)

    print(f"Generated config editor at: {output_file}")
    print(f"Extensions loaded: {len(extensions)}")
    print(f"Parameters loaded: {len(parameters)}")
    print(f"\nTo use: open {output_file}")


if __name__ == "__main__":
    main()
