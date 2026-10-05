# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Read-only access to raw, unconfigured UnifiedDB records.

This module intentionally does not resolve ``$inherits``, apply architecture
overlays, evaluate configuration conditions, or compile IDL. It exposes the
bundled source records as immutable mappings so those later features can be
added without implying semantics that are not implemented yet.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self

from ruamel.yaml.error import YAMLError

from .errors import (
    DataError,
    ObjectNotFoundError,
    ReferenceError,
    ResolutionError,
    UnknownKindError,
)
from .reference import Reference, ResolvedNode, classify_reference
from .resolver import YamlResolver
from .resources import package_data_root
from .schema import SchemaError, SchemaStore
from .source import (
    IdlSourceProvider,
    ParsedYaml,
    SourceMap,
    SourceSpan,
    SourceText,
    merge_patch_with_sources,
    parse_yaml,
)
from .versions import ExtensionVersion, ExtensionVersionSet, VersionLike

if TYPE_CHECKING:
    from .architecture import ConfiguredArchitecture
    from .configuration import Configuration
    from .progress import ProgressCallback

_KIND_DIRECTORIES = {
    "csr": "csr",
    "exception_code": "exception_code",
    "extension": "ext",
    "instruction": "inst",
    "instruction_opcode": "inst_opcode",
    "instruction_subtype": "inst_subtype",
    "instruction_type": "inst_type",
    "instruction_variable": "inst_var",
    "instruction_variable_type": "inst_var_type",
    "interrupt_code": "interrupt_code",
    "manual": "manual",
    "manual version": "manual_version",
    "parameter": "param",
    "profile": "profile",
    "profile family": "profile_family",
    "profile release": "profile_release",
    "register_file": "register_file",
}

_ALIASES = {
    "csrs": "csr",
    "ext": "extension",
    "extensions": "extension",
    "inst": "instruction",
    "instructions": "instruction",
    "params": "parameter",
    "parameters": "parameter",
    "profiles": "profile",
    "manual_version": "manual version",
    "profile_families": "profile family",
    "profile_family": "profile family",
    "profile_release": "profile release",
    "profile_releases": "profile release",
}


