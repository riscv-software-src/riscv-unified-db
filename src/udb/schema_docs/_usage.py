# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Track genuinely rendered schema content without changing legacy artifacts."""

from __future__ import annotations

_TRACKED = {
    "title",
    "description",
    "examples",
    "const",
    "enum",
    "required",
    "$ref",
    "type",
    "$schema",
    "$id",
    "$defs",
    "properties",
    "oneOf",
    "anyOf",
}
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


class ProjectionUsage:
    def __init__(self, schemas):
        self.locations = {}
        self.used = {}
        for filename, schema in schemas.items():
            self._walk(schema, filename, "")

    def _walk(self, node, filename, pointer):
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            token = key.replace("~", "~0").replace("/", "~1")
            location = f"{pointer}/{token}"
            if key in _TRACKED:
                self.locations[id(node), key] = (filename, location, key)
            if key in _MAPS:
                for name, child in value.items():
                    token = name.replace("~", "~0").replace("/", "~1")
                    self._walk(child, filename, f"{location}/{token}")
            elif key in _SINGLE:
                self._walk(value, filename, location)
            elif key in _ARRAYS:
                for index, child in enumerate(value):
                    self._walk(child, filename, f"{location}/{index}")

    def mark(self, node, keyword, *, complete=True):
        if keyword in node:
            key = (id(node), keyword)
            self.used[key] = self.used.get(key, False) or complete

    def omissions(self):
        for key, location in self.locations.items():
            if self.used.get(key) is True:
                continue
            qualifier = "only partially rendered" if key in self.used else "not rendered"
            yield (
                *location,
                f"legacy presentation: this {location[2]} is {qualifier}",
            )
