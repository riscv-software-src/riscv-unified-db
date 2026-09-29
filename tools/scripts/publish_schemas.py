#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Publish resolved schema files as GitHub release assets."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN_SCHEMAS_DIR = ROOT / "gen" / "schemas"
SCHEMA_PAGES_URL = "https://riscv.github.io/riscv-unified-db/schemas"


def schema_versions(schemas_dir: Path) -> Iterator[tuple[str, str, Path]]:
    for schema_dir in sorted(path for path in schemas_dir.iterdir() if path.is_dir()):
        for version_dir in sorted(path for path in schema_dir.iterdir() if path.is_dir()):
            yield schema_dir.name, version_dir.name, version_dir


def release_exists(tag: str) -> bool:
    return (
        subprocess.run(
            ["gh", "release", "view", tag],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def create_release(schema_name: str, version: str, tag: str) -> None:
    published_url = f"{SCHEMA_PAGES_URL}/{schema_name}/{version}/{schema_name}"
    notes = (
        f"{schema_name} version {version} for riscv-unified-db.\n\nPublished at:\n{published_url}"
    )

    print(f"  Creating release {tag}...")
    subprocess.run(
        [
            "gh",
            "release",
            "create",
            tag,
            "--title",
            f"{schema_name} {version}",
            "--notes",
            notes,
            "--latest=false",
        ],
        check=True,
    )


def asset_names(tag: str) -> set[str]:
    result = subprocess.run(
        ["gh", "release", "view", tag, "--json", "assets"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {asset["name"] for asset in json.loads(result.stdout)["assets"]}


def asset_content(tag: str, asset_name: str) -> bytes | None:
    if asset_name not in asset_names(tag):
        return None

    result = subprocess.run(
        ["gh", "release", "download", tag, "--pattern", asset_name, "--output", "-"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode().strip()
        raise RuntimeError(f"Failed to download {asset_name} from {tag}:\n{stderr}")

    return result.stdout


def publish_asset(tag: str, schema_file: Path) -> None:
    asset_name = schema_file.name
    local_content = schema_file.read_bytes()
    remote_content = asset_content(tag, asset_name)

    if remote_content is None:
        print(f"  Uploading new asset: {asset_name}")
        subprocess.run(["gh", "release", "upload", tag, str(schema_file)], check=True)
        return

    if remote_content == local_content:
        print(f"  Unchanged: {asset_name}")
        return

    raise RuntimeError(
        f"Published schema asset differs for {tag}/{asset_name}.\n"
        "Published schema versions are immutable; bump the schema $id instead of "
        "overwriting this release."
    )


def main() -> None:
    if not GEN_SCHEMAS_DIR.is_dir():
        raise FileNotFoundError("gen/schemas does not exist; run './do gen:schemas' first")

    for schema_name, version, version_dir in schema_versions(GEN_SCHEMAS_DIR):
        tag = f"schemas/{schema_name}/{version}"
        print(f"Processing {schema_name} {version}")

        if not release_exists(tag):
            create_release(schema_name, version, tag)

        for schema_file in sorted(version_dir.glob("*.json")):
            publish_asset(tag, schema_file)

    print("Schema release publishing complete.")


if __name__ == "__main__":
    main()