def _freeze(value: Any, active: set[int] | None = None) -> Any:
    if active is None:
        active = set()
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            raise DataError("Recursive YAML aliases are not supported")
        active.add(identity)
        try:
            return MappingProxyType({key: _freeze(item, active) for key, item in value.items()})
        finally:
            active.remove(identity)
    if isinstance(value, list | tuple):
        identity = id(value)
        if identity in active:
            raise DataError("Recursive YAML aliases are not supported")
        active.add(identity)
        try:
            return tuple(_freeze(item, active) for item in value)
        finally:
            active.remove(identity)
    if isinstance(value, set):
        return frozenset(_freeze(item, active) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple | frozenset):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class DatabaseObject(Mapping[Any, Any]):
    """One raw top-level UDB YAML document."""

    name: str
    kind: str
    path: PurePosixPath
    data: Mapping[Any, Any] = field(repr=False)
    sources: SourceMap | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.data, Mapping):
            raise DataError("DatabaseObject data must be a mapping")
        if self.data.get("name") != self.name:
            raise DataError(
                f"DatabaseObject name {self.name!r} does not match data name "
                f"{self.data.get('name')!r}"
            )
        if self.data.get("kind") != self.kind:
            raise DataError(
                f"DatabaseObject kind {self.kind!r} does not match data kind "
                f"{self.data.get('kind')!r}"
            )
        object.__setattr__(self, "data", _freeze(self.data))

    def __getitem__(self, key: Any) -> Any:
        return self.data[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def to_dict(self) -> dict[Any, Any]:
        """Return a mutable copy of this record's YAML data."""
        return _thaw(self.data)

    def source_at(self, *path: str | int) -> SourceSpan | None:
        """Return the exact original YAML span defining a field."""
        return None if self.sources is None else self.sources.at(*path)


class Extension(DatabaseObject):
    """A raw extension record."""

    @property
    def version_set(self) -> ExtensionVersionSet:
        """Return this extension's immutable, numerically ordered releases."""
        values = self.data.get("versions")
        if not isinstance(values, Sequence) or isinstance(values, str | bytes):
            raise DataError(f"Extension {self.name!r} has no valid versions sequence")
        try:
            return ExtensionVersionSet.from_metadata(self.name, values)
        except (TypeError, ValueError) as error:
            raise DataError(
                f"Extension {self.name!r} has invalid version metadata: {error}"
            ) from error

    @property
    def versions(self) -> tuple[ExtensionVersion, ...]:
        return self.version_set.versions

    def version(self, value: VersionLike) -> ExtensionVersion:
        """Return an exact release by version."""
        try:
            result = self.version_set.get(value)
        except (TypeError, ValueError) as error:
            raise ObjectNotFoundError(
                f"Invalid version {value!r} requested for extension {self.name!r}"
            ) from error
        if result is None:
            raise ObjectNotFoundError(f"Extension {self.name!r} has no version {value!r}")
        return result

    def compatible_versions(self, value: VersionLike) -> tuple[ExtensionVersion, ...]:
        """Return releases compatible with the requested version boundary."""
        return self.version_set.compatible_versions(value)

    @property
    def ratified_versions(self) -> tuple[ExtensionVersion, ...]:
        return tuple(version for version in self.versions if version.state == "ratified")

    @property
    def min_version(self) -> ExtensionVersion:
        if not self.versions:
            raise DataError(f"Extension {self.name!r} has no versions")
        return self.versions[0]

    @property
    def max_version(self) -> ExtensionVersion:
        if not self.versions:
            raise DataError(f"Extension {self.name!r} has no versions")
        return self.versions[-1]

    @property
    def min_ratified_version(self) -> ExtensionVersion | None:
        return self.ratified_versions[0] if self.ratified_versions else None


class Instruction(DatabaseObject):
    """A raw instruction record."""


class Csr(DatabaseObject):
    """A raw CSR record."""


class Profile(DatabaseObject):
    """A raw profile record."""


_RECORD_TYPES: dict[str, type[DatabaseObject]] = {
    "extension": Extension,
    "instruction": Instruction,
    "csr": Csr,
    "profile": Profile,
}


class Database:
    """A lazy, read-only collection of raw UDB ISA records."""

    def __init__(self, isa_root: Any, *, schemas_root: Any | None = None) -> None:
        self._isa_root = isa_root
        self._schemas_root = schemas_root
        self._objects: dict[str, tuple[DatabaseObject, ...]] = {}
        self._object_maps: dict[str, Mapping[str, DatabaseObject]] = {}

    @classmethod
    def bundled(cls) -> Self:
        """Open the standard ISA and schemas bundled in the installed package."""
        try:
            data_root = package_data_root()
        except metadata.PackageNotFoundError as error:
            raise DataError("The installed udb distribution could not be located") from error
        isa_root = data_root.joinpath("isa")
        if not isa_root.is_dir():
            raise DataError(f"Bundled ISA data directory is missing: {isa_root}")
        schemas_root = data_root.joinpath("schemas")
        return cls(isa_root, schemas_root=schemas_root if schemas_root.is_dir() else None)

    @classmethod
    def from_path(cls, path: str | Path, *, schemas_path: str | Path | None = None) -> Self:
        """Open a source ISA directory without resolving or modifying its YAML."""
        isa_root = Path(path).resolve()
        if not isa_root.is_dir():
            raise DataError(f"ISA data directory does not exist: {isa_root}")
        schema_root = Path(schemas_path).resolve() if schemas_path is not None else None
        if schema_root is not None and not schema_root.is_dir():
            raise DataError(f"Schema directory does not exist: {schema_root}")
        return cls(isa_root, schemas_root=schema_root)

    @property
    def schemas_root(self) -> Any | None:
        """The schema resource or path associated with this database, if any."""
        return self._schemas_root

    @property
    def isa_root(self) -> Any:
        """The source/resource root backing this database."""
        return self._isa_root

    @property
    def is_resolved(self) -> bool:
        """Whether this database has completed YAML inheritance resolution."""
        return False

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted(_KIND_DIRECTORIES))

    def objects(self, kind: str | None = None) -> tuple[DatabaseObject, ...]:
        """Return records of *kind*, or every record when *kind* is omitted."""
        if kind is None:
            return tuple(obj for known_kind in self.kinds for obj in self.objects(known_kind))

        canonical_kind = self._canonical_kind(kind)
        if canonical_kind not in self._objects:
            self._load_kind(canonical_kind)
        return self._objects[canonical_kind]

    def get(self, kind: str, name: str) -> DatabaseObject:
        """Return a named record, raising a descriptive error when absent."""
        canonical_kind = self._canonical_kind(kind)
        if canonical_kind not in self._object_maps:
            self._load_kind(canonical_kind)
        try:
            return self._object_maps[canonical_kind][name]
        except KeyError as error:
            raise ObjectNotFoundError(f"No {canonical_kind!r} object named {name!r}") from error

    @property
    def extensions(self) -> tuple[Extension, ...]:
        return self.objects("extension")  # type: ignore[return-value]

    @property
    def instructions(self) -> tuple[Instruction, ...]:
        return self.objects("instruction")  # type: ignore[return-value]

    @property
    def csrs(self) -> tuple[Csr, ...]:
        return self.objects("csr")  # type: ignore[return-value]

    @property
    def profiles(self) -> tuple[Profile, ...]:
        return self.objects("profile")  # type: ignore[return-value]

    def extension(self, name: str) -> Extension:
        return self.get("extension", name)  # type: ignore[return-value]

    def instruction(self, name: str) -> Instruction:
        return self.get("instruction", name)  # type: ignore[return-value]

    def csr(self, name: str) -> Csr:
        return self.get("csr", name)  # type: ignore[return-value]

    def profile(self, name: str) -> Profile:
        return self.get("profile", name)  # type: ignore[return-value]

    def resolve(
        self,
        *,
        overlays: Sequence[str | Path] = (),
        validate: bool = False,
        progress: ProgressCallback | None = None,
    ) -> ResolvedDatabase:
        """Resolve inheritance after applying overlay trees in order.

        Overlay files are matched to source documents by their POSIX path
        relative to each overlay root and combined with JSON Merge Patch.
        Schema validation is optional and never inserts defaults or rewrites
        declared schema URIs.
        """
        from .progress import report_progress

        total = len(overlays) + 3
        completed = 0
        report_progress(
            progress,
            "database-resolution",
            "Reading database documents",
            completed=completed,
            total=total,
        )
        source_texts: dict[tuple[str, str], str] = {}
        documents, source_maps = self._load_documents(self._isa_root, source_texts=source_texts)
        idl_sources = self._load_idl_sources(self._isa_root, layer="source")
        idl_source_layers = {
            (source.layer, source.source): source for source in idl_sources.values()
        }
        idl_source_roots = (
            {"source": self._isa_root.resolve().as_posix()}
            if isinstance(self._isa_root, Path)
            else {}
        )
        for overlay_index, overlay in enumerate(overlays):
            overlay_root = Path(overlay).resolve()
            if not overlay_root.is_dir():
                raise ResolutionError(f"Overlay ISA directory does not exist: {overlay_root}")
            patches, patch_sources = self._load_documents(
                overlay_root,
                allow_non_mapping=True,
                layer=f"overlay[{overlay_index}]",
                source_texts=source_texts,
            )
            layer = f"overlay[{overlay_index}]"
            overlay_idl = self._load_idl_sources(overlay_root, layer=layer)
            idl_sources.update(overlay_idl)
            idl_source_layers.update(
                {(source.layer, source.source): source for source in overlay_idl.values()}
            )
            idl_source_roots[layer] = overlay_root.as_posix()
            for path, patch in patches.items():
                base_sources = source_maps.get(path, SourceMap(path))
                merged, merged_sources = merge_patch_with_sources(
                    documents.get(path), patch, base_sources, patch_sources[path]
                )
                if not isinstance(merged, Mapping):
                    raise ResolutionError(
                        f"{patch_sources[path].at().label}: overlay document {path} "
                        "must produce a top-level mapping"
                    )
                documents[path] = dict(merged)
                source_maps[path] = merged_sources
            completed += 1
            report_progress(
                progress,
                "database-resolution",
                "Applying database overlays",
                completed=completed,
                total=total,
            )

        completed += 1
        report_progress(
            progress,
            "database-resolution",
            "Resolving database inheritance",
            completed=completed,
            total=total,
        )
        result = YamlResolver(documents, sources=source_maps).resolve_with_sources()
        resolved = ResolvedDatabase(
            result.documents,
            schemas_root=self._schemas_root,
            sources=result.sources,
            source_texts=source_texts,
            idl_sources=idl_sources,
            idl_source_layers=idl_source_layers,
            idl_source_roots=idl_source_roots,
        )
        resolved._validate_duplicate_identities()
        completed += 1
        if validate:
            resolved.validate(progress=progress)
        report_progress(
            progress,
            "database-resolution",
            "Resolving database",
            completed=total,
            total=total,
            finished=True,
        )
        return resolved

    def _canonical_kind(self, kind: str) -> str:
        normalized = kind.strip().lower().replace("-", "_")
        normalized = _ALIASES.get(normalized, normalized)
        if normalized not in _KIND_DIRECTORIES:
            available = ", ".join(self.kinds)
            raise UnknownKindError(f"Unknown object kind {kind!r}; available kinds: {available}")
        return normalized

    def _load_kind(self, kind: str) -> None:
        directory = self._isa_root.joinpath(_KIND_DIRECTORIES[kind])
        records: list[DatabaseObject] = []
        by_name: dict[str, DatabaseObject] = {}

        if directory.is_dir():
            for resource, relative_path in sorted(
                self._yaml_files(directory, PurePosixPath(_KIND_DIRECTORIES[kind])),
                key=lambda entry: entry[1].as_posix(),
            ):
                record = self._load_record(resource, relative_path, expected_kind=kind)
                if record.name in by_name:
                    previous = by_name[record.name]
                    raise DataError(
                        f"Duplicate {kind!r} name {record.name!r} in "
                        f"{previous.path} and {record.path}"
                    )
                by_name[record.name] = record
                records.append(record)

        records.sort(key=lambda record: (record.name, record.path.as_posix()))
        self._objects[kind] = tuple(records)
        self._object_maps[kind] = MappingProxyType(by_name)

    def _load_documents(
        self,
        root: Any,
        *,
        allow_non_mapping: bool = False,
        layer: str = "source",
        source_texts: dict[tuple[str, str], str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, SourceMap]]:
        documents: dict[str, Any] = {}
        sources: dict[str, SourceMap] = {}
        for resource, relative_path in sorted(
            self._yaml_files(root, PurePosixPath()), key=lambda entry: entry[1].as_posix()
        ):
            path = relative_path.as_posix()
            parsed = self._parse_yaml(
                resource, relative_path, layer=layer, source_texts=source_texts
            )
            data = parsed.value
            if not allow_non_mapping and not isinstance(data, Mapping):
                raise DataError(f"UDB document {relative_path} must contain a mapping")
            documents[path] = _thaw(_freeze(data))
            sources[path] = parsed.sources
        return documents, sources

    def _yaml_files(self, directory: Any, relative_dir: PurePosixPath):
        yield from self._resource_files(directory, relative_dir, (".yaml", ".yml"))

    def _resource_files(
        self, directory: Any, relative_dir: PurePosixPath, suffixes: tuple[str, ...]
    ):
        for child in directory.iterdir():
            relative_path = relative_dir / child.name
            if child.is_dir():
                yield from self._resource_files(child, relative_path, suffixes)
            elif child.name.endswith(suffixes):
                yield child, relative_path

    def _load_idl_sources(self, root: Any, *, layer: str) -> dict[str, SourceText]:
        sources: dict[str, SourceText] = {}
        for resource, relative_path in sorted(
            self._resource_files(root, PurePosixPath(), (".isa", ".idl")),
            key=lambda entry: entry[1].as_posix(),
        ):
            try:
                with resource.open("r", encoding="utf-8") as stream:
                    text = stream.read()
            except (OSError, UnicodeError) as error:
                raise DataError(f"Cannot read UDB IDL source {relative_path}: {error}") from error
            path = relative_path.as_posix()
            sources[path] = SourceText(path, text, layer)
        return sources

    def _load_record(
        self, resource: Any, relative_path: PurePosixPath, *, expected_kind: str
    ) -> DatabaseObject:
        parsed = self._parse_yaml(resource, relative_path)
        data = parsed.value

        if not isinstance(data, Mapping):
            raise DataError(f"UDB document {relative_path} must contain a mapping")
        return self._record_from_data(
            data, relative_path, expected_kind=expected_kind, sources=parsed.sources
        )

    def _parse_yaml(
        self,
        resource: Any,
        relative_path: PurePosixPath,
        *,
        layer: str = "source",
        source_texts: dict[tuple[str, str], str] | None = None,
    ) -> ParsedYaml:
        try:
            with resource.open("r", encoding="utf-8") as stream:
                text = stream.read()
            parsed = parse_yaml(text, source=relative_path.as_posix(), layer=layer)
            if source_texts is not None:
                source_texts[(layer, relative_path.as_posix())] = text
            return parsed
        except (OSError, UnicodeError, YAMLError) as error:
            raise DataError(f"Cannot parse UDB YAML document {relative_path}: {error}") from error

    @staticmethod
    def _record_from_data(
        data: Mapping[Any, Any],
        relative_path: PurePosixPath,
        *,
        expected_kind: str,
        sources: SourceMap | None = None,
    ) -> DatabaseObject:
        name = data.get("name")
        kind = data.get("kind")
        if not isinstance(name, str) or not name:
            raise DataError(f"UDB document {relative_path} has no non-empty string 'name'")
        if not isinstance(kind, str) or not kind:
            raise DataError(f"UDB document {relative_path} has no non-empty string 'kind'")
        if kind != expected_kind:
            raise DataError(
                f"UDB document {relative_path} declares kind {kind!r}; "
                f"expected {expected_kind!r} for its directory"
            )
        if PurePosixPath(relative_path).stem != name:
            raise DataError(
                f"UDB document {relative_path} declares name {name!r}; "
                "the name must match its filename"
            )

        record_type = _RECORD_TYPES.get(kind, DatabaseObject)
        try:
            return record_type(name=name, kind=kind, path=relative_path, data=data, sources=sources)
        except DataError as error:
            raise DataError(f"Cannot load UDB YAML document {relative_path}: {error}") from error


