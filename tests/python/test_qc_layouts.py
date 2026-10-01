# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from udb import layouts
from udb.errors import AuthoringError, LayoutError
from udb.layout_collections import LayoutJob, get_layout_collection
from udb.layouts import generate_layouts, layout_plan, layout_sources, render_job
from udb.schema import SchemaStore

ROOT = Path(__file__).parents[2]
ORACLE = json.loads((ROOT / "tests/data/qc_layouts/oracle.json").read_text(encoding="utf-8"))
QC = get_layout_collection("qc_iu")


def original_bytes(content: bytes, source: str) -> bytes:
    first, rest = content.split(b"\n", 1)
    warning = f"\n# WARNING: This file is auto-generated from {source}\n\n".encode()
    assert rest.startswith(warning)
    return first + b"\n" + rest.removeprefix(warning)


def test_frozen_oracle_provenance_and_complete_output_set() -> None:
    assert ORACLE["revision"] == "d6b06ca35dacd03da77be638fc7b81f1b1297b64"
    assert (
        ORACLE["generator_sha256"]
        == hashlib.sha256(ORACLE["generator_source"].encode()).hexdigest()
    )
    assert ORACLE["generator_sha256"] == (
        "1759ceaf80aa55473f7434ed2e2c44c959fca9d206330ea6b3a71c25517b556a"
    )
    assert ORACLE["capture_command"][0] == "flock"
    assert ORACLE["capture_command"][2:7] == ["mise", "exec", "--no-deps", "--", "ruby"]
    assert ORACLE["capture_command"][-1].startswith("gen/handoff/qc-layouts-native/")
    assert ORACLE["ruby_version"].startswith("ruby 3.4.10")
    assert ORACLE["stdout"] == ORACLE["stderr"] == ""
    assert len(ORACLE["outputs"]) == 56
    assert sum(len(output["native"]) for output in ORACLE["outputs"].values()) == 96_366
    plan = layout_plan(ROOT, collections=(QC,))
    assert {path.name for path in plan.owned_paths} == set(ORACLE["outputs"])
    assert len(layout_sources(ROOT, collections=(QC,))) == 5
    for output in plan.outputs:
        assert output.mode == 0o444
        assert output.dependencies[0].as_posix() == output.owner.removeprefix("layout:")
        assert output.dependencies[1:] == QC.dependencies


@pytest.mark.parametrize("name", sorted(ORACLE["outputs"]))
def test_every_qc_output_matches_genuine_native_bytes_and_semantics(name: str) -> None:
    expected = ORACLE["outputs"][name]
    template_name = next(job.source for job in QC.jobs if job.target.name == name)
    job = next(job for job in QC.jobs if job.target.name == name)
    expanded = LayoutJob(QC.source_root / job.source, QC.output_root / job.target, job.values)
    generated = render_job(expanded, ROOT, repository_sources=True).encode()
    accepted = original_bytes(generated, (QC.source_root / template_name).as_posix())
    assert accepted == expected["accepted"].encode() == expected["native"].encode()
    assert hashlib.sha256(accepted).hexdigest() == expected["accepted_sha256"]
    assert expected["accepted_sha256"] == expected["native_sha256"]
    assert expected["classification"] == "identical"
    semantics = YAML(typ="safe").load(generated)
    assert semantics == expected["accepted_semantics"] == expected["native_semantics"]
    assert semantics["$schema"] == "csr_schema.json#"
    assert semantics["kind"] == "csr"
    assert semantics["length"] == 32
    assert semantics["priv_mode"] == "M"
    assert semantics["writable"] is True
    assert semantics["name"] == name.removesuffix(".yaml")
    assert semantics["definedBy"]["allOf"][0] == {"xlen": 32}
    extension = {"name": "Xqciint"}
    if name.startswith(("qc.mclicilvl", "qc.mwp")):
        extension["version"] = ">=0.4"
    assert semantics["definedBy"]["allOf"][1] == {"extension": extension}
    number = job.values["number"]
    if name.startswith("qc.mclicip"):
        base, count, description = 0x7F0, 32, "pending"
    elif name.startswith("qc.mclicie"):
        base, count, description = 0x7F8, 32, "enabled"
    elif name.startswith("qc.mclicilvl"):
        base, count, description = 0xBC0, 8, "level"
    else:
        base = 0x7D0 if name.startswith("qc.mwpstartaddr") else 0x7D4
        count = 1
        description = "Watchpoint start address" if base == 0x7D0 else "Watchpoint end address"
    assert semantics["address"] == base + number
    if count == 1:
        fields = {
            "ADDR": {"type": "RW", "reset_value": 0, "location": "31-0", "description": description}
        }
    else:
        fields = {
            f"IRQ{number * count + field}": {
                "type": "RW",
                "reset_value": 0,
                "location": f"{field * 4 + 3}-{field * 4}" if count == 8 else field,
                "description": f"IRQ{number * count + field} {description}",
            }
            for field in range(count)
        }
    assert semantics["fields"] == fields


