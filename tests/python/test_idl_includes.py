# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from idl_semantics_helpers import run_semantic_case


def test_include_statement_is_semantically_accepted():
    result = run_semantic_case({"root": "isa", "text": '%version: 1.0\ninclude "other.idl"\n'})
    assert result["ok"] is True
    assert 'include "other.idl"' in result["to_idl"]
