# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""SchemaStore snapshots and explicit legacy projection boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit

from jsonschema import Draft7Validator

from ..resources import package_data_root
from ..schema import SchemaStore
from ._types import SchemaDocsError

_MAPS = {"properties", "$defs", "patternProperties"}
_SINGLE = {
    "items",
    "additionalProperties",
    "not",
    "if",
    "then",
    "else",
    "propertyNames",
    "contains",
}
_ARRAYS = {"oneOf", "anyOf", "allOf"}
_VALIDATION = {
    "additionalProperties",
    "patternProperties",
    "not",
    "if",
    "then",
    "else",
    "propertyNames",
    "contains",
    "pattern",
    "format",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minLength",
    "maxLength",
    "minProperties",
    "maxProperties",
    "default",
    "readOnly",
    "writeOnly",
    "$comment",
    "allOf",
}
_VOCABULARY = (
    _MAPS
    | _SINGLE
    | _ARRAYS
    | _VALIDATION
    | {
        "$schema",
        "$id",
        "$ref",
        "title",
        "description",
        "examples",
        "type",
        "required",
        "const",
        "enum",
    }
)
_LEGACY = {
    (
        "inst_schema.json",
        "/$defs/fully_resolved_format/properties/opcodes/patternProperties/^[a-z][a-z0-9]*$/$refs",
    ): ("#/$defs/fully_resolved_opcodes"),
    ("inst_var_type_schema.json", "/unevaluatedProperties"): False,
    ("inst_schema.json", "/$defs/fully_resolved_opcodes/properties/location/type"): (
        "schema_defs.json#/$defs/field_location"
    ),
}


def _known_legacy(filename: str, pointer: str, value: Any) -> bool:
    key = (filename, pointer)
    return key in _LEGACY and value == _LEGACY[key] and type(value) is type(_LEGACY[key])


@dataclass(frozen=True)
class ProjectionNotice:
    """A located schema feature whose legacy presentation is limited."""

    schema: str
    pointer: str
    keyword: str
    message: str


class SchemaDocsProjectionWarning(UserWarning):
    """Generation includes explicitly disclosed legacy presentation omissions."""


def snapshot(store: SchemaStore | None) -> dict[str, dict[str, Any]]:
    if store is None:
        store = SchemaStore(package_data_root().joinpath("schemas"))
    published = store.resolved_schemas(base_url="https://schemas.udb.invalid")
    schemas = {}
    for path, schema in published.items():
        _, version, name = path.parts
        if name.startswith("json-schema-draft"):
            continue
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.json", name) is None:
            raise SchemaDocsError(f"unsupported documentation schema filename {name!r}")
        schema = dict(schema)
        schema["$id"] = version
        schemas[name] = schema
    return schemas


