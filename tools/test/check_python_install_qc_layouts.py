# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Check actual installed QC authoring offline; run with the installed Python -I."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from importlib.resources import files
from pathlib import Path, PurePosixPath

from ruamel.yaml import YAML

from udb.layout_collections import get_layout_collection
from udb.layouts import generate_layouts, layout_plan


def _without_warning(content: bytes, source: str) -> bytes:
    first, rest = content.split(b"\n", 1)
    warning = f"\n# WARNING: This file is auto-generated from {source}\n\n".encode()
    assert rest.startswith(warning), source
    return first + b"\n" + rest.removeprefix(warning)


def _cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-m", "udb", "author", "layouts", *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def check_installed_qc_layouts(root: Path, oracle_path: Path) -> None:
    """Verify installed resources, exact native oracle, generic API and real CLI."""

    assert not root.exists(), "acceptance output must be a new, caller-owned directory"
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    assert len(oracle["outputs"]) == 56
    assert oracle["generator_sha256"] == (
        "1759ceaf80aa55473f7434ed2e2c44c959fca9d206330ea6b3a71c25517b556a"
    )
    resources = files("udb").joinpath("_data")
    assert resources.is_dir(), "this gate requires an actual noneditable installed wheel"
    collection = get_layout_collection("qc_iu")
    source_bytes = {
        source: resources.joinpath(*collection.resource_root.parts, *source.parts).read_bytes()
        for source in {job.source for job in collection.jobs}
    }
    root.mkdir(parents=True)
    outputs = root / "bundled-api"
    plan = layout_plan(outputs, collections=(collection,))
    assert len(generate_layouts(outputs, collections=(collection,))) == 56
    assert generate_layouts(outputs, collections=(collection,), check=True) == ()
    for output in plan.outputs:
        actual = (outputs / output.path).read_bytes()
        captured = oracle["outputs"][output.path.name]
        native = _without_warning(actual, output.owner.removeprefix("layout:"))
        assert native == captured["native"].encode() == captured["accepted"].encode()
        assert hashlib.sha256(native).hexdigest() == captured["native_sha256"]
        assert YAML(typ="safe").load(actual) == captured["accepted_semantics"]
        relative = output.path.relative_to(collection.output_root)
        bundled = resources.joinpath("custom_isa", "qc_iu", *relative.parts).read_bytes()
        assert actual == bundled, output.path
        assert (outputs / output.path).stat().st_mode & 0o777 == 0o444
    combined = root / "combined-api"
    assert (
        len(
            generate_layouts(
                combined,
                collections=(get_layout_collection("standard"), collection),
            )
        )
        == 588
    )
    assert (
        generate_layouts(
            combined,
            collections=(get_layout_collection("standard"), collection),
            check=True,
        )
        == ()
    )

    relocated = replace(
        collection,
        source_root=PurePosixPath("vendor/templates"),
        output_root=PurePosixPath("vendor/generated"),
        resource_root=None,
    )
    source_root = root / "explicit-input"
    for source, content in source_bytes.items():
        target = source_root / relocated.source_root / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    explicit_output = root / "explicit-api"
    assert (
        len(
            generate_layouts(
                explicit_output,
                collections=(relocated,),
                source_root=source_root,
            )
        )
        == 56
    )
    for job in relocated.jobs:
        actual = (explicit_output / relocated.output_root / job.target).read_bytes()
        assert (
            _without_warning(
                actual,
                (relocated.source_root / job.source).as_posix(),
            )
            == oracle["outputs"][job.target.name]["accepted"].encode()
        )
        assert (source_root / relocated.source_root / job.source).read_bytes() == source_bytes[
            job.source
        ]

    cli_root = root / "cli"
    generated = _cli("--root", str(cli_root), "--collection", "qc-iu")
    assert generated.returncode == 0, generated.stderr
    assert generated.stdout == generated.stderr == ""
    checked = _cli("--root", str(cli_root), "--collection", "qc-iu", "--check")
    assert checked.returncode == 0, checked.stderr
    assert checked.stdout == checked.stderr == ""
    assert len(tuple(cli_root.rglob("*.yaml"))) == 56
    drift_path = plan.owned_paths[-1]
    drift = cli_root / drift_path
    drift.chmod(0o644)
    drift.write_bytes(b"drift\n")
    checked = _cli("--root", str(cli_root), "--collection", "qc-iu", "--check")
    assert checked.returncode == 1
    assert checked.stdout == f"{drift_path}\n" and checked.stderr == ""
    assert drift.read_bytes() == b"drift\n"
    missing = _cli(
        "--root",
        str(root / "missing-out"),
        "--collection",
        "qc-iu",
        "--source-root",
        str(root / "missing-input"),
    )
    assert missing.returncode == 2 and "layout source does not exist" in missing.stderr
    assert not (root / "missing-out").exists()
    unknown = _cli("--root", str(root / "unknown-out"), "--collection", "missing")
    assert unknown.returncode == 2
    assert not (root / "unknown-out").exists()
    cli_inputs = root / "cli-explicit-input"
    for source, content in source_bytes.items():
        target = cli_inputs / collection.source_root / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    cli_explicit = root / "cli-explicit-output"
    explicit = _cli(
        "--root",
        str(cli_explicit),
        "--collection",
        "qc-iu",
        "--source-root",
        str(cli_inputs),
    )
    assert explicit.returncode == 0, explicit.stderr
    assert explicit.stdout == explicit.stderr == ""
    for output in plan.outputs:
        assert (cli_explicit / output.path).read_bytes() == output.content
    assert all(
        (cli_inputs / collection.source_root / source).read_bytes() == content
        for source, content in source_bytes.items()
    )
    assert all(
        resources.joinpath(*collection.resource_root.parts, *source.parts).read_bytes() == content
        for source, content in source_bytes.items()
    )
    print(
        "Installed QC layouts: 56 exact native CSR outputs, 588 combined, explicit-source API and CLI"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", required=True, type=Path, help="new explicit acceptance output tree"
    )
    parser.add_argument(
        "--oracle", required=True, type=Path, help="explicit frozen native oracle JSON"
    )
    arguments = parser.parse_args()
    check_installed_qc_layouts(arguments.root.resolve(), arguments.oracle)


if __name__ == "__main__":
    main()
