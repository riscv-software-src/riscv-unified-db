#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Retained Xqci wrapper; explicitly supply this repository's input root."""

import sys
from pathlib import Path

from udb.extension_docs.compat import main

raise SystemExit(main(["--root", str(Path(__file__).resolve().parents[2]), "xqci", *sys.argv[1:]]))
