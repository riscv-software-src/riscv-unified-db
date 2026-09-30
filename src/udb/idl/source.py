# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""The origin of a parsed IDL syntax tree.

This mirrors the handful of pieces of state that Ruby's ``Idl::AstNode``
tracks about where a tree came from: the raw text that was parsed
(``input``), a label used for diagnostics and ``to_h`` ``"source"``
dictionaries (``AstNode#input_file``), the 0-based line/column at which the
text starts within some larger enclosing document (``AstNode#starting_line``
/ ``AstNode#source_starting_offset``), and, optionally, a table mapping each
line of ``text`` back to a byte offset in a *different* underlying file
(``AstNode#source_line_file_offsets``) -- used when IDL is embedded inside a
larger file (e.g. a YAML ``operation():`` block) and diagnostics should point
at the enclosing file rather than the extracted IDL snippet.

Ruby re-derives most of this per-node via a parent-fallback chain, because
only the root of a tree ever has ``set_input_file`` called on it. Since a
single :class:`IdlSource` is shared by every node produced from one parse,
Python does not need that fallback: every node just holds a reference to the
same object.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["IdlSource"]

# Ruby's Regexp `\s` character class (used by `source_yaml`'s trailing-whitespace
# trim). This is narrower than Python's `str.isspace()` (which also matches things
# like U+2028) so it is spelled out explicitly for exact parity.
_RUBY_WHITESPACE = " \t\r\n\f\v"


@dataclass(frozen=True, slots=True)
class IdlSource:
    """Immutable description of where a parsed IDL tree's text came from.

    Attributes:
        text: The exact string that was parsed (the same string every node's
            ``(start, end)`` interval indexes into).
        label: A logical origin label for diagnostics and ``to_h``'s
            ``source["file"]`` field. Ruby calls this ``input_file``; it is
            often a path, but the oracle protocol uses opaque case ids.
        starting_line: 0-based line number, within some larger enclosing
            document, that ``text`` starts at. Added to computed line numbers
            so diagnostics can point at the right place in that document.
        starting_offset: Byte offset, within some larger enclosing document,
            that ``text[0]`` corresponds to. Added to computed character
            offsets when ``line_file_offsets`` is not given.
        line_file_offsets: Optional per-line file-offset table. When set,
            entry ``i`` is the file byte offset of the first character of
            line ``i`` of ``text``; ``to_h``'s ``source`` dict is computed by
            mapping a position in ``text`` to a line/column and then adding
            ``line_file_offsets[line]``. This lets diagnostics for IDL
            embedded in a larger (e.g. YAML) file point at real file offsets
            even though `text` was extracted and possibly reflowed.
    """

    text: str
    label: str
    starting_line: int = 0
    starting_offset: int = 0
    line_file_offsets: tuple[int, ...] | None = None

    def lineno(self, pos: int) -> int:
        """1-based line number of character offset *pos* in ``text``.

        Mirrors ``Idl::AstNode#lineno``: counts newlines up to (and
        including) ``pos``, adds one (lines are 1-based), and adds
        ``starting_line``.
        """
        return self.text.count("\n", 0, pos + 1) + 1 + self.starting_line

    def failure_lineno(self, pos: int) -> int:
        """1-based line number of a syntax error at offset *pos*.

        Mirrors Treetop's ``String#line_of``, which (unlike
        ``Idl::AstNode#lineno``) does not count a newline *at* ``pos``.
        """
        return self.text.count("\n", 0, pos) + 1 + self.starting_line

    def column(self, pos: int) -> int:
        """1-based column number of character offset *pos* in ``text``."""
        line_start = self.text.rfind("\n", 0, pos) + 1
        return pos - line_start + 1

    def _pos_to_file_offset(self, pos: int) -> int:
        """Map a position in ``text`` to a file byte offset via ``line_file_offsets``.

        Mirrors ``Idl::AstNode#idl_pos_to_file_offset``: scans from the start
        of ``text`` counting newlines to determine the (0-based) line and
        column of ``pos``, then returns ``line_file_offsets[line] + column``
        (clamping to the last entry if ``text`` has more lines than the
        table, matching Ruby's ``line < lfo.size ? lfo[line] : lfo.last``).
        """
        lfo = self.line_file_offsets
        assert lfo is not None
        line = self.text.count("\n", 0, pos)
        line_start = self.text.rfind("\n", 0, pos) + 1
        col = pos - line_start
        line_offset = lfo[line] if line < len(lfo) else lfo[-1]
        return line_offset + col

    def source_dict(self, start: int, end: int) -> dict[str, object]:
        """The ``to_h`` ``"source"`` dictionary for the half-open interval ``[start, end)``.

        Mirrors ``Idl::AstNode#source_yaml`` exactly, including its two
        quirks:

        * A zero-size interval (``start == end``) is treated as if it had
          size 1 ending at ``start + 1`` (both with and without
          ``line_file_offsets``).
        * When ``line_file_offsets`` is set, the *end* of the interval is
          walked backwards over trailing whitespace (per Ruby's ``/\\s/``)
          before being mapped to a file offset, so the recorded range ends at
          the last non-whitespace character rather than including trailing
          whitespace that was part of the IDL-string interval only because of
          how the grammar captured it.
        """
        interval_end = start + 1 if end == start else end

        if self.line_file_offsets is not None:
            file_begin = self._pos_to_file_offset(start)
            if end == start:
                last_char = start + 1
            else:
                last_char = interval_end - 1
                while last_char > start and self.text[last_char] in _RUBY_WHITESPACE:
                    last_char -= 1
            file_end = self._pos_to_file_offset(last_char)
        else:
            file_begin = self.starting_offset + start
            file_end = self.starting_offset + interval_end

        return {"file": self.label, "begin": file_begin, "end": file_end}
