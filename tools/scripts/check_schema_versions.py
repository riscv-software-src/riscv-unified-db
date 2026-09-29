#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Check that generated schemas match already-published schema URLs.

Each resolved schema either has a new ``$id`` URL that is not published yet, or
it must be byte-for-byte identical to the content currently available at that
URL. This keeps published schema versions immutable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
GEN_SCHEMAS_DIR = ROOT / "gen" / "schemas"
TIMEOUT_SECONDS = 30


def schema_check_failed(schema_file: Path) -> bool:
    schema_data = json.loads(schema_file.read_text(encoding="utf-8"))
    published_id = schema_data.get("$id")
    if published_id is None:
        print(f"ERROR: {schema_file} has no '$id' field", file=sys.stderr)
        return True

    request = Request(published_id, headers={"User-Agent": "riscv-unified-db-schema-check"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            remote_content = response.read()
    except HTTPError as error:
        status = error.code
        remote_content = None
    except (TimeoutError, URLError) as error:
        print(f"ERROR: Could not reach {published_id}: {error}", file=sys.stderr)
        return True

    if status == 200:
        if remote_content != schema_file.read_bytes():
            print(
                f"Schema mismatch for {published_id}:\n"
                f"  Local:  {schema_file}\n"
                f"  Remote: {published_id}\n"
                "  The published schema differs from the local version.\n"
                "  To fix: bump the schema version ($id) to a new version number.\n"
                "  Note: new versions are published automatically when merged to main.",
                file=sys.stderr,
            )
            return True
        print(f"OK (matches published): {published_id}")
        return False

    if status == 404:
        print(f"OK (not yet published): {published_id}")
        return False

    print(f"ERROR: Unexpected HTTP {status} for {published_id}", file=sys.stderr)
    return True


def main() -> None:
    if not GEN_SCHEMAS_DIR.is_dir():
        raise FileNotFoundError("gen/schemas does not exist; run './do gen:schemas' first")

    schema_files = sorted(path for path in GEN_SCHEMAS_DIR.rglob("*.json") if path.is_file())
    failed = False
    for schema_file in schema_files:
        failed |= schema_check_failed(schema_file)

    if failed:
        raise RuntimeError("One or more schema version checks failed.")

    print("All schema version checks passed.")


if __name__ == "__main__":
    main()
