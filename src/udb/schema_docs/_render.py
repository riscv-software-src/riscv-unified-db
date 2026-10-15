# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Byte-compatible MDX pages and schema index."""

from __future__ import annotations

import re
from typing import Any

from ._examples import DETAILS, SUMMARY, full_examples, property_example, quick_start, ruby_string
from ._ordering import property_order
from ._types import TypeFormatter, truth

TABLE = (
    "| Property | Type | Required | Description |\n|----------|------|----------|-------------|\n"
)


def title_for(name: str) -> str:
    return " ".join(word.capitalize() for word in name.removesuffix(".json").split("_"))


def escape_angles(text: str) -> str:
    return text.replace("<", "&lt;").replace(">", "&gt;")


def table_description(text: str) -> str:
    return escape_angles(text.split("\n\n")[0].replace("\n", " ").strip())


def escape_markdown(text: str) -> str:
    result = []
    backtick = False
    for line in text.rstrip("\n").split("\n"):
        if line.strip().startswith(">"):
            result.append(line)
            continue
        rendered = ""
        for char in line:
            if char == "`":
                backtick = not backtick
            rendered += escape_angles(char) if not backtick else char
        result.append(rendered)
    return "\n".join(result)


class PageRenderer(TypeFormatter):
    def generate(self) -> str:
        self.consume(self.schema, "title", "$defs")
        title = self.schema.get("title", title_for(self.name))
        frontmatter = (
            "---\n"
            f"title: {title} ({self.version})\n"
            f"sidebar_label: {title}\n"
            "custom_edit_url: null\n"
            f"# This file is auto-generated from {self.name}\n"
            "# Do not edit manually - run `bin/chore gen schema-docs` to regenerate\n"
            "---\n"
        )
        body = [self.header(title)]
        examples = self.schema.get("examples")
        if examples is not None:
            self.consume(self.schema, "examples")
            body.append(quick_start(examples))
        composition = next((key for key in ("oneOf", "anyOf", "allOf") if key in self.schema), None)
        definitions = self.schema.get("$defs", {})
        if composition:
            variants = self.schema[composition]
            if self.internal_object_refs(variants):
                body.append(self.variants_section(composition, variants))
                referenced = {variant["$ref"].rsplit("/", 1)[-1] for variant in variants}
                remaining = {
                    name: schema for name, schema in definitions.items() if name not in referenced
                }
                if remaining:
                    body.append(self.defs_section(remaining))
            else:
                body.append(self.composition_section(composition, variants))
                if "$defs" in self.schema:
                    body.append(self.defs_section(definitions))
        elif "$defs" in self.schema:
            body.append(self.defs_section(definitions))
        if self.schema.get("type") == "object" and "properties" in self.schema and not composition:
            body.append("## Properties\n\n" + self.properties_table(self.schema))
        if examples is not None:
            body.append(full_examples(examples))
        body.append(self.metadata())
        content = "\n\n".join(body)
        if "<details" in content:
            return (
                f"{frontmatter}\n\n"
                "import AnchorOpenDetails from '@site/src/components/AnchorOpenDetails';\n\n"
                f"<AnchorOpenDetails />\n\n{content}"
            )
        return frontmatter + "\n\n" + content

    def header(self, title: str) -> str:
        result = (
            f"# {title}\n\n"
            f'<span class="badge badge--secondary">{self.version}</span>\n\n'
            "<br />\n\n:::note Auto-generated\n"
            f"This page is generated from [`{self.name}`]"
            f"(https://github.com/riscv/riscv-unified-db/blob/main/spec/schemas/{self.name}) "
            "by the [schema doc generator](https://github.com/riscv/riscv-unified-db/blob/main/"
            "tools/internal-gems/schema_doc_gen/lib/schema_doc_gen.rb). "
            "To update this page, edit the schema file and run `bin/chore gen schema-docs`.\n:::\n"
        )
        if self.schema.get("description"):
            self.consume(self.schema, "description")
            result += "\n" + escape_markdown(self.schema["description"]) + "\n"
        return result

    def metadata(self) -> str:
        self.consume(self.schema, "$id", "$schema")
        result = (
            "## Schema Information\n\n| Property | Value |\n|----------|-------|\n"
            f"| Version | `{self.version}` |\n"
        )
        url = self.schema.get("$schema")
        if url:
            year = re.search(r"/draft/(\d{4}-\d{2})/", url)
            number = re.search(r"draft-(\d+)", url)
            if year:
                value = f"[Draft {year[1]}](https://json-schema.org/draft/{year[1]})"
            elif number:
                value = f"[Draft {number[1]}](https://json-schema.org/draft-{number[1]})"
            else:
                value = f"[`{url}`]({url})"
            result += f"| JSON Schema Version | {value} |\n"
        return result

    def internal_object_refs(self, variants: list[Any]) -> bool:
        return bool(variants) and all(
            isinstance(variant, dict)
            and variant.get("$ref", "").startswith("#/$defs/")
            and self.schema.get("$defs", {}).get(variant["$ref"].rsplit("/", 1)[-1], {}).get("type")
            == "object"
            for variant in variants
        )

    def variant_label(self, name: str, definition: dict[str, Any]) -> str:
        kind = definition.get("properties", {}).get("type", {})
        if isinstance(kind, dict) and truth(kind.get("const")):
            self.consume(kind, "const")
            return ruby_string(kind["const"])
        return name.replace("_", " ")

    def variants_section(self, key: str, variants: list[dict[str, Any]]) -> str:
        self.consume(self.schema, key)
        label = {"oneOf": "one of", "anyOf": "any of", "allOf": "all of"}[key]
        result = (
            "## Variants\n\n"
            f"This schema accepts **{label}** the following variants, distinguished by the `type` field:\n\n"
        )
        names = [variant["$ref"].rsplit("/", 1)[-1] for variant in variants]
        for variant in variants:
            self.consume(variant, "$ref")
        for name in names:
            label = self.variant_label(name, self.schema["$defs"][name])
            anchor = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
            result += f"- [{label}](#{anchor})\n"
        result += "\n"
        for name in names:
            definition = self.schema["$defs"][name]
            result += f"### `{self.variant_label(name, definition)}`\n\n"
            if "description" in definition:
                self.consume(definition, "description")
                result += escape_markdown(definition["description"]) + "\n\n"
            result += self.properties_table(definition) + "\n"
        return result

    def composition_section(self, key: str, variants: list[Any]) -> str:
        self.consume(self.schema, key)
        phrase = {
            "oneOf": "accepts **one of** the following types",
            "anyOf": "accepts **any of** the following types",
            "allOf": "requires **all of** the following",
        }[key]
        result = f"## Schema Structure\n\nThis schema {phrase}:\n\n"
        for variant in variants:
            ref = variant.get("$ref", "") if isinstance(variant, dict) else ""
            if ref.startswith("#/$defs/"):
                self.consume(variant, "$ref")
                name = ref.rsplit("/", 1)[-1]
                result += f"- [`{name}`](#{name.lower().replace('_', '-')})\n"
            elif isinstance(variant, dict) and "type" in variant:
                self.consume(variant, "type")
                result += f"- Type: `{variant['type']}`\n"
            else:
                result += "- (Complex type)\n"
        return result

    def defs_section(self, definitions: dict[str, Any]) -> str:
        if not definitions:
            return ""
        result = "## Definitions\n\n"
        for name, definition in definitions.items():
            anchor = name.lower().replace("_", "-")
            result += (
                f'<details>\n<summary><a id="{anchor}"></a><strong><code>{name}</code></strong>'
            )
            if "description" in definition:
                self.consume(definition, "description")
                result += " — " + escape_angles(definition["description"].split("\n")[0])
            result += "</summary>\n\n"
            if "description" in definition:
                result += escape_angles(definition["description"]) + "\n\n"
            if definition.get("type") == "object":
                result += self.properties_table(definition) + "\n"
            elif "enum" in definition:
                self.consume(definition, "enum")
                result += (
                    "**Allowed values:**\n\n"
                    + "".join(f"- `{ruby_string(value)}`\n" for value in definition["enum"])
                    + "\n"
                )
            elif "type" in definition:
                self.consume(definition, "type")
                result += f"**Type:** `{definition['type']}`\n\n"
            result += "</details>\n\n"
        return result

    def properties_table(self, schema: dict[str, Any]) -> str:
        if "properties" not in schema:
            return ""
        self.consume(schema, "type")
        self.consume(
            schema,
            "properties",
            complete=not any(
                isinstance(prop, dict) and prop.get("type") == "null"
                for prop in schema["properties"].values()
            ),
        )
        self.consume(
            schema,
            "required",
            complete=all(
                name != "$source"
                and name in schema["properties"]
                and not (
                    isinstance(schema["properties"][name], dict)
                    and schema["properties"][name].get("type") == "null"
                )
                for name in schema.get("required", [])
            ),
        )
        result = TABLE
        required = schema.get("required", [])
        examples = []
        items = []
        source = False
        for name, prop in property_order(schema["properties"], required):
            if isinstance(prop, dict) and prop.get("type") == "null":
                continue
            if name == "$source":
                source = True
                continue
            description = (
                table_description(prop.get("description", "")) if isinstance(prop, dict) else ""
            )
            self.consume(
                prop,
                "description",
                complete="\n\n" not in prop.get("description", "")
                if isinstance(prop, dict)
                else True,
            )
            item_object = self.array_item_object(prop)
            if item_object:
                self.consume(prop, "type")
                anchor = name.lower().replace("_", "-") + "-schema"
                properties = item_object["properties"]
                keys = ", ".join(f"`{key}`" for key in properties)
                type_text = (
                    f"Array&lt;\\{{{keys}\\}}&gt;"
                    if len(properties) <= 3
                    else "Array&lt;object&gt;"
                )
                type_text += f" [↓&nbsp;schema](#{anchor})"
                items.append((name, item_object, anchor))
            else:
                type_text = self.format_type(prop)
            if isinstance(prop, dict) and "examples" in prop:
                self.consume(prop, "examples", complete=len(prop["examples"]) <= 1)
                if description:
                    description += f" [↓&nbsp;example](#{name.lower().replace('_', '-')}-example)"
                examples.append((name, prop["examples"]))
            result += (
                f"| `{name}` | {type_text} | {'✓' if name in required else ''} | {description} |\n"
            )
        if items or examples:
            result += "\n"
            for name, item, anchor in items:
                result += self.item_schema_block(name, item, anchor)
            for name, values in examples:
                result += property_example(name, values)
        if source:
            result += (
                "\n:::note Tooling field\n`$source` is an optional field set automatically by UDB "
                "tooling to record the file path this object was loaded from. You do not need to "
                "set it manually.\n:::\n"
            )
        return result

    def item_schema_block(self, name: str, item: dict[str, Any], anchor: str) -> str:
        self.consume(item, "type")
        self.consume(
            item,
            "properties",
            complete=not any(
                isinstance(prop, dict) and prop.get("type") == "null"
                for prop in item["properties"].values()
            ),
        )
        self.consume(
            item,
            "required",
            complete=all(
                key in item["properties"]
                and not (
                    isinstance(item["properties"][key], dict)
                    and item["properties"][key].get("type") == "null"
                )
                for key in item.get("required", [])
            ),
        )
        result = (
            f'{DETAILS}{SUMMARY}<a id="{anchor}"></a><code>{name}</code> item schema</summary>\n\n'
            + TABLE
        )
        for key, schema in item["properties"].items():
            if isinstance(schema, dict) and schema.get("type") == "null":
                continue
            ref = schema.get("$ref", "") if isinstance(schema, dict) else ""
            definition_name = ref.rsplit("/", 1)[-1]
            definition = (
                self.defs.get(definition_name)
                if (ref.startswith("#/$defs/") or "schema_defs.json#/$defs/" in ref)
                else None
            )
            if definition is not None:
                self.consume(schema, "$ref")
                kind = self.ref_type(definition_name, definition)
                description = (
                    schema["description"]
                    if "description" in schema
                    else self.ref_description(definition_name, definition)
                )
            else:
                kind = self.format_type(schema)
                description = schema.get("description", "") if isinstance(schema, dict) else ""
            self.consume(schema, "description", complete="\n\n" not in description)
            result += f"| `{key}` | {kind} | {'✓' if key in item.get('required', []) else ''} | {table_description(description)} |\n"
        return result + "\n</details>\n\n"


