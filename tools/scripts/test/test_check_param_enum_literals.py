#!/usr/bin/env python3
# Copyright (c) 2026 titoatwork
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Unit tests for check_param_enum_literals.py"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

SCRIPT = Path(__file__).resolve().parents[1] / "check_param_enum_literals.py"

PARAM_YAML = dedent(
    """\
    $schema: param_schema.json#
    kind: parameter
    name: DEMO_ENUM
    description: demo
    long_name: demo
    schema:
      type: string
      enum:
        - always zero
        - custom
    definedBy:
      extension:
        name: H
    """
)


def load_module():
    spec = importlib.util.spec_from_file_location("check_param_enum_literals", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestCheckParamEnumLiterals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def _run(self, compare: str, name: str = "demo.yaml") -> int:
        """One parameter plus one file under spec/ holding the comparison."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            param_dir = root / "spec" / "std" / "isa" / "param"
            param_dir.mkdir(parents=True)
            (param_dir / "DEMO_ENUM.yaml").write_text(PARAM_YAML, encoding="utf-8")
            (root / "spec" / name).write_text(compare, encoding="utf-8")
            return self.mod.main(["--root", str(root)])

    def test_valid_literal_passes(self):
        self.assertEqual(self._run('if (DEMO_ENUM != "always zero") {'), 0)

    def test_invalid_literal_fails(self):
        self.assertEqual(self._run('if (DEMO_ENUM != "always_zero") {'), 1)

    def test_single_quoted_literal_is_checked(self):
        self.assertEqual(self._run("if (DEMO_ENUM != 'always_zero') {"), 1)

    def test_unknown_identifier_ignored(self):
        self.assertEqual(self._run('if (NOT_A_PARAM != "always_zero") {'), 0)

    def test_layout_templates_are_scanned(self):
        """Generated instruction YAML comes from .layout, so the source is checked."""
        self.assertEqual(self._run('if (DEMO_ENUM != "always_zero") {', "demo.layout"), 1)


if __name__ == "__main__":
    unittest.main()
