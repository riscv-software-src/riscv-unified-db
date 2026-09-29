#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Download schema release assets for GitHub Pages.

The Pages and Schema Release workflows are both triggered by a successful CI/CD
run on main. Pages can therefore reach the schema download step before Schema
Release has created all releases for the same commit. To avoid publishing a
partial schema tree, this script waits for release tags corresponding to the
current generated schemas, then downloads every schema release asset.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GEN_SCHEMAS_DIR = ROOT / "gen" / "schemas"
DEFAULT_OUTPUT_DIR = ROOT / "_site" / "schemas"
DEFAULT_TIMEOUT_SECONDS = 600
RETRY_DELAY_SECONDS = 10
RELEASE_LIST_LIMIT = 1000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gen-schemas-dir",
        type=Path,
        default=DEFAULT_GEN_SCHEMAS_DIR,
        help="generated schemas directory used to determine current expected releases",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory where schema release assets are downloaded",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="maximum time to wait for current schema releases",
    )
    return parser.parse_args()


def generated_schema_tags(schemas_dir: Path) -> set[str]:
    if not schemas_dir.is_dir():
        raise FileNotFoundError(f"{schemas_dir} does not exist; run './do gen:schemas' first")

    return {
        f"schemas/{schema_dir.name}/{version_dir.name}"
        for schema_dir in schemas_dir.iterdir()
        if schema_dir.is_dir()
        for version_dir in schema_dir.iterdir()
        if version_dir.is_dir()
    }


def schema_release_tags() -> set[str]:
    result = subprocess.run(
        [
            "gh",
            "release",
            "list",
            "--limit",
            str(RELEASE_LIST_LIMIT),
            "--json",
            "tagName",
            "--jq",
            '.[] | .tagName | select(startswith("schemas/"))',
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return set(result.stdout.splitlines())


def wait_for_schema_releases(expected_tags: set[str], timeout_seconds: int) -> set[str]:
    deadline = time.monotonic() + timeout_seconds

    while True:
        tags = schema_release_tags()
        missing = expected_tags - tags
        if not missing:
            return tags

        if time.monotonic() >= deadline:
            missing_list = "\n".join(f"  {tag}" for tag in sorted(missing))
            raise TimeoutError(f"Timed out waiting for schema releases:\n{missing_list}")

        print(
            f"Waiting for {len(missing)} schema release(s) from schema-release workflow...",
            flush=True,
        )
        time.sleep(RETRY_DELAY_SECONDS)


def release_output_dir(output_dir: Path, tag: str) -> Path:
    parts = tag.split("/")
    if len(parts) != 3 or parts[0] != "schemas" or not all(parts):
        raise ValueError(f"Invalid schema release tag: {tag}")

    _schemas, schema_name, version = parts
    return output_dir / schema_name / version


def download_release(tag: str, output_dir: Path, timeout_seconds: int) -> None:
    destination = release_output_dir(output_dir, tag)
    destination.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds

    while True:
        result = subprocess.run(
            [
                "gh",
                "release",
                "download",
                tag,
                "--dir",
                str(destination),
                "--pattern",
                "*.json",
                "--clobber",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return

        if time.monotonic() >= deadline:
            raise RuntimeError(f"Failed to download schema release {tag}:\n{result.stderr.strip()}")

        print(f"Waiting for assets in schema release {tag}...", flush=True)
        time.sleep(RETRY_DELAY_SECONDS)


def main() -> None:
    args = parse_args()
    expected_tags = generated_schema_tags(args.gen_schemas_dir)
    if not expected_tags:
        raise RuntimeError(f"No generated schema versions found in {args.gen_schemas_dir}")

    tags = wait_for_schema_releases(expected_tags, args.timeout_seconds)
    for tag in sorted(tags):
        download_release(tag, args.output_dir, args.timeout_seconds)

    print(f"Downloaded {len(tags)} schema release(s) to {args.output_dir}")


if __name__ == "__main__":
    main()
