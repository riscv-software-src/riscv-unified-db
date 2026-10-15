# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""In-memory YAML inheritance and merge-patch resolution."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import PurePosixPath
from typing import Any

from .errors import ResolutionError

_PROVENANCE_KEYS = frozenset(("$child_of", "$parent_of"))
_MISSING = object()

type _PathPart = str | int
type _Location = tuple[str, tuple[_PathPart, ...]]


def _copy_value(value: Any, active: set[int] | None = None) -> Any:
    if active is None:
        active = set()
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            raise ResolutionError("Recursive document values are not supported")
        active.add(identity)
        try:
            return {key: _copy_value(item, active) for key, item in value.items()}
        finally:
            active.remove(identity)
    if isinstance(value, list | tuple):
        identity = id(value)
        if identity in active:
            raise ResolutionError("Recursive document values are not supported")
        active.add(identity)
        try:
            return [_copy_value(item, active) for item in value]
        finally:
            active.remove(identity)
    return deepcopy(value)


def merge_patch(base: Any, patch: Any) -> Any:
    """Apply an RFC 7386 JSON Merge Patch and return an isolated result."""
    if not isinstance(patch, Mapping):
        return _copy_value(patch)

    result = _copy_value(base) if isinstance(base, Mapping) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = merge_patch(result.get(key), value)
    return result


