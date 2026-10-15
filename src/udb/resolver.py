# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""In-memory YAML inheritance and merge-patch resolution."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from .errors import ResolutionError
from .source import SourceMap, SourceSpan, synthetic_source_map

_PROVENANCE_KEYS = frozenset(("$child_of", "$parent_of"))
_MISSING = object()

type _PathPart = str | int
type _Location = tuple[str, tuple[_PathPart, ...]]


@dataclass(slots=True)
class ResolvedYaml:
    """Mutable resolver result; database construction freezes both mappings."""

    documents: dict[str, dict[Any, Any]]
    sources: dict[str, SourceMap]


@dataclass(slots=True)
class _ResolvedValue:
    value: Any
    sources: dict[tuple[_PathPart, ...], SourceSpan]


def _copy_resolved(value: _ResolvedValue) -> _ResolvedValue:
    return _ResolvedValue(_copy_value(value.value), dict(value.sources))


def _subvalue(value: _ResolvedValue, path: tuple[_PathPart, ...]) -> _ResolvedValue:
    selected = value.value
    for part in path:
        selected = selected[part]
    length = len(path)
    return _ResolvedValue(
        _copy_value(selected),
        {key[length:]: span for key, span in value.sources.items() if key[:length] == path},
    )


def _set_subvalue(value: _ResolvedValue, key: _PathPart, child: _ResolvedValue) -> None:
    value.value[key] = _copy_value(child.value)
    prefix = (key,)
    for existing in tuple(value.sources):
        if existing[:1] == prefix:
            del value.sources[existing]
    value.sources.update({(key, *path): span for path, span in child.sources.items()})


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

    def __init__(
        self,
        documents: Mapping[str, Mapping[Any, Any]],
        *,
        sources: Mapping[str, SourceMap] | None = None,
    ) -> None:
        self._documents: dict[str, dict[Any, Any]] = {}
        self._sources: dict[str, SourceMap] = {}
        for path, document in documents.items():
            normalized = self._validate_document_path(path)
            if normalized in self._documents:
                raise ResolutionError(f"Duplicate YAML document path: {normalized}")
            if not isinstance(document, Mapping):
                raise ResolutionError(f"YAML document {normalized} must contain a mapping")
            self._documents[normalized] = _copy_value(document)
            self._sources[normalized] = (
                sources[normalized]
                if sources is not None and normalized in sources
                else synthetic_source_map(normalized, document)
            )

    def resolve(self) -> dict[str, dict[Any, Any]]:
        """Return fully resolved documents with no shared mutable input state."""
        return self.resolve_with_sources().documents

    def resolve_with_sources(self) -> ResolvedYaml:
        """Return resolved values and immutable field-level source provenance."""
        self._cache: dict[_Location, _ResolvedValue] = {}
        resolved: dict[str, dict[Any, Any]] = {}
        source_entries: dict[str, dict[tuple[_PathPart, ...], SourceSpan]] = {}
        for document_path in sorted(self._documents):
            item = self._resolve_location((document_path, ()), ())
            if not isinstance(item.value, dict):
                raise ResolutionError(f"Resolved YAML document {document_path} is not a mapping")
            resolved[document_path] = _copy_value(item.value)
            source_entries[document_path] = dict(item.sources)

        self._set_parent_relationships(resolved, source_entries)
        return ResolvedYaml(
            _copy_value(resolved),
            {path: SourceMap(path, entries) for path, entries in source_entries.items()},
        )

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

    def _resolve_location(
        self, location: _Location, active: tuple[_Location, ...]
    ) -> _ResolvedValue:
        if location in self._cache:
            return _copy_resolved(self._cache[location])
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
            resolved = _ResolvedValue([], {})
            root_span = self._source_span(location)
            if root_span is not None:
                resolved.sources[()] = root_span
            for index in range(len(raw)):
                child = self._resolve_location((location[0], (*location[1], index)), next_active)
                resolved.value.append(_copy_value(child.value))
                resolved.sources.update(
                    {(index, *path): span for path, span in child.sources.items()}
                )
        else:
            resolved = _ResolvedValue(_copy_value(raw), {})
            span = self._source_span(location)
            if span is not None:
                resolved.sources[()] = span

        self._cache[location] = _copy_resolved(resolved)
        return _copy_resolved(resolved)

    def _resolve_mapping(
        self,
        location: _Location,
        raw: Mapping[Any, Any],
        active: tuple[_Location, ...],
    ) -> _ResolvedValue:
        base = _ResolvedValue({}, {})
        return self._resolve_mapping_over(location, raw, active, base)

    def _resolve_mapping_over(
        self,
        location: _Location,
        raw: Mapping[Any, Any],
        active: tuple[_Location, ...],
        base: _ResolvedValue,
    ) -> _ResolvedValue:
        resolved = _copy_resolved(base)
        root_span = self._source_span(location)
        if root_span is not None:
            resolved.sources[()] = root_span
        inherits = raw.get("$inherits", _MISSING)
        if inherits is not _MISSING:
            targets = inherits if isinstance(inherits, list | tuple) else [inherits]
            if not targets:
                raise ResolutionError(
                    f"$inherits at {self._format_field(location, '$inherits')} "
                    "must name at least one parent"
                )
            for target in targets:
                if not isinstance(target, str):
                    raise ResolutionError(
                        f"$inherits at {self._format_field(location, '$inherits')} "
                        "must contain string references"
                    )
                parent = self._resolve_reference(target, location, active)
                if not isinstance(parent.value, Mapping):
                    raise ResolutionError(
                        f"$inherits target {target!r} at "
                        f"{self._format_field(location, '$inherits')} "
                        "must resolve to a mapping"
                    )
                resolved = self._deep_merge(resolved, self._without_provenance(parent))

        for key, raw_child in raw.items():
            if key in ("$inherits", "$remove"):
                continue
            child_location = (location[0], (*location[1], key))
            if isinstance(resolved.value.get(key), Mapping) and isinstance(raw_child, Mapping):
                if child_location in active:
                    chain = " -> ".join(
                        self._format_location(item) for item in (*active, child_location)
                    )
                    raise ResolutionError(f"Cyclic $inherits relationship: {chain}")
                child = self._resolve_mapping_over(
                    child_location,
                    raw_child,
                    (*active, child_location),
                    _subvalue(resolved, (key,)),
                )
            else:
                child = self._resolve_location(child_location, active)
            _set_subvalue(resolved, key, child)

        if inherits is not _MISSING:
            child_of = self._resolve_location((location[0], (*location[1], "$inherits")), active)
            _set_subvalue(resolved, "$child_of", child_of)
        if "$remove" in raw:
            remove = self._resolve_location((location[0], (*location[1], "$remove")), active)
            _set_subvalue(resolved, "$remove", remove)
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
                f"$inherits at {self._format_field(origin, '$inherits')} "
                "references missing document "
                f"{document_path!r}"
            )
        tokens = self._decode_pointer(pointer, reference, origin)
        return document_path, tokens

    def _resolve_reference(
        self, reference: str, origin: _Location, active: tuple[_Location, ...]
    ) -> _ResolvedValue:
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
                return self._traverse_value(
                    resolved_value, tokens[token_index + 1 :], reference, origin
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
    ) -> _ResolvedValue:
        inherited: _ResolvedValue | object = _MISSING
        inherits = raw["$inherits"]
        targets = inherits if isinstance(inherits, list | tuple) else [inherits]
        if not targets:
            raise ResolutionError(
                f"$inherits at {self._format_field(location, '$inherits')} "
                "must name at least one parent"
            )
        for target in targets:
            if not isinstance(target, str):
                raise ResolutionError(
                    f"$inherits at {self._format_field(location, '$inherits')} "
                    "must contain string references"
                )
            parent = self._resolve_reference(target, location, (*active, requested))
            if not isinstance(parent.value, Mapping):
                raise ResolutionError(
                    f"$inherits target {target!r} at "
                    f"{self._format_field(location, '$inherits')} "
                    "must resolve to a mapping"
                )
            if key not in parent.value or key in _PROVENANCE_KEYS:
                continue
            parent_value = _subvalue(parent, (key,))
            if (
                isinstance(inherited, _ResolvedValue)
                and isinstance(inherited.value, Mapping)
                and isinstance(parent_value.value, Mapping)
            ):
                inherited = self._deep_merge(inherited, parent_value)
            else:
                inherited = _copy_resolved(parent_value)

        if key not in raw:
            if inherited is _MISSING:
                self._missing_pointer(key, location)
            if self._key_is_removed(raw, key, location, active):
                self._missing_pointer(key, location)
            assert isinstance(inherited, _ResolvedValue)
            return _copy_resolved(inherited)

        raw_value = raw[key]
        if (
            isinstance(inherited, _ResolvedValue)
            and isinstance(inherited.value, Mapping)
            and isinstance(raw_value, Mapping)
        ):
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
        remove = self._resolve_location((location[0], (*location[1], "$remove")), active).value
        keys = remove if isinstance(remove, list | tuple) else [remove]
        return any(item == key for item in keys)

    def _validate_reference_path(self, path: str, origin: _Location) -> str:
        try:
            normalized = self._validate_document_path(path)
        except ResolutionError as error:
            raise ResolutionError(
                f"Invalid $inherits path {path!r} at {self._format_field(origin, '$inherits')}"
            ) from error
        if not normalized.endswith((".yaml", ".yml")):
            raise ResolutionError(
                f"Cross-document $inherits path {path!r} at "
                f"{self._format_field(origin, '$inherits')} must name a YAML file"
            )
        return normalized

    def _decode_pointer(self, pointer: str, reference: str, origin: _Location) -> tuple[str, ...]:
        if pointer == "":
            return ()
        if not pointer.startswith("/"):
            raise ResolutionError(
                f"Invalid JSON pointer in $inherits reference {reference!r} at "
                f"{self._format_field(origin, '$inherits')}"
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
                        f"at {self._format_field(origin, '$inherits')}"
                    )
                output.append("~" if token[index + 1] == "0" else "/")
                index += 2
            decoded.append("".join(output))
        return tuple(decoded)

    def _traverse_value(
        self,
        value: _ResolvedValue,
        tokens: tuple[str, ...],
        reference: str,
        origin: _Location,
    ) -> _ResolvedValue:
        path: list[_PathPart] = []
        current = value.value
        for token in tokens:
            if isinstance(current, Mapping):
                if token not in current:
                    self._missing_pointer(reference, origin)
                current = current[token]
                path.append(token)
            elif isinstance(current, list | tuple):
                index = self._array_index(token, len(current), reference, origin)
                current = current[index]
                path.append(index)
            else:
                self._missing_pointer(reference, origin)
        return _subvalue(value, tuple(path))

    def _array_index(self, token: str, length: int, reference: str, origin: _Location) -> int:
        if not token.isdecimal() or (len(token) > 1 and token.startswith("0")):
            self._missing_pointer(reference, origin)
        index = int(token)
        if index >= length:
            self._missing_pointer(reference, origin)
        return index

    def _missing_pointer(self, reference: str, origin: _Location) -> None:
        raise ResolutionError(
            f"$inherits at {self._format_field(origin, '$inherits')} "
            f"references missing path {reference!r}"
        )

    def _value_at(self, location: _Location) -> Any:
        value: Any = self._documents[location[0]]
        for part in location[1]:
            value = value[part]
        return value

    def _apply_remove(self, value: _ResolvedValue, location: _Location) -> _ResolvedValue:
        remove = value.value.pop("$remove", _MISSING)
        if remove is _MISSING:
            return value
        for path in tuple(value.sources):
            if path[:1] == ("$remove",):
                del value.sources[path]
        keys = remove if isinstance(remove, list | tuple) else [remove]
        for key in keys:
            try:
                value.value.pop(key, None)
                for path in tuple(value.sources):
                    if path[:1] == (key,):
                        del value.sources[path]
            except TypeError as error:
                raise ResolutionError(
                    f"$remove at {self._format_field(location, '$remove')} contains an invalid key"
                ) from error
        return value

    @classmethod
    def _deep_merge(cls, base: _ResolvedValue, override: _ResolvedValue) -> _ResolvedValue:
        result = _copy_resolved(base)
        for key, value in override.value.items():
            child = _subvalue(override, (key,))
            if isinstance(result.value.get(key), Mapping) and isinstance(value, Mapping):
                child = cls._deep_merge(_subvalue(result, (key,)), child)
            else:
                child = _copy_resolved(child)
            _set_subvalue(result, key, child)
        return result

    @classmethod
    def _without_provenance(cls, value: _ResolvedValue) -> _ResolvedValue:
        copied = _copy_resolved(value)
        copied.value = cls._without_nested_provenance(copied.value)
        copied.sources = {
            path: span
            for path, span in copied.sources.items()
            if not any(part in _PROVENANCE_KEYS for part in path)
        }
        return copied

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

    def _set_parent_relationships(
        self,
        documents: dict[str, dict[Any, Any]],
        sources: dict[str, dict[tuple[_PathPart, ...], SourceSpan]],
    ) -> None:
        relationships: list[tuple[_Location, str, SourceSpan | None]] = []
        for document_path in sorted(documents):
            self._collect_relationships(
                documents,
                sources,
                (document_path, ()),
                documents[document_path],
                relationships,
            )

        parent_sources: dict[_Location, list[SourceSpan | None]] = {}
        for parent_location, child_reference, child_source in relationships:
            parent = self._resolved_value_at(documents, parent_location)
            existing = parent.get("$parent_of", _MISSING)
            if existing is _MISSING:
                parent["$parent_of"] = child_reference
            else:
                values = list(existing) if isinstance(existing, list | tuple) else [existing]
                if child_reference not in values:
                    values.append(child_reference)
                parent["$parent_of"] = values[0] if len(values) == 1 else values
            parent_sources.setdefault(parent_location, []).append(child_source)

        for parent_location, spans in parent_sources.items():
            path = (*parent_location[1], "$parent_of")
            entries = sources[parent_location[0]]
            usable = [span for span in spans if span is not None]
            if usable:
                entries[path] = usable[0]
                if len(spans) > 1:
                    for index, span in enumerate(spans):
                        if span is not None:
                            entries[(*path, index)] = span

    def _collect_relationships(
        self,
        documents: dict[str, dict[Any, Any]],
        sources: dict[str, dict[tuple[_PathPart, ...], SourceSpan]],
        location: _Location,
        value: Any,
        relationships: list[tuple[_Location, str, SourceSpan | None]],
    ) -> None:
        if isinstance(value, Mapping):
            child_of = value.get("$child_of", _MISSING)
            if child_of is not _MISSING:
                targets = child_of if isinstance(child_of, list | tuple) else [child_of]
                for index, target in enumerate(targets):
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
                    child_source_path = (*location[1], "$child_of")
                    if isinstance(child_of, list | tuple):
                        child_source_path = (*child_source_path, index)
                    child_source = sources[location[0]].get(child_source_path)
                    relationships.append((parent, self._child_reference(location), child_source))
            for key, child in list(value.items()):
                self._collect_relationships(
                    documents,
                    sources,
                    (location[0], (*location[1], key)),
                    child,
                    relationships,
                )
        elif isinstance(value, list | tuple):
            for index, child in enumerate(value):
                self._collect_relationships(
                    documents,
                    sources,
                    (location[0], (*location[1], index)),
                    child,
                    relationships,
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

    def _source_span(self, location: _Location) -> SourceSpan | None:
        return self._sources[location[0]].at(*location[1])

    def _format_field(self, location: _Location, field: str) -> str:
        return self._format_location((location[0], (*location[1], field)))

    def _format_location(self, location: _Location) -> str:
        span = self._source_span(location)
        prefix = f"{span.label} (" if span is not None else ""
        suffix = ")" if span is not None else ""
        if not location[1]:
            return f"{prefix}{location[0]}#{suffix}"
        tokens = "/".join(self._escape_pointer_part(part) for part in location[1])
        return f"{prefix}{location[0]}#/{tokens}{suffix}"
