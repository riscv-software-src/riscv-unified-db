# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Offline JSON Schema loading and validation for UDB documents."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from os import PathLike
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError as JsonSchemaError
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT7

from .errors import DataError

_BASE_URI = "https://schemas.udb.invalid/"
_DRAFT7_URI = "http://json-schema.org/draft-07/schema#"
_SCHEMA_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.json")
_VERSION = re.compile(r"v[0-9]+\.[0-9]+")


class SchemaError(DataError):
    """A schema could not be loaded or a document failed validation."""


class SchemaStore:
    """A cached, offline collection of Draft 7 schemas from one directory."""

    def __init__(self, schema_root: Any) -> None:
        if isinstance(schema_root, str | PathLike):
            schema_root = Path(schema_root).resolve()
        if not schema_root.is_dir():
            raise SchemaError(f"Schema directory does not exist: {schema_root}")
        self._root = schema_root
        self._versions: dict[str, str] | None = None
        self._registry: Registry[Any] | None = None
        self._validators: dict[str, Draft7Validator] = {}

    def versioned_uri(self, uri: str) -> str:
        """Return *uri* stamped with the selected schema's declared version."""
        supplied_version, filename, fragment = self._parse_uri(uri)
        self._load()
        assert self._versions is not None
        try:
            actual_version = self._versions[filename]
        except KeyError as error:
            raise SchemaError(f"Unknown schema {filename!r} in {self._root}") from error
        if supplied_version is not None and supplied_version != actual_version:
            raise SchemaError(
                f"Schema version mismatch for {filename!r}: requested {supplied_version}, "
                f"available {actual_version}"
            )
        return f"{actual_version}/{filename}{fragment}"

    def validate(self, document: Mapping[Any, Any], source: str | Path = "<document>") -> None:
        """Validate *document* without applying defaults or mutating it."""
        source_name = str(source)
        if not isinstance(document, Mapping):
            raise SchemaError(f"{source_name}: document must be a mapping")
        schema_uri = document.get("$schema")
        if not isinstance(schema_uri, str) or not schema_uri:
            raise SchemaError(f"{source_name}: missing non-empty string '$schema'")

        try:
            versioned_uri = self.versioned_uri(schema_uri)
            _, filename, fragment = self._parse_uri(versioned_uri)
            validator = self._validator(versioned_uri)
        except SchemaError as error:
            raise SchemaError(f"{source_name}: {error}") from error
        normalized = self._json_normalize(document, source_name)
        normalized["$schema"] = f"{filename}{fragment}"

        try:
            errors = sorted(
                validator.iter_errors(normalized),
                key=lambda error: tuple(str(segment) for segment in error.absolute_path),
            )
        except Unresolvable as error:
            raise SchemaError(
                f"{source_name}: cannot resolve schema reference while validating "
                f"against {versioned_uri!r}: {error}"
            ) from error
        if errors:
            details = "; ".join(f"{error.json_path}: {error.message}" for error in errors[:8])
            if len(errors) > 8:
                details += f"; and {len(errors) - 8} more errors"
            raise SchemaError(
                f"{source_name}: schema validation failed against {versioned_uri!r}: {details}"
            )

    def _load(self) -> None:
        if self._registry is not None:
            return

        versions: dict[str, str] = {}
        resources: list[tuple[str, Resource[Any]]] = []
        schema_files = sorted(
            (
                entry
                for entry in self._root.iterdir()
                if entry.is_file() and entry.name.endswith(".json")
            ),
            key=lambda entry: entry.name,
        )
        if not schema_files:
            raise SchemaError(f"No JSON schemas found in {self._root}")

        for schema_file in schema_files:
            try:
                schema = json.loads(schema_file.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                raise SchemaError(f"{schema_file}: cannot load JSON schema: {error}") from error
            if not isinstance(schema, dict):
                raise SchemaError(f"{schema_file}: JSON schema must contain an object")
            dialect = schema.get("$schema")
            if dialect != _DRAFT7_URI:
                raise SchemaError(
                    f"{schema_file}: unsupported JSON Schema dialect {dialect!r}; "
                    f"expected {_DRAFT7_URI!r}"
                )

            identifier = schema.get("$id")
            if schema_file.name != "json-schema-draft-07.json":
                if not isinstance(identifier, str) or _VERSION.fullmatch(identifier) is None:
                    raise SchemaError(
                        f"{schema_file}: '$id' must be a version such as 'v0.1', not {identifier!r}"
                    )
                versions[schema_file.name] = identifier

            normalized_schema = deepcopy(schema)
            normalized_schema["$id"] = f"{_BASE_URI}{schema_file.name}"
            try:
                Draft7Validator.check_schema(normalized_schema)
            except JsonSchemaError as error:
                raise SchemaError(
                    f"{schema_file}: invalid Draft 7 schema: {error.message}"
                ) from error
            resources.append(
                (
                    f"{_BASE_URI}{schema_file.name}",
                    Resource.from_contents(normalized_schema, default_specification=DRAFT7),
                )
            )
            if schema_file.name != "json-schema-draft-07.json":
                resources.append(
                    (
                        f"{_BASE_URI}{identifier}/{schema_file.name}",
                        Resource.from_contents(normalized_schema, default_specification=DRAFT7),
                    )
                )

        self._versions = versions
        self._registry = Registry().with_resources(resources)

    def _validator(self, uri: str) -> Draft7Validator:
        try:
            return self._validators[uri]
        except KeyError:
            pass
        self._load()
        assert self._registry is not None
        _, filename, fragment = self._parse_uri(uri)
        reference = f"{_BASE_URI}{filename}{fragment}"
        validator = Draft7Validator({"$ref": reference}, registry=self._registry)
        self._validators[uri] = validator
        return validator

    @staticmethod
    def _parse_uri(uri: str) -> tuple[str | None, str, str]:
        if not isinstance(uri, str) or not uri:
            raise SchemaError("Schema URI must be a non-empty string")
        base, separator, fragment_value = uri.partition("#")
        parsed = urlsplit(base)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.path.startswith("/"):
            raise SchemaError(f"Schema URI must be local to the schema directory: {uri!r}")
        parts = parsed.path.split("/")
        if len(parts) == 1:
            version = None
            filename = parts[0]
        elif len(parts) == 2 and _VERSION.fullmatch(parts[0]):
            version, filename = parts
        else:
            raise SchemaError(f"Invalid schema URI {uri!r}")
        if _SCHEMA_NAME.fullmatch(filename) is None:
            raise SchemaError(f"Invalid schema filename in URI {uri!r}")
        fragment = f"#{fragment_value}" if separator else ""
        return version, filename, fragment

    @staticmethod
    def _json_normalize(document: Mapping[Any, Any], source: str) -> dict[str, Any]:
        def normalize_key(key: Any, path: str) -> str:
            try:
                encoded = json.dumps({key: None}, allow_nan=False)
                normalized_key = next(iter(json.loads(encoded)))
            except (TypeError, ValueError) as error:
                raise SchemaError(
                    f"{source}: mapping key at {path} is not representable as JSON: {error}"
                ) from error
            return normalized_key

        def thaw(value: Any, path: str) -> Any:
            if isinstance(value, Mapping):
                normalized: dict[str, Any] = {}
                original_keys: dict[str, Any] = {}
                for key, item in value.items():
                    normalized_key = normalize_key(key, path)
                    if normalized_key in normalized:
                        previous = original_keys[normalized_key]
                        raise SchemaError(
                            f"{source}: mapping keys {previous!r} and {key!r} at {path} "
                            f"both normalize to JSON key {normalized_key!r}"
                        )
                    original_keys[normalized_key] = key
                    normalized[normalized_key] = thaw(item, f"{path}[{normalized_key!r}]")
                return normalized
            if isinstance(value, tuple | list):
                return [thaw(item, f"{path}[{index}]") for index, item in enumerate(value)]
            return value

        try:
            encoded = json.dumps(thaw(document, "$"), allow_nan=False)
            normalized = json.loads(encoded)
        except (TypeError, ValueError) as error:
            raise SchemaError(
                f"{source}: document is not representable as JSON: {error}"
            ) from error
        if not isinstance(normalized, dict):
            raise SchemaError(f"{source}: document must be a mapping")
        return normalized
