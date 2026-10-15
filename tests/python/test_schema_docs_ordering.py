# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
from pathlib import Path

from udb.schema_docs._ordering import property_order


def test_required_property_sort_matches_real_ruby_binary_key_oracle():
    oracle = json.loads(
        (Path(__file__).parent / "fixtures/schema_docs/ruby-property-order.json").read_text()
    )
    assert oracle["ruby_version"] == "3.4.10"
    assert len(oracle["cases"]) == 60
    for case in oracle["cases"]:
        properties = {f"property_{index}": index for index in range(len(case["keys"]))}
        required = [f"property_{index}" for index, key in enumerate(case["keys"]) if key == 0]
        assert [index for _, index in property_order(properties, required)] == case["order"]
