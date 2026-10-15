# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Restricted migration adapter using the existing bounded native layout engine."""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .. import layouts
from ..database import ResolvedDatabase, _freeze
from ..errors import DataError, LayoutError
from ..source import SourceSpan
from ..versions import parse_version_requirements
from .inputs import (
    CapturedFailure,
    CapturedProse,
    CodeRecord,
    ParameterState,
    ProseInputs,
    all_exception_records,
)
from .legacy_syntax import EXT as _EXT
from .legacy_syntax import legacy_tokens as _legacy_tokens
from .legacy_syntax import ruby_expression

_LOOP = re.compile(
    r"implemented_(exception|interrupt)_codes\.sort_by\s*"
    r"\{\s*\|code\|\s*code\.num\s*\}\.each do \|code\|"
)
_VA = "ext?(:Sv57) ? 57 : (ext?(:Sv48) ? 48 : 39)"
_NATIVE_DELIMITERS = ("{{", "{%", "{#")
_ALLOWED_AST = (
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Attribute,
    ast.BinOp,
    ast.Sub,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.UnaryOp,
    ast.Not,
    ast.USub,
    ast.IfExp,
    ast.BoolOp,
    ast.And,
    ast.Or,
)


@dataclass(frozen=True, slots=True)
class ProseDiagnostic:
    code: str
    message: str
    prose: CapturedProse
    configuration: str
    tag: str | None
    observed_inputs: Mapping[str, object]
    legacy_error_class: str | None = None
    configuration_source: str | None = None
    input_sources: Mapping[str, SourceSpan] | None = None


class ProseError(DataError):
    def __init__(self, diagnostic: ProseDiagnostic):
        self.diagnostic = diagnostic
        super().__init__(f"{diagnostic.prose.label}: {diagnostic.message}")


class _Values(Mapping[str, object]):
    """Lazy typed values survive the layout renderer's loop scope copies."""

    def __init__(self, factories: Mapping[str, Callable[[], object]]):
        self.factories = dict(factories)

    def __getitem__(self, key: str) -> object:
        return self.factories[key]()

    def __iter__(self) -> Iterator[str]:
        return iter(self.factories)

    def __len__(self) -> int:
        return len(self.factories)

    def __contains__(self, key: object) -> bool:
        return key in self.factories


class _CodeRows(Sequence[str]):
    def __init__(self, factory: Callable[[], tuple[str, ...]]):
        self.factory = factory
        self.cache: tuple[str, ...] | None = None

    def _rows(self) -> tuple[str, ...]:
        if self.cache is None:
            self.cache = self.factory()
        return self.cache

    def __getitem__(self, index: int | slice) -> str | tuple[str, ...]:
        return self._rows()[index]

    def __len__(self) -> int:
        return len(self._rows())


