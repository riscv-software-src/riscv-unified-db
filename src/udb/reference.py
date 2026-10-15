# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Lazy, typed references between resolved UDB values."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlsplit

from .errors import ReferenceError
from .source import SourceSpan

if TYPE_CHECKING:
    from .database import ResolvedDatabase

type PathPart = str | int
_ARRAY_INDEX = re.compile(r"0|[1-9][0-9]*")


def _pointer(path: tuple[PathPart, ...]) -> str:
    if not path:
        return "#"
    tokens = (str(part).replace("~", "~0").replace("/", "~1") for part in path)
    return "#/" + "/".join(tokens)


def _decode_pointer(pointer: str, *, reference: str, location: str) -> tuple[str, ...]:
    malformed_percent = re.search(r"%(?![0-9A-Fa-f]{2})", pointer)
    if malformed_percent is not None:
        raise ReferenceError(f"{location}: invalid percent escape in data reference {reference!r}")
    try:
        pointer = unquote(pointer, errors="strict")
    except UnicodeDecodeError as error:
        raise ReferenceError(
            f"{location}: invalid UTF-8 escape in data reference {reference!r}"
        ) from error
    if pointer == "":
        return ()
    if not pointer.startswith("/"):
        raise ReferenceError(f"{location}: invalid JSON pointer in data reference {reference!r}")
    decoded: list[str] = []
    for token in pointer[1:].split("/"):
        output: list[str] = []
        index = 0
        while index < len(token):
            if token[index] != "~":
                output.append(token[index])
                index += 1
                continue
            if index + 1 >= len(token) or token[index + 1] not in ("0", "1"):
                raise ReferenceError(
                    f"{location}: invalid JSON pointer escape in data reference {reference!r}"
                )
            output.append("~" if token[index + 1] == "0" else "/")
            index += 2
        decoded.append("".join(output))
    return tuple(decoded)


@dataclass(frozen=True, slots=True)
class ResolvedNode:
    """A stable address into one immutable resolved database."""

    document: str
    path: tuple[PathPart, ...]
    _database: ResolvedDatabase = field(repr=False)

    @property
    def pointer(self) -> str:
        return _pointer(self.path)

    @property
    def value(self) -> Any:
        return self._database._value_at(self.document, self.path)

    @property
    def source(self) -> SourceSpan | None:
        return self._database.source_at(self.document, *self.path)

    def child(self, key: PathPart) -> ResolvedNode:
        """Return a child node after checking the mapping key or array index."""
        value = self.value
        if isinstance(value, Mapping):
            if key not in value:
                raise ReferenceError(f"{self.document}{self.pointer}: no child {key!r}")
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            if type(key) is not int or key < 0 or key >= len(value):
                raise ReferenceError(f"{self.document}{self.pointer}: no child {key!r}")
        else:
            raise ReferenceError(f"{self.document}{self.pointer}: value has no children")
        return ResolvedNode(self.document, (*self.path, key), self._database)

    def reference(self) -> Reference:
        """Interpret this mapping's `$ref` without eagerly following it."""
        return self._database.reference_at(self.document, *self.path)


@dataclass(frozen=True, slots=True)
class Reference:
    """A reference occurrence in a resolved document."""

    uri: str
    origin: ResolvedNode

    @property
    def source(self) -> SourceSpan | None:
        return self.origin._database.source_at(self.origin.document, *self.origin.path, "$ref")


@dataclass(frozen=True, slots=True)
class SchemaReference(Reference):
    """A JSON Schema reference, intentionally not resolved as UDB data."""


@dataclass(frozen=True, slots=True)
class DataReference(Reference):
    """A lazy link to another value in the same resolved database."""

    target_document: str
    target_path: tuple[str, ...]

    @property
    def target(self) -> ResolvedNode:
        database = self.origin._database
        current: Any = database.documents.get(self.target_document)
        location = (
            self.source.label
            if self.source is not None
            else (f"{self.origin.document}{self.origin.pointer}/$ref")
        )
        if current is None:
            raise ReferenceError(
                f"{location}: data reference {self.uri!r} names missing document "
                f"{self.target_document!r}"
            )
        path: list[PathPart] = []
        for token in self.target_path:
            if isinstance(current, Mapping):
                if token not in current:
                    self._missing(location)
                current = current[token]
                path.append(token)
            elif isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
                if _ARRAY_INDEX.fullmatch(token) is None:
                    self._missing(location)
                index = int(token)
                if index >= len(current):
                    self._missing(location)
                current = current[index]
                path.append(index)
            else:
                self._missing(location)
        return ResolvedNode(self.target_document, tuple(path), database)

    def _missing(self, location: str) -> None:
        raise ReferenceError(f"{location}: data reference {self.uri!r} names a missing value")


def classify_reference(origin: ResolvedNode, uri: str) -> Reference:
    """Classify schema JSON references separately from data YAML references."""
    source = origin._database.source_at(origin.document, *origin.path, "$ref")
    location = source.label if source is not None else f"{origin.document}{origin.pointer}/$ref"
    base, separator, fragment = uri.partition("#")
    try:
        parsed = urlsplit(base)
    except ValueError as error:
        raise ReferenceError(f"{location}: invalid reference URI {uri!r}: {error}") from error
    suffix = PurePosixPath(parsed.path).suffix.lower()
    root = origin._database.documents[origin.document]
    embedded_schema = (
        isinstance(root, Mapping)
        and root.get("kind") == "parameter"
        and bool(origin.path)
        and origin.path[0] == "schema"
    )
    if embedded_schema or parsed.scheme or parsed.netloc or suffix == ".json":
        return SchemaReference(uri, origin)
    if suffix not in ("", ".yaml", ".yml"):
        return SchemaReference(uri, origin)

    document = origin.document if not base else base
    if "\\" in document:
        raise ReferenceError(f"{location}: data reference path must use POSIX separators: {uri!r}")
    parsed_path = PurePosixPath(document)
    if parsed_path.is_absolute() or ".." in parsed_path.parts:
        raise ReferenceError(f"{location}: data reference must be root-relative: {uri!r}")
    pointer = fragment if separator else ""
    return DataReference(
        uri,
        origin,
        parsed_path.as_posix(),
        _decode_pointer(pointer, reference=uri, location=location),
    )
