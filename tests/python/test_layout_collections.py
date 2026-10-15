# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path, PurePosixPath

import pytest

from udb.errors import LayoutError
from udb.layout_collections import (
    LayoutCollection,
    LayoutJob,
    get_layout_collection,
    layout_collection_names,
)
from udb.layouts import generate_layouts, iter_layout_jobs, layout_plan


def test_registered_collections_have_exact_complete_recipe_sets() -> None:
    assert layout_collection_names() == ("standard", "qc_iu")
    standard = get_layout_collection("standard")
    qc = get_layout_collection("qc_iu")
    assert len(standard.jobs) == 532
    assert len(qc.jobs) == 56
    assert len({job.source for job in qc.jobs}) == 5
    assert len({job.target for job in qc.jobs}) == 56
    assert len(iter_layout_jobs(Path("."), collections=(standard, qc))) == 588
    with pytest.raises(LayoutError, match="unknown layout collection"):
        get_layout_collection("missing")


def test_job_inputs_and_collection_are_immutable_snapshots() -> None:
    values = {"item": {"name": "initial"}, "numbers": [1, 2]}
    job = LayoutJob(PurePosixPath("test.layout"), PurePosixPath("test.yaml"), values)
    values["item"]["name"] = "changed"
    values["numbers"].append(3)
    assert job.values["item"]["name"] == "initial"
    assert job.values["numbers"] == (1, 2)
    with pytest.raises(TypeError):
        job.values["item"]["name"] = "changed"
    with pytest.raises(TypeError):
        job.values["number"] = 3
    jobs = [job]
    collection = LayoutCollection("test", PurePosixPath("."), PurePosixPath("out"), jobs)
    jobs.clear()
    assert collection.jobs == (job,)
    with pytest.raises(FrozenInstanceError):
        collection.name = "changed"


@pytest.mark.parametrize("path", ["../outside", "/outside", r"bad\path", "bad:path", "bad\npath"])
def test_collection_rejects_unsafe_source_output_and_resource_roots(path: str) -> None:
    job = LayoutJob(PurePosixPath("test.layout"), PurePosixPath("test.yaml"), {})
    for field in ("source_root", "output_root", "resource_root"):
        arguments = {
            "name": "test",
            "source_root": PurePosixPath("."),
            "output_root": PurePosixPath("out"),
            "resource_root": PurePosixPath("resources"),
            "jobs": (job,),
        }
        arguments[field] = PurePosixPath(path)
        with pytest.raises(LayoutError, match="unsafe layout path"):
            LayoutCollection(**arguments)
    with pytest.raises(LayoutError, match="unsafe layout path"):
        LayoutJob(PurePosixPath(path), PurePosixPath("test.yaml"), {})


def test_job_rejects_cyclic_and_unsupported_inputs() -> None:
    values = {}
    values["loop"] = values
    for bad, match in ((values, "cycle"), ({"bad": object()}, "unsupported"), ({1: 2}, "keys")):
        with pytest.raises(LayoutError, match=match):
            LayoutJob(PurePosixPath("test.layout"), PurePosixPath("test.yaml"), bad)


def test_custom_source_and_output_roots_are_independent(tmp_path: Path) -> None:
    source_root = tmp_path / "inputs"
    template = source_root / "vendor/templates/test.layout"
    template.parent.mkdir(parents=True)
    template.write_text("# copyright\nname: {{ name }}\n", encoding="utf-8")
    collection = LayoutCollection(
        name="vendor",
        source_root=PurePosixPath("vendor/templates"),
        output_root=PurePosixPath("custom/generated"),
        jobs=(
            LayoutJob(PurePosixPath("test.layout"), PurePosixPath("test.yaml"), {"name": "custom"}),
        ),
    )
    output_root = tmp_path / "outputs"
    before = template.read_bytes()
    plan = layout_plan(output_root, collections=(collection,), source_root=source_root)
    assert plan.owned_paths == (PurePosixPath("custom/generated/test.yaml"),)
    assert plan.outputs[0].owner == "layout:vendor/templates/test.layout"
    assert plan.outputs[0].content.endswith(b"name: custom\n")
    assert generate_layouts(output_root, collections=(collection,), source_root=source_root)
    assert (
        generate_layouts(
            output_root, collections=(collection,), source_root=source_root, check=True
        )
        == ()
    )
    assert template.read_bytes() == before
    assert not (output_root / "vendor").exists()
    assert (output_root / plan.owned_paths[0]).stat().st_mode & 0o777 == 0o444


