#!/usr/bin/env python3
# Copyright (c) Ventana Micro Systems
# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Python utilities for using UDB"""

from pathlib import Path
import yaml


def find_and_load_yaml(path, kinds=None):
    """Load the YAML files in a directory hierarchy into an array of dictionaries.

    Optionally, restrict to specific "kinds" of YAML files.
    """
    database = []

    p = Path(path)
    for file in p.rglob("*.yaml"):
        with open(file, encoding="utf-8") as f:
            y = yaml.safe_load(f)
            if "kind" in y:
                if len(kinds) == 0 or y["kind"] in kinds:
                    y["file"] = file
                    database.append(y)
    return database