class _Adapter:
    def __init__(self, prose: CapturedProse, inputs: ProseInputs):
        self.prose = prose
        self.inputs = inputs
        self.source = Path(prose.source)
        self.factories: dict[str, Callable[[], object]] = {}
        self.values: dict[str, object] = {}
        self.locals: dict[str, object] = {}
        self.declared_locals: set[str] = set()
        self.current_tag: str | None = None
        self.observed: dict[str, object] = {}
        self.expression_count = 0

    def fail(self, code: str, message: str, *, legacy: str | None = None) -> ProseError:
        return ProseError(
            ProseDiagnostic(
                code,
                message,
                self.prose,
                self.inputs.configuration,
                self.current_tag,
                _freeze(self.observed),
                legacy,
                self.inputs.configuration_source,
                _freeze(
                    {
                        name: self.inputs.parameter_sources[name]
                        for name in self.observed
                        if name in self.inputs.parameter_sources
                    }
                ),
            )
        )

    def consumed(self, value: object, name: str) -> object:
        self.observed[name] = value
        if isinstance(value, CapturedFailure):
            raise self.fail("captured-input-error", value.message, legacy=value.error_class)
        return value

    def parameter(self, name: str) -> object:
        value = self.inputs.parameters.get(name, ParameterState.UNAVAILABLE)
        self.observed[name] = value
        if value is ParameterState.UNAVAILABLE:
            raise self.fail(
                "unavailable-parameter", f"uninitialized constant {name}", legacy="NameError"
            )
        return value

    def bit_length(self, name: str) -> int:
        value = self.parameter(name)
        if type(value) is not int:
            if type(value) is not str and value is not ParameterState.UNKNOWN:
                raise self.fail(
                    "invalid-parameter-type",
                    f"{name}.bit_length requires an integer; got {value!r}",
                )
            ruby_type = "String" if type(value) is str else "Symbol"
            raise self.fail(
                "invalid-parameter-type",
                f"undefined method 'bit_length' for an instance of {ruby_type}",
                legacy="NoMethodError",
            )
        return value.bit_length() if value >= 0 else (~value).bit_length()

    def minimum(self, names: tuple[str, ...]) -> int:
        values = [self.parameter(name) for name in names]
        if any(type(value) is not int for value in values):
            first, second = values

            if first is second is ParameterState.UNKNOWN:
                message = "comparison of Integer with :unknown failed"
            elif type(first) is str and type(second) is int:
                message = "comparison of Integer with String failed"
            else:
                raise self.fail(
                    "invalid-parameter-type",
                    f"minimum requires integer operands; got {values!r}",
                )
            raise self.fail(
                "invalid-parameter-type",
                message,
                legacy="ArgumentError",
            )
        return min(cast(list[int], values))

    def expression(
        self, expression: str, *, code: bool = False
    ) -> tuple[str, Mapping[str, object]]:
        original = expression.strip()
        selector = re.fullmatch(r"(" + _EXT.pattern + r")\s*\?\s*2\s*:\s*1", original)
        width_selector = re.fullmatch(
            r"possible_xlens\.include\?\(32\)\s*\?\s*32\s*:\s*64", original
        )
        if selector:
            expression = f"2 if {selector.group(1)} else 1"
        elif width_selector:
            expression = "32 if possible_xlens.include?(32) else 64"
        elif original == _VA:
            expression = "57 if ext?(:Sv57) else (48 if ext?(:Sv48) else 39)"
        elif "?" in _EXT.sub("", original).replace("possible_xlens.include?(32)", ""):
            raise self.fail("unsupported-expression", f"unsupported ternary: {original!r}")
        if (
            not selector
            and not width_selector
            and original != _VA
            and not ruby_expression(original, local_names=self.declared_locals, code=code)
        ):
            raise self.fail("unsupported-expression", f"unsupported Ruby expression {original!r}")
        bindings: dict[str, Callable[[], object]] = {}

        def extension(match: re.Match[str]) -> str:
            key = f"e{len(bindings)}"
            name, requirement = match.groups()
            if requirement is not None:
                try:
                    parse_version_requirements(requirement)
                except ValueError as error:
                    raise self.fail("unsupported-expression", str(error)) from error

            def value() -> bool:
                result = self.inputs.extension(name, requirement)
                self.observed[name + (f"@{requirement}" if requirement else "")] = result
                return result

            bindings[key] = value
            return f"bound.{key}"

        expression = _EXT.sub(extension, expression.strip())
        expression = re.sub(r"!(?!=)", "not ", expression)
        if "possible_xlens.include?(32)" in expression:

            def width32() -> bool:
                widths = self.consumed(self.inputs.possible_xlens, "possible_xlens")
                return 32 in cast(tuple[int, ...], widths)

            bindings["xlen32"] = width32
            expression = expression.replace("possible_xlens.include?(32)", "bound.xlen32")
        for name in re.findall(r"\b([A-Z][A-Z0-9_]*)\.bit_length\b", expression):
            key = f"bitlen{len(bindings)}"
            bindings[key] = lambda name=name: self.bit_length(name)
            expression = expression.replace(f"{name}.bit_length", f"bound.{key}")
        array_minimum = re.compile(r"\[([A-Z][A-Z0-9_]*),\s*([A-Z][A-Z0-9_]*)\]\.min")
        for match in tuple(array_minimum.finditer(expression)):
            key = f"min{len(bindings)}"
            names = match.groups()
            bindings[key] = lambda names=names: self.minimum(names)
            expression = expression.replace(match.group(), f"bound.{key}")
        expression = re.sub(r"\b([A-Z][A-Z0-9_]*)\b", r"params.\1", expression)
        for name in self.declared_locals:
            expression = re.sub(rf"\b{re.escape(name)}\b", f"local.{name}", expression)
        if len(expression) > 4096:
            raise self.fail("expression-budget", "expression exceeds 4096 characters")
        try:
            tree = ast.parse(expression.strip(), mode="eval")
        except (SyntaxError, RecursionError) as error:
            raise self.fail("unsupported-expression", f"invalid expression {original!r}") from error
        nodes = list(ast.walk(tree))
        if len(nodes) > 256:
            raise self.fail("expression-budget", "expression exceeds 256 AST nodes")
        for node in nodes:
            if not isinstance(node, _ALLOWED_AST):
                raise self.fail("unsupported-expression", f"unsupported expression {original!r}")
            if isinstance(node, ast.Compare) and len(node.ops) != 1:
                raise self.fail("unsupported-expression", "Ruby comparisons cannot be chained")
            if (
                isinstance(node, ast.IfExp)
                and not selector
                and not width_selector
                and original != _VA
            ):
                raise self.fail(
                    "unsupported-expression", f"unsupported Ruby expression {original!r}"
                )
            if isinstance(node, ast.Constant) and type(node.value) not in (int, bool):
                raise self.fail("unsupported-expression", f"unsupported literal {original!r}")
            if isinstance(node, ast.Name):
                allowed = {"params", "bound", "local"} | ({"code"} if code else set())
                if node.id not in allowed:
                    raise self.fail("unsupported-expression", f"unsupported name {node.id!r}")
            if isinstance(node, ast.Attribute) and (
                not isinstance(node.value, ast.Name)
                or node.attr.startswith("_")
                or (node.value.id == "code" and node.attr not in ("num", "name"))
                or (node.value.id == "bound" and node.attr not in bindings)
                or (node.value.id == "local" and node.attr not in self.declared_locals)
                or (
                    node.value.id == "params"
                    and re.fullmatch(r"[A-Z][A-Z0-9_]*", node.attr) is None
                )
            ):
                raise self.fail("unsupported-expression", f"unsupported attribute {original!r}")
        params = _Values(
            {name: lambda name=name: self.parameter(name) for name in self.inputs.parameters}
        )
        # An unavailable constant absent from the supplied facts still receives
        # the same explicit unavailable diagnostic rather than a layout key error.
        for name in re.findall(r"\bparams\.([A-Z][A-Z0-9_]*)", expression):
            params.factories.setdefault(name, lambda name=name: self.parameter(name))
        return expression.strip(), {
            "params": params,
            "bound": _Values(bindings),
            "local": self.locals,
        }

    def alias(
        self, expression: str, tag: str, *, condition: bool = False, assign: str | None = None
    ) -> str:
        translated, values = self.expression(expression)
        name = f"v{self.expression_count}"
        self.expression_count += 1

        def value() -> object:
            self.current_tag = tag
            try:
                result = layouts._expression(translated, values, self.source)
            except LayoutError as error:
                raise self.fail("expression-error", str(error)) from error
            if assign is not None:
                self.locals[assign] = result
                return ""
            if condition:
                return result is not False and result is not None
            if result is ParameterState.UNKNOWN:
                return "unknown"
            if type(result) is bool:
                return "true" if result else "false"
            if not isinstance(result, str | int):
                raise self.fail(
                    "invalid-interpolation", "interpolation requires scalar text or integer"
                )
            return result

        self.factories[name] = value
        return f"inputs.{name}"

    def loop(
        self,
        kind: str,
        tokens: Sequence[tuple[re.Match[str], str, str]],
        prefix: str,
        suffix: str,
        tag: str,
    ) -> str:
        self.current_tag = tag
        parts: list[str] = [prefix]
        for match, literal, rspace in tokens:
            self.current_tag = match.group()
            parts.append(literal)
            expression = match.group(2).strip()
            if expression not in ("= code.num", "= code.name"):
                raise self.fail(
                    "unsupported-directive",
                    "code-loop bodies allow only code.num/name interpolation",
                )
            parts.append("{{ " + expression[2:].strip() + " }}" + rspace)
        parts.append(suffix)
        native_body = "".join(parts)
        try:
            nodes = layouts._parse(native_body, self.source)
        except LayoutError as error:
            raise self.fail("template-syntax", str(error)) from error
        key = f"rows{len(self.values)}"

        def rows() -> tuple[str, ...]:
            self.current_tag = tag
            records = self.consumed(
                self.inputs.exception_codes if kind == "exception" else self.inputs.interrupt_codes,
                f"{kind}_codes",
            )
            typed_records = cast(tuple[CodeRecord, ...], records)
            if any("<%" in record.name for record in typed_records):
                raise self.fail("unresolved-code-name", "code-loop names must already be resolved")
            budget = layouts._RenderBudget()
            return tuple(
                layouts._render_nodes(
                    nodes, {"code": {"name": record.name, "num": record.num}}, self.source, budget
                )
                for record in typed_records
            )

        self.values[key] = _CodeRows(rows)
        return "{% for code_row in " + key + " %}{{ code_row }}{% endfor %}"

    def compile(self) -> str:
        if len(self.prose.text) > 16 * 1024 * 1024:
            raise self.fail("template-budget", "template exceeds 16 MiB")
        if any(delimiter in self.prose.text for delimiter in _NATIVE_DELIMITERS):
            raise self.fail(
                "mixed-template-format", "legacy prose contains native template delimiters"
            )
        parts: list[str] = []
        try:
            tokens, remainder = _legacy_tokens(self.prose.text)
        except ValueError as error:
            raise self.fail("template-syntax", str(error)) from error
        if len(tokens) > 10_000:
            raise self.fail("template-budget", "template exceeds 10000 tags")
        stack: list[str] = []
        index = 0

        while index < len(tokens):
            match, literal, rspace = tokens[index]
            parts.append(literal)
            tag = match.group()[: len(match.group()) - len(match.group(4) or "")]
            self.current_tag = tag
            directive = match.group(2).strip()
            expression_tag = False
            loop = _LOOP.fullmatch(directive)
            if loop:
                if stack:
                    raise self.fail("unsupported-directive", "legacy code loops must be top-level")
                if index + 1 >= len(tokens):
                    raise self.fail("template-syntax", "unterminated code loop")
                ending = index + 1
                while ending < len(tokens) and tokens[ending][0].group(2).strip() != "end":
                    ending += 1
                if ending == len(tokens):
                    raise self.fail("template-syntax", "unterminated code loop")
                parts.append(
                    self.loop(
                        loop.group(1), tokens[index + 1 : ending], rspace, tokens[ending][1], tag
                    )
                    + tokens[ending][2]
                )
                index = ending + 1
                continue
            if directive.startswith("="):
                translated = self.alias(directive[1:].strip(), tag)
                expression_tag = True
            elif directive.startswith("va_size = "):
                if stack or "va_size" in self.declared_locals:
                    raise self.fail(
                        "unsupported-directive", "va_size must be assigned once at top-level"
                    )
                rhs = directive.removeprefix("va_size = ")
                if rhs != _VA:
                    raise self.fail("unsupported-directive", "unsupported va_size assignment")
                translated = self.alias(rhs, tag, assign="va_size")
                self.declared_locals.add("va_size")
                expression_tag = True
            elif directive.startswith(("if ", "unless ")):
                unless = directive.startswith("unless ")
                condition = directive.split(" ", 1)[1]
                name = self.alias(condition, tag, condition=True)
                translated = "if " + ("not " if unless else "") + name
                stack.append("unless" if unless else "if")
            elif directive.startswith("elsif "):
                if not stack or stack[-1] != "if":
                    raise self.fail("template-syntax", "elsif without matching if")
                translated = "elif " + self.alias(directive[6:], tag, condition=True)
            elif directive == "else":
                if not stack:
                    raise self.fail("template-syntax", "else without matching if/unless")
                if stack[-1].endswith(":else"):
                    raise self.fail("template-syntax", "duplicate else")
                stack[-1] += ":else"
                translated = "else"
            elif directive == "end":
                if not stack:
                    raise self.fail("template-syntax", "end without an open block")
                stack.pop()
                translated = "endif"
            else:
                raise self.fail("unsupported-directive", f"unsupported directive {directive!r}")
            opening, closing = ("{{", "}}") if expression_tag else ("{%", "%}")
            parts.append(opening + " " + translated + " " + closing + rspace)
            index += 1
        parts.append(remainder)
        return "".join(parts)

    def render(self) -> str:
        try:
            native = self.compile()
            nodes = layouts._parse(native, self.source)
            return layouts._render_nodes(
                nodes, {"inputs": _Values(self.factories), **self.values}, self.source
            )
        except LayoutError as error:
            raise self.fail("template-error", str(error)) from error
        except ProseError:
            raise
        except DataError as error:
            raise self.fail("captured-input-error", str(error)) from error
        except (RecursionError, TypeError, ValueError, KeyError) as error:
            raise self.fail("input-error", str(error)) from error