def test_explicit_source_root_never_falls_back_to_resources(tmp_path: Path) -> None:
    with pytest.raises(LayoutError, match="repository layout source does not exist"):
        layout_plan(
            tmp_path / "outputs",
            collections=(get_layout_collection("standard"),),
            source_root=tmp_path / "missing-inputs",
        )
    assert not (tmp_path / "outputs").exists()


def test_unbundled_collection_requires_explicit_sources(tmp_path: Path) -> None:
    collection = LayoutCollection(
        "custom",
        PurePosixPath("templates"),
        PurePosixPath("generated"),
        (LayoutJob(PurePosixPath("test.layout"), PurePosixPath("test.yaml"), {}),),
    )
    with pytest.raises(LayoutError, match="no sources or bundled layout resources"):
        layout_plan(tmp_path, collections=(collection,))


def test_separate_source_root_cannot_be_overwritten_through_a_different_logical_path(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "vendor"
    template = source_root / "templates/test.layout"
    template.parent.mkdir(parents=True)
    template.write_text("# copyright\nname: custom\n", encoding="utf-8")
    collection = LayoutCollection(
        "custom",
        PurePosixPath("templates"),
        PurePosixPath("vendor/templates"),
        (LayoutJob(PurePosixPath("test.layout"), PurePosixPath("test.layout"), {}),),
    )
    with pytest.raises(LayoutError, match="aliases layout source"):
        generate_layouts(tmp_path, collections=(collection,), source_root=source_root)
    assert template.read_text() == "# copyright\nname: custom\n"


def test_custom_collection_can_use_arbitrary_package_resource_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from udb import layouts

    resources = tmp_path / "resources"
    template = resources / "vendor/data/test.layout"
    template.parent.mkdir(parents=True)
    template.write_text("# copyright\nname: {{ name }}\n", encoding="utf-8")
    monkeypatch.setattr(layouts, "package_data_root", lambda: resources)
    collection = LayoutCollection(
        "custom",
        PurePosixPath("input/templates"),
        PurePosixPath("output/csrs"),
        (LayoutJob(PurePosixPath("test.layout"), PurePosixPath("test.yaml"), {"name": "custom"}),),
        resource_root=PurePosixPath("vendor/data"),
    )
    output_root = tmp_path / "output"
    assert generate_layouts(output_root, collections=(collection,)) == (
        PurePosixPath("output/csrs/test.yaml"),
    )
    assert (output_root / "output/csrs/test.yaml").read_text().endswith("name: custom\n")


@pytest.mark.parametrize("collections", [(), ("standard",)])
def test_invalid_collection_selection_is_an_explicit_error(collections) -> None:
    with pytest.raises(LayoutError, match="LayoutCollection"):
        iter_layout_jobs(Path("."), collections=collections)
    with pytest.raises(LayoutError, match="LayoutCollection"):
        layout_plan(Path("."), collections=collections)


def test_separate_source_root_is_protected_from_output_hardlink_aliases(tmp_path: Path) -> None:
    source_root = tmp_path / "inputs"
    source = source_root / "templates/test.layout"
    source.parent.mkdir(parents=True)
    source.write_text("# copyright\nname: custom\n", encoding="utf-8")
    output_root = tmp_path / "outputs"
    target = output_root / "generated/test.yaml"
    target.parent.mkdir(parents=True)
    target.hardlink_to(source)
    collection = LayoutCollection(
        "custom",
        PurePosixPath("templates"),
        PurePosixPath("generated"),
        (LayoutJob(PurePosixPath("test.layout"), PurePosixPath("test.yaml"), {}),),
    )
    with pytest.raises(LayoutError, match="aliases layout source"):
        generate_layouts(output_root, collections=(collection,), source_root=source_root)
    assert source.read_text() == "# copyright\nname: custom\n"
    assert target.samefile(source)


def test_direct_job_cannot_escape_package_resources(tmp_path: Path) -> None:
    from udb.layouts import render_job

    job = LayoutJob(PurePosixPath("custom/test.layout"), PurePosixPath("out.yaml"), {})
    with pytest.raises(LayoutError, match="unsafe layout path"):
        render_job(job, tmp_path, repository_sources=False, resource=PurePosixPath("../escape"))
    with pytest.raises(LayoutError, match="no bundled layout resource mapping"):
        render_job(job, tmp_path, repository_sources=False)
