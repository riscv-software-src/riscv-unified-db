# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Deterministic serialization for resolved UDB data."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections.abc import Mapping, Sequence
from io import StringIO
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Any, Literal

from ruamel.yaml import YAML
from ruamel.yaml.nodes import ScalarNode
from ruamel.yaml.resolver import VersionedResolver
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from .errors import SerializationError
from .schema import SchemaError, SchemaStore

if TYPE_CHECKING:
    from .database import ResolvedDatabase

SCHEMAS_BASE_URL = "https://riscv.github.io/riscv-unified-db/schemas"
_OWNERSHIP_MANIFEST = ".udb-serialization.json"


def _pointer(path: tuple[Any, ...]) -> str:
    if not path:
        return "#"
    tokens = (str(part).replace("~", "~0").replace("/", "~1") for part in path)
    return "#/" + "/".join(tokens)


def _canonicalize(
    value: Any,
    *,
    source: str,
    path: tuple[Any, ...] = (),
    active: set[int] | None = None,
    json_keys: bool = False,
    sort_mappings: bool = True,
) -> Any:
    if active is None:
        active = set()

    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            raise SerializationError(
                f"{source}{_pointer(path)}: recursive mappings are unsupported"
            )
        active.add(identity)
        try:
            result: dict[Any, Any] = {}
            items = list(value.items())
            if sort_mappings:
                items.sort(key=lambda item: (type(item[0]).__name__, repr(item[0])))
            for key, item in items:
                if json_keys:
                    if isinstance(key, str):
                        normalized_key = key
                    elif key is None:
                        normalized_key = "null"
                    elif isinstance(key, bool):
                        normalized_key = "true" if key else "false"
                    elif isinstance(key, int):
                        normalized_key = str(key)
                    elif isinstance(key, float) and math.isfinite(key):
                        normalized_key = json.dumps(key, allow_nan=False)
                    else:
                        raise SerializationError(
                            f"{source}{_pointer(path)}: mapping key {key!r} is not "
                            "representable in JSON"
                        )
                    if normalized_key in result:
                        raise SerializationError(
                            f"{source}{_pointer(path)}: mapping key {key!r} collides after "
                            f"JSON normalization as {normalized_key!r}"
                        )
                elif isinstance(key, str | bool | int | float) or key is None:
                    if isinstance(key, float) and not math.isfinite(key):
                        raise SerializationError(
                            f"{source}{_pointer(path)}: non-finite mapping keys are unsupported"
                        )
                    normalized_key = key
                else:
                    raise SerializationError(
                        f"{source}{_pointer(path)}: mapping key {key!r} is not a YAML scalar"
                    )
                if key == "$source" and isinstance(item, (str, PurePath)):
                    source_path = str(item)
                    windows_source = PureWindowsPath(source_path)
                    if (
                        Path(source_path).is_absolute()
                        or windows_source.is_absolute()
                        or windows_source.drive
                        or "\\" in source_path
                    ):
                        raise SerializationError(
                            f"{source}{_pointer((*path, key))}: absolute source paths are not "
                            "portable"
                        )
                result[normalized_key] = _canonicalize(
                    item,
                    source=source,
                    path=(*path, normalized_key),
                    active=active,
                    json_keys=json_keys,
                    sort_mappings=sort_mappings,
                )
            return result
        finally:
            active.remove(identity)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        identity = id(value)
        if identity in active:
            raise SerializationError(
                f"{source}{_pointer(path)}: recursive sequences are unsupported"
            )
        active.add(identity)
        try:
            return [
                _canonicalize(
                    item,
                    source=source,
                    path=(*path, index),
                    active=active,
                    json_keys=json_keys,
                    sort_mappings=sort_mappings,
                )
                for index, item in enumerate(value)
            ]
        finally:
            active.remove(identity)

    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        raise SerializationError(f"{source}{_pointer(path)}: non-finite numbers are unsupported")
    if isinstance(value, PurePath):
        if value.is_absolute() or (
            isinstance(value, PureWindowsPath) and (value.is_absolute() or value.drive)
        ):
            raise SerializationError(
                f"{source}{_pointer(path)}: absolute path values are not portable"
            )
        return value.as_posix()
    raise SerializationError(
        f"{source}{_pointer(path)}: value of type {type(value).__name__} is not serializable"
    )


