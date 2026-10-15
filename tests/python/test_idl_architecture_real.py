# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Check every available body and explicitly account for absent semantics."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from udb import Configuration, Database, QueryPresence
from udb.idl_architecture import ArchitectureCompiler
from udb.idl_environment import possible_xlens

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("name", ["_", "rv32", "rv64", "qc_iu"])
def test_actual_architecture_bodies_and_unavailable_coverage(name, tmp_path):
    configuration = Configuration.from_file(ROOT / "cfgs" / f"{name}.yaml")
    overlays = (
        () if configuration.overlay is None else (ROOT / "spec/custom/isa" / configuration.overlay,)
    )
    database = Database.from_path(
        ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas"
    ).resolve(overlays=overlays)
    architecture = database.configure(configuration)
    result = ArchitectureCompiler(architecture).type_check()
    source_epoch = hashlib.sha256(
        json.dumps(
            {
                "configuration": configuration.source_text,
                "documents": {str(record.path): record.to_dict() for record in database.objects()},
                "idl_sources": {
                    f"{layer}:{path}": source.text
                    for (layer, path), source in database.idl_source_layers.items()
                },
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    (tmp_path / f"{name}-idl-body.json").write_text(
        json.dumps(
            {
                "configuration": name,
                "source_epoch": source_epoch,
                "checked": result.checked,
                "unavailable": [asdict(item) for item in result.unavailable],
                "diagnostics": [
                    {
                        "context": item.context,
                        "exception": type(item.error).__name__,
                        "message": str(item.error),
                    }
                    for item in result.diagnostics
                ],
                "ok": result.ok,
                "complete": result.complete,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert result.ok, [(item.context, str(item.error)) for item in result.diagnostics]
    expected_unavailable = {
        f"instruction {instruction.name}/RV{xlen}"
        for instruction in database.instructions
        if "operation()" not in instruction.data
        and architecture.object_presence(instruction) is not QueryPresence.ABSENT
        for xlen in possible_xlens(architecture)
        if instruction.data.get("base") in (None, xlen)
    }
    assert {item.context for item in result.unavailable} == expected_unavailable
    assert len(result.unavailable) == len(expected_unavailable)
    assert not expected_unavailable.intersection(result.checked)
    assert result.complete is (not expected_unavailable)
    assert any(context.startswith("instruction ") for context in result.checked)
    assert any(context.startswith("function ") for context in result.checked)
    for item in result.unavailable:
        assert str(item.source)
        assert "operation()" in item.reason
