# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Realistic scalar/collection cases, including the independent review probes."""

from __future__ import annotations

import random

ATOMS = [
    "yes",
    "no",
    "Yes",
    "NO",
    "on",
    "off",
    "true",
    "True",
    "null",
    "~",
    "Null",
    "1",
    "1.5",
    "1e3",
    "0x1f",
    "0o17",
    "017",
    "1_000",
    "2024-01-01",
    "2024-01-01 10:00:00",
    "12:30",
    "1:2:3",
    ":sym",
    "*a",
    "&a",
    "!t",
    "@x",
    "`x",
    "%x",
    "|",
    "|x",
    ">",
    "<",
    "=",
    "'q'",
    '"q"',
    "a: b",
    "a #b",
    "a# b",
    "# c",
    "- x",
    "? y",
    "x:",
    "x: ",
    "[a]",
    "{a}",
    "a, b",
    "",
    " ",
    " lead",
    "trail ",
    "tab\tx",
    "é",
    "日本",
    "😀",
    "line1\nline2",
    "line1\n",
    "\nlead",
    "a\n\nb",
    "  indented\nnext",
    "x" * 79,
    "x" * 80,
    "x" * 81,
    "x" * 200,
    ("word " * 30).strip(),
    ("word " * 30).strip() + " ",
    "a b " * 41,
    "-",
    "--",
    "---",
    "...",
    "- ",
    "a\\b",
    "null ",
    "nan",
    ".inf",
    "-.5",
    "+1",
    "1.",
    "0b101",
    "0.1e-5",
    "1,000",
    "y",
    "n",
    "Y",
    "N",
    "<<",
    "$x",
    "$",
    "a'b",
    'a"b',
    "it's: fine",
    "v1.0",
    "1.0",
    "1.2.3",
    "0",
    "00",
    "-1",
    "3.14",
    "a/b",
    "~/x",
    "a@b.com",
    "http://x.y/z?q=1#f",
    "[x] y",
    "{{x}}",
    "a:b",
    "foo: bar baz qux " + "z " * 40,
    "0o8",
    "1e3.5",
    "1E3",
    "-1e3",
    "1e-3",
    ".5",
    "5.",
    "+.5",
    "0x",
    "1__0",
    "_1",
    "1_",
    "0_1",
    "0.1_0",
    "2024-1-1",
    "2024-01-01T10:00:00Z",
    "10:00",
    "60:00:00",
    "1:30:00.5",
    "true ",
    "yes.",
    "=x",
    "<x",
    "~x",
    "^x",
    "!",
    "!!str x",
    "&",
    "*",
    "&x y",
    "%",
    "%TAG",
]
NUMBERS = [
    0,
    1,
    -5,
    3.14,
    1e20,
    1e-7,
    1e16,
    1.5e-5,
    1e15,
    100.0,
    True,
    False,
    None,
    10**20,
    2.0,
    0.1,
    1e100,
    -0.0,
]


def cases() -> list:
    strings = [
        *ATOMS,
        "\0",
        "\x01",
        "\a\b\t\v\f\r\x1b",
        "\x85",
        "\xa0",
        "\u2028",
        "\u2029",
        "\ufeff",
        "𐐀",
        "👩‍💻",
        "e\u0301",
        "\u0301mark",
        "Ω",
        "\u203f",
        "line1\nline2\n",
        "line1\n\n",
        "\n",
        "\n\n",
        "first \nsecond",
        "first\n  indented",
        "first\r\nsecond",
        "line with \ttab\nnext",
        "a" * 1025,
        "''",
        '""',
        "2024-02-29",
        "2023-02-29",
        "0000-1-1",
    ]
    result = [
        *({"k": value} for value in strings),
        *({value: 1} for value in strings),
        *({"k": value} for value in NUMBERS),
        *([value] for value in strings),
        *({"nested": {"value": [value, None, {"again": value}]}} for value in strings),
        {},
        [],
        {"empty": {}, "array": [], "nil": None},
        {"items": [{}, [], {"empty": ""}, {"nil": None}]},
        {"array": [[1], [2, {"sequence": [None, True, False]}]]},
        [{"long text": ("word " * 70).strip()}, {"float": NUMBERS}],
    ]
    rng = random.Random(7411)
    vocabulary = ["word", "é", "日本", "😀", "x" * 95, "a:b", "a'\"b", "two  spaces"]
    for _ in range(240):
        text = " ".join(rng.choices(vocabulary, k=rng.randrange(1, 35)))
        result.append({"deep": [{"text": text}, {"value": rng.choice(NUMBERS)}]})
    for _ in range(160):
        result.append({"value": rng.uniform(-9, 9) * 10.0 ** rng.randrange(-200, 201)})
    return result