def render_legacy(prose: CapturedProse, inputs: ProseInputs) -> str:
    """Render the specified migration subset; unsupported source is an error."""
    return _Adapter(prose, inputs).render()


def _validate_native(nodes: Sequence[object], source: Path) -> None:
    """Reject unsupported expressions even when their branches are inactive."""
    expressions = []
    for node in nodes:
        if isinstance(node, layouts._Expression):
            expressions.append(node.value)
        elif isinstance(node, layouts._If):
            for condition, body in node.branches:
                if condition is not None:
                    expressions.append(condition)
                _validate_native(body, source)
        elif isinstance(node, layouts._For):
            expressions.append(node.values)
            _validate_native(node.body, source)
    extra_native = (ast.Add, ast.Mult, ast.FloorDiv, ast.Mod, ast.UAdd)
    for expression in expressions:
        if len(expression) > 4096:
            raise LayoutError(f"{source}: native expression exceeds 4096 characters")
        try:
            tree = ast.parse(expression, mode="eval")
        except (SyntaxError, RecursionError) as error:
            raise LayoutError(f"{source}: invalid native expression {expression!r}") from error
        parts = list(ast.walk(tree))
        if len(parts) > 256:
            raise LayoutError(f"{source}: native expression exceeds 256 AST nodes")
        if any(
            not isinstance(part, _ALLOWED_AST + extra_native)
            or (isinstance(part, ast.Attribute) and part.attr.startswith("_"))
            or (isinstance(part, ast.Constant) and type(part.value) not in (int, bool, str))
            for part in parts
        ):
            raise LayoutError(f"{source}: unsupported native expression {expression!r}")