def validate_projection(schemas: dict[str, dict[str, Any]]) -> tuple[ProjectionNotice, ...]:
    notices = []

    def walk(node: Any, filename: str, pointer: str) -> None:
        if isinstance(node, bool):
            return
        if not isinstance(node, dict):
            raise SchemaDocsError(f"{filename}#{pointer}: unsupported non-object schema")
        if not pointer and node.get("type") not in (None, "object"):
            raise SchemaDocsError(f"{filename}#: unsupported non-object root presentation")
        if not pointer and "$ref" in node:
            raise SchemaDocsError(f"{filename}#: root references are unsupported")
        if not pointer and ("const" in node or "enum" in node):
            raise SchemaDocsError(f"{filename}#: root literals are unsupported")
        if not pointer and "properties" in node and any(key in node for key in _ARRAYS):
            notices.append(
                ProjectionNotice(
                    filename,
                    "/properties",
                    "properties",
                    "legacy composition presentation suppresses the root property table",
                )
            )
        if "const" in node and "type" not in node:
            notices.append(
                ProjectionNotice(
                    filename,
                    f"{pointer}/const",
                    "const",
                    "legacy constants without an explicit type are not displayed",
                )
            )
        for key, value in node.items():
            location = f"{pointer}/{key}"
            if _known_legacy(filename, location, value):
                notices.append(
                    ProjectionNotice(
                        filename,
                        location,
                        key,
                        "legacy non-Draft-7 spelling retained without interpretation",
                    )
                )
                continue
            if key not in _VOCABULARY:
                raise SchemaDocsError(f"{filename}#{location}: unsupported keyword {key!r}")
            if key == "$id" and pointer:
                raise SchemaDocsError(
                    f"{filename}#{location}: nested schema identifiers are unsupported"
                )
            if key == "$defs" and pointer:
                raise SchemaDocsError(f"{filename}#{location}: nested definitions are unsupported")
            if key == "type" and not isinstance(value, str):
                raise SchemaDocsError(f"{filename}#{location}: type unions are unsupported")
            if key == "type" and value not in (
                "object",
                "array",
                "string",
                "integer",
                "number",
                "boolean",
                "null",
            ):
                raise SchemaDocsError(f"{filename}#{location}: invalid definition type {value!r}")
            if key == "const" and isinstance(value, dict | list):
                raise SchemaDocsError(
                    f"{filename}#{location}: structured constants are unsupported"
                )
            if key == "enum" and any(isinstance(item, dict | list) for item in value):
                raise SchemaDocsError(
                    f"{filename}#{location}: structured enum values are unsupported"
                )
            if key == "$ref":
                validate_ref(value, filename, location, schemas)
            if key in _VALIDATION:
                notices.append(
                    ProjectionNotice(
                        filename,
                        location,
                        key,
                        "validated by SchemaStore; legacy MDX is not a complete constraint reference",
                    )
                )
            if key == "items":
                notices.append(
                    ProjectionNotice(
                        filename,
                        location,
                        key,
                        "legacy item presentation is limited to type strings and object mini-tables",
                    )
                )
            if key in ("oneOf", "anyOf", "$ref") and re.fullmatch(r"/\$defs/[^/]+", pointer):
                notices.append(
                    ProjectionNotice(
                        filename,
                        location,
                        key,
                        "definition details do not expand this feature; property references may inline it",
                    )
                )
            if key == "required" and any(name not in node.get("properties", {}) for name in value):
                notices.append(
                    ProjectionNotice(
                        filename,
                        location,
                        key,
                        "required fields without explicit properties do not have legacy table rows",
                    )
                )
            if key == "properties" and pointer and not re.fullmatch(r"/\$defs/[^/]+", pointer):
                notices.append(
                    ProjectionNotice(
                        filename,
                        location,
                        key,
                        "nested object properties are shown only in legacy array-item mini-tables",
                    )
                )
            if key == "type" and value == "null":
                notices.append(
                    ProjectionNotice(
                        filename,
                        location,
                        key,
                        "legacy null placeholder is excluded from property tables",
                    )
                )
            if key == "const" and value is False:
                notices.append(
                    ProjectionNotice(
                        filename,
                        location,
                        key,
                        "legacy Ruby false constant is not displayed",
                    )
                )
            if key in _MAPS:
                for name, child in value.items():
                    token = name.replace("~", "~0").replace("/", "~1")
                    if key == "$defs" and not isinstance(child, dict):
                        raise SchemaDocsError(
                            f"{filename}#{location}/{token}: boolean definitions are unsupported"
                        )
                    if key == "$defs":
                        for error in Draft7Validator(Draft7Validator.META_SCHEMA).iter_errors(
                            child
                        ):
                            error_pointer = f"{location}/{token}/" + "/".join(
                                str(part).replace("~", "~0").replace("/", "~1")
                                for part in error.path
                            )
                            if not _known_legacy(filename, error_pointer, error.instance):
                                raise SchemaDocsError(
                                    f"{filename}#{error_pointer}: invalid definition: {error.message}"
                                )
                    walk(child, filename, f"{location}/{token}")
            elif key in _SINGLE:
                if isinstance(value, list):
                    raise SchemaDocsError(f"{filename}#{location}: tuple schemas are unsupported")
                walk(value, filename, location)
            elif key in _ARRAYS:
                for index, child in enumerate(value):
                    if not pointer and isinstance(child, bool):
                        raise SchemaDocsError(
                            f"{filename}#{location}/{index}: boolean composition variants are unsupported"
                        )
                    walk(child, filename, f"{location}/{index}")

    for filename, schema in schemas.items():
        walk(schema, filename, "")
    return tuple(notices)


def validate_ref(ref: str, filename: str, pointer: str, schemas: dict[str, dict[str, Any]]) -> None:
    location = f"{filename}#{pointer}"
    uri = urlsplit(ref)
    if uri.scheme:
        if uri.scheme not in ("http", "https") or not uri.netloc:
            raise SchemaDocsError(f"{location}: unsupported reference URI {ref!r}")
        return
    if uri.netloc or uri.query or "\\" in ref:
        raise SchemaDocsError(f"{location}: unsupported reference URI {ref!r}")
    name, _, fragment = ref.partition("#")
    if name == "json-schema-draft-07.json":
        if fragment:
            raise SchemaDocsError(f"{location}: meta-schema fragments are unsupported")
        return
    if name and name not in schemas:
        raise SchemaDocsError(f"{location}: unknown local schema reference {ref!r}")
    target = schemas[name or filename]
    decoded = unquote(fragment)
    if decoded:
        if not decoded.startswith("/"):
            raise SchemaDocsError(f"{location}: unsupported named reference anchor {ref!r}")
        for segment in decoded[1:].split("/"):
            key = segment.replace("~1", "/").replace("~0", "~")
            try:
                if re.search(r"~(?![01])", segment) or (
                    isinstance(target, list) and re.fullmatch(r"0|[1-9][0-9]*", key) is None
                ):
                    raise ValueError("invalid JSON pointer token")
                target = target[int(key)] if isinstance(target, list) else target[key]
            except (KeyError, ValueError, TypeError, IndexError) as error:
                raise SchemaDocsError(f"{location}: unresolved JSON pointer in {ref!r}") from error
    if not isinstance(target, dict | bool):
        raise SchemaDocsError(f"{location}: reference does not point to a schema: {ref!r}")
