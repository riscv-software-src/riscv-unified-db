# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Fail-closed descriptor-rooted custody for authoritative evidence paths."""

from __future__ import annotations

import errno
import os
import stat
from collections.abc import Mapping
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


def _write_all(descriptor: int, content: bytes) -> None:
    """Write a complete immutable payload or fail before it can be trusted."""
    offset = 0
    while offset < len(content):
        written = os.write(descriptor, content[offset:])
        if written <= 0:
            raise OSError(errno.EIO, "short authoritative write")
        offset += written


def _existing_leaf_kind(parent: int, leaf: str, accepted_device: int) -> os.stat_result:
    """Return one existing regular leaf without following a mutable name."""
    try:
        details = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
    except OSError as error:
        _raise_open_boundary_error(error)
        raise AssertionError("unreachable")
    if stat.S_ISLNK(details.st_mode):
        raise FilesystemPolicyError("SYMLINK_REJECTED")
    if not stat.S_ISREG(details.st_mode) or details.st_dev != accepted_device:
        raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
    return details


def create_descriptor_directories(root: Path, relative_directories: tuple[str, ...]) -> None:
    """Durably create recoverable no-follow directories beneath one held root."""
    directories = sorted({require_relative_posix_path(value) for value in relative_directories}, key=lambda value: value.parts)
    held: dict[tuple[str, ...], int] = {}
    root_descriptor: int | None = None
    try:
        root_descriptor, root_parts = _directory_components(root)
        if root_parts:
            raise FilesystemPolicyError("DIRECTORY_DESCRIPTOR_UNAVAILABLE")
        authority = os.fstat(root_descriptor)
        if not stat.S_ISDIR(authority.st_mode):
            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
        held[()] = root_descriptor
        for relative in directories:
            for depth, part in enumerate(relative.parts, start=1):
                prefix = relative.parts[:depth]
                if prefix in held:
                    continue
                parent = held[prefix[:-1]]
                try:
                    child = _open_directory(parent, part, authority.st_dev)
                except FilesystemPolicyError as error:
                    if str(error) != "AUTHORITATIVE_FILE_MISSING":
                        raise
                    try:
                        os.mkdir(part, 0o755, dir_fd=parent)
                        os.fsync(parent)
                    except FileExistsError:
                        pass
                    except (NotImplementedError, TypeError, OSError) as mkdir_error:
                        raise FilesystemPolicyError("AUTHORITATIVE_WRITE_INVALID") from mkdir_error
                    child = _open_directory(parent, part, authority.st_dev)
                held[prefix] = child
    finally:
        for prefix, descriptor in sorted(held.items(), key=lambda item: len(item[0]), reverse=True):
            if descriptor != root_descriptor:
                os.close(descriptor)
        if root_descriptor is not None:
            os.close(root_descriptor)


def write_new_descriptor_file(root: Path, relative_path: str, content: bytes) -> None:
    """Durably create one exact no-replace authoritative leaf through held parents."""
    relative = require_relative_posix_path(relative_path)
    descriptors, parent, leaf, _ = _held_parent(root, relative)
    descriptor: int | None = None
    try:
        try:
            existing = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            existing = None
        except OSError as error:
            _raise_open_boundary_error(error)
            raise AssertionError("unreachable")
        if existing is not None:
            if stat.S_ISLNK(existing.st_mode):
                raise FilesystemPolicyError("SYMLINK_REJECTED")
            raise FilesystemPolicyError("AUTHORITATIVE_DESTINATION_EXISTS")
        descriptor = os.open(
            leaf,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _require_flag("O_NOFOLLOW") | _require_flag("O_CLOEXEC"),
            0o644,
            dir_fd=parent,
        )
        _write_all(descriptor, content)
        os.fsync(descriptor)
        os.fsync(parent)
    except FilesystemPolicyError:
        raise
    except FileExistsError as error:
        raise FilesystemPolicyError("AUTHORITATIVE_DESTINATION_EXISTS") from error
    except (NotImplementedError, TypeError, OSError) as error:
        raise FilesystemPolicyError("AUTHORITATIVE_WRITE_INVALID") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for held in reversed(descriptors):
            os.close(held)


