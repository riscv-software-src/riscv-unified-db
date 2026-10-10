# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import contextlib
import importlib.util
import io
import shutil
import subprocess
from pathlib import Path

import pytest

from udb import cli, layouts
from udb.layout_collections import get_layout_collection
from udb.layouts import layout_plan

ROOT = Path(__file__).parents[2]
HELPER = ROOT / "tools/test/check_python_install_qc_layouts.py"


def test_installed_helper_logic_with_explicit_simulated_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unit-test helper wiring; actual isolated installed acceptance is a separate gate."""

    spec = importlib.util.spec_from_file_location("qc_install_helper", HELPER)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    package = tmp_path / "package"
    data = package / "_data"
    qc = get_layout_collection("qc_iu")
    for collection in (get_layout_collection("standard"), qc):
        for source in {job.source for job in collection.jobs}:
            target = data / collection.resource_root / source
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / collection.source_root / source, target)
    for output in layout_plan(ROOT, collections=(qc,)).outputs:
        relative = output.path.relative_to(qc.output_root)
        target = data / "custom_isa/qc_iu" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / output.path, target)
    monkeypatch.setattr(helper, "files", lambda _name: package)
    monkeypatch.setattr(layouts, "package_data_root", lambda: data)

    def simulated_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                result = cli.main(["generate-layouts", *arguments])
            except SystemExit as error:
                result = error.code
        return subprocess.CompletedProcess(arguments, result, stdout.getvalue(), stderr.getvalue())

    monkeypatch.setattr(helper, "_cli", simulated_cli)
    helper.check_installed_qc_layouts(
        tmp_path / "acceptance", ROOT / "tests/data/qc_layouts/oracle.json"
    )