def render_native(prose: CapturedProse, values: Mapping[str, object]) -> str:
    """Render captured native syntax with the shared bounded layout machinery."""
    if "<%" in prose.text:
        raise ProseError(
            ProseDiagnostic(
                "legacy-template-format",
                "native templates cannot contain ERB",
                prose,
                "<native>",
                None,
                {},
            )
        )
    source = Path(prose.source)
    try:
        nodes = layouts._parse(prose.text, source)
        _validate_native(nodes, source)
        return layouts._render_nodes(nodes, _freeze(values), source)
    except (LayoutError, RecursionError, TypeError, ValueError) as error:
        raise ProseError(
            ProseDiagnostic(
                "native-template-error",
                str(error),
                prose,
                "<native>",
                None,
                _freeze(values),
            )
        ) from error


def resolved_exception_names(inputs: ProseInputs) -> tuple[Mapping[str, object], ...]:
    """Config-available codes, NOT the all-code C/SV/Go wrapper selection."""
    if isinstance(inputs.exception_codes, CapturedFailure):
        adapter = _Adapter(CapturedProse("", "<exception names>"), inputs)
        adapter.consumed(inputs.exception_codes, "exception_codes")
        return ()  # pragma: no cover
    return resolve_exception_records(inputs.exception_codes, inputs)


