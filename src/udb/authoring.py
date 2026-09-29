# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Reusable, deterministic support for generated repository files."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .errors import AuthoringError


@dataclass(frozen=True)
class GeneratedFile:
    """One generated file, its owner, and the inputs it depends on."""

    path: PurePosixPath
    content: bytes
    owner: str
    dependencies: tuple[PurePosixPath, ...]
    mode: int = 0o444


class AuthoringPlan:
    """A validated set of generated files with exclusive output ownership."""

    def __init__(self, outputs: tuple[GeneratedFile, ...]) -> None:
        outputs = tuple(
            GeneratedFile(
                path=PurePosixPath(output.path),
                content=bytes(output.content),
                owner=output.owner,
                dependencies=tuple(PurePosixPath(path) for path in output.dependencies),
                mode=output.mode,
            )
            for output in outputs
        )
        owners: dict[PurePosixPath, str] = {}
        for output in outputs:
            _validate_relative_path(output.path, what="output")
            if not output.owner:
                raise AuthoringError(f"{output.path}: generated output has no owner")
            if not output.dependencies:
                raise AuthoringError(f"{output.path}: generated output has no dependencies")
            for dependency in output.dependencies:
                _validate_relative_path(dependency, what="dependency")
            if output.mode < 0 or output.mode > 0o777:
                raise AuthoringError(
                    f"{output.path}: invalid generated output mode {output.mode:#o}"
                )
            previous = owners.get(output.path)
            if previous is not None:
                raise AuthoringError(
                    f"{output.path}: output is owned by both {previous!r} and {output.owner!r}"
                )
            for parent in output.path.parents:
                if parent == PurePosixPath("."):
                    break
                if parent in owners:
                    raise AuthoringError(
                        f"{output.path}: output is nested below generated file {parent}"
                    )
            child = next(
                (path for path in owners if output.path in path.parents),
                None,
            )
            if child is not None:
                raise AuthoringError(
                    f"{output.path}: output is an ancestor of generated file {child}"
                )
            owners[output.path] = output.owner
        dependencies = {dependency for output in outputs for dependency in output.dependencies}
        collision = next((path for path in owners if path in dependencies), None)
        if collision is not None:
            raise AuthoringError(f"{collision}: generated output is also declared as a dependency")
        self._outputs = outputs

    @property
    def outputs(self) -> tuple[GeneratedFile, ...]:
        """Return outputs in deterministic generation order."""

        return self._outputs

    @property
    def owned_paths(self) -> tuple[PurePosixPath, ...]:
        """Return the paths exclusively owned by this plan."""

        return tuple(output.path for output in self._outputs)

    def apply(self, root: Path, *, check: bool = False) -> tuple[PurePosixPath, ...]:
        """Write changed outputs atomically, or report drift without writes."""

        resolved_root = root.resolve()
        if resolved_root.exists() and not resolved_root.is_dir():
            raise AuthoringError(f"authoring root is not a directory: {root}")
        targets = tuple(_target_path(resolved_root, output.path) for output in self._outputs)
        for index, target in enumerate(targets):
            for previous_index, previous in enumerate(targets[:index]):
                if target.resolve(strict=False) == previous.resolve(strict=False) or (
                    target.exists() and previous.exists() and target.samefile(previous)
                ):
                    raise AuthoringError(
                        f"{self._outputs[index].path}: output aliases generated output "
                        f"{self._outputs[previous_index].path}"
                    )

        dependency_paths = {
            dependency: _dependency_path(resolved_root, dependency)
            for output in self._outputs
            for dependency in output.dependencies
        }
        for output, target in zip(self._outputs, targets, strict=True):
            for dependency, dependency_path in dependency_paths.items():
                if target.resolve(strict=False) == dependency_path.resolve(strict=False) or (
                    target.exists()
                    and dependency_path.exists()
                    and target.samefile(dependency_path)
                ):
                    raise AuthoringError(
                        f"{output.path}: generated output aliases dependency {dependency}"
                    )

        drift: list[PurePosixPath] = []
        pending: list[tuple[Path, bytes, int]] = []
        for output, target in zip(self._outputs, targets, strict=True):
            try:
                actual = target.read_bytes() if target.is_file() else None
            except OSError as error:
                raise AuthoringError(
                    f"cannot inspect generated output {target}: {error}"
                ) from error
            if actual == output.content:
                if not check and target.is_file():
                    try:
                        target.chmod(output.mode)
                    except OSError as error:
                        raise AuthoringError(
                            f"cannot set generated output mode for {target}: {error}"
                        ) from error
                continue
            drift.append(output.path)
            pending.append((target, output.content, output.mode))

        if not check:
            for target, content, mode in pending:
                _atomic_write(target, content, mode)
        return tuple(drift)


def _validate_relative_path(path: PurePosixPath, *, what: str) -> None:
    text = path.as_posix()
    if (
        path.is_absolute()
        or not path.parts
        or path == PurePosixPath(".")
        or ".." in path.parts
        or "\\" in text
        or any(":" in part for part in path.parts)
    ):
        raise AuthoringError(f"unsafe {what} path: {path}")


def _target_path(root: Path, relative: PurePosixPath) -> Path:
    target = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise AuthoringError(f"generated output path contains a symlink: {relative}")
    resolved_target = target.resolve(strict=False)
    if not resolved_target.is_relative_to(root):
        raise AuthoringError(f"generated output escapes root through a symlink: {relative}")
    if target.exists() and not target.is_file():
        raise AuthoringError(f"generated output is not a regular file: {relative}")
    parent = target.parent
    while parent != root:
        if parent.exists() and not parent.is_dir():
            raise AuthoringError(f"generated output parent is not a directory: {relative}")
        parent = parent.parent
    return target


def _dependency_path(root: Path, relative: PurePosixPath) -> Path:
    dependency = root.joinpath(*relative.parts)
    resolved_dependency = dependency.resolve(strict=False)
    if not resolved_dependency.is_relative_to(root):
        raise AuthoringError(f"dependency escapes root through a symlink: {relative}")
    return dependency


def _atomic_write(path: Path, content: bytes, mode: int) -> None:
    descriptor: int | None = None
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        stream = os.fdopen(descriptor, "wb")
        descriptor = None
        with stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    except OSError as error:
        raise AuthoringError(f"cannot write generated output {path}: {error}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            temporary.unlink(missing_ok=True)
