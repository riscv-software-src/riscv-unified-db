# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Map an IDL field embedded in a YAML document to an :class:`~udb.idl.source.IdlSource`.

Port of ``Udb::YamlResolver#track_source_locations_helper`` /
``#build_line_file_offsets`` (``udb/yaml/yaml_resolver.rb``), adapted to read
from the Stage 2c :class:`~udb.source.SourceSpan` (``udb/source.py``) instead
of re-walking raw ``Psych`` parse events.

Ruby allows two YAML scalar styles for a nonempty field whose key ends in ``)``
(e.g. ``operation()``, ``sw_read()``): a single-line **plain** scalar, or a
**literal** block scalar (``|``). Any other style (folded ``>``, single- or
double-quoted) is rejected with a clear error at resolve time -- see
``track_source_locations_helper``'s ``raise "ERROR: Unsupported YAML
style..."``. Empty values are allowed in every style, including the quoted empty
operations of Zcmop instructions. This module preserves both rules.

``starting_line`` maps source lines, ``line_file_offsets`` maps character
offsets, and ``line_start_columns`` restores stripped indentation for original
YAML diagnostic columns. Unlike Ruby's snippet-relative columns, diagnostics
identify the enclosing file position required by the Stage 4 source contract.
"""

from __future__ import annotations

from .idl.errors import IdlInternalError
from .idl.source import IdlSource
from .source import SourceSpan

__all__ = ["UnsupportedYamlIdlStyle", "idl_field_source"]


class UnsupportedYamlIdlStyle(IdlInternalError):
    """A YAML IDL field uses a scalar style Ruby's resolver rejects (folded/quoted)."""


def _line_starts(document_text: str) -> list[int]:
    """``starts[i]`` is the character offset of the start of 0-based line ``i``."""
    starts = [0]
    for line in document_text.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    return starts


def _line_offset(starts: list[int], line_index: int) -> int:
    return starts[line_index] if line_index < len(starts) else starts[-1]


def _build_line_file_offsets(
    document_text: str, idl_string: str, first_line_file_offset: int
) -> tuple[int, ...]:
    """Port of ``YamlResolver#build_line_file_offsets``.

    Deviation: Ruby operates on raw file *bytes* to avoid UTF-8 char/byte
    mismatches; this operates on Python ``str`` character indices instead.
    IDL source text is ASCII-only in every real file (as documented by
    ``udb.idl.source`` itself), so the two coincide exactly in practice.
    """
    size = len(document_text)

    # Compare raw and decoded indentation: explicit |N can preserve leading spaces.
    indent_width = 0
    scan_pos = first_line_file_offset
    for line in idl_string.splitlines(keepends=True):
        spaces = 0
        while scan_pos + spaces < size and document_text[scan_pos + spaces] == " ":
            spaces += 1
        if line.strip():
            decoded_spaces = len(line) - len(line.lstrip(" "))
            indent_width = max(0, spaces - decoded_spaces)
            break
        newline_pos = document_text.find("\n", scan_pos)
        scan_pos = newline_pos + 1 if newline_pos != -1 else size

    offsets: list[int] = []
    file_pos = first_line_file_offset
    for _line in idl_string.splitlines(keepends=True) or [""]:
        content_pos = file_pos
        skipped = 0
        while skipped < indent_width and content_pos < size and document_text[content_pos] == " ":
            content_pos += 1
            skipped += 1
        offsets.append(content_pos)
        newline_pos = document_text.find("\n", file_pos)
        file_pos = newline_pos + 1 if newline_pos != -1 else size
    return tuple(offsets)


def idl_field_source(document_text: str, span: SourceSpan, value: str, *, label: str) -> IdlSource:
    """Build the :class:`IdlSource` for an IDL field's *value* found at *span* in *document_text*.

    Args:
        document_text: The full raw text of the YAML file *span* came from.
        span: The :class:`~udb.source.SourceSpan` of the field's value, as
            produced by :func:`udb.source.parse_yaml` (e.g.
            ``parsed.sources[("operation()",)]``).
        value: The resolved string value of that field (must equal what YAML
            parsed at *span*; ``ParsedYaml.value`` already holds it, so
            callers should pass that rather than re-extracting from
            ``document_text``).
        label: Passed through to :class:`IdlSource` (``AstNode#input_file``);
            typically *span.source* / the file path.

    Raises:
        UnsupportedYamlIdlStyle: A nonempty *span* is a folded (``>``),
            single-quoted, or double-quoted scalar.
    """
    starts = _line_starts(document_text)

    if value == "" or span.style is None:
        content_line_0based = (span.start_line - 1) if span.start_line is not None else 0
        start_column = span.start_column or 1
        marked_offset = _line_offset(starts, content_line_0based) + (start_column - 1)
        return IdlSource(
            text=value,
            label=label,
            starting_line=content_line_0based,
            starting_offset=marked_offset,
            line_start_columns=(start_column,),
        )

    if span.style == "|":
        # Verified empirically (see gen/handoff/s16-env-progress.md): for a
        # literal block scalar, `span.start_line` (the *key*'s 1-based file
        # line) already numerically equals the first content line's 0-based
        # index -- e.g. `sw_read(): |` on file line 41 (1-based) has its
        # first content line at file line 42 (1-based) == 0-based index 41.
        content_line_0based = span.start_line if span.start_line is not None else 0
        first_line_file_offset = _line_offset(starts, content_line_0based)
        line_file_offsets = _build_line_file_offsets(document_text, value, first_line_file_offset)
        return IdlSource(
            text=value,
            label=label,
            starting_line=content_line_0based,
            starting_offset=first_line_file_offset,
            line_file_offsets=line_file_offsets,
            line_start_columns=tuple(
                offset - _line_offset(starts, content_line_0based + index) + 1
                for index, offset in enumerate(line_file_offsets)
            ),
        )

    style_name = {
        ">": "FOLDED",
        "'": "SINGLE_QUOTED",
        '"': "DOUBLE_QUOTED",
    }.get(span.style, f"UNKNOWN ({span.style!r})")
    raise UnsupportedYamlIdlStyle(
        f"Unsupported YAML style for IDL field in {label}.\n"
        "IDL functions must use either PLAIN (single-line) or LITERAL block scalar (|) style.\n"
        f"Found style: {style_name}"
    )
