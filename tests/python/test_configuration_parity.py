# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
import os
import subprocess
from pathlib import Path

import pytest

from udb.configuration import Configuration


@pytest.mark.skipif(os.environ.get("UDB_TEST_RUBY") != "1", reason="live Ruby oracle is opt-in")
def test_repository_configuration_parsing_matches_ruby():
    root = Path(__file__).parents[2]
    configs = [Configuration.from_file(path) for path in sorted((root / "cfgs").rglob("*.yaml"))]
    result = subprocess.run(
        [
            "bundle",
            "exec",
            "ruby",
            f"-I{root / 'tools/ruby-gems/udb/lib'}",
            str(Path(__file__).with_name("ruby_configuration_oracle.rb")),
            str(root),
        ],
        input=json.dumps([config.to_dict() for config in configs]),
        text=True,
        capture_output=True,
        check=True,
        cwd=root,
    )
    expected = [
        {
            "name": config.name,
            "mxlen": config.mxlen,
            "params": config.to_dict().get("params", {}),
            "extensions": [
                [item.name, item.presence.value, [str(req) for req in item.requirements]]
                for item in config.extensions
            ],
        }
        for config in configs
    ]
    assert json.loads(result.stdout) == expected
