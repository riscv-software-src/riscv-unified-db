# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Lexical migration boundary for the captured Ruby/Erubi syntax."""

from __future__ import annotations

import re
from collections.abc import Collection

TAG = re.compile(r"<%(-?)(.*?)(-?)%>([ \t]*\r?\n)?", re.DOTALL)
EXT = re.compile(r'ext\?\(:([A-Za-z][A-Za-z0-9_]*)(?:,\s*"([^"]+)")?\)')
_ATOMS = (
    EXT.pattern + r"|possible_xlens\.include\?\(32\)"
    r"|\[[A-Z][A-Z0-9_]*,\s*[A-Z][A-Z0-9_]*\]\.min"
    r"|[A-Z][A-Z0-9_]*\.bit_length"
    r"|[A-Z][A-Z0-9_]*\b|[0-9]+"
    r"|==|!=|<=|>=|[!<>()-]|\s+"
)


def ruby_expression(
    expression: str, *, local_names: Collection[str] = (), code: bool = False
) -> bool:
    """Whitelist source tokens before translation; AST validation follows."""
    atoms = _ATOMS + (r"|code\.(?:num|name)\b" if code else "")
    if local_names:
        atoms += "|" + "|".join(re.escape(name) + r"\b" for name in local_names)
    token = re.compile(atoms)
    cursor = 0
    while cursor < len(expression):
        match = token.match(expression, cursor)
        if match is None:
            return False
        cursor = match.end()
    return True


def legacy_tokens(text: str) -> tuple[list[tuple[re.Match[str], str, str]], str]:
    """Erubi 1.13 standalone trimming, independently of native trim flags."""
    tokens = []
    cursor = 0
    is_bol = True
    for match in TAG.finditer(text):
        literal = text[cursor : match.start()]
        if "<%" in literal:
            raise ValueError("unterminated legacy delimiter")
        rspace = match.group(4) or ""
        if match.group(2).strip().startswith("="):
            if match.group(3):
                rspace = ""
        else:
            suffix = literal.rsplit("\n", 1)[-1]
            standalone = ("\n" in literal or is_bol) and re.fullmatch(r"[ \t]*", suffix) is not None
            if standalone and match.group(4):
                literal = literal[: len(literal) - len(suffix)] if suffix else literal
                rspace = ""
        is_bol = bool(match.group(4))
        tokens.append((match, literal.replace("\r\n", "\n"), rspace.replace("\r\n", "\n")))
        cursor = match.end()
    remainder = text[cursor:]
    if "<%" in remainder:
        raise ValueError("unterminated legacy delimiter")
    # Ruby parses CRLF in Erubi's multiline string literals as LF.
    return tokens, remainder.replace("\r\n", "\n")