def test_qc_plan_regenerates_only_owned_files_and_check_never_writes(tmp_path: Path) -> None:
    unowned = tmp_path / QC.output_root / "csr/Xqci/qc.unowned.yaml"
    unowned.parent.mkdir(parents=True)
    unowned.write_bytes(b"unowned\n")
    plan = layout_plan(tmp_path, collections=(QC,), source_root=ROOT)
    assert plan.apply(tmp_path, check=True) == plan.owned_paths
    assert list(tmp_path.rglob("*.yaml")) == [unowned]
    assert plan.apply(tmp_path) == plan.owned_paths
    assert plan.apply(tmp_path, check=True) == ()
    assert unowned.read_bytes() == b"unowned\n"
    for output in plan.outputs:
        assert (tmp_path / output.path).read_bytes() == output.content
        assert (tmp_path / output.path).stat().st_mode & 0o777 == 0o444
    drift = tmp_path / plan.owned_paths[-1]
    drift.chmod(0o644)
    drift.write_bytes(b"drift\n")
    assert plan.apply(tmp_path, check=True) == (plan.owned_paths[-1],)
    assert drift.read_bytes() == b"drift\n"
    assert plan.apply(tmp_path) == (plan.owned_paths[-1],)
    assert plan.apply(tmp_path, check=True) == ()


def test_qc_bundled_resources_generate_without_any_repository_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resources = tmp_path / "installed-data"
    for relative in {job.source for job in QC.jobs}:
        destination = resources / QC.resource_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / QC.source_root / relative, destination)
    monkeypatch.setattr(layouts, "package_data_root", lambda: resources)
    output_root = tmp_path / "outside-checkout"
    plan = layout_plan(output_root, collections=(QC,))
    assert len(generate_layouts(output_root, collections=(QC,))) == 56
    assert generate_layouts(output_root, collections=(QC,), check=True) == ()
    assert len(tuple(resources.rglob("*.layout"))) == 5
    for output in plan.outputs:
        assert (
            original_bytes(
                (output_root / output.path).read_bytes(), output.owner.removeprefix("layout:")
            )
            == ORACLE["outputs"][output.path.name]["accepted"].encode()
        )
    resource = resources / QC.resource_root / QC.jobs[0].source
    resource.write_bytes(b"\xff")
    with pytest.raises(LayoutError, match="not valid UTF-8"):
        layout_plan(output_root, collections=(QC,))
    resource.unlink()
    with pytest.raises(LayoutError, match="bundled layout source does not exist"):
        layout_plan(output_root, collections=(QC,))


def test_partial_qc_sources_do_not_mix_with_bundled_resources(tmp_path: Path) -> None:
    source = tmp_path / QC.source_root / QC.jobs[0].source
    source.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / QC.source_root / QC.jobs[0].source, source)
    with pytest.raises(LayoutError, match="repository layout source does not exist"):
        layout_plan(tmp_path, collections=(QC,))
    assert not tuple(tmp_path.rglob("*.yaml"))


def test_qc_and_standard_collections_preserve_all_standard_bytes() -> None:
    plan = layout_plan(ROOT, collections=(get_layout_collection("standard"), QC))
    assert len(plan.outputs) == 588
    assert len(set(plan.owned_paths)) == 588
    standard = [output for output in plan.outputs if output.path.is_relative_to("spec/std/isa")]
    assert len(standard) == 532
    assert all(output.content == (ROOT / output.path).read_bytes() for output in standard)


def test_qc_tracked_outputs_are_exactly_the_current_layout_plan() -> None:
    assert generate_layouts(ROOT, collections=(QC,), check=True) == ()
    for output in layout_plan(ROOT, collections=(QC,)).outputs:
        assert (ROOT / output.path).read_bytes() == output.content


def test_readonly_qc_outputs_are_excluded_from_eof_rewriting() -> None:
    config = YAML(typ="safe").load(ROOT / ".pre-commit-config.yaml")
    hook = next(
        hook
        for repo in config["repos"]
        for hook in repo["hooks"]
        if hook["id"] == "end-of-file-fixer"
    )
    for output in layout_plan(ROOT, collections=(QC,)).outputs:
        assert re.search(hook["exclude"], output.path.as_posix())
        assert output.content.endswith(b"\n")
    assert not re.search(hook["exclude"], "spec/custom/isa/qc_iu/csr/Xqci/qc.mcause.yaml")


def test_every_qc_output_validates_against_unchanged_current_schema() -> None:
    schemas = SchemaStore(ROOT / "spec/schemas")
    for output in layout_plan(ROOT, collections=(QC,)).outputs:
        schemas.validate(YAML(typ="safe").load(output.content), source=output.path)


def test_duplicate_collections_are_rejected_before_any_writes(tmp_path: Path) -> None:
    with pytest.raises(AuthoringError, match="owned by both"):
        generate_layouts(tmp_path, collections=(QC, QC), source_root=ROOT)
    assert not tuple(tmp_path.rglob("*.yaml"))


def test_qc_sources_cannot_escape_explicit_source_tree(tmp_path: Path) -> None:
    for relative in {job.source for job in QC.jobs}:
        destination = tmp_path / "source" / QC.source_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(ROOT / QC.source_root / relative)
    with pytest.raises(LayoutError, match="escapes source root"):
        layout_plan(tmp_path / "output", collections=(QC,), source_root=tmp_path / "source")
