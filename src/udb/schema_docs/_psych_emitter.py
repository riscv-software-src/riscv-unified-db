# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# Copyright (c) 2006-2016 Kirill Simonov
# Copyright (c) 2017-2020 Ingy döt Net
# SPDX-License-Identifier: MIT AND BSD-3-Clause-Clear

"""Libyaml 0.2.5 scalar emission on ruamel's existing event/state machinery.

Adapted from libyaml's MIT-licensed emitter.c. No native library is required.
"""

from __future__ import annotations

from ruamel.yaml.emitter import RoundTripEmitter
from ruamel.yaml.events import DocumentEndEvent, ScalarEvent


class PsychEmitter(RoundTripEmitter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unicode_supplementary = False
        self.allow_space_break = False
        self._keep_document_end = False

    def analyze_scalar(self, scalar):
        analysis = super().analyze_scalar(scalar)
        if "\r" in scalar:
            analysis.multiline = True
        if "\x85" in scalar:
            analysis.allow_flow_plain = analysis.allow_block_plain = False
            analysis.allow_single_quoted = analysis.allow_block = False
        return analysis

    def check_simple_key(self):
        if isinstance(self.event, ScalarEvent):
            if self.analysis is None:
                self.analysis = self.analyze_scalar(self.event.value)
            length = len(self.event.value.encode("utf-8")) + len(self.event.anchor or "")
            return length <= 128 and not self.analysis.multiline
        return super().check_simple_key()

    def write_literal(self, text, comment=None):
        self._keep_document_end = self.determine_block_hints(text)[2] == "+"
        super().write_literal(text, comment)

    def expect_document_end(self):
        if isinstance(self.event, DocumentEndEvent) and (
            self.open_ended or self._keep_document_end
        ):
            self.event.explicit = True
        super().expect_document_end()
        self._keep_document_end = False

    def process_scalar(self):
        if self.event.value == "" and self.choose_scalar_style() == "":
            self.analysis = self.style = None
            return
        super().process_scalar()

    def choose_scalar_style(self):
        if self.analysis is None:
            self.analysis = self.analyze_scalar(self.event.value)
        analysis = self.analysis
        style = self.event.style or ""
        if self.canonical or (self.simple_key_context and analysis.multiline):
            return '"'
        if style == "" and (
            (self.flow_level and not analysis.allow_flow_plain)
            or (not self.flow_level and not analysis.allow_block_plain)
            or (analysis.empty and (self.flow_level or self.simple_key_context))
            or not self.event.implicit[0]
        ):
            style = "'"
        if style == "'" and not analysis.allow_single_quoted:
            style = '"'
        if style in {"|", ">"} and (
            not analysis.allow_block or self.flow_level or self.simple_key_context
        ):
            style = '"'
        return style

    def _write(self, text: str):
        self.column += len(text)
        self.stream.write(text.encode(self.encoding) if self.encoding else text)

    def write_plain(self, text, split=True):
        if self.root_context:
            self.open_ended = True
        if not text:
            return
        if not self.whitespace:
            self._write(" ")
        self.whitespace = self.indention = False
        previous_space = previous_break = False
        for character in text:
            if character == " ":
                if split and not previous_space and self.column > self.best_width:
                    self.write_indent()
                    self.whitespace = self.indention = False
                else:
                    self._write(character)
                previous_space = True
            elif character in "\n\x85\u2028\u2029":
                if not previous_break and character == "\n":
                    self.write_line_break()
                self.write_line_break(None if character == "\n" else character)
                previous_space = False
            else:
                if previous_break:
                    self.write_indent()
                    self.whitespace = self.indention = False
                self._write(character)
                previous_space = False
            previous_break = character in "\n\x85\u2028\u2029"

    def write_double_quoted(self, text, split=True):
        self.write_indicator('"', True)
        spaces = False
        for index, character in enumerate(text):
            printable = (
                "\x20" <= character <= "\x7e"
                or "\xa0" <= character <= "\ud7ff"
                or "\ue000" <= character <= "\ufffd"
            )
            if (
                not printable
                or character in '"\\\ufeff\x85\u2028\u2029'
                or (not self.allow_unicode and ord(character) > 127)
            ):
                escape = self.ESCAPE_REPLACEMENTS.get(character)
                if escape is None:
                    code = ord(character)
                    escape = (
                        f"x{code:02X}"
                        if code <= 0xFF
                        else f"u{code:04X}"
                        if code <= 0xFFFF
                        else f"U{code:08X}"
                    )
                self._write("\\" + escape)
                spaces = False
            elif character == " ":
                if (
                    split
                    and not spaces
                    and self.column > self.best_width
                    and 0 < index < len(text) - 1
                ):
                    self.write_indent()
                    if text[index + 1] == " ":
                        self._write("\\")
                else:
                    self._write(" ")
                spaces = True
            else:
                self._write(character)
                spaces = False
        self.write_indicator('"', False)