class YamlResolver:
    """Resolve ``$inherits`` relationships in an in-memory document set."""

    def __init__(self, documents: Mapping[str, Mapping[Any, Any]]) -> None:
        self._documents: dict[str, dict[Any, Any]] = {}
        for path, document in documents.items():
            normalized = self._validate_document_path(path)
            if normalized in self._documents:
                raise ResolutionError(f"Duplicate YAML document path: {normalized}")
            if not isinstance(document, Mapping):
                raise ResolutionError(f"YAML document {normalized} must contain a mapping")
            self._documents[normalized] = _copy_value(document)

    def resolve(self) -> dict[str, dict[Any, Any]]:
        """Return fully resolved documents with no shared mutable input state."""
        self._cache: dict[_Location, Any] = {}
        resolved: dict[str, dict[Any, Any]] = {}
        for document_path in sorted(self._documents):
            value = self._resolve_location((document_path, ()), ())
            if not isinstance(value, dict):
                raise ResolutionError(f"Resolved YAML document {document_path} is not a mapping")
            resolved[document_path] = _copy_value(value)

        self._set_parent_relationships(resolved)
        return _copy_value(resolved)

    @staticmethod
    def _validate_document_path(path: str) -> str:
        if not isinstance(path, str) or not path:
            raise ResolutionError("YAML document paths must be non-empty strings")
        if "\\" in path:
            raise ResolutionError(f"YAML document path must use POSIX separators: {path!r}")
        parsed = PurePosixPath(path)
        if parsed.is_absolute() or any(part in ("", ".", "..") for part in parsed.parts):
            raise ResolutionError(f"YAML document path must be root-relative: {path!r}")
        normalized = parsed.as_posix()
        if normalized != path:
            raise ResolutionError(f"Invalid YAML document path: {path!r}")
        return normalized

    def _resolve_location(self, location: _Location, active: tuple[_Location, ...]) -> Any:
        if location in self._cache:
            return _copy_value(self._cache[location])
        if location in active:
            first = active.index(location)
            cycle = (*active[first:], location)
            chain = " -> ".join(self._format_location(item) for item in cycle)
            raise ResolutionError(f"Cyclic $inherits relationship: {chain}")

        raw = self._value_at(location)
        next_active = (*active, location)
        if isinstance(raw, Mapping):
            resolved = self._resolve_mapping(location, raw, next_active)
        elif isinstance(raw, list | tuple):
            resolved = [
                self._resolve_location((location[0], (*location[1], index)), next_active)
                for index in range(len(raw))
            ]
        else:
            resolved = _copy_value(raw)

        self._cache[location] = _copy_value(resolved)
        return resolved

    def _resolve_mapping(
        self,
        location: _Location,
        raw: Mapping[Any, Any],
        active: tuple[_Location, ...],
    ) -> dict[Any, Any]:
        return self._resolve_mapping_over(location, raw, active, {})

    def _resolve_mapping_over(
        self,
        location: _Location,
        raw: Mapping[Any, Any],
        active: tuple[_Location, ...],
        base: Mapping[Any, Any],
    ) -> dict[Any, Any]:
        resolved = _copy_value(base)
        inherits = raw.get("$inherits", _MISSING)
        if inherits is not _MISSING:
            targets = inherits if isinstance(inherits, list | tuple) else [inherits]
            if not targets:
                raise ResolutionError(
                    f"$inherits at {self._format_location(location)} must name at least one parent"
                )
            for target in targets:
                if not isinstance(target, str):
                    raise ResolutionError(
                        f"$inherits at {self._format_location(location)} "
                        "must contain string references"
                    )
                parent = self._resolve_reference(target, location, active)
                if not isinstance(parent, Mapping):
                    raise ResolutionError(
                        f"$inherits target {target!r} at {self._format_location(location)} "
                        "must resolve to a mapping"
                    )
                resolved = self._deep_merge(resolved, self._without_provenance(parent))

        for key, raw_child in raw.items():
            if key in ("$inherits", "$remove"):
                continue
            child_location = (location[0], (*location[1], key))
            if isinstance(resolved.get(key), Mapping) and isinstance(raw_child, Mapping):
                if child_location in active:
                    chain = " -> ".join(
                        self._format_location(item) for item in (*active, child_location)
                    )
                    raise ResolutionError(f"Cyclic $inherits relationship: {chain}")
                resolved[key] = self._resolve_mapping_over(
                    child_location,
                    raw_child,
                    (*active, child_location),
                    resolved[key],
                )
            else:
                resolved[key] = self._resolve_location(child_location, active)

        if inherits is not _MISSING:
            resolved["$child_of"] = _copy_value(inherits)
        if "$remove" in raw:
            remove = self._resolve_location((location[0], (*location[1], "$remove")), active)
            resolved["$remove"] = remove
        return self._apply_remove(resolved, location)

    def _parse_reference(self, reference: str, origin: _Location) -> tuple[str, tuple[str, ...]]:
        if "#" in reference:
            file_part, pointer = reference.split("#", 1)
            document_path = (
                origin[0] if not file_part else self._validate_reference_path(file_part, origin)
            )
        else:
            document_path = origin[0]
            pointer = reference if reference.startswith("/") else f"/{reference}"

        if document_path not in self._documents:
            raise ResolutionError(
                f"$inherits at {self._format_location(origin)} references missing document "
                f"{document_path!r}"
            )
        tokens = self._decode_pointer(pointer, reference, origin)
        return document_path, tokens

    def _resolve_reference(
        self, reference: str, origin: _Location, active: tuple[_Location, ...]
    ) -> Any:
        document_path, tokens = self._parse_reference(reference, origin)
        value: Any = self._documents[document_path]
        path: list[_PathPart] = []

        for token_index, token in enumerate(tokens):
            location = (document_path, tuple(path))
            if isinstance(value, Mapping) and "$inherits" in value:
                requested = (document_path, (*path, token))
                if requested in active:
                    first = active.index(requested)
                    cycle = (*active[first:], requested)
                    chain = " -> ".join(self._format_location(item) for item in cycle)
                    raise ResolutionError(f"Cyclic $inherits relationship: {chain}")
                resolved_value = self._resolve_inherited_key(
                    location, value, token, active, requested
                )
                return _copy_value(
                    self._traverse_value(
                        resolved_value, tokens[token_index + 1 :], reference, origin
                    )
                )

            if isinstance(value, Mapping):
                if token not in value:
                    self._missing_pointer(reference, origin)
                value = value[token]
                path.append(token)
            elif isinstance(value, list | tuple):
                index = self._array_index(token, len(value), reference, origin)
                value = value[index]
                path.append(index)
            else:
                self._missing_pointer(reference, origin)

        return self._resolve_location((document_path, tuple(path)), active)

    def _resolve_inherited_key(
        self,
        location: _Location,
        raw: Mapping[Any, Any],
        key: str,
        active: tuple[_Location, ...],
        requested: _Location,
    ) -> Any:
        inherited: Any = _MISSING
        inherits = raw["$inherits"]
        targets = inherits if isinstance(inherits, list | tuple) else [inherits]
        if not targets:
            raise ResolutionError(
                f"$inherits at {self._format_location(location)} must name at least one parent"
            )
        for target in targets:
            if not isinstance(target, str):
                raise ResolutionError(
                    f"$inherits at {self._format_location(location)} must contain string references"
                )
            parent = self._resolve_reference(target, location, (*active, requested))
            if not isinstance(parent, Mapping):
                raise ResolutionError(
                    f"$inherits target {target!r} at {self._format_location(location)} "
                    "must resolve to a mapping"
                )
            if key not in parent or key in _PROVENANCE_KEYS:
                continue
            parent_value = parent[key]
            if isinstance(inherited, Mapping) and isinstance(parent_value, Mapping):
                inherited = self._deep_merge(inherited, parent_value)
            else:
                inherited = _copy_value(parent_value)

        if key not in raw:
            if inherited is _MISSING:
                self._missing_pointer(key, location)
            if self._key_is_removed(raw, key, location, active):
                self._missing_pointer(key, location)
            return inherited

        raw_value = raw[key]
        if isinstance(inherited, Mapping) and isinstance(raw_value, Mapping):
            value = self._resolve_mapping_over(
                requested, raw_value, (*active, requested), inherited
            )
        else:
            value = self._resolve_location(requested, active)
        if self._key_is_removed(raw, key, location, active):
            self._missing_pointer(key, location)
        return value

    def _key_is_removed(
        self,
        raw: Mapping[Any, Any],
        key: str,
        location: _Location,
        active: tuple[_Location, ...],
    ) -> bool:
        if "$remove" not in raw:
            return False
        remove = self._resolve_location((location[0], (*location[1], "$remove")), active)
        keys = remove if isinstance(remove, list | tuple) else [remove]
        return any(item == key for item in keys)

    def _validate_reference_path(self, path: str, origin: _Location) -> str:
        try:
            normalized = self._validate_document_path(path)
        except ResolutionError as error:
            raise ResolutionError(
                f"Invalid $inherits path {path!r} at {self._format_location(origin)}"
            ) from error
        if not normalized.endswith((".yaml", ".yml")):
            raise ResolutionError(
                f"Cross-document $inherits path {path!r} at "
                f"{self._format_location(origin)} must name a YAML file"
            )
        return normalized

    def _decode_pointer(self, pointer: str, reference: str, origin: _Location) -> tuple[str, ...]:
        if pointer == "":
            return ()
        if not pointer.startswith("/"):
            raise ResolutionError(
                f"Invalid JSON pointer in $inherits reference {reference!r} at "
                f"{self._format_location(origin)}"
            )

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
                    raise ResolutionError(
                        f"Invalid JSON pointer escape in $inherits reference {reference!r} "
                        f"at {self._format_location(origin)}"
                    )
                output.append("~" if token[index + 1] == "0" else "/")
                index += 2
            decoded.append("".join(output))
        return tuple(decoded)

    def _traverse_value(
        self, value: Any, tokens: tuple[str, ...], reference: str, origin: _Location
    ) -> Any:
        for token in tokens:
            if isinstance(value, Mapping):
                if token not in value:
                    self._missing_pointer(reference, origin)
                value = value[token]
            elif isinstance(value, list | tuple):
                index = self._array_index(token, len(value), reference, origin)
                value = value[index]
            else:
                self._missing_pointer(reference, origin)
        return value

    def _array_index(self, token: str, length: int, reference: str, origin: _Location) -> int:
        if not token.isdecimal() or (len(token) > 1 and token.startswith("0")):
            self._missing_pointer(reference, origin)
        index = int(token)
        if index >= length:
            self._missing_pointer(reference, origin)
        return index

    def _missing_pointer(self, reference: str, origin: _Location) -> None:
        raise ResolutionError(
            f"$inherits at {self._format_location(origin)} references missing path {reference!r}"
        )

    def _value_at(self, location: _Location) -> Any:
        value: Any = self._documents[location[0]]
        for part in location[1]:
            value = value[part]
        return value

    def _apply_remove(self, value: dict[Any, Any], location: _Location) -> dict[Any, Any]:
        remove = value.pop("$remove", _MISSING)
        if remove is _MISSING:
            return value
        keys = remove if isinstance(remove, list | tuple) else [remove]
        for key in keys:
            try:
                value.pop(key, None)
            except TypeError as error:
                raise ResolutionError(
                    f"$remove at {self._format_location(location)} contains an invalid key"
                ) from error
        return value

    @classmethod
    def _deep_merge(cls, base: Mapping[Any, Any], override: Mapping[Any, Any]) -> dict[Any, Any]:
        result = _copy_value(base)
        for key, value in override.items():
            if isinstance(result.get(key), Mapping) and isinstance(value, Mapping):
                result[key] = cls._deep_merge(result[key], value)
            else:
                result[key] = _copy_value(value)
        return result

    @classmethod
    def _without_provenance(cls, value: Mapping[Any, Any]) -> dict[Any, Any]:
        return {
            key: cls._without_nested_provenance(item)
            for key, item in value.items()
            if key not in _PROVENANCE_KEYS
        }

    @classmethod
    def _without_nested_provenance(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                key: cls._without_nested_provenance(item)
                for key, item in value.items()
                if key not in _PROVENANCE_KEYS
            }
        if isinstance(value, list | tuple):
            return [cls._without_nested_provenance(item) for item in value]
        return _copy_value(value)

    def _set_parent_relationships(self, documents: dict[str, dict[Any, Any]]) -> None:
        relationships: list[tuple[_Location, str]] = []
        for document_path in sorted(documents):
            self._collect_relationships(
                documents, (document_path, ()), documents[document_path], relationships
            )

        for parent_location, child_reference in relationships:
            parent = self._resolved_value_at(documents, parent_location)
            existing = parent.get("$parent_of", _MISSING)
            if existing is _MISSING:
                parent["$parent_of"] = child_reference
                continue
            values = list(existing) if isinstance(existing, list | tuple) else [existing]
            if child_reference not in values:
                values.append(child_reference)
            parent["$parent_of"] = values[0] if len(values) == 1 else values

    def _collect_relationships(
        self,
        documents: dict[str, dict[Any, Any]],
        location: _Location,
        value: Any,
        relationships: list[tuple[_Location, str]],
    ) -> None:
        if isinstance(value, Mapping):
            child_of = value.get("$child_of", _MISSING)
            if child_of is not _MISSING:
                targets = child_of if isinstance(child_of, list | tuple) else [child_of]
                for target in targets:
                    if not isinstance(target, str):
                        raise ResolutionError(
                            f"$child_of at {self._format_location(location)} is not a string reference"
                        )
                    parent = self._resolved_reference_location(target, location, documents)
                    parent_value = self._resolved_value_at(documents, parent)
                    if not isinstance(parent_value, Mapping):
                        raise ResolutionError(
                            f"$child_of target {target!r} at {self._format_location(location)} "
                            "is not a mapping"
                        )
                    relationships.append((parent, self._child_reference(location)))
            for key, child in list(value.items()):
                self._collect_relationships(
                    documents, (location[0], (*location[1], key)), child, relationships
                )
        elif isinstance(value, list | tuple):
            for index, child in enumerate(value):
                self._collect_relationships(
                    documents, (location[0], (*location[1], index)), child, relationships
                )

    def _resolved_reference_location(
        self, reference: str, origin: _Location, documents: dict[str, dict[Any, Any]]
    ) -> _Location:
        if "#" in reference:
            file_part, pointer = reference.split("#", 1)
            document_path = origin[0] if not file_part else file_part
        else:
            document_path = origin[0]
            pointer = reference if reference.startswith("/") else f"/{reference}"
        tokens = self._decode_pointer(pointer, reference, origin)

        value: Any = documents.get(document_path, _MISSING)
        if value is _MISSING:
            self._missing_pointer(reference, origin)
        path: list[_PathPart] = []
        for token in tokens:
            if isinstance(value, Mapping) and token in value:
                value = value[token]
                path.append(token)
            elif isinstance(value, list | tuple) and token.isdecimal():
                index = int(token)
                if index >= len(value):
                    self._missing_pointer(reference, origin)
                value = value[index]
                path.append(index)
            else:
                self._missing_pointer(reference, origin)
        return document_path, tuple(path)

    @staticmethod
    def _resolved_value_at(documents: Mapping[str, Any], location: _Location) -> Any:
        value = documents[location[0]]
        for part in location[1]:
            value = value[part]
        return value

    @classmethod
    def _child_reference(cls, location: _Location) -> str:
        if not location[1]:
            return f"{location[0]}#/"
        tokens = "/".join(cls._escape_pointer_part(part) for part in location[1])
        return f"{location[0]}#/{tokens}"

    @staticmethod
    def _escape_pointer_part(part: _PathPart) -> str:
        return str(part).replace("~", "~0").replace("/", "~1")

    @classmethod
    def _format_location(cls, location: _Location) -> str:
        if not location[1]:
            return f"{location[0]}#"
        tokens = "/".join(cls._escape_pointer_part(part) for part in location[1])
        return f"{location[0]}#/{tokens}"
