# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# Copyright (c) 2009 Aaron Patterson, et al.
# SPDX-License-Identifier: MIT AND BSD-3-Clause-Clear

"""Psych 5 string/scalar rules, adapted from its MIT-licensed scalar scanner."""

from __future__ import annotations

import calendar
import math
import re
import unicodedata
from decimal import Decimal
from typing import Any

_INTEGER = re.compile(
    r"^(?:[-+]?0b[_,]*[0-1][0-1_,]*|[-+]?0[_,]*[0-7][0-7_,]*"
    r"|[-+]?(?:0|[1-9](?:[0-9]|,[0-9]|_[0-9])*)"
    r"|[-+]?0x[_,]*[0-9a-fA-F][0-9a-fA-F_,]*)$"
)
_FLOAT = re.compile(r"^[-+]?(?:[0-9][0-9_,]*)?\.[0-9]*(?:[eE][-+][0-9]+)?$")
_DATE = re.compile(r"^([0-9]{4})-(1[012]|0[0-9]|[0-9])-([12][0-9]|3[01]|0[0-9]|[0-9])$")
_TIME = re.compile(
    r"^(-?[0-9]{4})-([0-9]{1,2})-([0-9]{1,2})(?:[Tt]|\s+)"
    r"([0-9]{1,2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]*)?"
    r"(?:\s*(Z|[-+][0-9]{1,2}:?(?:[0-9]{2})?))?$"
)
_SEXAGESIMAL = re.compile(r"^[-+]?[0-9][0-9_]*(?::[0-5]?[0-9]){1,2}(?:\.[0-9_]*)?$")


def ruby_float(value: float) -> str:
    """Ruby Float#to_s uses shortest digits, a .0 coefficient, and its own cutoffs."""
    if not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("-Infinity" if value < 0 else "Infinity")
    decimal = Decimal(repr(value))
    significant = decimal.normalize()
    if value and (
        abs(value) < 1e-4
        or (
            decimal.adjusted() >= 15
            and decimal.adjusted() + 1 >= len(significant.as_tuple().digits)
        )
    ):
        exponent = decimal.adjusted()
        coefficient = format(decimal.scaleb(-exponent), "f").rstrip("0").rstrip(".")
        if "." not in coefficient:
            coefficient += ".0"
        return f"{coefficient}e{exponent:+03d}"
    result = format(decimal, "f")
    return result if "." in result else result + ".0"


def ruby_string(value: Any) -> str:
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
        return ruby_float(value)
    if isinstance(value, dict | list):
        return ruby_inspect(value)
    return str(value)


def ruby_inspect(value: Any) -> str:
    """Ruby collection #to_s recursively uses #inspect, including quoted strings."""
    if value is None:
        return "nil"
    if isinstance(value, list):
        return "[" + ", ".join(ruby_inspect(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ", ".join(
                f"{ruby_inspect(key)} => {ruby_inspect(item)}" for key, item in value.items()
            )
            + "}"
        )
    if not isinstance(value, str):
        return ruby_string(value)
    escapes = dict(zip("\a\b\t\n\v\f\r\x1b", ("a", "b", "t", "n", "v", "f", "r", "e")))
    result = '"'
    for index, character in enumerate(value):
        if character in escapes:
            result += "\\" + escapes[character]
        elif character in '"\\' or (
            character == "#" and value[index + 1 : index + 2] in ("{", "$", "@")
        ):
            result += "\\" + character
        elif (
            ord(character) < 32
            or 0x7F <= ord(character) <= 0x9F
            or character in "\u2028\u2029\ufffe\uffff"
        ):
            result += f"\\u{ord(character):04X}"
        else:
            result += character
    return result + '"'


def _word(character: str) -> bool:
    return (
        unicodedata.category(character)[0] in "LMN"
        or unicodedata.category(character) == "Pc"
        or character in "\u200c\u200d"
    )


def non_string_token(value: str) -> bool:
    """Whether Psych's legacy scanner would resolve a string as another type."""
    if value == "" or value.lower() in {"~", "null", "yes", "true", "on", "no", "false", "off"}:
        return True
    if "\n" in value:
        return False
    if value.lower() in {".inf", "+.inf", "-.inf", ".nan"} or (
        value.startswith(":") and len(value) > 1
    ):
        return True
    date = _DATE.fullmatch(value)
    if date:
        year, month, day = map(int, date.groups())
        return 1 <= month <= 12 and 1 <= day <= calendar.monthrange(year, month)[1]
    timestamp = _TIME.fullmatch(value)
    if timestamp:
        _, month, day, hour, minute, second = map(int, timestamp.groups()[:6])
        zone = timestamp[7]
        if zone and zone != "Z":
            offset = re.fullmatch(r"[-+]([0-9]{1,2}):?([0-9]{1,2})?", zone)
            hours = int(offset[1])
            minutes = int(offset[2] or 0)
            if hours * 60 + minutes >= 24 * 60:
                return False
        return (
            1 <= month <= 12
            and 1 <= day <= 31
            and 0 <= hour <= 24
            and 0 <= minute <= 59
            and 0 <= second <= 60
            and (hour != 24 or minute == second == 0)
        )
    if _SEXAGESIMAL.fullmatch(value):
        return True
    if _FLOAT.fullmatch(value) and re.search(r"[0-9]", value):
        return True
    return bool(_INTEGER.fullmatch(value))


def plain_tag(value: str) -> str:
    if value.lower() in {"", "~", "null"}:
        return "null"
    if value.lower() in {"yes", "true", "on", "no", "false", "off"}:
        return "bool"
    if _INTEGER.fullmatch(value):
        return "int"
    return "float" if non_string_token(value) else "str"


def string_style(value: str) -> str:
    """Psych's requested style; the libyaml emitter can further restrict it."""
    if re.search(r"\n(?!\n?\Z)", value):
        return "|"
    if value == "<<":
        return "'"
    if value in {"y", "Y", "n", "N"}:
        return '"'
    for index, character in enumerate(value):
        if (
            (index == 0 or value[index - 1] == "\n")
            and not _word(character)
            and '"' not in value[index + 1 :].split("\n", 1)[0]
        ):
            return '"'
    if non_string_token(value) or re.match(r"^0[0-7]*[89]", value):
        return "'"
    return ""