def dumps_json(value: Any, *, source: str = "<value>", sort_keys: bool = True) -> str:
    """Return canonical, UTF-8-friendly JSON terminated by one newline."""
    canonical = _canonicalize(value, source=source, json_keys=True, sort_mappings=sort_keys)
    return json.dumps(canonical, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def dumps_yaml(value: Any, *, source: str = "<value>") -> str:
    """Return canonical YAML 1.2-compatible text terminated by one newline."""
    canonical = _canonicalize(value, source=source)
    resolver = VersionedResolver(version=(1, 1))

    def quote_ambiguous_strings(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                quote_ambiguous_strings(key): quote_ambiguous_strings(child)
                for key, child in item.items()
            }
        if isinstance(item, list):
            return [quote_ambiguous_strings(child) for child in item]
        if isinstance(item, str):
            tag = resolver.resolve(ScalarNode, item, (True, False))
            if tag.suffix != "tag:yaml.org,2002:str":
                return DoubleQuotedScalarString(item)
        return item

    yaml = YAML(typ="rt")
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    yaml.width = 4096
    output = StringIO()
    yaml.dump(quote_ambiguous_strings(canonical), output)
    text = output.getvalue()
    return text if text.endswith("\n") else f"{text}\n"


def _write_atomic(path: Path, contents: str) -> None:
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except OSError as error:
        raise SerializationError(f"Cannot write {path}: {error}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _output_path(root: Path, relative_path: PurePosixPath) -> Path:
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise SerializationError(f"Invalid output path {relative_path.as_posix()!r}")
    output_path = root.joinpath(*relative_path.parts)
    try:
        output_path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError as error:
        raise SerializationError(
            f"Output path {relative_path.as_posix()!r} escapes {root} through a symbolic link"
        ) from error
    return output_path


def _resolved_document_path(value: str) -> PurePosixPath:
    if "\\" in value or ":" in value or PureWindowsPath(value).drive:
        raise SerializationError(f"Resolved document path must use POSIX separators: {value!r}")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in ("", ".", "..") for part in path.parts)
        or path.suffix not in (".yaml", ".yml")
        or value in ("index.yaml", "index.json", _OWNERSHIP_MANIFEST)
    ):
        raise SerializationError(f"Invalid or reserved resolved document path {value!r}")
    return path


def _previous_documents(root: Path) -> tuple[PurePosixPath, ...]:
    manifest = root / "index.json"
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ()
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SerializationError(
            f"Cannot read previous resolved index {manifest}: {error}"
        ) from error
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SerializationError(f"Previous resolved index {manifest} must contain a string list")
    return tuple(_resolved_document_path(item) for item in value)


def _previous_ownership(root: Path) -> Mapping[str, str]:
    manifest = root / _OWNERSHIP_MANIFEST
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SerializationError(f"Cannot read ownership manifest {manifest}: {error}") from error
    documents = value.get("documents") if isinstance(value, dict) else None
    if not isinstance(documents, dict) or not all(
        isinstance(path, str) and isinstance(digest, str) for path, digest in documents.items()
    ):
        raise SerializationError(f"Ownership manifest {manifest} is malformed")
    for path in documents:
        _resolved_document_path(path)
    return documents


def _preflight_output_targets(
    root: Path,
    document_paths: Sequence[PurePosixPath],
    special_paths: Sequence[PurePosixPath],
) -> None:
    if root.exists() and not root.is_dir():
        raise SerializationError(f"Output directory path is an existing file: {root}")
    resolved_root = root.resolve(strict=False)
    all_paths = {*document_paths, *special_paths}
    for relative_path in sorted(all_paths):
        for depth in range(1, len(relative_path.parts)):
            ancestor = PurePosixPath(*relative_path.parts[:depth])
            if ancestor in all_paths:
                raise SerializationError(
                    f"Output path collision: {ancestor.as_posix()!r} is also an ancestor of "
                    f"{relative_path.as_posix()!r}"
                )

        output_path = _output_path(root, relative_path)
        if output_path.exists() and output_path.is_dir():
            raise SerializationError(f"Output file path is an existing directory: {output_path}")
        parent = output_path.parent.resolve(strict=False)
        if parent != resolved_root and resolved_root not in parent.parents:
            raise SerializationError(f"Output path escapes output directory: {output_path}")
        while parent != resolved_root:
            if parent.exists() and not parent.is_dir():
                raise SerializationError(f"Output directory path is an existing file: {parent}")
            parent = parent.parent


def write_config(
    config: Mapping[str, Any],
    destination: str | Path,
    *,
    format: Literal["yaml", "json"] | None = None,
) -> Path:
    """Write a configuration mapping without embedding its checkout location."""
    path = Path(destination)
    selected_format = format
    if selected_format is None:
        selected_format = "json" if path.suffix.lower() == ".json" else "yaml"
    if selected_format not in ("yaml", "json"):
        raise SerializationError(f"Unknown serialization format {selected_format!r}")
    contents = (
        dumps_yaml(config, source=str(path))
        if selected_format == "yaml"
        else dumps_json(config, source=str(path))
    )
    _write_atomic(path, contents)
    return path


