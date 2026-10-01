# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Python-only register diagrams and IDL highlighting for official PDF rendering."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .model import ExtensionDocumentError

_TOKEN = re.compile(
    r"(xref:#[^\[\n]+\[[^\]\n]*\]|pass:\[[^\]\n]*\]|\+\+\+.*?\+\+\+)"
    r"|(?P<comment>\#[^\n]*)"
    r'|(?P<string>"(?:[^"\\]|\\.)*")'
    r"|(?P<number>0x[0-9a-fA-F]+|(?:[0-9]+|MXLEN)?'s?[bodh]?[0-9_a-fA-F]+|\b\d+\b)"
    r"|(?P<identifier>\$?[A-Za-z_][A-Za-z0-9_?]*)"
    r"|(?P<operator>[~!%^&*+=|?:<>/`-])"
)
_KEYWORDS = {
    "if",
    "else",
    "for",
    "return",
    "returns",
    "arguments",
    "description",
    "body",
    "function",
    "builtin",
    "enum",
    "bitfield",
    "generated",
    "struct",
}
_TYPES = {"Bits", "XReg", "U32", "U64", "String", "Boolean"}
_BUILTINS = {
    "true",
    "false",
    "$encoding",
    "$pc",
    "$signed",
    "$bits",
    "$width",
    "$enum_size",
    "$enum_element_size",
    "$enum_to_a",
    "$enum",
    "$array_size",
}
HIGHLIGHT_ROLES = """role:
  idl-keyword:
    font-color: 000080
    font-style: bold
  idl-type:
    font-color: 000080
  idl-constant:
    font-color: 008080
  idl-number:
    font-color: 009999
  idl-comment:
    font-color: 998877
    font-style: italic
  idl-string:
    font-color: DD1144
  idl-builtin:
    font-color: 0086B3
  idl-operator:
    font-color: 000000
"""


def highlight_idl(text: str) -> str:
    """Port the retained IDL lexer into bounded source markup, not a Ruby plugin.

    Macro tokens emitted by the accepted AsciiDoc pass remain opaque so link
    labels/targets and pass-through operators are never recolored or corrupted.
    """

    def token(match: re.Match[str]) -> str:
        value = match[0]
        kind = match.lastgroup
        if kind is None:
            return value
        if kind == "identifier":
            kind = (
                "keyword"
                if value in _KEYWORDS
                else "type"
                if value in _TYPES
                else "builtin"
                if value in _BUILTINS
                else "constant"
                if value[0].isupper()
                else None
            )
        if kind is None:
            return value
        # Delimiter escapes keep comments/strings containing '#' literal.
        value = value.replace("#", r"\#")
        return f"[.idl-{kind}]##{value}##"

    return _TOKEN.sub(token, text)


