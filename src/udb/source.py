# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Immutable YAML source locations and comments."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from posixpath import dirname, isabs, join, normpath
from types import MappingProxyType
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.nodes import MappingNode, Node, SequenceNode

from .errors import DataError

type PathPart = str | int
type ValuePath = tuple[PathPart, ...]


@dataclass(frozen=True, slots=True)
class SourceText:
    """A captured source file, independent of its original resource or directory."""

    source: str
    text: str = field(repr=False)
    layer: str = "source"

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source:
            raise DataError("SourceText source must be a non-empty string")
        if not isinstance(self.text, str):
            raise DataError("SourceText text must be a string")
        if not isinstance(self.layer, str) or not self.layer:
            raise DataError("SourceText layer must be a non-empty string")

    @property
    def label(self) -> str:
        return self.source if self.layer == "source" else f"{self.layer}:{self.source}"


@dataclass(frozen=True, slots=True, init=False)
class IdlSourceProvider:
    """Captured effective and layered IDL files with lexical include provenance."""

    sources: Mapping[str, SourceText]
    layers: Mapping[tuple[str, str], SourceText]
    roots: Mapping[str, str]
    _origins: Mapping[str, tuple[SourceText, ...]] = field(repr=False)

    def __init__(
        self,
        sources: Mapping[str, SourceText] | None = None,
        *,
        layers: Mapping[tuple[str, str], SourceText] | None = None,
        roots: Mapping[str, str] | None = None,
    ) -> None:
        effective: dict[str, SourceText] = {}
        captured: dict[tuple[str, str], SourceText] = {}
        for path, source in (sources or {}).items():
            if (
                not isinstance(source, SourceText)
                or path != source.source
                or not self._relative_path(path)
            ):
                raise DataError("IDL sources require paths matching their SourceText source")
            effective[path] = source
            captured[(source.layer, path)] = source
        for key, source in (layers or {}).items():
            if (
                not isinstance(key, tuple)
                or len(key) != 2
                or not isinstance(source, SourceText)
                or key != (source.layer, source.source)
                or not self._relative_path(source.source)
            ):
                raise DataError(
                    "Layered IDL sources require (layer, path) keys matching their SourceText"
                )
            if key in captured and captured[key] != source:
                raise DataError(f"Conflicting captured IDL source {source.label}")
            captured[key] = source
        root_paths: dict[str, str] = {}
        for layer, root in (roots or {}).items():
            if (
                not isinstance(layer, str)
                or not layer
                or not isinstance(root, str)
                or not isabs(root)
                or "\\" in root
            ):
                raise DataError("IDL source roots require layer keys and absolute POSIX paths")
            root_paths[layer] = normpath(root)
        origins: dict[str, list[SourceText]] = {}
        for (layer, path), source in captured.items():
            if layer in root_paths:
                origins.setdefault(join(root_paths[layer], path), []).append(source)
        object.__setattr__(self, "sources", MappingProxyType(effective))
        object.__setattr__(self, "layers", MappingProxyType(captured))
        object.__setattr__(self, "roots", MappingProxyType(root_paths))
        object.__setattr__(
            self,
            "_origins",
            MappingProxyType({key: tuple(value) for key, value in origins.items()}),
        )

    @staticmethod
    def _relative_path(path: Any) -> bool:
        return (
            isinstance(path, str)
            and bool(path)
            and "\\" not in path
            and not isabs(path)
            and path not in (".", "..")
            and not path.startswith("../")
            and normpath(path) == path
        )

    def include(self, owner: SourceText, filename: str) -> SourceText:
        """Resolve only captured identities; root paths are metadata, never reopened."""
        if (
            not isinstance(owner, SourceText)
            or self.layers.get((owner.layer, owner.source)) != owner
        ):
            raise DataError("IDL include owner must be a captured source")
        if not isinstance(filename, str) or not filename or isabs(filename) or "\\" in filename:
            raise DataError(f"IDL include escapes the source provider: {filename!r}")
        relative = normpath(join(dirname(owner.source), filename))
        root = self.roots.get(owner.layer)
        if root is not None:
            origin = normpath(join(root, dirname(owner.source), filename))
            candidates = self._origins.get(origin, ())
            same_layer = next(
                (source for source in candidates if source.layer == owner.layer), None
            )
            if same_layer is not None:
                return same_layer
            if len(candidates) == 1:
                return candidates[0]
            if candidates:
                raise DataError(f"Ambiguous captured IDL include {filename!r} from {owner.label}")
            rootless = [
                source.label
                for (layer, path), source in self.layers.items()
                if path == relative and layer not in self.roots
            ]
            if rootless:
                raise DataError(
                    f"No captured physical origin for IDL include {filename!r} "
                    f"from {owner.label}; supply idl_source_roots provenance for "
                    f"{', '.join(rootless)}"
                )
        elif self._relative_path(relative):
            source = self.layers.get((owner.layer, relative), self.sources.get(relative))
            if source is not None:
                return source
        if not self._relative_path(relative):
            raise DataError(f"IDL include escapes the source provider: {filename!r}")
        raise DataError(f"Missing captured IDL source {relative!r}, required by {owner.label}")


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Half-open, one-based source range for one YAML value."""

    source: str
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    style: str | None = None
    comments: tuple[str, ...] = ()
    layer: str = "source"

    @property
    def label(self) -> str:
        prefix = "" if self.layer == "source" else f"{self.layer}:"
        location = f"{prefix}{self.source}"
        if self.start_line is not None:
            location += f":{self.start_line}"
            if self.start_column is not None:
                location += f":{self.start_column}"
        return location


@dataclass(frozen=True, slots=True, init=False)
class SourceMap(Mapping[ValuePath, SourceSpan]):
    """Immutable mapping from value paths to their actual defining spans."""

    document: str
    _entries: Mapping[ValuePath, SourceSpan] = field(repr=False)
    layer: str

    def __init__(
        self,
        document: str,
        entries: Mapping[ValuePath, SourceSpan] | None = None,
        *,
        layer: str = "source",
    ) -> None:
        object.__setattr__(self, "document", document)
        object.__setattr__(self, "layer", layer)
        object.__setattr__(self, "_entries", MappingProxyType(dict(entries or {})))

    def __getitem__(self, path: ValuePath) -> SourceSpan:
        return self._entries[path]

    def __iter__(self) -> Iterator[ValuePath]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def at(self, *path: PathPart) -> SourceSpan | None:
        """Return the exact defining span for *path*, without guessing."""
        return self._entries.get(tuple(path))

    def nearest(self, *path: PathPart) -> SourceSpan | None:
        """Return the nearest enclosing span for diagnostic fallback."""
        current = tuple(path)
        while True:
            span = self._entries.get(current)
            if span is not None:
                return span
            if not current:
                return None
            current = current[:-1]

    def subtree(self, path: ValuePath) -> dict[ValuePath, SourceSpan]:
        length = len(path)
        return {key[length:]: span for key, span in self._entries.items() if key[:length] == path}


@dataclass(frozen=True, slots=True)
class ParsedYaml:
    value: Any
    sources: SourceMap


def _comments(value: Any, *, max_line: int | None = None) -> tuple[str, ...]:
    found: list[str] = []

    def collect(item: Any) -> None:
        if item is None:
            return
        token_value = getattr(item, "value", None)
        if isinstance(token_value, str) and token_value.startswith("#"):
            start_line = getattr(getattr(item, "start_mark", None), "line", None)
            for offset, line in enumerate(token_value.splitlines()):
                if max_line is None or start_line is None or start_line + offset <= max_line:
                    found.append(line)
            return
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for child in item:
                collect(child)

    collect(value)
    return tuple(found)


def _preceding_comments(node: Node, lines: tuple[str, ...]) -> tuple[str, ...]:
    index = node.start_mark.line - 1
    found: list[str] = []
    while index >= 0:
        stripped = lines[index].strip()
        if not stripped:
            index -= 1
            continue
        if not stripped.startswith("#"):
            break
        found.append(stripped)
        index -= 1
    return tuple(reversed(found))


def _span(
    node: Node,
    source: str,
    layer: str,
    lines: tuple[str, ...],
    leading_comments: tuple[str, ...] = (),
) -> SourceSpan:
    comments = (
        *_preceding_comments(node, lines),
        *leading_comments,
        *_comments(getattr(node, "comment", None), max_line=node.end_mark.line),
    )
    return SourceSpan(
        source=source,
        start_line=node.start_mark.line + 1,
        start_column=node.start_mark.column + 1,
        end_line=node.end_mark.line + 1,
        end_column=node.end_mark.column + 1,
        style=getattr(node, "style", None),
        comments=tuple(dict.fromkeys(comments)),
        layer=layer,
    )


def _collect_sources(
    node: Node,
    value: Any,
    source: str,
    layer: str,
    path: ValuePath,
    entries: dict[ValuePath, SourceSpan],
    active: set[int],
    lines: tuple[str, ...],
    *,
    record_root: bool = True,
    leading_comments: tuple[str, ...] = (),
) -> None:
    identity = id(node)
    if identity in active:
        raise DataError(f"{source}: Recursive YAML aliases are not supported")
    if record_root:
        entries[path] = _span(node, source, layer, lines, leading_comments)
    if isinstance(node, MappingNode):
        active.add(identity)
        try:
            remaining = list(value)
            merge_values = [
                value_node
                for key_node, value_node in node.value
                if key_node.tag == "tag:yaml.org,2002:merge"
            ]
            for value_node in merge_values:
                merge_nodes = (
                    reversed(value_node.value)
                    if isinstance(value_node, SequenceNode)
                    else (value_node,)
                )
                for merge_node in merge_nodes:
                    _collect_sources(
                        merge_node,
                        _construct_node(merge_node),
                        source,
                        layer,
                        path,
                        entries,
                        active,
                        lines,
                        record_root=False,
                    )
            for key_node, value_node in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    continue
                key = _matching_key(key_node, remaining)
                child = value[key]
                remaining.remove(key)
                child_path = (*path, key)
                for existing in tuple(entries):
                    if existing[: len(child_path)] == child_path:
                        del entries[existing]
                _collect_sources(
                    value_node,
                    child,
                    source,
                    layer,
                    child_path,
                    entries,
                    active,
                    lines,
                    leading_comments=_comments(getattr(key_node, "comment", None)),
                )
        finally:
            active.remove(identity)
    elif isinstance(node, SequenceNode):
        active.add(identity)
        try:
            for index, (child, value_node) in enumerate(zip(value, node.value, strict=True)):
                _collect_sources(
                    value_node,
                    child,
                    source,
                    layer,
                    (*path, index),
                    entries,
                    active,
                    lines,
                )
        finally:
            active.remove(identity)


def _construct_node(node: Node) -> Any:
    return YAML(typ="safe").constructor.construct_object(node, deep=True)


def _matching_key(node: Node, candidates: list[Any]) -> Any:
    constructed = _construct_node(node)
    matching = [
        candidate
        for candidate in candidates
        if type(candidate) is type(constructed) and candidate == constructed
    ]
    if len(matching) == 1:
        return matching[0]
    raise DataError(f"Cannot correlate YAML mapping key {node.value!r} with parsed data")


def parse_yaml(text: str, *, source: str, layer: str = "source") -> ParsedYaml:
    """Safely parse YAML and collect locations/comments without changing values."""
    safe = YAML(typ="safe")
    value = safe.load(text)
    syntax = YAML(typ="rt").compose(text)
    entries: dict[ValuePath, SourceSpan] = {}
    if syntax is not None:
        _collect_sources(syntax, value, source, layer, (), entries, set(), tuple(text.splitlines()))
    return ParsedYaml(value, SourceMap(source, entries, layer=layer))


def synthetic_source_map(document: str, value: Any) -> SourceMap:
    """Create path-only provenance for callers supplying in-memory documents."""
    span = SourceSpan(document)
    entries: dict[ValuePath, SourceSpan] = {}

    def visit(item: Any, path: ValuePath, active: set[int]) -> None:
        entries[path] = span
        if isinstance(item, Mapping):
            identity = id(item)
            if identity in active:
                raise DataError(f"{document}: Recursive document values are not supported")
            active.add(identity)
            try:
                for key, child in item.items():
                    visit(child, (*path, key), active)
            finally:
                active.remove(identity)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            identity = id(item)
            if identity in active:
                raise DataError(f"{document}: Recursive document values are not supported")
            active.add(identity)
            try:
                for index, child in enumerate(item):
                    visit(child, (*path, index), active)
            finally:
                active.remove(identity)

    visit(value, (), set())
    return SourceMap(document, entries)


def merge_patch_with_sources(
    base: Any,
    patch: Any,
    base_sources: SourceMap,
    patch_sources: SourceMap,
) -> tuple[Any, SourceMap]:
    """Apply JSON Merge Patch while retaining the defining span of each result value."""

    def rebase(
        source_map: SourceMap, source_path: ValuePath, destination: ValuePath
    ) -> dict[ValuePath, SourceSpan]:
        return {
            (*destination, *relative): span
            for relative, span in source_map.subtree(source_path).items()
        }

    def merge(
        target: Any,
        overlay: Any,
        target_path: ValuePath,
        overlay_path: ValuePath,
        output_path: ValuePath,
    ) -> tuple[Any, dict[ValuePath, SourceSpan]]:
        if not isinstance(overlay, Mapping):
            return deepcopy(overlay), rebase(patch_sources, overlay_path, output_path)

        target_is_mapping = isinstance(target, Mapping)
        result = deepcopy(target) if target_is_mapping else {}
        entries = (
            rebase(base_sources, target_path, output_path)
            if target_is_mapping
            else rebase(patch_sources, overlay_path, output_path)
        )
        if output_path not in entries:
            span = patch_sources.at(*overlay_path)
            if span is not None:
                entries[output_path] = span

        for key, value in overlay.items():
            child_output = (*output_path, key)
            for existing in tuple(entries):
                if existing[: len(child_output)] == child_output:
                    del entries[existing]
            if value is None:
                result.pop(key, None)
                continue
            merged, child_entries = merge(
                result.get(key),
                value,
                (*target_path, key),
                (*overlay_path, key),
                child_output,
            )
            result[key] = merged
            entries.update(child_entries)
        return result, entries

    value, entries = merge(base, patch, (), (), ())
    return value, SourceMap(base_sources.document, entries)