def _read_bounded_descriptor(descriptor: int, expected_length: int) -> bytes:
    """Rewind and read no more than one byte beyond an already-bounded payload."""
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while total <= expected_length:
        chunk = os.read(descriptor, min(1024 * 1024, expected_length + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


def write_exact_descriptor_files(root: Path, payloads: Mapping[str, bytes]) -> None:
    """Preflight, durably create, and postflight one exact no-replace file set.

    The lexical root is opened exactly once. Every directory and leaf descriptor
    remains rooted in that authority through the cross-leaf postflight, so a
    pathname rebind cannot split one batch across two trees. The final sweep
    detects mutations overlapping the first verification pass; it does not
    provide cross-file transaction atomicity or protect against a same-UID
    writer modifying a leaf after that leaf's final observation.
    """
    if not isinstance(payloads, Mapping) or not payloads:
        raise FilesystemPolicyError("AUTHORITATIVE_WRITE_INVALID")
    normalized: list[tuple[PurePosixPath, bytes]] = []
    for path, raw in payloads.items():
        if not isinstance(path, str) or not isinstance(raw, bytes):
            raise FilesystemPolicyError("AUTHORITATIVE_WRITE_INVALID")
        normalized.append((require_relative_posix_path(path), raw))
    normalized.sort(key=lambda item: item[0].parts)
    names = [relative.as_posix() for relative, _ in normalized]
    target_parts = {relative.parts for relative, _ in normalized}
    if len(names) != len(set(names)) or any(
        relative.parts[:depth] in target_parts
        for relative, _ in normalized
        for depth in range(1, len(relative.parts))
    ):
        raise FilesystemPolicyError("AUTHORITATIVE_WRITE_INVALID")

    root_descriptor: int | None = None
    directories: dict[tuple[str, ...], int] = {}
    directory_signatures: dict[tuple[str, ...], tuple[int, int, int, int, int, int, int]] = {}
    absent_directories: set[tuple[str, ...]] = set()
    files: dict[str, tuple[int, int, str, os.stat_result]] = {}
    try:
        root_descriptor, root_parts = _directory_components(root)
        if root_parts:
            raise FilesystemPolicyError("DIRECTORY_DESCRIPTOR_UNAVAILABLE")
        authority = os.fstat(root_descriptor)
        if not stat.S_ISDIR(authority.st_mode):
            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
        directories[()] = root_descriptor
        directory_signatures[()] = _signature(authority)

        # Complete the read-only preflight before any mkdir, create, or fsync.
        missing: list[tuple[PurePosixPath, bytes]] = []
        for relative, expected in normalized:
            parent = root_descriptor
            parent_prefix: tuple[str, ...] = ()
            parent_missing = False
            for depth, part in enumerate(relative.parts[:-1], start=1):
                prefix = relative.parts[:depth]
                if prefix in absent_directories:
                    parent_missing = True
                    break
                child = directories.get(prefix)
                if child is None:
                    try:
                        child = _open_directory(parent, part, authority.st_dev)
                    except FilesystemPolicyError as error:
                        if str(error) != "AUTHORITATIVE_FILE_MISSING":
                            raise
                        absent_directories.add(prefix)
                        parent_missing = True
                        break
                    directories[prefix] = child
                    directory_signatures[prefix] = _signature(os.fstat(child))
                parent = child
                parent_prefix = prefix
            if parent_missing:
                missing.append((relative, expected))
                continue
            leaf = relative.parts[-1]
            try:
                before = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                missing.append((relative, expected))
                continue
            except (NotImplementedError, TypeError, OSError) as error:
                raise FilesystemPolicyError("AUTHORITATIVE_WRITE_INVALID") from error
            if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode) or before.st_dev != authority.st_dev:
                raise FilesystemPolicyError("AUTHORITATIVE_DESTINATION_COLLISION")
            descriptor: int | None = None
            try:
                descriptor = os.open(leaf, _file_flags(), dir_fd=parent)
                opened = os.fstat(descriptor)
                if not _same_identity(before, opened) or not stat.S_ISREG(opened.st_mode) or opened.st_dev != authority.st_dev:
                    raise FilesystemPolicyError("AUTHORITATIVE_POSTWRITE_MISMATCH")
                if opened.st_nlink != 1 or opened.st_size != len(expected):
                    raise FilesystemPolicyError("AUTHORITATIVE_DESTINATION_COLLISION")
                actual = _read_bounded_descriptor(descriptor, len(expected))
                after = os.fstat(descriptor)
                namespace_after = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                if _signature(before) != _signature(after) or not _same_identity(after, namespace_after):
                    raise FilesystemPolicyError("AUTHORITATIVE_FILE_CHANGED")
                if actual != expected:
                    raise FilesystemPolicyError("AUTHORITATIVE_DESTINATION_COLLISION")
                files[relative.as_posix()] = (descriptor, parent, leaf, after)
                descriptor = None
            finally:
                if descriptor is not None:
                    os.close(descriptor)

        # Exact resume leaves are not accepted until both file and namespace
        # durability have been acknowledged through the held descriptors.
        for descriptor, parent, _, baseline in files.values():
            os.fsync(descriptor)
            os.fsync(parent)
            if _signature(os.fstat(descriptor)) != _signature(baseline):
                raise FilesystemPolicyError("AUTHORITATIVE_FILE_CHANGED")

        # Create every missing parent relative to the original held root.
        for relative, _ in missing:
            for depth, part in enumerate(relative.parts[:-1], start=1):
                prefix = relative.parts[:depth]
                if prefix in directories:
                    continue
                parent_prefix = prefix[:-1]
                parent = directories[parent_prefix]
                if _signature(os.fstat(parent)) != directory_signatures[parent_prefix]:
                    raise FilesystemPolicyError("AUTHORITATIVE_DIRECTORY_CHANGED")
                try:
                    os.mkdir(part, 0o755, dir_fd=parent)
                    os.fsync(parent)
                    child = _open_directory(parent, part, authority.st_dev)
                except (NotImplementedError, TypeError, OSError) as error:
                    raise FilesystemPolicyError("AUTHORITATIVE_WRITE_INVALID") from error
                directories[prefix] = child
                directory_signatures[parent_prefix] = _signature(os.fstat(parent))
                directory_signatures[prefix] = _signature(os.fstat(child))

        # Only now may leaves be created. Keep every descriptor for the batch
        # postflight; if durability fails, remove only the inode we created.
        for relative, expected in missing:
            parent_prefix = relative.parts[:-1]
            parent = directories[parent_prefix]
            leaf = relative.parts[-1]
            if _signature(os.fstat(parent)) != directory_signatures[parent_prefix]:
                raise FilesystemPolicyError("AUTHORITATIVE_DIRECTORY_CHANGED")
            descriptor: int | None = None
            created = False
            try:
                descriptor = os.open(
                    leaf,
                    os.O_RDWR | os.O_CREAT | os.O_EXCL | _require_flag("O_NOFOLLOW") | _require_flag("O_CLOEXEC"),
                    0o644,
                    dir_fd=parent,
                )
                created = True
                _write_all(descriptor, expected)
                os.fsync(descriptor)
                os.fsync(parent)
                opened = os.fstat(descriptor)
                if not stat.S_ISREG(opened.st_mode) or opened.st_dev != authority.st_dev or opened.st_nlink != 1 or opened.st_size != len(expected):
                    raise OSError(errno.EIO, "invalid created authoritative leaf")
                files[relative.as_posix()] = (descriptor, parent, leaf, opened)
                descriptor = None
                directory_signatures[parent_prefix] = _signature(os.fstat(parent))
            except (NotImplementedError, TypeError, OSError) as error:
                cleanup_error: BaseException | None = None
                if created and descriptor is not None:
                    try:
                        current = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                        if _same_identity(current, os.fstat(descriptor)):
                            os.unlink(leaf, dir_fd=parent)
                            os.fsync(parent)
                            directory_signatures[parent_prefix] = _signature(os.fstat(parent))
                    except FileNotFoundError:
                        pass
                    except (NotImplementedError, TypeError, OSError) as cleanup_failure:
                        cleanup_error = cleanup_failure
                raise FilesystemPolicyError("AUTHORITATIVE_WRITE_INVALID") from (cleanup_error or error)
            finally:
                if descriptor is not None:
                    os.close(descriptor)

        # Read every held leaf before validating any final signature. A later
        # leaf mutation of an earlier one is therefore visible in the final pass.
        observed: dict[str, bytes] = {}
        expected_by_name = {relative.as_posix(): raw for relative, raw in normalized}
        for name in names:
            descriptor, _, _, _ = files[name]
            observed[name] = _read_bounded_descriptor(descriptor, len(expected_by_name[name]))
        verified_signatures: dict[str, tuple[int, int, int, int, int, int, int]] = {}
        for name in names:
            descriptor, parent, leaf, baseline = files[name]
            os.fsync(descriptor)
            os.fsync(parent)
            after = os.fstat(descriptor)
            try:
                namespace_after = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
            except (NotImplementedError, TypeError, OSError) as error:
                raise FilesystemPolicyError("AUTHORITATIVE_POSTWRITE_MISMATCH") from error
            if (
                observed[name] != expected_by_name[name]
                or after.st_nlink != 1
                or _signature(after) != _signature(baseline)
                or not _same_identity(after, namespace_after)
                or _signature(after) != _signature(namespace_after)
            ):
                raise FilesystemPolicyError("AUTHORITATIVE_POSTWRITE_MISMATCH")
            verified_signatures[name] = _signature(after)
        # Close mutations that occur after an earlier leaf's verification while
        # a later leaf is still being checked. All descriptors stay held until
        # this second namespace-and-inode sweep has completed.
        for name in names:
            descriptor, parent, leaf, _ = files[name]
            after = os.fstat(descriptor)
            try:
                namespace_after = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
            except (NotImplementedError, TypeError, OSError) as error:
                raise FilesystemPolicyError("AUTHORITATIVE_POSTWRITE_MISMATCH") from error
            if (
                after.st_nlink != 1
                or _signature(after) != verified_signatures[name]
                or not _same_identity(after, namespace_after)
                or _signature(after) != _signature(namespace_after)
            ):
                raise FilesystemPolicyError("AUTHORITATIVE_POSTWRITE_MISMATCH")
        for prefix, descriptor in directories.items():
            if _signature(os.fstat(descriptor)) != directory_signatures[prefix]:
                raise FilesystemPolicyError("AUTHORITATIVE_ROOT_CHANGED" if not prefix else "AUTHORITATIVE_DIRECTORY_CHANGED")
    except FilesystemPolicyError:
        raise
    except (NotImplementedError, TypeError, OSError) as error:
        raise FilesystemPolicyError("AUTHORITATIVE_WRITE_INVALID") from error
    finally:
        for descriptor, _, _, _ in files.values():
            os.close(descriptor)
        for prefix, descriptor in sorted(directories.items(), key=lambda item: len(item[0]), reverse=True):
            if descriptor != root_descriptor:
                os.close(descriptor)
        if root_descriptor is not None:
            os.close(root_descriptor)


def _read_held_regular_file(
    parent: int, leaf: str, accepted_device: int, *, require_single_link: bool = False,
) -> bytes:
    """Read one held regular leaf and reject identity or byte races."""
    return _read_held_regular_file_evidence(
        parent, leaf, accepted_device, require_single_link=require_single_link,
    )[1]


def _read_held_regular_file_evidence(
    parent: int, leaf: str, accepted_device: int, *, require_single_link: bool = False,
    max_bytes: int | None = None,
) -> tuple[os.stat_result, bytes]:
    """Read one held regular leaf and retain the matching descriptor evidence."""
    if max_bytes is not None and (isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 0):
        raise FilesystemPolicyError("AUTHORITATIVE_READ_LIMIT_INVALID")
    descriptor: int | None = None
    try:
        before = _existing_leaf_kind(parent, leaf, accepted_device)
        descriptor = os.open(leaf, _file_flags(), dir_fd=parent)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_identity(before, opened) or opened.st_dev != accepted_device:
            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
        if require_single_link and opened.st_nlink != 1:
            raise FilesystemPolicyError("HARDLINK_DEPENDENCY_REJECTED")
        if max_bytes is not None and opened.st_size > max_bytes:
            raise FilesystemPolicyError("AUTHORITATIVE_FILE_TOO_LARGE")
        chunks: list[bytes] = []
        total = 0
        exceeded = False
        while True:
            read_size = 1024 * 1024 if max_bytes is None else min(1024 * 1024, max_bytes + 1 - total)
            chunk = os.read(descriptor, read_size)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if max_bytes is not None and total > max_bytes:
                exceeded = True
                break
        if _signature(before) != _signature(os.fstat(descriptor)):
            raise FilesystemPolicyError("AUTHORITATIVE_FILE_CHANGED")
        if exceeded:
            raise FilesystemPolicyError("AUTHORITATIVE_FILE_TOO_LARGE")
        return opened, b"".join(chunks)
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _fsync_held_regular_file(parent: int, leaf: str, accepted_device: int) -> None:
    """Durably acknowledge an exact process-death temporary without reopening paths."""
    descriptor: int | None = None
    try:
        before = _existing_leaf_kind(parent, leaf, accepted_device)
        descriptor = os.open(leaf, _file_flags(), dir_fd=parent)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_identity(before, opened) or opened.st_dev != accepted_device:
            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
        if opened.st_nlink != 1:
            raise FilesystemPolicyError("HARDLINK_DEPENDENCY_REJECTED")
        os.fsync(descriptor)
    finally:
        if descriptor is not None:
            os.close(descriptor)


def replace_descriptor_file(root: Path, relative_path: str, content: bytes, expected_current: bytes) -> None:
    """Replace only an unchanged held target, reusing an exact crash temporary."""
    relative = require_relative_posix_path(relative_path)
    descriptors, parent, leaf, accepted_device = _held_parent(root, relative)
    descriptor: int | None = None
    temporary = f".{leaf}.cutover"
    try:
        if _read_held_regular_file(parent, leaf, accepted_device) != expected_current:
            raise FilesystemPolicyError("AUTHORITATIVE_TARGET_MISMATCH")
        try:
            temporary_raw = _read_held_regular_file(
                parent, temporary, accepted_device, require_single_link=True,
            )
        except FilesystemPolicyError as error:
            if str(error) != "AUTHORITATIVE_FILE_MISSING":
                raise
            temporary_raw = None
        if temporary_raw is None:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _require_flag("O_NOFOLLOW") | _require_flag("O_CLOEXEC"),
                0o644,
                dir_fd=parent,
            )
            _write_all(descriptor, content)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
        elif temporary_raw != content:
            raise FilesystemPolicyError("AUTHORITATIVE_TEMPORARY_MISMATCH")
        else:
            _fsync_held_regular_file(parent, temporary, accepted_device)
        # This second held-parent read closes target changes detectable between
        # temporary creation/reuse and the dirfd-only replacement.
        if _read_held_regular_file(parent, leaf, accepted_device) != expected_current:
            raise FilesystemPolicyError("AUTHORITATIVE_TARGET_MISMATCH")
        # Validate the source name last so the only remaining interval is the
        # unavoidable boundary between this descriptor check and rename(2).
        if _read_held_regular_file(
            parent, temporary, accepted_device, require_single_link=True,
        ) != content:
            raise FilesystemPolicyError("AUTHORITATIVE_TEMPORARY_MISMATCH")
        os.replace(temporary, leaf, src_dir_fd=parent, dst_dir_fd=parent)
        os.fsync(parent)
    except FilesystemPolicyError:
        raise
    except FileExistsError as error:
        raise FilesystemPolicyError("AUTHORITATIVE_DESTINATION_EXISTS") from error
    except (NotImplementedError, TypeError, OSError) as error:
        raise FilesystemPolicyError("AUTHORITATIVE_WRITE_INVALID") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for held in reversed(descriptors):
            os.close(held)


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


