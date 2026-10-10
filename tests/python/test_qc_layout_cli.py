# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from udb import cli
from udb.layout_collections import get_layout_collection
from udb.layouts import layout_plan

ROOT = Path(__file__).parents[2]


def test_cli_qc_generation_reads_independent_explicit_source_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "output"
    source_plan = layout_plan(ROOT, collections=(get_layout_collection("qc_iu"),))
    original_sources = {
        item.dependencies[0]: hashlib.sha256((ROOT / item.dependencies[0]).read_bytes()).hexdigest()
        for item in source_plan.outputs
    }
    arguments = [
        "generate-layouts",
        "--root",
        str(output),
        "--collection",
        "qc_iu",
        "--source-root",
        str(ROOT),
    ]
    assert cli.main(arguments) == 0
    assert len(tuple(output.rglob("*.yaml"))) == 56
    assert cli.main([*arguments, "--check"]) == 0
    assert capsys.readouterr().out == ""
    for item in source_plan.outputs:
        assert (output / item.path).read_bytes() == item.content
    assert all(
        hashlib.sha256((ROOT / source).read_bytes()).hexdigest() == digest
        for source, digest in original_sources.items()
    )


def test_cli_both_collections_check_reports_exact_drift_without_writes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        cli.main(
            [
                "generate-layouts",
                "--root",
                str(tmp_path),
                "--source-root",
                str(ROOT),
                "--collection",
                "standard",
                "--collection",
                "qc_iu",
                "--check",
            ]
        )
        == 1
    )
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(set(lines)) == 588
    assert sum(line.startswith("spec/custom/isa/qc_iu/") for line in lines) == 56
    assert not tuple(tmp_path.rglob("*.yaml"))


def test_cli_unknown_collection_fails_explicitly_before_writes(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["generate-layouts", "--root", str(tmp_path), "--collection", "unknown"])
    assert error.value.code == 2
    assert not tuple(tmp_path.rglob("*.yaml"))


def test_cli_missing_explicit_source_never_falls_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(
            [
                "generate-layouts",
                "--root",
                str(tmp_path / "output"),
                "--source-root",
                str(tmp_path / "missing"),
                "--collection",
                "qc_iu",
            ]
        )
    assert error.value.code == 2
    assert "layout source does not exist" in capsys.readouterr().err
    assert not (tmp_path / "output").exists()
