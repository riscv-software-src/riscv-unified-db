# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]


def test_profile_extensions_reads_resolved_database_without_mutating_it(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    (profile_dir / "Demo.yaml").write_text(
        """\
kind: profile
name: Demo
extensions:
  $child_of: profile_release/Demo.yaml#/extensions
  Zoptional:
    presence: optional
  A:
    version: "~> 2.1"
    presence: mandatory
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "python" / "profile_extensions.py"),
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "Demo:\n- A ~> 2.1 mandatory\n- Zoptional any optional\n"
    assert "$child_of" in (profile_dir / "Demo.yaml").read_text(encoding="utf-8")
