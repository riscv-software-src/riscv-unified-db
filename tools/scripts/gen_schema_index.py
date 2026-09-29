#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Generate or update a JSON index of all available schema versions.

Each schema has its own independent version history. Existing index entries are
preserved so old versions stored only in release assets are not dropped.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

type SchemaIndex = dict[str, list[str]]


def parse_args() -> tuple[Path, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schemas_dir", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    return args.schemas_dir, args.output_json


def load_schemas(index_path: Path) -> SchemaIndex:
    if not index_path.is_file():
        return {}

    data: dict[str, SchemaIndex] = json.loads(index_path.read_text(encoding="utf-8"))
    return data["schemas"]


def find_schemas(schemas_dir: Path) -> SchemaIndex:
    if not schemas_dir.is_dir():
        return {}

    schemas: SchemaIndex = {}
    for schema_entry in sorted(schemas_dir.iterdir()):
        if not schema_entry.is_dir():
            continue

        versions = sorted(
            version_dir.name for version_dir in schema_entry.iterdir() if version_dir.is_dir()
        )
        if versions:
            schemas[schema_entry.name] = versions

    return schemas


def merge_schemas(existing: SchemaIndex, discovered: SchemaIndex) -> SchemaIndex:
    merged = existing.copy()
    for schema_name, versions in discovered.items():
        merged[schema_name] = sorted({*merged.get(schema_name, []), *versions})
    return merged


def main() -> None:
    schemas_dir, output_json = parse_args()
    schemas = merge_schemas(load_schemas(output_json), find_schemas(schemas_dir))

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps({"schemas": schemas}, indent=2) + "\n", encoding="utf-8")
    print(f"Schema index written to {output_json}")


if __name__ == "__main__":
    main()