class ResolvedDatabase(Database):
    """An immutable database after overlays and YAML inheritance resolution."""

    def __init__(
        self,
        documents: Mapping[str, Mapping[Any, Any]],
        *,
        schemas_root: Any | None = None,
        sources: Mapping[str, SourceMap] | None = None,
        source_texts: Mapping[tuple[str, str], str] | None = None,
        idl_sources: Mapping[str, SourceText] | None = None,
        idl_source_layers: Mapping[tuple[str, str], SourceText] | None = None,
        idl_source_roots: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(None, schemas_root=schemas_root)
        copied: dict[str, Mapping[Any, Any]] = {}
        for path, document in documents.items():
            if not isinstance(document, Mapping):
                raise ResolutionError(f"Resolved YAML document {path} is not a mapping")
            copied[path] = _freeze(document)
        self._resolved_documents = MappingProxyType(copied)
        self._resolved_sources = MappingProxyType(
            {
                path: sources[path] if sources is not None and path in sources else SourceMap(path)
                for path in copied
            }
        )
        captured_texts: dict[tuple[str, str], str] = {}
        for key, text in (source_texts or {}).items():
            if (
                not isinstance(key, tuple)
                or len(key) != 2
                or any(not isinstance(part, str) or not part for part in key)
                or not isinstance(text, str)
            ):
                raise DataError(
                    "Source texts require (layer, source) string keys and string values"
                )
            captured_texts[key] = text
        self._resolved_source_texts = MappingProxyType(captured_texts)
        self._idl_source_provider = IdlSourceProvider(
            idl_sources, layers=idl_source_layers, roots=idl_source_roots
        )

    @property
    def is_resolved(self) -> bool:
        return True

    @property
    def documents(self) -> Mapping[str, Mapping[Any, Any]]:
        """Resolved documents keyed by their relative POSIX source paths."""
        return self._resolved_documents

    @property
    def source_maps(self) -> Mapping[str, SourceMap]:
        """Field-level provenance keyed by resolved document path."""
        return self._resolved_sources

    @property
    def idl_sources(self) -> Mapping[str, SourceText]:
        """Captured `.isa`/`.idl` sources, with later overlay files replacing earlier ones."""
        return self._idl_source_provider.sources

    @property
    def idl_source_layers(self) -> Mapping[tuple[str, str], SourceText]:
        """All captured IDL versions keyed by their original layer and relative path."""
        return self._idl_source_provider.layers

    @property
    def idl_source_roots(self) -> Mapping[str, str]:
        """Captured root provenance, used lexically without reopening any directory."""
        return self._idl_source_provider.roots

    def resolve_idl_include(self, owner: SourceText, filename: str) -> SourceText:
        """Resolve a relative include to an explicitly captured original source."""
        return self._idl_source_provider.include(owner, filename)

    def source_text(self, source: str, *, layer: str = "source") -> str:
        """Return original YAML text for a defining span, without reading a source tree."""
        try:
            return self._resolved_source_texts[(layer, source)]
        except KeyError as error:
            raise DataError(f"No captured YAML source {layer}:{source}") from error

    def source_at(self, document: str, *path: str | int) -> SourceSpan | None:
        """Return the exact original YAML span defining a resolved value."""
        try:
            return self._resolved_sources[document].at(*path)
        except KeyError as error:
            raise ObjectNotFoundError(f"No resolved YAML document {document!r}") from error

    def node(self, document: str, *path: str | int) -> ResolvedNode:
        """Return an immutable, source-aware node at a resolved document path."""
        self._value_at(document, tuple(path))
        return ResolvedNode(document, tuple(path), self)

    def reference_at(self, document: str, *path: str | int) -> Reference:
        """Return the typed, lazy `$ref` stored in the mapping at *path*."""
        node = self.node(document, *path)
        value = node.value
        if not isinstance(value, Mapping) or "$ref" not in value:
            raise ReferenceError(f"{document}{node.pointer}: value is not a reference mapping")
        uri = value["$ref"]
        if not isinstance(uri, str) or not uri:
            source = self.source_at(document, *path, "$ref")
            location = source.label if source is not None else f"{document}{node.pointer}"
            raise ReferenceError(f"{location}: '$ref' must be a non-empty string")
        return classify_reference(node, uri)

    def references(self) -> tuple[Reference, ...]:
        """Enumerate data and schema references without following their targets."""
        found: list[Reference] = []

        def visit(document: str, value: Any, path: tuple[str | int, ...]) -> None:
            if isinstance(value, Mapping):
                if "$ref" in value:
                    found.append(self.reference_at(document, *path))
                for key, child in value.items():
                    visit(document, child, (*path, key))
            elif isinstance(value, tuple):
                for index, child in enumerate(value):
                    visit(document, child, (*path, index))

        for document in sorted(self._resolved_documents):
            visit(document, self._resolved_documents[document], ())
        return tuple(found)

    def _value_at(self, document: str, path: tuple[str | int, ...]) -> Any:
        try:
            value: Any = self._resolved_documents[document]
        except KeyError as error:
            raise ObjectNotFoundError(f"No resolved YAML document {document!r}") from error
        for part in path:
            if isinstance(value, Mapping):
                try:
                    value = value[part]
                except (KeyError, TypeError) as error:
                    pointer = ResolvedNode(document, path, self).pointer
                    raise ObjectNotFoundError(
                        f"No resolved value at {document}{pointer}"
                    ) from error
            elif isinstance(value, tuple) and type(part) is int and 0 <= part < len(value):
                value = value[part]
            else:
                pointer = ResolvedNode(document, path, self).pointer
                raise ObjectNotFoundError(f"No resolved value at {document}{pointer}")
        return value

    def resolve(
        self,
        *,
        overlays: Sequence[str | Path] = (),
        validate: bool = False,
        progress: ProgressCallback | None = None,
    ) -> ResolvedDatabase:
        if overlays:
            raise ResolutionError("Cannot apply source overlays to an already resolved database")
        if validate:
            self.validate(progress=progress)
        return self

    def validate(self, *, progress: ProgressCallback | None = None) -> None:
        """Validate every resolved document against its declared schema."""
        from .progress import report_progress

        if self._schemas_root is None:
            raise SchemaError("Resolved database has no schema directory")
        store = SchemaStore(self._schemas_root)
        total = len(self._resolved_documents)
        for completed, (path, document) in enumerate(self._resolved_documents.items(), 1):
            store.validate(document, source=self._resolved_sources[path])
            report_progress(
                progress,
                "database-validation",
                "Validating database documents",
                completed=completed,
                total=total,
                finished=completed == total,
            )

    def configure(self, configuration: Configuration) -> ConfiguredArchitecture:
        """Create an immutable configured view from an explicit declaration."""

        from .architecture import ConfiguredArchitecture
        from .configuration import Configuration

        if not isinstance(configuration, Configuration):
            raise TypeError("ResolvedDatabase.configure() requires a Configuration")
        return ConfiguredArchitecture(self, configuration)

    def _validate_duplicate_identities(self) -> None:
        identities: dict[tuple[str, str], str] = {}
        for path, document in self._resolved_documents.items():
            kind = document.get("kind")
            name = document.get("name")
            if not isinstance(kind, str) or not isinstance(name, str):
                continue
            identity = kind, name
            previous = identities.get(identity)
            if previous is not None:
                span = self.source_at(path, "name")
                location = span.label if span is not None else path
                raise ResolutionError(
                    f"{location}: duplicate {kind!r} identity {name!r}; first defined in {previous}"
                )
            first = self.source_at(path, "name")
            identities[identity] = first.label if first is not None else path

    def write(self, output_dir: str | Path) -> tuple[Path, ...]:
        """Write this database as a deterministic, version-stamped YAML tree."""
        from .serialization import write_resolved_database

        return write_resolved_database(self, output_dir)

    def _load_kind(self, kind: str) -> None:
        directory = _KIND_DIRECTORIES[kind]
        records: list[DatabaseObject] = []
        by_name: dict[str, DatabaseObject] = {}
        for path, frozen_data in self._resolved_documents.items():
            relative_path = PurePosixPath(path)
            if not relative_path.parts or relative_path.parts[0] != directory:
                continue
            data = _thaw(frozen_data)
            record = self._record_from_data(
                data,
                relative_path,
                expected_kind=kind,
                sources=self._resolved_sources[path],
            )
            if record.name in by_name:
                previous = by_name[record.name]
                raise DataError(
                    f"Duplicate {kind!r} name {record.name!r} in {previous.path} and {record.path}"
                )
            by_name[record.name] = record
            records.append(record)

        records.sort(key=lambda record: (record.name, record.path.as_posix()))
        self._objects[kind] = tuple(records)
        self._object_maps[kind] = MappingProxyType(by_name)
