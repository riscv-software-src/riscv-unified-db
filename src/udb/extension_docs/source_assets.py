# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Declared source-asset closure, with no checkout or network discovery."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path

from .model import ExtensionDocumentError

_INCLUDE = re.compile(r"(?m)^include::([^\[\r\n]+)\[([^\]\r\n]*)\]$")
_IMAGE = re.compile(r"(?<![/\w])image::?([^\[\r\n]+)\[")


def packaged_source(name: str) -> bytes:
    root = files("udb.extension_docs").joinpath("assets")
    entries = json.loads(root.joinpath("manifest.json").read_text(encoding="utf-8"))
    entry = next((entry for entry in entries if entry["path"] == name), None)
    if entry is None:
        raise ExtensionDocumentError(f"No declared packaged asset {name!r}; supply explicit input")
    data = root.joinpath(*Path(name).parts).read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ExtensionDocumentError(f"Packaged source asset failed integrity: {name}")
    return data


def safe_relative(name: str) -> Path:
    path = Path(name)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or any(char in name for char in "\\\0\r\n{}")
    ):
        raise ExtensionDocumentError(f"Asset must be a declared relative path: {name!r}")
    return path


def source_asset_closure(
    text: str,
    *,
    supplied: Mapping[str, bytes] | None = None,
) -> dict[Path, bytes]:
    result = {}
    active = set()
    declared = {}
    for name, data in (supplied or {}).items():
        path = safe_relative(name)
        if not isinstance(data, bytes):
            raise ExtensionDocumentError(f"Explicit source asset must contain bytes: {name}")
        declared[path] = data
    budget = 5_000_000

    def read(path: Path) -> bytes:
        return declared[path] if path in declared else packaged_source(path.as_posix())

    def visit(content: str, depth: int = 0, base: Path = Path(".")) -> None:
        nonlocal budget
        budget -= len(content.encode("utf-8"))
        if depth > 12 or budget < 0:
            raise ExtensionDocumentError("Source asset closure exceeds its bounded budget")
        for match in _INCLUDE.finditer(content):
            name, options = match.groups()
            path = base / safe_relative(name)
            if options:
                raise ExtensionDocumentError(f"Unsupported declared include options: {match[0]}")
            if path in active:
                raise ExtensionDocumentError(f"Cyclic declared include: {name}")
            if path in result:
                continue
            data = read(path)
            result[path] = data
            active.add(path)
            try:
                visit(data.decode("utf-8"), depth + 1, path.parent)
            except UnicodeDecodeError as error:
                raise ExtensionDocumentError(f"Include is not UTF-8: {name}") from error
            active.remove(path)
        for match in _IMAGE.finditer(content):
            name = match[1]
            if name.startswith(("https://", "http://")):
                raise ExtensionDocumentError(
                    f"Offline source requires an explicit local image: {name}"
                )
            path = safe_relative(name)
            # Native headers use image names relative to imagesdir; actual
            # source assets are emitted under the conventional images folder.
            asset = path if path.parts[0] == "images" else Path("images") / path
            if asset not in result:
                result[asset] = read(asset)

    visit(text)
    return result


def write_source_assets(assets: dict[Path, bytes], output: Path) -> None:
    for relative, data in assets.items():
        target = output / relative
        if not target.resolve().is_relative_to(output.resolve()):
            raise ExtensionDocumentError(f"Source-asset directory escapes output: {target}")
        if target.is_symlink():
            raise ExtensionDocumentError(f"Refusing to overwrite a source-asset symlink: {target}")
        if target.exists() and target.read_bytes() != data:
            raise ExtensionDocumentError(
                f"Source asset conflicts with existing caller input: {target}"
            )
    for relative, data in assets.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def expand_render_includes(text: str, roots: tuple[Path, ...]) -> str:
    """Inline explicit local inputs before Python diagram preparation.

    This is an asset include boundary, not an AsciiDoc/ERB interpreter.
    Only empty-option includes are accepted; relative paths cannot leave the
    caller-declared roots, and unknown paths never trigger checkout discovery.
    """
    active: set[Path] = set()
    budget = 5_000_000

    def expand(content: str, depth: int, base: Path | None = None) -> str:
        nonlocal budget
        if depth > 12 or len(content.encode()) > budget:
            raise ExtensionDocumentError("Render include closure exceeds its bounded budget")
        budget -= len(content.encode())

        def include(match: re.Match[str]) -> str:
            name, options = match.groups()
            relative = safe_relative(name)
            if options:
                raise ExtensionDocumentError(f"Unsupported render include options: {match[0]}")
            candidates = ([base / relative] if base is not None else []) + [
                root / relative for root in roots
            ]
            path = next((path for path in candidates if path.is_file()), None)
            if path is None:
                raise ExtensionDocumentError(f"Missing explicit render include: {name}")
            resolved = path.resolve()
            if not any(resolved.is_relative_to(root.resolve()) for root in roots):
                raise ExtensionDocumentError(f"Render include escapes its declared root: {name}")
            if resolved in active:
                raise ExtensionDocumentError(f"Cyclic render include: {name}")
            active.add(resolved)
            try:
                return expand(path.read_text(encoding="utf-8"), depth + 1, path.parent)
            except (OSError, UnicodeError) as error:
                raise ExtensionDocumentError(f"Cannot read UTF-8 render include: {name}") from error
            finally:
                active.remove(resolved)

        return _INCLUDE.sub(include, content)

    return expand(text, 0)
