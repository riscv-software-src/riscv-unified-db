# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Fail-closed descriptor-rooted custody for authoritative evidence paths."""

from __future__ import annotations

import errno
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


def _require_flag(name: str) -> int:
    value = getattr(os, name, 0)
    if not isinstance(value, int) or value == 0:
        raise FilesystemPolicyError("NOFOLLOW_UNAVAILABLE")
    return value


def _directory_flags() -> int:
    return os.O_RDONLY | _require_flag("O_DIRECTORY") | _require_flag("O_NOFOLLOW") | _require_flag("O_CLOEXEC")


def _file_flags() -> int:
    return os.O_RDONLY | _require_flag("O_NOFOLLOW") | _require_flag("O_NONBLOCK") | _require_flag("O_CLOEXEC")


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _raise_open_boundary_error(error: OSError) -> None:
    """Keep namespace substitution distinct from unavailable descriptor support."""
    if error.errno == errno.ELOOP:
        raise FilesystemPolicyError("SYMLINK_REJECTED") from error
    if error.errno == errno.ENOENT:
        raise FilesystemPolicyError("AUTHORITATIVE_FILE_MISSING") from error
    raise FilesystemPolicyError("DIRECTORY_DESCRIPTOR_UNAVAILABLE") from error


def _directory_components(root: Path) -> tuple[int, tuple[str, ...]]:
    """Open the lexical authority root without resolving it through a pathname."""
    text = os.fspath(root)
    if not text or any(part == ".." for part in Path(text).parts):
        raise FilesystemPolicyError("PATH_ESCAPE_DETECTED")
    try:
        # Opening the authority root once is itself the root binding.  Descendant
        # components are subsequently opened only relative to this held descriptor.
        return os.open(text, _directory_flags()), ()
    except (NotImplementedError, TypeError) as error:
        raise FilesystemPolicyError("DIRECTORY_DESCRIPTOR_UNAVAILABLE") from error
    except OSError as error:
        _raise_open_boundary_error(error)


def _open_directory(parent: int, name: str, accepted_device: int | None) -> int:
    try:
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if stat.S_ISLNK(before.st_mode):
            raise FilesystemPolicyError("SYMLINK_REJECTED")
        if not stat.S_ISDIR(before.st_mode):
            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
        child = os.open(name, _directory_flags(), dir_fd=parent)
    except FilesystemPolicyError:
        raise
    except (NotImplementedError, TypeError) as error:
        raise FilesystemPolicyError("DIRECTORY_DESCRIPTOR_UNAVAILABLE") from error
    except OSError as error:
        _raise_open_boundary_error(error)
    opened = os.fstat(child)
    if not _same_identity(before, opened) or stat.S_ISLNK(opened.st_mode) or not stat.S_ISDIR(opened.st_mode):
        os.close(child)
        raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
    if accepted_device is not None and opened.st_dev != accepted_device:
        os.close(child)
        raise FilesystemPolicyError("MOUNT_BOUNDARY_UNPROVEN")
    return child


def _held_parent(root: Path, relative: PurePosixPath, *, include_leaf_directory: bool = False) -> tuple[list[int], int, str, int]:
    """Return every held directory through the parent of an authoritative leaf."""
    descriptors: list[int] = []
    try:
        current, root_parts = _directory_components(root)
        descriptors.append(current)
        for part in root_parts:
            current = _open_directory(current, part, None)
            descriptors.append(current)
        authority = os.fstat(current)
        if not stat.S_ISDIR(authority.st_mode):
            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
        names = relative.parts if include_leaf_directory else relative.parts[:-1]
        for part in names:
            current = _open_directory(current, part, authority.st_dev)
            descriptors.append(current)
        leaf = relative.parts[-1]
        return descriptors, current, leaf, authority.st_dev
    except Exception:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise


def _signature(details: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        stat.S_IFMT(details.st_mode), details.st_dev, details.st_ino, details.st_nlink,
        details.st_size, details.st_mtime_ns, details.st_ctime_ns,
    )


