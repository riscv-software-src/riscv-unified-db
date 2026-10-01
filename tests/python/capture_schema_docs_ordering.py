# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Capture the real Ruby numeric-key sort tie-ordering used by schema tables."""

from __future__ import annotations

import argparse
import json
import random
import subprocess
from pathlib import Path

from capture_schema_docs_oracle import RUBY_LOCK


def capture(destination: Path) -> None:
    root = Path.cwd().resolve()
    if not destination.resolve().is_relative_to(root) or destination.exists():
        raise ValueError("ordering capture requires a new path inside the worktree")
    rng = random.Random(42)
    cases = []
    for width in (0, 1, 2, 15, 16, 17, 20, 32, 64, 128):
        cases.extend(
            [
                [0] * width,
                [1] * width,
                [0] * (width // 2) + [1] * (width - width // 2),
                [1] * (width // 2) + [0] * (width - width // 2),
                [index % 2 for index in range(width)],
                [rng.randrange(2) for _ in range(width)],
            ]
        )
    result = subprocess.run(
        [
            "flock",
            RUBY_LOCK,
            "mise",
            "exec",
            "--no-deps",
            "--",
            "ruby",
            "-rjson",
            "-e",
            (
                "cases=JSON.parse(STDIN.read); "
                "puts JSON.pretty_generate({ruby_version: RUBY_VERSION, cases: cases.map { |keys| "
                "{keys: keys, order: (0...keys.size).sort_by { |i| keys[i] }} }})"
            ),
        ],
        input=json.dumps(cases),
        text=True,
        capture_output=True,
        cwd=root,
        check=True,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result.stdout, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    capture(parser.parse_args().destination)