def _version_document_schema(
    document: Mapping[str, Any], store: SchemaStore | None, *, source: str
) -> dict[str, Any]:
    copied = _canonicalize(document, source=source)
    schema_uri = copied.get("$schema")
    if isinstance(schema_uri, str):
        if store is None:
            raise SerializationError(
                f"{source}#/$schema: cannot version schema URI without a schema directory"
            )
        try:
            copied["$schema"] = store.versioned_uri(schema_uri)
        except SchemaError as error:
            raise SerializationError(f"{source}#/$schema: {error}") from error
        copied = _canonicalize(copied, source=source)
    return copied


def write_resolved_database(database: ResolvedDatabase, output_dir: str | Path) -> tuple[Path, ...]:
    """Write a resolved database as a deterministic YAML tree and indexes."""
    if not database.is_resolved:
        raise SerializationError("Only a resolved database can be serialized as resolved data")

    root = Path(output_dir)
    store = SchemaStore(database.schemas_root) if database.schemas_root is not None else None
    relative_paths = tuple(sorted(database.documents))
    previous_paths = _previous_documents(root)
    previous_ownership = _previous_ownership(root)
    yaml_index_path = PurePosixPath("index.yaml")
    json_index_path = PurePosixPath("index.json")
    ownership_manifest_path = PurePosixPath(_OWNERSHIP_MANIFEST)
    yaml_index = _output_path(root, yaml_index_path)
    json_index = _output_path(root, json_index_path)
    ownership_manifest = _output_path(root, ownership_manifest_path)
    rendered: list[tuple[PurePosixPath, Path, str]] = []
    for relative_name in relative_paths:
        relative_path = _resolved_document_path(relative_name)
        document = _version_document_schema(
            database.documents[relative_name], store, source=relative_name
        )
        rendered.append(
            (
                relative_path,
                _output_path(root, relative_path),
                dumps_yaml(document, source=relative_name),
            )
        )

    _preflight_output_targets(
        root,
        [relative_path for relative_path, _output_path_value, _contents in rendered],
        [yaml_index_path, json_index_path, ownership_manifest_path],
    )

    current_paths = {relative_path for relative_path, _output_path_value, _contents in rendered}
    stale_paths = sorted(set(previous_paths) - current_paths)
    for stale_path in stale_paths:
        output_path = _output_path(root, stale_path)
        if not output_path.exists() and not output_path.is_symlink():
            continue
        expected_digest = previous_ownership.get(stale_path.as_posix())
        if expected_digest is None:
            raise SerializationError(
                f"Cannot safely remove stale output {output_path}: no ownership digest is recorded"
            )
        try:
            actual_digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
        except OSError as error:
            raise SerializationError(
                f"Cannot inspect stale output {output_path}: {error}"
            ) from error
        if actual_digest != expected_digest:
            raise SerializationError(
                f"Cannot remove modified stale output {output_path}; choose a clean output directory"
            )

    written: list[Path] = []
    for _relative_path, output_path, contents in rendered:
        _write_atomic(output_path, contents)
        written.append(output_path)

    for stale_path in stale_paths:
        output_path = _output_path(root, stale_path)
        if output_path.is_file() or output_path.is_symlink():
            output_path.unlink()

    index = list(relative_paths)
    _write_atomic(yaml_index, dumps_yaml(index, source="index.yaml"))
    _write_atomic(json_index, dumps_json(index, source="index.json"))
    ownership = {
        "version": 1,
        "documents": {
            relative_path.as_posix(): hashlib.sha256(contents.encode("utf-8")).hexdigest()
            for relative_path, _output_path_value, contents in rendered
        },
    }
    _write_atomic(
        ownership_manifest,
        dumps_json(ownership, source=_OWNERSHIP_MANIFEST),
    )
    written.extend((yaml_index, json_index))
    return tuple(written)


def write_resolved_schemas(
    store: SchemaStore,
    output_dir: str | Path,
    *,
    base_url: str = SCHEMAS_BASE_URL,
) -> tuple[Path, ...]:
    """Publish schemas using the versioned path and identifier contract."""
    root = Path(output_dir)
    written: list[Path] = []
    for relative_path, schema in store.resolved_schemas(base_url=base_url).items():
        output_path = _output_path(root, relative_path)
        _write_atomic(
            output_path,
            dumps_json(schema, source=relative_path.as_posix(), sort_keys=False),
        )
        written.append(output_path)
    return tuple(written)