def _read_authoritative_regular_file(root: Path, relative: PurePosixPath) -> tuple[FileEvidence, bytes]:
    """Read exactly one regular leaf from the descriptor that passed custody checks."""
    descriptors, parent, leaf, accepted_device = _held_parent(root, relative)
    descriptor: int | None = None
    try:
        try:
            before = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
            if stat.S_ISLNK(before.st_mode):
                raise FilesystemPolicyError("SYMLINK_REJECTED")
            if not stat.S_ISREG(before.st_mode):
                raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
            descriptor = os.open(leaf, _file_flags(), dir_fd=parent)
        except FilesystemPolicyError:
            raise
        except (NotImplementedError, TypeError) as error:
            raise FilesystemPolicyError("DIRECTORY_DESCRIPTOR_UNAVAILABLE") from error
        except OSError as error:
            _raise_open_boundary_error(error)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_identity(before, opened) or opened.st_dev != accepted_device:
            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if _signature(before) != _signature(after):
            raise FilesystemPolicyError("AUTHORITATIVE_FILE_CHANGED")
        content = b"".join(chunks)
        return FileEvidence(relative.as_posix(), "regular_file", len(content), sha256_bytes(content), opened.st_nlink), content
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for held in reversed(descriptors):
            os.close(held)


def read_authoritative_file(root: Path, relative_path: str) -> tuple[FileEvidence, bytes]:
    """Return regular-file evidence and bytes from one no-follow descriptor read."""
    return _read_authoritative_regular_file(root, require_relative_posix_path(relative_path))


def inspect_authoritative_path(root: Path, relative_path: str) -> FileEvidence:
    """Classify a contained path while retaining descriptors until classification ends."""
    relative = require_relative_posix_path(relative_path)
    descriptors, parent, leaf, accepted_device = _held_parent(root, relative)
    try:
        before = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
        if stat.S_ISLNK(before.st_mode):
            raise FilesystemPolicyError("SYMLINK_REJECTED")
        if stat.S_ISDIR(before.st_mode):
            child = _open_directory(parent, leaf, accepted_device)
            os.close(child)
            return FileEvidence(relative.as_posix(), "directory")
        if not stat.S_ISREG(before.st_mode):
            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
    finally:
        for held in reversed(descriptors):
            os.close(held)
    evidence, _ = _read_authoritative_regular_file(root, relative)
    return evidence


def enumerate_authoritative_files(root: Path) -> set[str]:
    """Enumerate a closed authority tree using only held directory descriptors."""
    descriptors: list[int] = []
    try:
        current, root_parts = _directory_components(root)
        descriptors.append(current)
        for part in root_parts:
            current = _open_directory(current, part, None)
            descriptors.append(current)
        authority = os.fstat(current)
        result: set[str] = set()

        def visit(directory: int, prefix: str) -> None:
            before = _signature(os.fstat(directory))
            try:
                with os.scandir(directory) as entries:
                    names = sorted(entry.name for entry in entries)
            except (NotImplementedError, TypeError, OSError) as error:
                raise FilesystemPolicyError("DIRECTORY_DESCRIPTOR_UNAVAILABLE") from error
            for name in names:
                try:
                    details = os.stat(name, dir_fd=directory, follow_symlinks=False)
                except (NotImplementedError, TypeError, OSError) as error:
                    raise FilesystemPolicyError("DIRECTORY_DESCRIPTOR_UNAVAILABLE") from error
                relative = f"{prefix}/{name}" if prefix else name
                if stat.S_ISLNK(details.st_mode) or not (stat.S_ISDIR(details.st_mode) or stat.S_ISREG(details.st_mode)):
                    raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
                if details.st_dev != authority.st_dev:
                    raise FilesystemPolicyError("MOUNT_BOUNDARY_UNPROVEN")
                if stat.S_ISREG(details.st_mode):
                    result.add(relative)
                    continue
                child = _open_directory(directory, name, authority.st_dev)
                try:
                    visit(child, relative)
                finally:
                    os.close(child)
            if before != _signature(os.fstat(directory)):
                raise FilesystemPolicyError("AUTHORITATIVE_DIRECTORY_CHANGED")

        visit(current, "")
        return result
    finally:
        for held in reversed(descriptors):
            os.close(held)


def reject_hardlink_dependency(declared_shared_inode: bool) -> None:
    """Reject layouts whose accepted meaning depends on a hardlink relationship."""
    if declared_shared_inode:
        raise FilesystemPolicyError("HARDLINK_DEPENDENCY_REJECTED")
