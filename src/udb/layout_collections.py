# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Immutable layout recipes with independent source, output and resource roots."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from .errors import LayoutError


def _relative_path(value: PurePosixPath, *, root: bool = False) -> PurePosixPath:
    path = PurePosixPath(value)
    text = path.as_posix()
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in text
        or ":" in text
        or any(ord(character) < 32 for character in text)
        or (not root and path == PurePosixPath("."))
    ):
        raise LayoutError(f"unsafe layout path: {path}")
    return path


def _freeze(value: object, active: frozenset[int] = frozenset()) -> object:
    if value is None or isinstance(value, str | bool | int):
        return value
    if id(value) in active:
        raise LayoutError("layout recipe inputs contain a cycle")
    if len(active) >= 64:
        raise LayoutError("layout recipe inputs exceed 64 nested containers")
    active = active | {id(value)}
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise LayoutError("layout recipe mapping keys must be strings")
        return MappingProxyType({key: _freeze(item, active) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item, active) for item in value)
    raise LayoutError(f"unsupported layout recipe input type: {type(value).__name__}")


@dataclass(frozen=True)
class LayoutJob:
    """One relative template/output pair and a captured, immutable input mapping."""

    source: PurePosixPath
    target: PurePosixPath
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", _relative_path(self.source))
        object.__setattr__(self, "target", _relative_path(self.target))
        if not isinstance(self.values, Mapping):
            raise LayoutError("layout recipe values must be a mapping")
        object.__setattr__(self, "values", _freeze(self.values))


@dataclass(frozen=True)
class LayoutCollection:
    """Recipes relative to explicit logical roots, with optional bundled resources."""

    name: str
    source_root: PurePosixPath
    output_root: PurePosixPath
    jobs: tuple[LayoutJob, ...]
    resource_root: PurePosixPath | None = None
    dependencies: tuple[PurePosixPath, ...] = (
        PurePosixPath("src/udb/layouts.py"),
        PurePosixPath("src/udb/layout_collections.py"),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", self.name):
            raise LayoutError(f"invalid layout collection name: {self.name!r}")
        object.__setattr__(self, "source_root", _relative_path(self.source_root, root=True))
        object.__setattr__(self, "output_root", _relative_path(self.output_root, root=True))
        if self.resource_root is not None:
            object.__setattr__(self, "resource_root", _relative_path(self.resource_root, root=True))
        jobs = tuple(self.jobs)
        if not jobs or any(not isinstance(job, LayoutJob) for job in jobs):
            raise LayoutError(f"{self.name}: layout collection requires LayoutJob recipes")
        object.__setattr__(self, "jobs", jobs)
        object.__setattr__(
            self, "dependencies", tuple(_relative_path(path) for path in self.dependencies)
        )


def layout_collection_names() -> tuple[str, ...]:
    """Return names accepted by the generic layout authoring collection selector."""

    return ("standard", "qc_iu")


def get_layout_collection(name: str) -> LayoutCollection:
    """Return a built-in recipe collection, without consulting a checkout."""

    if name == "standard":
        from .layouts import iter_layout_jobs

        prefix = PurePosixPath("spec/std/isa")
        jobs = tuple(
            LayoutJob(job.source.relative_to(prefix), job.target.relative_to(prefix), job.values)
            for job in iter_layout_jobs(Path("."))
        )
        return LayoutCollection(
            name=name,
            source_root=prefix,
            output_root=prefix,
            jobs=jobs,
            resource_root=PurePosixPath("layouts"),
            dependencies=(PurePosixPath("src/udb/layouts.py"),),
        )
    if name != "qc_iu":
        raise LayoutError(f"unknown layout collection: {name!r}")

    jobs: list[LayoutJob] = []
    for stem, count, base, fields in (
        ("mclicip", 8, 0x7F0, 32),
        ("mclicie", 8, 0x7F8, 32),
        ("mclicilvl", 32, 0xBC0, 8),
        ("mwpstartaddr", 4, 0x7D0, 1),
        ("mwpendaddr", 4, 0x7D4, 1),
    ):
        for number in range(count):
            index = f"{number:02}" if stem == "mclicilvl" else str(number)
            jobs.append(
                LayoutJob(
                    PurePosixPath(f"csr/Xqci/qc.{stem}N.layout"),
                    PurePosixPath(f"csr/Xqci/qc.{stem}{index}.yaml"),
                    {
                        "number": number,
                        "index": index,
                        "address": f"0x{base + number:x}",
                        "field_numbers": tuple(range(fields)),
                    },
                )
            )
    prefix = PurePosixPath("spec/custom/isa/qc_iu")
    return LayoutCollection(
        name=name,
        source_root=prefix,
        output_root=prefix,
        jobs=tuple(jobs),
        resource_root=PurePosixPath("custom_layouts/qc_iu"),
    )
