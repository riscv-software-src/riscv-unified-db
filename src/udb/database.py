# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Read-only access to raw, unconfigured UnifiedDB records.

This module intentionally does not resolve ``$inherits``, apply architecture
overlays, evaluate configuration conditions, or compile IDL. It exposes the
bundled source records as immutable mappings so those later features can be
added without implying semantics that are not implemented yet.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from importlib import metadata, resources
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Self

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .errors import DataError, ObjectNotFoundError, UnknownKindError

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


class Extension(DatabaseObject):
    """A raw extension record."""


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
        self._yaml = YAML(typ="safe")

    @classmethod
    def bundled(cls) -> Self:
        """Open the standard ISA and schemas bundled in the installed package."""
        data_root = resources.files("udb").joinpath("_data")
        if not data_root.joinpath("isa").is_dir():
            try:
                data_root = metadata.distribution("udb").locate_file("udb/_data")
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

    def _yaml_files(self, directory: Any, relative_dir: PurePosixPath):
        for child in directory.iterdir():
            relative_path = relative_dir / child.name
            if child.is_dir():
                yield from self._yaml_files(child, relative_path)
            elif child.name.endswith((".yaml", ".yml")):
                yield child, relative_path

    def _load_record(
        self, resource: Any, relative_path: PurePosixPath, *, expected_kind: str
    ) -> DatabaseObject:
        try:
            with resource.open("r", encoding="utf-8") as stream:
                data = self._yaml.load(stream)
        except (OSError, UnicodeError, YAMLError) as error:
            raise DataError(f"Cannot parse UDB YAML document {relative_path}: {error}") from error

        if not isinstance(data, Mapping):
            raise DataError(f"UDB document {relative_path} must contain a mapping")
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
            return record_type(name=name, kind=kind, path=relative_path, data=data)
        except DataError as error:
            raise DataError(f"Cannot load UDB YAML document {relative_path}: {error}") from error
