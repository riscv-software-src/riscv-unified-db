# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Repository authoring support for layout-derived architecture files.

The renderer intentionally implements only the constructs used by UDB data
layouts: scalar interpolation, boolean branches, and bounded iteration.  It
does not evaluate Python or Ruby source and it has no access to builtins,
imports, attributes, or the filesystem.
"""

from __future__ import annotations

import ast
import operator
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path, PurePosixPath
from typing import Any

from .authoring import AuthoringPlan, GeneratedFile
from .errors import LayoutError
from .layout_collections import LayoutCollection, LayoutJob, _relative_path, get_layout_collection
from .resources import package_data_root

_OPENING_TAG = re.compile(r"{{|{%|{#")
_MAX_NESTING = 64
_MAX_TEMPLATE_NODES = 10_000
_MAX_EXPRESSION_CHARACTERS = 4096
_MAX_EXPRESSION_NODES = 256
_MAX_RENDER_STEPS = 100_000
_MAX_OUTPUT_CHARACTERS = 16 * 1024 * 1024


@dataclass(frozen=True)
class _Text:
    value: str


@dataclass(frozen=True)
class _Expression:
    value: str


@dataclass(frozen=True)
class _If:
    branches: tuple[tuple[str | None, tuple[object, ...]], ...]


@dataclass(frozen=True)
class _For:
    variable: str
    values: str
    body: tuple[object, ...]


@dataclass
class _RenderBudget:
    steps: int = 0
    characters: int = 0

    def consume(self, source: Path, *, characters: int = 0) -> None:
        self.steps += 1
        self.characters += characters
        if self.steps > _MAX_RENDER_STEPS:
            raise LayoutError(f"{source}: layout rendering exceeds {_MAX_RENDER_STEPS} steps")
        if self.characters > _MAX_OUTPUT_CHARACTERS:
            raise LayoutError(
                f"{source}: layout output exceeds {_MAX_OUTPUT_CHARACTERS} characters"
            )


def _tokenize(template: str, source: Path) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    cursor = 0
    trim_next_newline = False
    while match := _OPENING_TAG.search(template, cursor):
        opening = match.group()
        if opening == "{#":
            raise LayoutError(f"{source}: unterminated or unsupported layout delimiter")
        text = template[cursor : match.start()]
        if trim_next_newline:
            text = re.sub(r"\A\r?\n", "", text, count=1)
            trim_next_newline = False
        closing = "}}" if opening == "{{" else "%}"
        end = _tag_end(template, match.end(), closing)
        if end is None:
            raise LayoutError(f"{source}: unterminated or unsupported layout delimiter")
        body = template[match.end() : end]
        if body.startswith("-"):
            body = body[1:]
            if re.search(r"(?:^|\n)[ \t]*\Z", text):
                text = re.sub(r"[ \t]*\Z", "", text)
        if text:
            tokens.append(("text", text))
        if body.endswith("-"):
            body = body[:-1]
            trim_next_newline = True
        tokens.append(("expression" if opening == "{{" else "tag", body.strip()))
        cursor = end + len(closing)
    text = template[cursor:]
    if trim_next_newline:
        text = re.sub(r"\A\r?\n", "", text, count=1)
    if any(delimiter in text for delimiter in ("{{", "{%", "{#")):
        raise LayoutError(f"{source}: unterminated or unsupported layout delimiter")
    if text:
        tokens.append(("text", text))
    return tokens


def _tag_end(template: str, start: int, closing: str) -> int | None:
    """Find a tag terminator while ignoring terminator text inside Python strings."""

    quote: str | None = None
    triple = False
    escaped = False
    index = start
    while index < len(template):
        if quote is None:
            if template.startswith(closing, index):
                return index
            if template[index] in {"'", '"'}:
                quote = template[index]
                triple = template.startswith(quote * 3, index)
                index += 3 if triple else 1
                continue
        elif escaped:
            escaped = False
        elif template[index] == "\\":
            escaped = True
        elif triple and template.startswith(quote * 3, index):
            quote = None
            triple = False
            index += 3
            continue
        elif not triple and template[index] == quote:
            quote = None
        index += 1
    return None


def _parse(template: str, source: Path) -> tuple[object, ...]:
    root: list[object] = []
    current = root
    stack: list[tuple[str, Any, list[object]]] = []

    tokens = _tokenize(template, source)
    if len(tokens) > _MAX_TEMPLATE_NODES:
        raise LayoutError(f"{source}: layout exceeds {_MAX_TEMPLATE_NODES} template nodes")
    for kind, value in tokens:
        if kind == "text":
            current.append(_Text(value))
            continue
        if kind == "expression":
            current.append(_Expression(value))
            continue
        if value.startswith("if "):
            if len(stack) >= _MAX_NESTING:
                raise LayoutError(f"{source}: layout nesting exceeds {_MAX_NESTING} blocks")
            branches: list[tuple[str | None, list[object]]] = [(value[3:].strip(), [])]
            current.append(branches)
            stack.append(("if", branches, current))
            current = branches[-1][1]
            continue
        if value.startswith("elif "):
            if not stack or stack[-1][0] != "if":
                raise LayoutError(f"{source}: elif without matching if")
            branches = stack[-1][1]
            if branches[-1][0] is None:
                raise LayoutError(f"{source}: elif after else")
            branches.append((value[5:].strip(), []))
            current = branches[-1][1]
            continue
        if value == "else":
            if not stack or stack[-1][0] != "if":
                raise LayoutError(f"{source}: else without matching if")
            branches = stack[-1][1]
            if branches[-1][0] is None:
                raise LayoutError(f"{source}: duplicate else")
            branches.append((None, []))
            current = branches[-1][1]
            continue
        loop = re.fullmatch(r"for ([A-Za-z_]\w*) in ([A-Za-z_]\w*)", value)
        if loop:
            if len(stack) >= _MAX_NESTING:
                raise LayoutError(f"{source}: layout nesting exceeds {_MAX_NESTING} blocks")
            body: list[object] = []
            node = [loop.group(1), loop.group(2), body]
            current.append(node)
            stack.append(("for", node, current))
            current = body
            continue
        if value in {"endif", "endfor"}:
            if not stack:
                raise LayoutError(f"{source}: end without an open block")
            block_kind, node, parent = stack.pop()
            expected = "endif" if block_kind == "if" else "endfor"
            if value != expected:
                raise LayoutError(f"{source}: expected {expected}, found {value}")
            index = parent.index(node)
            if block_kind == "if":
                parent[index] = _If(tuple((condition, tuple(body)) for condition, body in node))
            else:
                variable, values, body = node
                parent[index] = _For(variable, values, tuple(body))
            current = parent
            continue
        raise LayoutError(f"{source}: unsupported layout directive: {value!r}")

    if stack:
        raise LayoutError(f"{source}: unterminated {stack[-1][0]} block")
    return tuple(root)


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
_COMPARISON_OPERATORS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def _expression(expression: str, values: Mapping[str, object], source: Path) -> object:
    if len(expression) > _MAX_EXPRESSION_CHARACTERS:
        raise LayoutError(
            f"{source}: layout expression exceeds {_MAX_EXPRESSION_CHARACTERS} characters"
        )
    try:
        tree = ast.parse(expression, mode="eval")
    except (RecursionError, SyntaxError) as error:
        raise LayoutError(f"{source}: invalid layout expression: {expression!r}") from error
    if sum(1 for _node in ast.walk(tree)) > _MAX_EXPRESSION_NODES:
        raise LayoutError(f"{source}: layout expression exceeds {_MAX_EXPRESSION_NODES} AST nodes")

    def visit(node: ast.AST) -> object:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, str | int | bool):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in values:
                raise LayoutError(f"{source}: unknown layout value {node.id!r}")
            return values[node.id]
        if isinstance(node, ast.Attribute) and not node.attr.startswith("_"):
            parent = visit(node.value)
            if isinstance(parent, Mapping) and node.attr in parent:
                return parent[node.attr]
        if isinstance(node, ast.BinOp):
            operation = _BINARY_OPERATORS.get(type(node.op))
            left = visit(node.left)
            right = visit(node.right)
            if operation is not None and type(left) is int and type(right) is int:
                return operation(left, right)
        if isinstance(node, ast.UnaryOp):
            operand = visit(node.operand)
            if isinstance(node.op, ast.Not) and type(operand) is bool:
                return not operand
            if isinstance(node.op, ast.USub) and type(operand) is int:
                return -operand
            if isinstance(node.op, ast.UAdd) and type(operand) is int:
                return operand
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for item in node.values:
                    result = visit(item)
                    if type(result) is not bool:
                        raise LayoutError(f"{source}: boolean operators require boolean values")
                    if not result:
                        return False
                return True
            if isinstance(node.op, ast.Or):
                for item in node.values:
                    result = visit(item)
                    if type(result) is not bool:
                        raise LayoutError(f"{source}: boolean operators require boolean values")
                    if result:
                        return True
                return False
        if isinstance(node, ast.Compare):
            left = visit(node.left)
            for operation_node, comparator in zip(node.ops, node.comparators, strict=True):
                operation = _COMPARISON_OPERATORS.get(type(operation_node))
                right = visit(comparator)
                if operation is None:
                    raise LayoutError(f"{source}: unsupported layout comparison: {expression!r}")
                if not operation(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            condition = visit(node.test)
            if type(condition) is not bool:
                raise LayoutError(f"{source}: conditional expression requires a boolean")
            return visit(node.body if condition else node.orelse)
        raise LayoutError(f"{source}: unsupported layout expression: {expression!r}")

    try:
        return visit(tree)
    except (ArithmeticError, RecursionError, TypeError) as error:
        raise LayoutError(
            f"{source}: invalid layout expression: {expression!r}: {error}"
        ) from error


def _condition(expression: str, values: Mapping[str, object], source: Path) -> bool:
    result = _expression(expression, values, source)
    if type(result) is not bool:
        raise LayoutError(f"{source}: layout condition is not boolean: {expression!r}")
    return result


def _render_nodes(
    nodes: Sequence[object],
    values: Mapping[str, object],
    source: Path,
    budget: _RenderBudget | None = None,
) -> str:
    if budget is None:
        budget = _RenderBudget()
    output: list[str] = []
    for node in nodes:
        budget.consume(source)
        if isinstance(node, _Text):
            budget.consume(source, characters=len(node.value))
            output.append(node.value)
        elif isinstance(node, _Expression):
            result = _expression(node.value, values, source)
            if isinstance(result, bool) or not isinstance(result, str | int):
                raise LayoutError(
                    f"{source}: interpolation is not a string or integer: {node.value!r}"
                )
            rendered = str(result)
            budget.consume(source, characters=len(rendered))
            output.append(rendered)
        elif isinstance(node, _If):
            for condition, body in node.branches:
                if condition is None or _condition(condition, values, source):
                    output.append(_render_nodes(body, values, source, budget))
                    break
        elif isinstance(node, _For):
            loop_values = _expression(node.values, values, source)
            if not isinstance(loop_values, Sequence) or isinstance(loop_values, str | bytes):
                raise LayoutError(f"{source}: loop value {node.values!r} is not a bounded sequence")
            if len(loop_values) > 1024:
                raise LayoutError(f"{source}: loop value {node.values!r} exceeds 1024 items")
            for item in loop_values:
                budget.consume(source)
                if not isinstance(item, str | int | bool):
                    raise LayoutError(f"{source}: loop items must be scalar values")
                child_values = dict(values)
                child_values[node.variable] = item
                output.append(_render_nodes(node.body, child_values, source, budget))
        else:  # pragma: no cover - parser constructs every node
            raise TypeError(f"unknown layout node {node!r}")
    return "".join(output)


def _recipe_values(source: Path, supplied: Mapping[str, object]) -> dict[str, object]:
    values = dict(supplied)
    size = values.get("size")
    aq = values.get("aq")
    rl = values.get("rl")
    if size is not None:
        if source.name == "lSIZE.AQRL.layout":
            aq = values["aq"] = True
        elif source.name == "sSIZE.AQRL.layout":
            rl = values["rl"] = True
        if type(aq) is not bool or type(rl) is not bool:
            raise LayoutError(f"{source}: 'aq' and 'rl' must be booleans")
        common_sizes = {
            "b": {"name": "byte", "long_name_suffix": "Byte", "bits": 8, "funct3": "000"},
            "h": {"name": "halfword", "long_name_suffix": "Halfword", "bits": 16, "funct3": "001"},
            "w": {"name": "word", "long_name_suffix": "Word", "bits": 32, "funct3": "010"},
            "d": {
                "name": "doubleword",
                "long_name_suffix": "Doubleword",
                "bits": 64,
                "funct3": "011",
            },
            "q": {"name": "quadword", "long_name_suffix": "Quadword", "bits": 128, "funct3": "100"},
        }
        if size not in common_sizes:
            raise LayoutError(f"{source}: unsupported size {size!r}")
        allowed_sizes = (
            {"b", "h", "w", "d", "q"}
            if source.name == "amocas.SIZE.AQRL.layout"
            else {"w", "d"}
            if source.name in {"lr.SIZE.AQRL.layout", "sc.SIZE.AQRL.layout"}
            else {"b", "h", "w", "d"}
        )
        if size not in allowed_sizes:
            raise LayoutError(f"{source}: size {size!r} is not valid for this layout")
        current = dict(common_sizes[str(size)])
        if source.name == "sc.SIZE.AQRL.layout":
            current["long_name_suffix"] = str(current["long_name_suffix"]).lower()
        current.update(
            operation_bits=str(current["bits"]),
            align_bits=str(current["bits"]),
            load_reserved_bits=str(current["bits"]),
            aq_not="0" if aq else "1",
            rl_not="0" if rl else "1",
            extension="Zabha" if size in {"b", "h"} else "Zacas",
        )
        values["current_size"] = current
        values["aq_rl_suffix"] = ".aqrl" if aq and rl else ".aq" if aq else ".rl" if rl else ""
        values["aq_bit"] = "1" if aq else "0"
        values["rl_bit"] = "1" if rl else "0"
        values["aq_bit_val"] = "1'b1" if aq else "1'b0"
        values["rl_bit_val"] = "1'b1" if rl else "1'b0"
        values["aq_bool"] = "1'b1" if aq else "1'b0"
        values["rl_bool"] = "1'b1" if rl else "1'b0"
        values["alignment_bytes"] = int(current["bits"]) // 8
        values["acquire_suffix"] = " Acquire" if aq else ""
        values["release_suffix"] = " Release" if rl else ""
        values["store_slice"] = "" if size == "d" else f"[{int(current['bits']) - 1}:0]"
        values["ordering_parenthetical"] = (
            " (acquire-release)"
            if aq and rl
            else " (acquire)"
            if aq
            else " (release)"
            if rl
            else ""
        )
        values["ordering_description"] = (
            " with acquire and release ordering"
            if aq and rl
            else " with acquire ordering"
            if aq
            else " with release ordering"
            if rl
            else ""
        )
        values["load_result_description"] = (
            "sign-extended value" if size in {"b", "h", "w"} else "loaded value"
        )
        values["operand_description"] = (
            f"least-significant {current['name']} of register"
            if size in {"b", "h", "w"}
            else "value of register"
        )
        values["amo_extension"] = "Zabha" if size in {"b", "h"} else "Zaamo"
        values["sign_extend_prefix"] = "sext(" if size in {"b", "h", "w"} else ""
        values["value_slice"] = f"[{int(current['bits']) - 1}:0]" if size in {"b", "h", "w"} else ""
        values["sign_extend_suffix"] = f", {current['bits']})" if size in {"b", "h", "w"} else ""
    if "pmpaddr_num" in values:
        number = int(values["pmpaddr_num"])
        if number not in range(64):
            raise LayoutError(f"{source}: pmpaddr_num must be between 0 and 63")
        values["pmpcfg_num_32"] = number // 4
        values["pmpcfg_num_64"] = (number // 8) * 2
        values["address"] = f"{0x3B0 + number:X}"
        values["pmp_presence"] = "greaterThan: 0" if number < 16 else "greaterThan: 16"
    if "pmpcfg_num" in values:
        number = int(values["pmpcfg_num"])
        if number not in range(16):
            raise LayoutError(f"{source}: pmpcfg_num must be between 0 and 15")
        values["address"] = f"{0x3A0 + number:X}"
        values["pmpcfg_is_odd"] = number % 2 == 1
        values["pmpcfg_name"] = f"pmpcfg{number}"
        values["pmp_presence"] = "greaterThan: 0" if number < 4 else "greaterThan: 16"
        values["pmpcfg_fields"] = tuple(range(4 if number % 2 else 8))
    if "hpm_num" in values:
        number = int(values["hpm_num"])
        if number not in range(3, 32):
            raise LayoutError(f"{source}: hpm_num must be between 3 and 31")
        values["hpm_parameter_name"] = f"HPM_COUNTER{number}_WIDTH"
        values["mhpmcounter_name"] = (
            f"mhpmcounter{number}{'h' if source.name.endswith('Nh.layout') else ''}"
        )
        values["mhpmevent_name"] = (
            f"mhpmevent{number}{'h' if source.name.endswith('Nh.layout') else ''}"
        )
        address_bases = {
            "hpmcounterN.layout": (0xC00, ""),
            "hpmcounterNh.layout": (0xC80, ""),
            "mhpmcounterN.layout": (0xB00, "0x"),
            "mhpmcounterNh.layout": (0xB80, "0x"),
            "mhpmeventN.layout": (0x320, "0x"),
            "mhpmeventNh.layout": (0x720, ""),
        }
        if source.name in address_bases:
            base, prefix = address_bases[source.name]
            values["address"] = f"{prefix}{base + number:X}"
    if "n" in values:
        number = int(values["n"])
        if source.name == "mop.r.N.layout":
            if number not in range(32):
                raise LayoutError(f"{source}: n must be between 0 and 31")
            values["match"] = (
                f"1{number >> 4 & 1}00{number >> 3 & 1}{number >> 2 & 1}0111"
                f"{number >> 1 & 1}{number & 1}-----100-----1110011"
            )
        elif source.name == "mop.rr.N.layout":
            if number not in range(8):
                raise LayoutError(f"{source}: n must be between 0 and 7")
            values["match"] = (
                f"1{number >> 2 & 1}00{number >> 1 & 1}{number & 1}1----------100-----1110011"
            )
        elif source.name == "c.mop.N.layout":
            if number not in range(1, 16, 2):
                raise LayoutError(f"{source}: n must be odd and between 1 and 15")
            index = (number - 1) // 2
            values["match"] = f"01100{index >> 2 & 1}{index >> 1 & 1}{index & 1}10000001"
    values["hpm_numbers"] = tuple(range(3, 32))
    return values


def render_layout(source: Path, values: Mapping[str, object]) -> str:
    """Render one layout using its typed recipe values."""

    template = _read_layout_text(source, source)
    return _render_template(template, source, values)


def _render_template(template: str, source: Path, values: Mapping[str, object]) -> str:
    return _render_nodes(_parse(template, source), _recipe_values(source, values), source)


def _with_source_warning(rendered: str, source: PurePosixPath) -> str:
    first_line, separator, remainder = rendered.partition("\n")
    if not separator:
        raise LayoutError(f"{source}: generated output must contain a newline")
    return f"{first_line}\n\n# WARNING: This file is auto-generated from {source}\n\n{remainder}"


def iter_layout_jobs(
    root: Path, *, collections: Sequence[LayoutCollection] | None = None
) -> tuple[LayoutJob, ...]:
    """Return deterministic jobs; omitted collections retain the standard recipe set."""

    del root
    if collections is not None:
        collections = tuple(collections)
        if not collections or any(not isinstance(item, LayoutCollection) for item in collections):
            raise LayoutError("layout job selection requires at least one LayoutCollection")
        return tuple(
            LayoutJob(
                collection.source_root / job.source,
                collection.output_root / job.target,
                job.values,
            )
            for collection in collections
            for job in collection.jobs
        )
    jobs: list[LayoutJob] = []

    def add(source: str, target: str, **values: object) -> None:
        jobs.append(
            LayoutJob(
                PurePosixPath("spec/std/isa") / source,
                PurePosixPath("spec/std/isa") / target,
                values,
            )
        )

    for number in range(3, 32):
        for stem in ("mhpmcounter", "mhpmevent", "hpmcounter"):
            add(f"csr/Zihpm/{stem}N.layout", f"csr/Zihpm/{stem}{number}.yaml", hpm_num=number)
            add(f"csr/Zihpm/{stem}Nh.layout", f"csr/Zihpm/{stem}{number}h.yaml", hpm_num=number)
        add(
            "param/HPM_COUNTERN_WIDTH.layout",
            f"param/HPM_COUNTER{number}_WIDTH.yaml",
            hpm_num=number,
        )
    for number in range(64):
        add("csr/I/pmpaddrN.layout", f"csr/I/pmpaddr{number}.yaml", pmpaddr_num=number)
    for number in range(16):
        add("csr/I/pmpcfgN.layout", f"csr/I/pmpcfg{number}.yaml", pmpcfg_num=number)
    for path in (
        "csr/I/mcounteren",
        "csr/S/scounteren",
        "csr/Sscofpmf/scountovf",
        "csr/H/hcounteren",
        "csr/Zicntr/mcountinhibit",
    ):
        add(f"{path}.layout", f"{path}.yaml")

    variants = (
        ("", False, False),
        (".aq", True, False),
        (".rl", False, True),
        (".aqrl", True, True),
    )
    for operation in (
        "amoadd",
        "amoand",
        "amomax",
        "amomaxu",
        "amomin",
        "amominu",
        "amoor",
        "amoswap",
        "amoxor",
    ):
        for size in ("b", "h", "w", "d"):
            directory = "Zabha" if size in {"b", "h"} else "Zaamo"
            for suffix, aq, rl in variants:
                add(
                    f"inst/Zaamo/{operation}.SIZE.AQRL.layout",
                    f"inst/{directory}/{operation}.{size}{suffix}.yaml",
                    size=size,
                    aq=aq,
                    rl=rl,
                )
    for size in ("b", "h", "w", "d", "q"):
        directory = "Zacas" if size in {"w", "d", "q"} else "Zabha"
        for suffix, aq, rl in variants:
            add(
                "inst/Zacas/amocas.SIZE.AQRL.layout",
                f"inst/{directory}/amocas.{size}{suffix}.yaml",
                size=size,
                aq=aq,
                rl=rl,
            )
    for operation in ("lr", "sc"):
        for size in ("w", "d"):
            for suffix, aq, rl in variants:
                add(
                    f"inst/Zalrsc/{operation}.SIZE.AQRL.layout",
                    f"inst/Zalrsc/{operation}.{size}{suffix}.yaml",
                    size=size,
                    aq=aq,
                    rl=rl,
                )
    for size in ("b", "h", "w", "d"):
        for suffix, rl in ((".aq", False), (".aqrl", True)):
            add(
                "inst/Zalasr/lSIZE.AQRL.layout",
                f"inst/Zalasr/l{size}{suffix}.yaml",
                size=size,
                rl=rl,
            )
        for suffix, aq in ((".rl", False), (".aqrl", True)):
            add(
                "inst/Zalasr/sSIZE.AQRL.layout",
                f"inst/Zalasr/s{size}{suffix}.yaml",
                size=size,
                aq=aq,
            )
    for number in range(32):
        add("inst/Zimop/mop.r.N.layout", f"inst/Zimop/mop.r.{number}.yaml", n=number)
    for number in range(8):
        add("inst/Zimop/mop.rr.N.layout", f"inst/Zimop/mop.rr.{number}.yaml", n=number)
    for number in range(1, 16, 2):
        add("inst/Zcmop/c.mop.N.layout", f"inst/Zcmop/c.mop.{number}.yaml", n=number)
    return tuple(jobs)


def render_job(
    job: LayoutJob,
    root: Path,
    *,
    repository_sources: bool | None = None,
    resource: PurePosixPath | None = None,
) -> str:
    """Render a job and add its stable source ownership header."""

    source = Path(job.source.as_posix())
    template = _layout_text(
        root, job.source, repository_sources=repository_sources, resource=resource
    )
    rendered = _render_template(template, source, job.values)
    return _with_source_warning(rendered, job.source)


def _layout_text(
    root: Path,
    source: PurePosixPath,
    *,
    repository_sources: bool | None = None,
    resource: PurePosixPath | None = None,
) -> str:
    repository_source = root.joinpath(*source.parts)
    if repository_sources is True or (repository_sources is None and repository_source.is_file()):
        if not repository_source.is_file():
            raise LayoutError(f"layout source does not exist: {repository_source}")
        if not repository_source.resolve().is_relative_to(root.resolve()):
            raise LayoutError(f"layout source escapes source root: {repository_source}")
        return _read_layout_text(repository_source, repository_source)
    if resource is None:
        if not source.is_relative_to(PurePosixPath("spec/std/isa")):
            raise LayoutError(f"{source}: no bundled layout resource mapping")
        resource = PurePosixPath("layouts") / source.relative_to("spec/std/isa")
    resource = _relative_path(resource)
    try:
        bundled = package_data_root().joinpath(*resource.parts)
    except metadata.PackageNotFoundError as error:
        raise LayoutError("the installed udb distribution could not be located") from error
    if not bundled.is_file():
        raise LayoutError(f"{source}: bundled layout source does not exist: {resource}")
    return _read_layout_text(bundled, Path(source.as_posix()))


def _read_layout_text(resource: Any, source: Path) -> str:
    try:
        return resource.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise LayoutError(f"{source}: layout source is not valid UTF-8: {error}") from error
    except OSError as error:
        raise LayoutError(f"{source}: cannot read layout source: {error}") from error


def layout_plan(
    root: Path,
    *,
    collections: Sequence[LayoutCollection] | None = None,
    source_root: Path | None = None,
) -> AuthoringPlan:
    """Plan selected layouts, optionally reading an explicit separate source tree."""

    selected = (
        tuple(collections) if collections is not None else (get_layout_collection("standard"),)
    )
    if not selected or any(not isinstance(item, LayoutCollection) for item in selected):
        raise LayoutError("layout planning requires at least one LayoutCollection")
    inputs = root if source_root is None else source_root
    outputs: list[GeneratedFile] = []
    input_paths: set[Path] = set()
    for collection in selected:
        sources = tuple(sorted({collection.source_root / job.source for job in collection.jobs}))
        present = tuple(source for source in sources if inputs.joinpath(*source.parts).exists())
        repository_sources = source_root is not None or bool(present)
        if repository_sources and len(present) != len(sources):
            missing = next(source for source in sources if source not in present)
            raise LayoutError(f"repository layout source does not exist: {inputs / missing}")
        if not repository_sources and collection.resource_root is None:
            raise LayoutError(f"{collection.name}: no sources or bundled layout resources")
        parsed: dict[PurePosixPath, tuple[object, ...]] = {}
        for job in collection.jobs:
            relative = collection.source_root / job.source
            source = Path(relative.as_posix())
            if relative not in parsed:
                resource = (
                    None
                    if collection.resource_root is None
                    else collection.resource_root / job.source
                )
                template = _layout_text(
                    inputs, relative, repository_sources=repository_sources, resource=resource
                )
                if repository_sources:
                    input_paths.add(inputs / relative)
                parsed[relative] = _parse(template, source)
            rendered = _render_nodes(parsed[relative], _recipe_values(source, job.values), source)
            outputs.append(
                GeneratedFile(
                    path=collection.output_root / job.target,
                    content=_with_source_warning(rendered, relative).encode("utf-8"),
                    owner=f"layout:{relative}",
                    dependencies=(relative, *collection.dependencies),
                )
            )
    try:
        resolved_inputs = {source.resolve(): source for source in input_paths}
        input_inodes = {
            (status.st_dev, status.st_ino): source
            for source in input_paths
            for status in (source.stat(),)
        }
        for output in outputs:
            target = root / output.path
            source = resolved_inputs.get(target.resolve(strict=False))
            if source is None and target.exists():
                status = target.stat()
                source = input_inodes.get((status.st_dev, status.st_ino))
            if source is not None:
                raise LayoutError(f"{output.path}: generated output aliases layout source {source}")
    except OSError as error:
        raise LayoutError(f"cannot inspect layout source/output paths: {error}") from error
    return AuthoringPlan(tuple(outputs))


def generate_layouts(
    root: Path,
    *,
    check: bool = False,
    collections: Sequence[LayoutCollection] | None = None,
    source_root: Path | None = None,
) -> tuple[PurePosixPath, ...]:
    """Generate every layout output, or return drift without writing in check mode."""

    resolved_root = root.resolve()
    return layout_plan(resolved_root, collections=collections, source_root=source_root).apply(
        resolved_root, check=check
    )


def layout_sources(
    root: Path, *, collections: Sequence[LayoutCollection] | None = None
) -> tuple[PurePosixPath, ...]:
    """Return all layout source dependencies used by the generation plan."""

    return tuple(sorted({job.source for job in iter_layout_jobs(root, collections=collections)}))
