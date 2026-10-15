# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Legacy Psych-compatible YAML examples, without invoking Ruby."""

from __future__ import annotations

from typing import Any

from ._psych import dump
from ._psych_scalars import ruby_string

DETAILS = (
    "<details style={{padding: '1rem', backgroundColor: "
    "'var(--ifm-color-emphasis-100)', borderLeft: '4px solid "
    "var(--ifm-color-primary)', borderRadius: '4px', marginBottom: '1rem'}}>\n"
)
SUMMARY = "<summary style={{cursor: 'pointer', fontWeight: 'bold'}}>"


def _truth(value: Any) -> bool:
    return value is not None and value is not False


def _title(example: Any, fallback: str) -> str:
    value = example.get("_title") if isinstance(example, dict) else None
    return ruby_string(value if _truth(value) else fallback)


def example_text(value: Any) -> str:
    """Serialize example data in source insertion order, stripping root metadata."""
    if not isinstance(value, dict | list):
        return ruby_string(value)
    if isinstance(value, dict):
        value = {key: child for key, child in value.items() if not key.startswith("_")}
    return dump(value)


def quick_start(examples: list[Any]) -> str:
    selected = [
        example
        for example in examples
        if isinstance(example, dict) and _truth(example.get("_quick_start"))
    ]
    if not selected:
        return ""
    return "## Quick Start\n\n" + "".join(
        f"**{_title(example, 'Example')}:**\n```yaml\n{example_text(example)}\n```\n\n"
        for example in selected
    )


def full_examples(examples: list[Any]) -> str:
    selected = [
        example
        for example in examples
        if not (isinstance(example, dict) and _truth(example.get("_quick_start")))
    ]
    if not selected:
        return ""
    text = "## Examples\n\n"
    for index, example in enumerate(selected, 1):
        title = _title(example, f"Example {index}")
        text += (
            f"{DETAILS}{SUMMARY}{title}</summary>\n\n"
            f"```yaml\n{example_text(example)}\n```\n\n</details>\n\n"
        )
    return text


def property_example(name: str, examples: list[Any]) -> str:
    anchor = name.lower().replace("_", "-") + "-example"
    example = examples[0] if examples else None
    return (
        f'{DETAILS}{SUMMARY}<a id="{anchor}"></a><code>{name}</code> example'
        f"</summary>\n\n```yaml\n{example_text(example)}\n```\n\n</details>\n\n"
    )