def register_svg(raw: str) -> str:
    """Draw every declared bit and field in a self-contained offline SVG."""
    if len(raw) > 1_000_000:
        raise ExtensionDocumentError("Register diagram exceeds the bounded input size")
    try:
        data = json.loads(
            re.sub(
                r'"(?:\\.|[^"\\])*"|\b0x[0-9a-fA-F]+\b',
                lambda match: match[0] if match[0].startswith('"') else str(int(match[0], 16)),
                raw,
            )
        )
    except (ValueError, TypeError) as error:
        raise ExtensionDocumentError(f"Invalid register diagram: {error}") from error
    fields = data.get("reg") if isinstance(data, dict) else None
    if not isinstance(fields, list) or len(fields) > 256:
        raise ExtensionDocumentError("Register diagram requires a bounded reg array")
    if any(
        not isinstance(field, dict)
        or type(field.get("bits")) is not int
        or field["bits"] < 1
        or field["bits"] > 128
        or not isinstance(field.get("name", ""), (str, int))
        or type(field.get("type", 1)) is not int
        for field in fields
    ):
        raise ExtensionDocumentError("Register diagram has invalid bit widths")
    total = sum(field["bits"] for field in fields)
    config = data.get("config", {})
    if not isinstance(config, dict):
        raise ExtensionDocumentError("Register diagram config must be an object")
    bits = config.get("bits", total)
    lanes = config.get("lanes", 1)
    if type(bits) is not int or not 1 <= bits <= 128 or bits < total:
        raise ExtensionDocumentError("Register diagram length is invalid")
    if type(lanes) is not int or not 1 <= lanes <= 8 or bits % lanes:
        raise ExtensionDocumentError("Register diagram lane count is invalid")
    per_lane = bits // lanes
    if not fields:
        fields = [{"bits": bits, "type": 1}]
    font_size = config.get("fontsize", 11)
    if (
        isinstance(font_size, bool)
        or not isinstance(font_size, (int, float))
        or not 6 <= font_size <= 24
    ):
        raise ExtensionDocumentError("Register diagram font size is invalid")
    for field in fields:
        attributes = field.get("attr", ())
        if (
            not isinstance(attributes, (tuple, list))
            or len(attributes) > 8
            or any(
                not isinstance(value, (str, int)) or len(str(value)) > 256 for value in attributes
            )
        ):
            raise ExtensionDocumentError("Register diagram attributes must be bounded text")
    cell, margin, row_height = 24, 12, 62
    row_height += 13 * max((len(field.get("attr", ())) for field in fields), default=0)
    width, height = per_lane * cell + 2 * margin, lanes * row_height + 10
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
        ),
        f'<g font-family="sans-serif" font-size="{font_size}" text-anchor="middle">',
    ]
    offset = 0
    fills = {1: "#ffffff", 2: "#ffffb4", 3: "#b4e1ff", 4: "#b4e1ff"}
    for field in fields:
        end = offset + field["bits"]
        name = field.get("name", "")
        for lane in range(offset // per_lane, (end - 1) // per_lane + 1):
            low, high = max(offset, lane * per_lane), min(end, (lane + 1) * per_lane)
            x = margin + (per_lane - high % per_lane) * cell if high % per_lane else margin
            y = 20 + lane * row_height
            span = (high - low) * cell
            fill = fills.get(field.get("type", 1), "#ffffff")
            parts.append(
                f'<rect x="{x}" y="{y}" width="{span}" height="28" '
                f'fill="{fill}" stroke="#000000" stroke-width="1"/>'
            )
            if isinstance(name, int):
                for bit in range(low, high):
                    bit_x = margin + (per_lane - 1 - bit % per_lane) * cell + cell / 2
                    parts.append(
                        f'<text x="{bit_x}" y="{y + 18}">{(name >> (bit - offset)) & 1}</text>'
                    )
            else:
                parts.append(
                    f'<text x="{x + span / 2}" y="{y + 18}">{html.escape(str(name))}</text>'
                )
            for index, attribute in enumerate(field.get("attr", ())):
                parts.append(
                    f'<text x="{x + span / 2}" y="{y + 42 + index * 13}">'
                    f"{html.escape(str(attribute))}</text>"
                )
            parts.append(f'<text x="{x + cell / 2}" y="{y - 5}">{high - 1}</text>')
            if high - low > 1:
                parts.append(f'<text x="{x + span - cell / 2}" y="{y - 5}">{low}</text>')
        offset = end
    parts.extend(("</g>", "</svg>"))
    return "\n".join(parts) + "\n"


def prepare_render_source(text: str, scratch: Path) -> str:
    """Replace register blocks with SVGs and IDL listings with colored markup."""
    sequence = 0

    def waveform(match: re.Match[str]) -> str:
        nonlocal sequence
        sequence += 1
        name = f"register-{sequence}.svg"
        target = scratch / name
        target.write_text(register_svg(match[1]), encoding="utf-8")
        preceding = text[: match.start()].rstrip().splitlines()
        continuation = "+\n" if preceding and preceding[-1].endswith("::") else ""
        return continuation + f"image::{target.as_posix()}[Register format,pdfwidth=100%]\n"

    text = re.sub(
        r"(?m)^\[wavedrom,[^\n]*\]\n\.\.\.\.\n(.*?)\n\.\.\.\.\n?",
        waveform,
        text,
        flags=re.DOTALL,
    )
    if "[wavedrom," in text:
        raise ExtensionDocumentError("Unrecognized WaveDrom block; refusing to lose a diagram")

    def listing(match: re.Match[str]) -> str:
        return (
            '[listing,subs="specialchars,quotes,macros"]\n----\n'
            + highlight_idl(match[1])
            + "\n----"
        )

    return re.sub(
        r"(?m)^\[source,idl[^\n]*\]\n----\n(.*?)\n----",
        listing,
        text,
        flags=re.DOTALL,
    )
