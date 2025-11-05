#!/usr/bin/env python3
# Copyright (c) Ventana Micro Systems
# SPDX-License-Identifier: BSD-3-Clause-Clear

import yaml
from pathlib import Path


def store_yaml(path, kinds=None):
    if kinds is None:
        kinds = []

    database = []
    with open(path) as f:
        y = yaml.safe_load(f)
        if "kind" in y:
            if len(kinds) == 0 or y["kind"] in kinds:
                y["file"] = path
                database.append(y)
    return database


database = []


def find_and_load_yaml(path, kinds=[]):
    global database
    p = Path(path)
    if p.is_dir():
        for dirent in p.iterdir():
            find_and_load_yaml(dirent, kinds)
    else:
        if str(path).endswith(".yaml"):
            database += store_yaml(path, kinds)
    return database
