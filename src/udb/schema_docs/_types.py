# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Schema type/ref presentation retained from the Ruby MDX generator."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from ..errors import UdbError
from ._examples import ruby_string
from ._usage import ProjectionUsage


class SchemaDocsError(UdbError):
    """Schema documentation cannot be generated safely or faithfully."""


def truth(value: Any) -> bool:
    return value is not None and value is not False


def enum_text(values: list[Any]) -> str:
    return " \\| ".join(f"`{ruby_string(value)}`" for value in values)


class TypeFormatter:
    def __init__(
        self,
        name: str,
        schemas: dict[str, dict[str, Any]],
        usage: ProjectionUsage | None = None,
    ) -> None:
        self.name = name
        self.schemas = schemas
        self.schema = schemas[name]
        self.version = self.schema["$id"]
        self.defs = schemas.get("schema_defs.json", {}).get("$defs", {})
        self._active: set[tuple[str, str]] = set()
        self.usage = usage or ProjectionUsage(schemas)

    def consume(self, schema, *keywords, complete=True):
        if isinstance(schema, dict):
            for key in keywords:
                self.usage.mark(schema, key, complete=complete)

    @contextmanager
    def expansion(self, kind: str, name: str):
        key = (kind, name)
        if key in self._active:
            raise SchemaDocsError(f"{self.name}: cyclic {kind} reference to {name!r}")
        self._active.add(key)
        try:
            yield
        finally:
            self._active.remove(key)

    def ref_type(self, name: str, schema: Any) -> str:
        if not isinstance(schema, dict):
            return "`string`"
        with self.expansion("type", name):
            ref = schema.get("$ref", "")
            if ref.startswith("#/$defs/"):
                self.consume(schema, "$ref")
                nested_name = ref.rsplit("/", 1)[-1]
                nested = self.defs.get(nested_name)
                if nested is not None:
                    return self.ref_type(nested_name, nested)
            if "type" in schema:
                if schema["type"] == "array" and isinstance(schema.get("items"), dict):
                    self.consume(schema, "type")
                    return self.ref_array_type(schema["items"])
                if "enum" in schema:
                    self.consume(schema, "enum")
                    return enum_text(schema["enum"])
                self.consume(schema, "type")
                return f"`{schema['type']}`"
            if "enum" in schema:
                self.consume(schema, "enum")
                return enum_text(schema["enum"])
            composition = schema.get("oneOf", schema.get("anyOf"))
            if composition is not None:
                types = []
                for item in composition:
                    ref = item.get("$ref", "") if isinstance(item, dict) else ""
                    if ref.startswith("#/$defs/") and ref.rsplit("/", 1)[-1] in self.defs:
                        item_name = ref.rsplit("/", 1)[-1]
                        types.append(self.ref_type(item_name, self.defs[item_name]))
                    elif (
                        isinstance(item, dict)
                        and item.get("type") == "array"
                        and isinstance(item.get("items"), dict)
                        and item["items"].get("$ref", "").startswith("#/$defs/")
                    ):
                        types.append(self.ref_array_type(item["items"]))
                    else:
                        types.append(self.format_type(item))
                return " \\| ".join(types)
            return "`any`"

    def ref_array_type(self, items: dict[str, Any]) -> str:
        ref = items.get("$ref", "")
        if ref.startswith("#/$defs/"):
            self.consume(items, "$ref")
            name = ref.rsplit("/", 1)[-1]
            item_type = self.ref_type(name, self.defs[name]) if name in self.defs else "`string`"
        else:
            item_type = self.format_type(items)
        return f"Array&lt;{item_type}&gt;"

    def ref_description(self, name: str, schema: Any) -> str:
        if not isinstance(schema, dict):
            return ""
        with self.expansion("description", name):
            if "description" in schema:
                self.consume(schema, "description", complete="\n\n" not in schema["description"])
                return schema["description"]
            ref = schema.get("$ref", "")
            if ref.startswith("#/$defs/"):
                self.consume(schema, "$ref")
                nested_name = ref.rsplit("/", 1)[-1]
                if nested_name in self.defs:
                    return self.ref_description(nested_name, self.defs[nested_name])
            return ""

    def inline_or_type(self, schema: Any) -> str:
        ref = schema.get("$ref", "") if isinstance(schema, dict) else ""
        if ref.startswith("#/$defs/"):
            self.consume(schema, "$ref")
            name = ref.rsplit("/", 1)[-1]
            if name in self.defs:
                return self.inline_definition(name, self.defs[name])
        return self.format_type(schema)

    def inline_definition(self, name: str, schema: dict[str, Any]) -> str:
        with self.expansion("inline", name):
            if "description" in schema:
                self.consume(schema, "description")
                return schema["description"]
            ref = schema.get("$ref", "")
            if ref.startswith("#/$defs/"):
                self.consume(schema, "$ref")
                nested_name = ref.rsplit("/", 1)[-1]
                if nested_name in self.defs:
                    return self.inline_definition(nested_name, self.defs[nested_name])
            if "enum" in schema:
                self.consume(schema, "enum")
                return enum_text(schema["enum"])
            if "type" in schema:
                self.consume(schema, "type")
                constraints = []
                if schema["type"] == "string":
                    for key, label in (
                        ("pattern", "pattern"),
                        ("format", "format"),
                        ("minLength", "min"),
                        ("maxLength", "max"),
                    ):
                        if key in schema:
                            value = (
                                f"`{schema[key]}`"
                                if key in ("pattern", "format")
                                else ruby_string(schema[key])
                            )
                            constraints.append(f"{label}: {value}")
                elif schema["type"] in ("integer", "number"):
                    for key, label in (("minimum", "min"), ("maximum", "max")):
                        if key in schema:
                            constraints.append(f"{label}: {ruby_string(schema[key])}")
                result = f"`{schema['type']}`"
                if constraints:
                    result += " (" + ", ".join(constraints) + ")"
                return result
            composition = schema.get("oneOf", schema.get("anyOf"))
            if composition is not None:
                return " \\| ".join(self.inline_or_type(item) for item in composition)
            return "`any`"

    def format_type(self, schema: Any) -> str:
        if schema is True:
            return "`any`"
        if schema is False:
            return "`never`"
        if "type" in schema:
            kind = schema["type"]
            if truth(schema.get("const")):
                self.consume(schema, "type", "const")
                return f"`{kind}` (const: `{ruby_string(schema['const'])}`)"
            if "enum" in schema:
                self.consume(schema, "enum")
                return enum_text(schema["enum"])
            self.consume(schema, "type")
            if kind == "array" and "items" in schema:
                items = schema["items"]
                if isinstance(items, bool):
                    return f"Array&lt;{self.format_type(items)}&gt;"
                ref = items.get("$ref", "")
                if "schema_defs.json#/$defs/" in ref:
                    name = ref.rsplit("/", 1)[-1]
                    definition = self.defs.get(name)
                    if definition and not (
                        definition.get("type") == "object" and definition.get("properties")
                    ):
                        return f"Array&lt;{self.inline_definition(name, definition)}&gt;"
                    return "Array&lt;object&gt;"
                if items.get("type") == "object" and "properties" in items:
                    return "Array&lt;object&gt;"
                return f"Array&lt;{self.format_type(items)}&gt;"
            return f"`{kind}`"
        if "$ref" in schema:
            self.consume(schema, "$ref")
            return self.format_ref(schema["$ref"])
        if "enum" in schema:
            self.consume(schema, "enum")
            return enum_text(schema["enum"])
        if "oneOf" in schema:
            self.consume(schema, "oneOf")
            return "One of: " + " \\| ".join(self.format_type(item) for item in schema["oneOf"])
        if "anyOf" in schema:
            self.consume(schema, "anyOf")
            return "Any of: " + " \\| ".join(self.format_type(item) for item in schema["anyOf"])
        return "`any`"

    def format_ref(self, ref: str) -> str:
        if ref.startswith("#"):
            name = ref.rsplit("/", 1)[-1]
            return f"[`{name}`](#{name.lower().replace('_', '-')})"
        if ref.startswith(("http://", "https://")):
            return f"[`{ref}`]({ref})"
        filename, separator, fragment = ref.partition("#")
        name = filename.removesuffix(".json")
        parts = fragment.split("/")
        if (
            name == "schema_defs"
            and separator
            and len(parts) == 3
            and parts[1] in ("$defs", "definitions")
        ):
            definition = self.defs.get(parts[2])
            if definition is not None:
                return self.inline_definition(parts[2], definition)
        anchor = fragment.replace("/", "-").lower() if separator else ""
        version = (
            self.schemas[filename]["$id"]
            if filename in self.schemas
            else (
                "http://json-schema.org/draft-07/schema#"
                if filename == "json-schema-draft-07.json"
                else self.version
            )
        )
        if version.startswith(("http://", "https://")):
            return f"[`{name}`]({version})"
        prefix = "./" if version == self.version else f"../{version}/"
        if anchor:
            return f"[`{name}#{anchor}`]({prefix}{name}.mdx#{anchor})"
        return f"[`{name}`]({prefix}{name}.mdx)"

    def array_item_object(self, schema: Any) -> dict[str, Any] | None:
        if not isinstance(schema, dict) or schema.get("type") != "array":
            return None
        items = schema.get("items")
        if not isinstance(items, dict):
            return None
        if items.get("type") == "object" and "properties" in items:
            return items
        ref = items.get("$ref", "")
        if "schema_defs.json#/$defs/" in ref:
            definition = self.defs.get(ref.rsplit("/", 1)[-1])
            if definition and definition.get("type") == "object" and "properties" in definition:
                return definition
        return None
