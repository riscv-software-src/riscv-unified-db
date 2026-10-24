# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
from pathlib import Path

import pytest

from udb.cli import main


def test_cli_can_resolve_and_overlay_without_changing_source(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source"
    (source / "ext").mkdir(parents=True)
    (source / "ext" / "Xbase.yaml").write_text(
        "kind: extension\nname: Xbase\nlong_name: Base\n", encoding="utf-8"
    )
    child = source / "ext" / "Xchild.yaml"
    original = "kind: extension\nname: Xchild\n$inherits: ext/Xbase.yaml#\n"
    child.write_text(original, encoding="utf-8")
    overlay = tmp_path / "overlay"
    (overlay / "ext").mkdir(parents=True)
    (overlay / "ext" / "Xbase.yaml").write_text("long_name: Patched\n", encoding="utf-8")

    assert (
        main(
            [
                "--path",
                str(source),
                "--resolved",
                "--overlay",
                str(overlay),
                "show",
                "extension",
                "Xchild",
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["long_name"] == "Patched"
    assert "$inherits" not in output
    assert child.read_text(encoding="utf-8") == original


def test_overlay_without_resolution_is_an_error(tmp_path: Path, capsys) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--overlay", str(tmp_path), "list", "extension"])
    assert error.value.code == 2
    assert "--overlay requires --resolved" in capsys.readouterr().err
