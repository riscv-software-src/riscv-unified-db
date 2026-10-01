# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Legacy report text conventions; no schema access or architecture solving."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from ..conditions import (
    AllOf,
    AnyOf,
    ConstantCondition,
    ExactlyOne,
    ExtensionTerm,
    Implies,
    NoneOf,
    Not,
    ParameterOperator,
    ParameterTerm,
    XlenTerm,
    parse_condition,
)
from ..errors import DataError
from ..versions import VersionRequirement


class ReportError(DataError):
    """A requested report has unsupported or invalid input."""


def _number_words(number: int, *, ordinal: bool = False) -> str:
    cardinal = (
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
    )
    ordinals = (
        "zeroth",
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "sixth",
        "seventh",
        "eighth",
        "ninth",
        "tenth",
        "eleventh",
        "twelfth",
        "thirteenth",
        "fourteenth",
        "fifteenth",
        "sixteenth",
        "seventeenth",
        "eighteenth",
        "nineteenth",
    )
    tens = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
    if number < 20:
        return (ordinals if ordinal else cardinal)[number]
    if number < 100:
        quotient, remainder = divmod(number, 10)
        return (
            tens[quotient] + " " + _number_words(remainder, ordinal=ordinal)
            if remainder
            else tens[quotient][:-1] + "ieth"
            if ordinal
            else tens[quotient]
        )
    for scale, name in (
        (10**18, "quintillion"),
        (10**15, "quadrillion"),
        (10**12, "trillion"),
        (10**9, "billion"),
        (10**6, "million"),
        (1000, "thousand"),
        (100, "hundred"),
    ):
        if scale <= number:
            if number >= 10**21:
                raise ReportError("indexed human conditions above quintillions are unsupported")
            quotient, remainder = divmod(number, scale)
            head = _number_words(quotient) + " " + name
            return (
                head + " " + _number_words(remainder, ordinal=ordinal)
                if remainder
                else head + "th"
                if ordinal
                else head
            )
    raise ReportError("invalid parameter condition index")


