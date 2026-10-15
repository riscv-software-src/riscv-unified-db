# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

import pytest
from idl_passes_helpers import analyze_real_sample
from idl_passes_real_corrections import corrected_real_expectation

from udb import Configuration, Database

ROOT = Path(__file__).parents[2]
DATA_FILE = Path(__file__).parent / "data" / "idl" / "passes.json"
DOCUMENT = json.loads(DATA_FILE.read_text(encoding="utf-8"))
SAMPLES = DOCUMENT["real_samples"]


def _without_known_ruby_pass_crashes(value):
    def clean(passes):
        return {
            name: observation
            for name, observation in passes.items()
            if name not in {"return_values", "option_adoc"}
        }

    if isinstance(value, list):
        return [
            {
                **entry,
                "value": {
                    **entry["value"],
                    "passes": clean(entry["value"]["passes"]),
                },
            }
            for entry in value
        ]
    return clean(value)


@pytest.fixture(scope="module", params=DOCUMENT["configs"])
def configured_architecture(request):
    name = request.param
    configuration = Configuration.from_file(ROOT / "cfgs" / f"{name}.yaml")
    overlays = ()
    if configuration.overlay is not None:
        overlays = (ROOT / "spec" / "custom" / "isa" / configuration.overlay,)
    database = Database.from_path(
        ROOT / "spec" / "std" / "isa",
        schemas_path=ROOT / "spec" / "schemas",
    ).resolve(overlays=overlays)
    architecture = database.configure(configuration)
    return name, architecture


@pytest.mark.parametrize("sample", SAMPLES, ids=[sample["id"] for sample in SAMPLES])
def test_real_database_passes_match_ruby(configured_architecture, sample):
    config_name, architecture = configured_architecture
    expected = {result["id"]: result for result in DOCUMENT["real"][config_name]}[sample["id"]]
    if not expected["ok"]:
        pytest.skip(f"Ruby sample is unavailable: {expected['error']}")
    actual = analyze_real_sample(architecture, sample)
    # Ruby's return-value pass crashes on every non-empty real body, and option
    # rendering lacks array-element support. Corrected behavior for both is
    # specified by synthetic cases; retain real crashes without copying them.
    assert _without_known_ruby_pass_crashes(actual) == _without_known_ruby_pass_crashes(
        corrected_real_expectation(config_name, sample["id"], expected["value"])
    )
