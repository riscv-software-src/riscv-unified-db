# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Capture real Ruby schema-doc entry points; never regenerate tracked docs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

RUBY_LOCK = (
    "/home/jcarlin/.copilot/session-state/e7cf3328-386d-40d9-b677-2d92e44c2ebb/files/ruby.lock"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(root: Path, destination: Path, schemas: Path, *, history: bool = False) -> None:
    destination = destination.resolve()
    if destination.exists():
        raise ValueError(f"capture output must not exist: {destination}")
    if not destination.is_relative_to(root):
        raise ValueError("capture destination must be inside the worktree")
    destination.mkdir(parents=True)
    if history:
        shutil.copytree(root / "doc/docs/schemas", destination / "all")
    gem = root / "tools/internal-gems/schema_doc_gen"
    command = [
        "flock",
        RUBY_LOCK,
        "mise",
        "exec",
        "--no-deps",
        "--",
        "ruby",
        f"-I{gem / 'lib'}",
    ]
    environment = {**os.environ, "TMPDIR": str(destination)}
    subprocess.run(
        [
            *command,
            str(gem / "bin/schema-docs-all"),
            f"--schema-dir={schemas}",
            f"--output-dir={destination / 'all'}",
            "--generate-index",
        ],
        cwd=root,
        env=environment,
        check=True,
    )
    subprocess.run(
        [
            *command,
            str(gem / "bin/schema-doc-gen"),
            str(schemas / "config_schema.json"),
            f"--ref-base={schemas}",
            f"--output={destination / 'single.mdx'}",
        ],
        cwd=root,
        env=environment,
        check=True,
    )
    config_version = json.loads((schemas / "config_schema.json").read_text())["$id"]
    assert (destination / "single.mdx").read_bytes() == (
        destination / "all" / config_version / "config_schema.mdx"
    ).read_bytes()
    historical = root / "doc/docs/schemas"
    artifacts = {
        path.relative_to(destination / "all").as_posix(): digest(path)
        for path in sorted((destination / "all").rglob("*"))
        if path.is_file()
    }
    drift = {}
    for relative, expected in artifacts.items():
        old = historical / relative
        if old.is_file() and digest(old) != expected:
            drift[relative] = {"tracked_sha256": digest(old), "ruby_sha256": expected}
    manifest = {
        "capture": "real schema-docs-all --generate-index and schema-doc-gen --output",
        "schemas": {path.name: digest(path) for path in sorted(schemas.glob("*.json"))},
        "ruby_sources": {
            path.relative_to(gem).as_posix(): digest(path)
            for path in sorted(gem.rglob("*"))
            if path.is_file() and (path.suffix == ".rb" or path.parent.name == "bin")
        },
        "artifacts": artifacts,
        "historical_drift": drift,
        "historical_missing": [
            relative for relative in artifacts if not (historical / relative).exists()
        ],
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--schemas", type=Path, default=Path("spec/schemas"))
    parser.add_argument(
        "--history", action="store_true", help="seed an isolated copy of tracked history"
    )
    args = parser.parse_args()
    capture(Path.cwd().resolve(), args.destination, args.schemas.resolve(), history=args.history)
