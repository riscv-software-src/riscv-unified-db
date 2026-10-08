# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Fail-closed filesystem checks for authoritative evidence paths."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .canonical import sha256_bytes


class FilesystemPolicyError(ValueError):
    """Stable diagnostic emitted before an authoritative path is consumed."""


@dataclass(frozen=True)
class FileEvidence:
    path: str
    file_kind: str
    byte_length: int | None = None
    sha256: str | None = None
    hardlink_count: int | None = None


def require_relative_posix_path(value: str) -> PurePosixPath:
    """Reject absolute, traversal, empty, and platform-specific escape syntax."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise FilesystemPolicyError("PATH_ESCAPE_DETECTED")
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise FilesystemPolicyError("PATH_ESCAPE_DETECTED")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or any(part in {".", ".."} for part in candidate.parts):
        raise FilesystemPolicyError("PATH_ESCAPE_DETECTED")
    return candidate


def _reject_kind(mode: int) -> None:
    if stat.S_ISLNK(mode):
        raise FilesystemPolicyError("SYMLINK_REJECTED")
    if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
        raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")


def _lstat_components(root: Path, relative: PurePosixPath) -> tuple[Path, os.stat_result, int]:
    root_stat = root.lstat()
    if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
        raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
    accepted_device = root_stat.st_dev
    current = root
    for part in relative.parts:
        current = current / part
        details = current.lstat()
        _reject_kind(details.st_mode)
        if details.st_dev != accepted_device:
            raise FilesystemPolicyError("MOUNT_BOUNDARY_UNPROVEN")
    return current, details, accepted_device


def inspect_authoritative_path(root: Path, relative_path: str) -> FileEvidence:
    """Classify one contained regular file/directory without following links."""
    relative = require_relative_posix_path(relative_path)
    path, details, _ = _lstat_components(root, relative)
    if stat.S_ISDIR(details.st_mode):
        return FileEvidence(path=relative.as_posix(), file_kind="directory")
    # Opening only happens after every path component was lstat and accepted.
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_dev != details.st_dev or opened.st_ino != details.st_ino:
            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    content = b"".join(chunks)
    return FileEvidence(
        path=relative.as_posix(),
        file_kind="regular_file",
        byte_length=len(content),
        sha256=sha256_bytes(content),
        hardlink_count=opened.st_nlink,
    )


def reject_hardlink_dependency(declared_shared_inode: bool) -> None:
    """Reject layouts whose accepted meaning depends on a hardlink relationship."""
    if declared_shared_inode:
        raise FilesystemPolicyError("HARDLINK_DEPENDENCY_REJECTED")
