# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

from udb.layout_collections import get_layout_collection

ROOT = Path(__file__).parents[2]
PACKAGING_ROOT = ROOT


def test_qc_package_data_maps_exactly_five_layouts_and_56_owned_outputs() -> None:
    spec = importlib.util.spec_from_file_location(
        "qc_hatch_build", PACKAGING_ROOT / "hatch_build.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    mappings = module.package_data(ROOT)
    qc = get_layout_collection("qc_iu")
    expected_sources = {
        ROOT / qc.source_root / source for source in {job.source for job in qc.jobs}
    } | {ROOT / qc.output_root / job.target for job in qc.jobs}
    actual = {
        source: target
        for source, target in mappings.items()
        if source.is_relative_to(ROOT / qc.source_root)
    }
    assert set(actual) == expected_sources
    assert len(actual) == 61
    assert (
        sum(target.is_relative_to("udb/_data/custom_layouts/qc_iu") for target in actual.values())
        == 5
    )
    assert (
        sum(target.is_relative_to("udb/_data/custom_isa/qc_iu") for target in actual.values()) == 56
    )
    assert all(source.suffix != ".rb" for source in actual)
    config = tomllib.loads((PACKAGING_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    includes = config["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    matches = {
        source
        for pattern in includes
        for source in ROOT.glob(pattern.removeprefix("/"))
        if source in expected_sources
    }
    assert matches == expected_sources