def resolve_all_exception_records(
    database: ResolvedDatabase, inputs: ProseInputs
) -> tuple[Mapping[str, object], ...]:
    """Database-derived all-code rows for retained generator wrappers.

    Extension-major order and repeated rows are preserved in full configurations,
    even for absent extensions. Configuration facts only render the names.
    """
    return resolve_exception_records(all_exception_records(database), inputs)


def resolve_exception_records(
    records: Sequence[CodeRecord], inputs: ProseInputs
) -> tuple[Mapping[str, object], ...]:
    """Resolve the legacy generator JSON shape without selecting or deduplicating.

    Callers own record selection. One row is retained per defining extension,
    downstream consumers still own deduplication. Use resolve_all_exception_records
    for the database-derived wrapper policy, not a config-filtered input list.
    """
    if len(records) > 1024 or any(not isinstance(code, CodeRecord) for code in records):
        raise DataError("Structured exception inputs require at most 1024 typed code records")
    if sum(max(1, len(code.extensions)) for code in records) > 1024:
        raise DataError("Structured exception output exceeds 1024 extension rows")
    result = []
    for code in records:
        prose = code.name_source or CapturedProse(code.name, f"<exception {code.var}>")
        name = render_legacy(prose, inputs)
        for extension in code.extensions or ("",):
            result.append(
                _freeze(
                    {
                        "num": code.num,
                        "name": name,
                        "var": code.var,
                        "ext": extension,
                    }
                )
            )
    return tuple(result)
