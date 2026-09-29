# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import stat
from pathlib import Path, PurePosixPath

import pytest

from udb import authoring
from udb.authoring import AuthoringPlan, GeneratedFile
from udb.errors import AuthoringError


def _output(path: str, *, owner: str = "test") -> GeneratedFile:
    return GeneratedFile(
        PurePosixPath(path),
        b"generated\n",
        owner,
        (PurePosixPath("templates/source.layout"),),
    )


def test_plan_writes_atomically_and_check_never_writes(tmp_path: Path) -> None:
    plan = AuthoringPlan((_output("generated/out.yaml"),))
    target = tmp_path / "generated/out.yaml"

    assert plan.apply(tmp_path, check=True) == (PurePosixPath("generated/out.yaml"),)
    assert not target.exists()
    assert plan.apply(tmp_path) == (PurePosixPath("generated/out.yaml"),)
    assert target.read_bytes() == b"generated\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o444

    target.chmod(0o644)
    assert plan.apply(tmp_path, check=True) == ()
    assert stat.S_IMODE(target.stat().st_mode) == 0o644
    assert plan.apply(tmp_path) == ()
    assert stat.S_IMODE(target.stat().st_mode) == 0o444

    target.chmod(0o644)
    target.write_bytes(b"drift\n")
    before = target.stat().st_mtime_ns
    assert plan.apply(tmp_path, check=True) == (PurePosixPath("generated/out.yaml"),)
    assert target.read_bytes() == b"drift\n"
    assert target.stat().st_mtime_ns == before


@pytest.mark.parametrize(
    "path",
    ["/absolute", "../escape", "nested/../../escape", r"windows\\escape", "C:/drive"],
)
def test_plan_rejects_nonportable_or_escaping_paths(path: str) -> None:
    with pytest.raises(AuthoringError, match="unsafe output path"):
        AuthoringPlan((_output(path),))


@pytest.mark.parametrize(
    "outputs,match",
    [
        ((_output("same"), _output("same")), "owned by both"),
        ((_output("parent"), _output("parent/child")), "nested below"),
        ((_output("parent/child"), _output("parent")), "ancestor"),
    ],
)
def test_plan_rejects_conflicting_output_ownership(
    outputs: tuple[GeneratedFile, ...], match: str
) -> None:
    with pytest.raises(AuthoringError, match=match):
        AuthoringPlan(outputs)


def test_plan_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    plan = AuthoringPlan((_output("linked/out.yaml"),))

    with pytest.raises(AuthoringError, match="symlink"):
        plan.apply(tmp_path, check=True)


def test_plan_rejects_a_symlink_even_when_it_stays_inside_root(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.write_bytes(b"generated\n")
    (tmp_path / "output").symlink_to(actual)

    with pytest.raises(AuthoringError, match="path contains a symlink"):
        AuthoringPlan((_output("output"),)).apply(tmp_path, check=True)


def test_plan_rejects_symlinked_parent_aliases_between_outputs(tmp_path: Path) -> None:
    (tmp_path / "actual").mkdir()
    (tmp_path / "alias").symlink_to(tmp_path / "actual", target_is_directory=True)
    plan = AuthoringPlan((_output("actual/out.yaml"), _output("alias/out.yaml")))

    with pytest.raises(AuthoringError, match="path contains a symlink"):
        plan.apply(tmp_path, check=True)


def test_plan_rejects_output_dependency_collisions(tmp_path: Path) -> None:
    with pytest.raises(AuthoringError, match="also declared as a dependency"):
        AuthoringPlan(
            (
                GeneratedFile(
                    PurePosixPath("source.layout"),
                    b"generated\n",
                    "test",
                    (PurePosixPath("source.layout"),),
                ),
            )
        )

    source = tmp_path / "inputs/source.layout"
    source.parent.mkdir()
    source.write_bytes(b"source\n")
    (tmp_path / "alias.layout").symlink_to(source)
    plan = AuthoringPlan(
        (
            GeneratedFile(
                PurePosixPath("inputs/source.layout"),
                b"generated\n",
                "test",
                (PurePosixPath("alias.layout"),),
            ),
        )
    )

    with pytest.raises(AuthoringError, match="output aliases dependency"):
        plan.apply(tmp_path, check=True)


def test_plan_copies_mutable_input_collections() -> None:
    dependencies = [PurePosixPath("templates/source.layout")]
    outputs = [GeneratedFile(PurePosixPath("out"), b"x", "test", dependencies)]  # type: ignore[arg-type]
    plan = AuthoringPlan(outputs)  # type: ignore[arg-type]
    dependencies.append(PurePosixPath("templates/other.layout"))
    outputs.clear()

    assert len(plan.outputs) == 1
    assert plan.outputs[0].dependencies == (PurePosixPath("templates/source.layout"),)


def test_atomic_write_wraps_filesystem_errors_and_preserves_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out"
    target.write_bytes(b"old\n")
    plan = AuthoringPlan((_output("out"),))

    def fail_replace(_source: Path, _target: Path) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(authoring.os, "replace", fail_replace)
    with pytest.raises(AuthoringError, match=r"cannot write generated output.*denied"):
        plan.apply(tmp_path)

    assert target.read_bytes() == b"old\n"
    assert not tuple(tmp_path.glob(".out.*"))
