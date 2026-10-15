# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Locate force-included package data in wheels and editable installs."""

from __future__ import annotations

from importlib import metadata, resources
from typing import Any


def package_data_root() -> Any:
    """Return the installed ``udb/_data`` resource root."""

    direct = resources.files("udb").joinpath("_data")
    if direct.is_dir():
        return direct
    return metadata.distribution("udb").locate_file("udb/_data")