def read_authoritative_files(
    root: Path, relative_paths: list[str], *, max_bytes: int | None = None,
) -> dict[str, tuple[FileEvidence, bytes]]:
    """Read a fixed file set through one held authority-root descriptor."""
    if max_bytes is not None and (isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 0):
        raise FilesystemPolicyError("AUTHORITATIVE_READ_LIMIT_INVALID")
    normalized = [require_relative_posix_path(value) for value in relative_paths]
    names = [value.as_posix() for value in normalized]
    if len(names) != len(set(names)):
        raise FilesystemPolicyError("AUTHORITATIVE_BATCH_DUPLICATE")
    root_descriptor: int | None = None
    try:
        root_descriptor, root_parts = _directory_components(root)
        if root_parts:
            raise FilesystemPolicyError("DIRECTORY_DESCRIPTOR_UNAVAILABLE")
        root_stat = os.fstat(root_descriptor)
        if not stat.S_ISDIR(root_stat.st_mode):
            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
        directories: dict[tuple[str, ...], int] = {(): root_descriptor}
        result: dict[str, tuple[FileEvidence, bytes]] = {}
        for relative in normalized:
            parent = root_descriptor
            prefix: tuple[str, ...] = ()
            for part in relative.parts[:-1]:
                prefix += (part,)
                child = directories.get(prefix)
                if child is None:
                    child = _open_directory(parent, part, root_stat.st_dev)
                    directories[prefix] = child
                parent = child
            leaf = relative.parts[-1]
            details, content = _read_held_regular_file_evidence(
                parent, leaf, root_stat.st_dev, max_bytes=max_bytes,
            )
            result[relative.as_posix()] = (
                FileEvidence(relative.as_posix(), "regular_file", len(content), sha256_bytes(content), details.st_nlink),
                content,
            )
        if _signature(root_stat) != _signature(os.fstat(root_descriptor)):
            raise FilesystemPolicyError("AUTHORITATIVE_ROOT_CHANGED")
        return result
    finally:
        if root_descriptor is not None and "directories" in locals():
            for _, descriptor in sorted(directories.items(), key=lambda item: len(item[0]), reverse=True):
                if descriptor != root_descriptor:
                    os.close(descriptor)
        if root_descriptor is not None:
            os.close(root_descriptor)


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