def _value(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return ""
    if isinstance(value, tuple):
        return "[" + ", ".join(_value(item) for item in value) + "]"
    return str(value)


def condition_text(raw: Any, *, pretty: bool = False) -> str:
    if isinstance(raw, str):
        raw = {"extension": {"name": raw}}
    spellings = {}

    def collect(value):
        if isinstance(value, Mapping):
            if isinstance(value.get("name"), str) and "version" in value:
                versions = value["version"]
                for text in versions if isinstance(versions, (tuple, list)) else (versions,):
                    requirement = VersionRequirement.parse(text)
                    spellings[
                        (value["name"], requirement.operator.value, requirement.version.canonical)
                    ] = re.sub(
                        r"^(?:>=|>|~>|<=|<|!=|=)?\s*",
                        "",
                        text.strip(),
                    )
            for child in value.values():
                collect(child)
        elif isinstance(value, (tuple, list)):
            for child in value:
                collect(child)

    collect(raw)
    return _condition_text(parse_condition(raw), pretty, spellings)


def _condition_text(condition, pretty: bool, spellings: dict) -> str:
    if isinstance(condition, ConstantCondition):
        return _value(condition.value) if pretty else ("1" if condition.value else "0")
    if isinstance(condition, ExtensionTerm):
        terms = []
        for requirement in condition.requirements:
            version = (
                "0" if requirement.version.canonical == "0.0.0" else requirement.version.canonical
            )
            version = spellings.get(
                (condition.name, requirement.operator.value, requirement.version.canonical), version
            )
            terms.append(
                f"Extension {condition.name}, version {version}"
                if pretty
                else f"{condition.name}{requirement.operator.value}{version}"
            )
        return (
            terms[0] if len(terms) == 1 else "(" + (" and " if pretty else " && ").join(terms) + ")"
        )
    if isinstance(condition, ParameterTerm):
        name = condition.name
        if condition.index is not None:
            name += f"[{condition.index}]"
        elif condition.size:
            name = f"$array_size({name})"
        elif condition.bit_range is not None:
            name += f"[{condition.bit_range[0]}:{condition.bit_range[1]}]"
        value = _value(condition.value)
        if pretty:
            # The retained renderer preserves the original spelling and missing
            # scalar @name in Ruby's human report; structured rows keep the name.
            phrases = {
                ParameterOperator.EQUAL: "equals",
                ParameterOperator.NOT_EQUAL: "does not equal",
                ParameterOperator.LESS_THAN: "is less than",
                ParameterOperator.GREATER_THAN: "is greater than",
                ParameterOperator.LESS_THAN_OR_EQUAL: "is less than or equal to",
                ParameterOperator.GREATER_THAN_OR_EQUAL: "is greater than or equal to",
                ParameterOperator.INCLUDES: "(an array) includes the value",
                ParameterOperator.ONE_OF: "is one of the following values:",
            }
            if condition.index is None:
                return f"Paremeter  {phrases[condition.operator]} {value}"
            phrase = phrases[condition.operator]
            if condition.operator is ParameterOperator.ONE_OF:
                phrase = "equals on of the following values:"
            return f"The {_number_words(condition.index, ordinal=True)} element of paremeter  {phrase} {value}"
        if isinstance(condition.value, str):
            value = json.dumps(condition.value, ensure_ascii=False)
        if condition.operator is ParameterOperator.INCLUDES:
            return f"$array_includes?({name}, {value})"
        if condition.operator is ParameterOperator.ONE_OF:
            terms = [
                f"({name}=={json.dumps(item, ensure_ascii=False)})" for item in condition.value
            ]
            return (
                "("
                + " || ".join(
                    "("
                    + term
                    + " && "
                    + " && ".join("!" + other for index, other in enumerate(terms) if index != own)
                    + ")"
                    for own, term in enumerate(terms)
                )
                + ")"
            )
        symbols = {
            ParameterOperator.EQUAL: "==",
            ParameterOperator.NOT_EQUAL: "!=",
            ParameterOperator.LESS_THAN: "<",
            ParameterOperator.GREATER_THAN: ">",
            ParameterOperator.LESS_THAN_OR_EQUAL: "<=",
            ParameterOperator.GREATER_THAN_OR_EQUAL: ">=",
        }
        return f"({name}{symbols[condition.operator]}{value})"
    if isinstance(condition, XlenTerm):
        return f"xlen={condition.value}"
    if isinstance(condition, Not):
        return ("not " if pretty else "!") + _condition_text(condition.child, pretty, spellings)
    if isinstance(condition, (AllOf, AnyOf, ExactlyOne)):
        operator = {
            AllOf: "and" if pretty else "&&",
            AnyOf: "or" if pretty else "||",
            ExactlyOne: "xor" if pretty else "^",
        }[type(condition)]
        return (
            "("
            + f" {operator} ".join(
                _condition_text(child, pretty, spellings) for child in condition.children
            )
            + ")"
        )
    if isinstance(condition, NoneOf):
        terms = [_condition_text(child, pretty, spellings) for child in condition.children]
        return "none of (" + ", ".join(terms) + ")" if pretty else "!(" + " || ".join(terms) + ")"
    if isinstance(condition, Implies):
        left, right = (
            _condition_text(condition.antecedent, pretty, spellings),
            _condition_text(condition.consequent, pretty, spellings),
        )
        return f"if {left} then {right})" if pretty else f"({left} -> {right})"
    raise ReportError(f"cannot render condition of type {type(condition).__name__}")


def _number(value: Any) -> str:
    return hex(value) if type(value) is int and value > 999 else _value(value)


def schema_text(schema: Mapping[str, Any]) -> str:
    """Describe the declared schema, not a parameter's configured value."""
    if not isinstance(schema, Mapping) or not schema:
        raise ReportError("expected a nonempty parameter schema")
    if "const" in schema:
        return _number(schema["const"])
    if "enum" in schema:
        return "[" + ", ".join(_value(item) for item in schema["enum"]) + "]"
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        if name in ("uint32", "uint64"):
            return name[4:] + "-bit integer"
        raise ReportError(f"unhandled type ref: {schema['$ref']}")
    if "not" in schema:
        exclusion = schema["not"]
        if "const" in exclusion:
            return "≠ " + _number(exclusion["const"])
        if "anyOf" in exclusion and all("const" in item for item in exclusion["anyOf"]):
            return "≠ " + " or ".join(_number(item["const"]) for item in exclusion["anyOf"])
        raise ReportError("unsupported parameter schema exclusion")
    if "allOf" in schema:
        return ", ".join(schema_text(item) for item in schema["allOf"])
    kind = schema.get("type")
    if kind == "integer":
        minimum, maximum = schema.get("minimum"), schema.get("maximum")
        if minimum is not None and maximum is not None:
            if minimum == 0 and maximum > 0 and maximum & (maximum + 1) == 0:
                return f"{maximum.bit_length()}-bit integer"
            return f"{_number(minimum)} to {_number(maximum)}"
        if minimum is not None:
            return "&#8805; " + _number(minimum)
        if maximum is not None:
            return "&#8804; " + _number(maximum)
        return "integer"
    if kind == "string":
        return schema.get("format") or (
            "string matching " + schema["pattern"] if schema.get("pattern") else "string"
        )
    if kind == "boolean":
        return "boolean"
    if kind == "array":
        minimum, maximum = schema.get("minItems"), schema.get("maxItems")
        size = ""
        if minimum is not None and maximum is not None:
            size = (
                f"{minimum}-element "
                if minimum == maximum
                else f"{minimum}-element to {maximum}-element "
            )
        elif minimum is not None:
            size = f"at least {minimum}-element "
        elif maximum is not None:
            size = f"at most {maximum}-element "
        items = schema.get("items")
        text = size + "array"
        if isinstance(items, Mapping):
            text += " of " + schema_text(items)
        elif isinstance(items, Sequence) and not isinstance(items, str):
            text += " where: +\n" + "".join(
                f"&nbsp;&nbsp;[{index}] is {schema_text(item)} +\n"
                for index, item in enumerate(items)
            )
            if schema.get("additionalItems"):
                text += "additional items are: +\n&nbsp;&nbsp;" + schema_text(
                    schema["additionalItems"]
                )
        elif items is not None:
            raise ReportError("unsupported array items in parameter schema")
        if "contains" in schema:
            text += " Contains : [" + schema_text(schema["contains"]) + "]"
        return text
    raise ReportError(f"unsupported parameter schema type: {kind!r}")


def _display_width(text: str) -> int:
    return sum(
        0
        if unicodedata.combining(character)
        else 2
        if unicodedata.east_asian_width(character) in ("W", "F")
        else 1
        for character in text
    )


def ascii_table(rows: Sequence[Sequence[str]]) -> str:
    cells = [["Name", "Defined By", "description"], *rows]
    lines = [[cell.splitlines() or [""] for cell in row] for row in cells]
    widths = [
        max(_display_width(line) for row in lines for line in row[column]) for column in range(3)
    ]
    separator = "+" + "+".join("-" * (width + 2) for width in widths) + "+\n"
    result = separator
    for row in lines:
        for index in range(max(map(len, row))):
            values = [cell[index] if index < len(cell) else "" for cell in row]
            result += (
                "|"
                + "|".join(
                    " " + value + " " * (width - _display_width(value) + 1)
                    for value, width in zip(values, widths, strict=True)
                )
                + "|\n"
            )
        result += separator
    return result