def edge_cases() -> list:
    strings = [
        "0b_1",
        "0b1_",
        "0x_FF",
        "0xFF_",
        "0_1",
        "00_",
        "1,",
        "1,,0",
        "0x__",
        "0b_",
        "0,,1",
        "001",
        "09",
        "019",
        "0.0",
        "1.e+3",
        ".e+3",
        "1,0.0",
        "1_0.0",
        "1.0E3",
        "1.0e+3",
        "1.0e3",
        "+.inf",
        ".NAN",
        '"unclosed',
        "first\n\n\n",
        "\n\n\n",
        "first\nsecond\n\n",
        "first\rsecond",
        "first\r",
        "first\u2028second",
        "first\x85second",
        "a\u2029b",
        "\u007f",
        "\u009f",
        "\ufffe",
        "\uffff",
        "2024-1-1 24:00:00",
        "2024-1-1 24:01:00",
        "2024-1-1 23:59:60",
        "2024-02-31 10:00:00",
        "2024-01-01 10:00:00+25:00",
        "2024-01-01 10:00:00+23:59",
        "2024-01-01 10:00:00+01:99",
        "2024-01-01 10:00:00-00:30",
        "2024-01-01 10:00:00+1200",
        "0000-00-00",
        "0000-02-29",
        "1900-02-29",
        "2000-02-29",
        "あ" * 80,
        "a" * 1090 + " b",
        "line\n  " + "a" * 90,
    ]
    values = [
        [],
        {},
        [None, True, False, 1e20, "😀"],
        {"caption": "multi\nline", "number": 1e-7, "quoted": 'a"b'},
        ["\0\a\v\x1b\x7f", "\u2028", "\u2029", "👩‍💻", "\u0301mark"],
        *({"nested": [text]} for text in strings[-10:]),
    ]
    numbers = [
        5e-324,
        2.2250738585072014e-308,
        1.7976931348623157e308,
        9.999999999999999e-5,
        0.0001,
        0.00015,
        999999999999999.0,
        1234567890123456.0,
        -3832926594478627.5,
    ]
    rng = random.Random(2389)
    numbers.extend(rng.uniform(-9, 9) * 10.0 ** rng.randrange(-305, 305) for _ in range(300))
    return [
        *({"value": text} for text in strings),
        *({text: {"value": text}} for text in strings),
        *({"nested": [text, None]} for text in strings),
        *({"value": value} for value in values),
        *({"value": number} for number in numbers),
    ]


def boundary_cases() -> list:
    result = []
    for length in (80, 105, 106, 107, 108, 109, 126, 127, 128, 129, 130, 1024):
        for character in ("a", "é", "あ", "😀"):
            result.append({character * length: {"value": 1}})
    for tail in (None, "", 1, True, [], {}, ["next"], {"next": None}):
        for text in ("first\n\n", "\n\n\n", "first\n  indented\n\n"):
            result.extend(([text, tail], {"first": text, "last": tail}))
    strings = [
        *map(chr, range(1, 160)),
        "\u00ad",
        "\u200b",
        "\u200d",
        "\ufeff",
        "\ufffe",
        "\uffff",
        "#{ruby}",
        "#$ruby",
        "#@ruby",
        "\\n",
        'a"b',
        "日本",
        "😀",
        ":a\nb",
        ":a\n",
        "a\tb",
        "a\n",
        "a\r",
        "\r\n",
        "2024-01-01 10:00:00+24:00",
        "2024-01-01 10:00:00+23:99",
        "2024-01-01 10:00:00+1:99",
        "2024-01-01 10:00:00+01",
        "2024-01-01 10:00:00+120",
        "2024-01-01 10:00:00-00:99",
        "2024-01-01 10:00:00.001Z",
        "0000-02-30",
        "2024-00-1 10:00:00",
        "2024-02-32 10:00:00",
    ]
    result.extend({"value": [text, {text: text}]} for text in strings)
    for prefix in ("", "'", '"', "*", ":", " leading ", "multi\n"):
        for word in ("word", "  space", "😀", "日本", "a:b", 'a"b', "x" * 95):
            result.append({"value": prefix + (word + " ") * 40})
    rng = random.Random(98431)
    vocabulary = [*ATOMS, *strings, *NUMBERS]
    for _ in range(180):
        result.append({"value": [rng.choice(vocabulary) for _ in range(rng.randrange(1, 7))]})
    return result


def scanner_cases() -> list:
    result = []
    for date in ("2024-01-01", "0000-02-30"):
        for time in ("10:00:00", "24:00:00", "24:01:00", "23:59:60"):
            for zone in (
                "Z",
                "",
                "+00",
                "-00:30",
                "+120",
                "+239",
                "+240",
                "+250",
                "+2399",
                "+2400",
                "+25:00",
                "+23:99",
                "+01:99",
            ):
                text = f"{date} {time}{zone}"
                result.extend(({"value": text}, {text: [text]}, {"nested": [[text, None]]}))
    return result


def block_scalar_cases() -> list:
    result = [
        {"a": "p\nq\n\n", "b": "r\ns"},
        {"a": "p\nq\n\n", "b": "r\ns\n"},
        {"a": ["p\nq\n\n", "r\ns"]},
        {"a": "p\nq\n\n", "b": "r\ns\n\n", "c": "t\nu"},
    ]
    literals = ["p\nq" + ending for ending in ("", "\n", "\n\n", "\n\n\n")]
    for first in literals:
        for second in [*literals, "plain", None, 1, {}, []]:
            result.extend(
                (
                    {"a": first, "b": second},
                    {"a": [first, second]},
                    {"a": [{"text": first}, {"text": second}]},
                )
            )
    for first in literals:
        for second in literals:
            for third in literals:
                result.append({"a": first, "b": second, "c": third})
    return result
