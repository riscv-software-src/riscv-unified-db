# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Capture unmodified native Psych output over scalar and collection examples."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from capture_schema_docs_oracle import RUBY_LOCK
from schema_docs_psych_cases import (
    block_scalar_cases,
    boundary_cases,
    cases,
    edge_cases,
    scanner_cases,
)


def capture(
    destination: Path,
    *,
    extended: bool = False,
    boundaries: bool = False,
    scanner: bool = False,
    block_chains: bool = False,
) -> None:
    root = Path.cwd().resolve()
    if destination.exists() or not destination.resolve().is_relative_to(root):
        raise ValueError("capture requires a new path inside the worktree")
    values = (
        block_scalar_cases()
        if block_chains
        else scanner_cases()
        if scanner
        else boundary_cases()
        if boundaries
        else edge_cases()
        if extended
        else cases()
    )
    payload = json.dumps(values, ensure_ascii=False, allow_nan=False)
    ruby = subprocess.run(
        [
            "flock",
            RUBY_LOCK,
            "mise",
            "exec",
            "--no-deps",
            "--",
            "ruby",
            "-rjson",
            "-ryaml",
            "-e",
            (
                "values=JSON.parse(STDIN.read); "
                "puts JSON.generate({ruby_version: RUBY_VERSION, psych_version: Psych::VERSION, "
                "libyaml_version: Psych.libyaml_version, "
                "yaml: values.map { |v| YAML.dump(v).sub(/^---\\n/, '') }, "
                "scalar_text: values.map { |v| v.is_a?(Hash) && v.keys == ['value'] ? v['value'].to_s : nil }})"
            ),
        ],
        input=payload,
        text=True,
        capture_output=True,
        check=True,
        cwd=root,
    )
    result = {
        "input_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "inputs": values,
        **json.loads(ruby.stdout),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--extended", action="store_true")
    selection.add_argument("--boundaries", action="store_true")
    selection.add_argument("--scanner", action="store_true")
    selection.add_argument("--block-chains", action="store_true")
    args = parser.parse_args()
    capture(
        args.destination,
        extended=args.extended,
        boundaries=args.boundaries,
        scanner=args.scanner,
        block_chains=args.block_chains,
    )