def render_index(pages: dict[str, set[str]]) -> str:
    content = [
        "---\ntitle: Schema Reference\nsidebar_position: 1\n---\n",
        (
            "# Schema Reference\n\n"
            "UDB uses JSON Schema to define and validate the structure of YAML files in `spec/`. "
            "Each schema is versioned independently — the version shown on each card is that schema's current version.\n"
        ),
        (
            "## About Schema Versions\n\n"
            "Schemas are versioned independently of the UDB repository. Each schema file declares "
            "its version in the `$id` field. When a schema format changes, a new version is created "
            "to maintain backward compatibility with existing data files.\n"
        ),
    ]
    if not pages:
        content.append("No schema documentation found.")
    else:
        cards = (
            "## Schemas\n\n"
            "<div style={{display: 'grid', gridTemplateColumns: "
            "'repeat(auto-fill, minmax(220px, 1fr))', gap: '1rem', marginBottom: '2rem'}}>\n\n"
        )
        for name, version in sorted(
            (name, version) for version, names in pages.items() for name in names
        ):
            cards += (
                "<div style={{padding: '1rem', border: '1px solid var(--ifm-color-emphasis-300)', borderRadius: '8px'}}>\n"
                f'  <strong><a href="./{version}/{name}">{title_for(name)}</a></strong><br />\n'
                '  <span className="badge badge--secondary" style={{marginTop: '
                f"'0.4rem', display: 'inline-block'}}}}>{version}</span>\n"
                "</div>\n\n"
            )
        content.append(cards + "</div>\n\n")
    return "\n\n".join(content).rstrip() + "\n"