def read_closed_authoritative_tree(root: Path) -> dict[str, tuple[FileEvidence, bytes]]:
    """Read a complete regular-file authority tree through one held root descriptor."""
    descriptors: list[int] = []
    try:
        current, root_parts = _directory_components(root)
        descriptors.append(current)
        for part in root_parts:
            current = _open_directory(current, part, None)
            descriptors.append(current)
        authority = os.fstat(current)
        result: dict[str, tuple[FileEvidence, bytes]] = {}

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
                    opened, content = _read_held_regular_file_evidence(directory, name, authority.st_dev)
                    result[relative] = (
                        FileEvidence(relative, "regular_file", len(content), sha256_bytes(content), opened.st_nlink), content,
                    )
                    continue
                child = _open_directory(directory, name, authority.st_dev)
                try:
                    visit(child, relative)
                finally:
                    os.close(child)
            if prefix and before != _signature(os.fstat(directory)):
                raise FilesystemPolicyError("AUTHORITATIVE_DIRECTORY_CHANGED")

        visit(current, "")
        if _signature(authority) != _signature(os.fstat(current)):
            raise FilesystemPolicyError("AUTHORITATIVE_ROOT_CHANGED")
        return result
    finally:
        for held in reversed(descriptors):
            os.close(held)


def reject_hardlink_dependency(declared_shared_inode: bool) -> None:
    """Reject layouts whose accepted meaning depends on a hardlink relationship."""
    if declared_shared_inode:
        raise FilesystemPolicyError("HARDLINK_DEPENDENCY_REJECTED")
