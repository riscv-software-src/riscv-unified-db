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
from .inputs import (
    CapturedFailure,
    CapturedProse,
    CodeRecord,
    ParameterState,
    ProseInputs,
    all_exception_records,
)

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


class _NativeValues(dict[str, object]):
    """Marker for a validated, per-template lazy native input projection."""

    def __init__(self, adapter: _NativeInputs):
        super().__init__()
        self.adapter = adapter


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


_NATIVE_NAMESPACES = {"extensions", "extension_queries", "params", "derived"}
_NATIVE_DERIVED = {
    "has_xlen_32",
    "va_size",
    "cache_block_size_log2",
    "min_cache_granularity",
}
_NATIVE_CODE_ROWS = {"interrupt_code_rows", "exception_code_rows"}


class _NativeInputs:
    """Build only the native values referenced by one captured scalar."""

    def __init__(self, prose: CapturedProse, inputs: ProseInputs):
        self.prose = prose
        self.inputs = inputs
        self.current_tag: str | None = None
        self.observed: dict[str, object] = {}

    def fail(self, code: str, message: str) -> ProseError:
        return ProseError(
            ProseDiagnostic(
                code,
                message,
                self.prose,
                self.inputs.configuration,
                self.current_tag,
                _freeze(self.observed),
                configuration_source=self.inputs.configuration_source,
                input_sources=_freeze(
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
            raise self.fail("captured-input-error", value.message)
        return value

    def extension(self, name: str, requirement: str | None = None) -> bool:
        key = name + (f"@{requirement}" if requirement else "")
        try:
            result = self.inputs.extension(name, requirement)
        except DataError as error:
            raise self.fail("captured-input-error", str(error)) from error
        self.observed[key] = result
        return result

    def parameter(self, name: str) -> object:
        value = self.inputs.parameters.get(name, ParameterState.UNAVAILABLE)
        self.observed[name] = value
        if value is ParameterState.UNAVAILABLE:
            raise self.fail(
                "unavailable-parameter",
                f"parameter {name} is unavailable in prose configuration",
            )
        return value

    def integer_parameter(self, name: str) -> int:
        value = self.parameter(name)
        if type(value) is not int:
            raise self.fail(
                "invalid-parameter-type",
                f"parameter {name} must be an integer; got {value!r}",
            )
        return cast(int, value)

    def derived(self, name: str) -> int | bool:
        if name == "has_xlen_32":
            widths = self.consumed(self.inputs.possible_xlens, "possible_xlens")
            return 32 in cast(tuple[int, ...], widths)
        if name == "va_size":
            return 57 if self.extension("Sv57") else 48 if self.extension("Sv48") else 39
        if name == "cache_block_size_log2":
            value = self.integer_parameter("CACHE_BLOCK_SIZE")
            return (value.bit_length() if value >= 0 else (~value).bit_length()) - 1
        if name == "min_cache_granularity":
            return min(
                self.integer_parameter("PMP_GRANULARITY"),
                self.integer_parameter("PMA_GRANULARITY"),
            )
        raise self.fail("unsupported-native-input", f"unsupported derived input {name!r}")

    def code_rows(self, kind: str) -> tuple[str, ...]:
        records = self.consumed(
            self.inputs.interrupt_codes if kind == "interrupt" else self.inputs.exception_codes,
            f"{kind}_codes",
        )
        typed_records = cast(tuple[CodeRecord, ...], records)
        return tuple(
            f"! {record.num} ! {_render_native_code_name(record, self.inputs)}"
            for record in typed_records
        )


def _native_references(
    nodes: Sequence[object], source: Path
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    namespaced: dict[str, dict[str, str]] = {}
    bare: dict[str, str] = {}

    def expression_references(expression: str, locals_: frozenset[str]) -> None:
        try:
            tree = ast.parse(expression, mode="eval")
        except (SyntaxError, RecursionError) as error:  # Already diagnosed by validation.
            raise LayoutError(f"{source}: invalid native expression {expression!r}") from error
        attribute_parents: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            if not isinstance(node.value, ast.Name) or node.value.id not in _NATIVE_NAMESPACES:
                raise LayoutError(f"{source}: unsupported native prose input in {expression!r}")
            attribute_parents.add(id(node.value))
            namespaced.setdefault(node.value.id, {}).setdefault(node.attr, expression)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name) or id(node) in attribute_parents:
                continue
            if node.id in locals_:
                continue
            if node.id not in _NATIVE_CODE_ROWS:
                raise LayoutError(
                    f"{source}: unsupported native prose input {node.id!r} in {expression!r}"
                )
            bare.setdefault(node.id, expression)

    def visit(items: Sequence[object], locals_: frozenset[str]) -> None:
        for node in items:
            if isinstance(node, layouts._Expression):
                expression_references(node.value, locals_)
            elif isinstance(node, layouts._If):
                for condition, body in node.branches:
                    if condition is not None:
                        expression_references(condition, locals_)
                    visit(body, locals_)
            elif isinstance(node, layouts._For):
                expression_references(node.values, locals_)
                visit(node.body, locals_ | {node.variable})

    visit(nodes, frozenset())
    return namespaced, bare


def native_prose_values(prose: CapturedProse, inputs: ProseInputs) -> Mapping[str, object]:
    """Return the lazy, per-template native projection of ``ProseInputs``.

    Only supported fields referenced by this scalar are exposed. Captured failures
    and malformed parameters are therefore observed only if rendering evaluates the
    expression that consumes them.
    """
    adapter = _NativeInputs(prose, inputs)
    source = Path(prose.source)
    try:
        nodes = layouts._parse(prose.text, source)
        _validate_native(nodes, source)
        namespaced, bare = _native_references(nodes, source)
    except LayoutError as error:
        raise adapter.fail("native-template-error", str(error)) from error

    values = _NativeValues(adapter)
    for namespace, fields in namespaced.items():
        factories: dict[str, Callable[[], object]] = {}
        for field, expression in fields.items():
            adapter.current_tag = expression
            if namespace == "extensions":
                factory = lambda field=field: adapter.extension(field)
            elif namespace == "extension_queries":
                if field != "S_gt_1_9_1":
                    raise adapter.fail(
                        "unsupported-native-input",
                        f"unsupported extension query {field!r}",
                    )
                factory = lambda: adapter.extension("S", "> 1.9.1")
            elif namespace == "params":
                if re.fullmatch(r"[A-Z][A-Z0-9_]*", field) is None:
                    raise adapter.fail(
                        "unsupported-native-input", f"unsupported parameter input {field!r}"
                    )
                factory = lambda field=field: adapter.parameter(field)
            else:
                if field not in _NATIVE_DERIVED:
                    raise adapter.fail(
                        "unsupported-native-input", f"unsupported derived input {field!r}"
                    )
                factory = lambda field=field: adapter.derived(field)

            def tagged(
                factory: Callable[[], object] = factory, expression: str = expression
            ) -> object:
                adapter.current_tag = expression
                return factory()

            factories[field] = tagged
        values[namespace] = _Values(factories)

    for name, expression in bare.items():
        kind = name.removesuffix("_code_rows")

        def rows(kind: str = kind, expression: str = expression) -> tuple[str, ...]:
            adapter.current_tag = expression
            return adapter.code_rows(kind)

        values[name] = _CodeRows(rows)
    return values


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
        render_values = values if isinstance(values, _NativeValues) else _freeze(values)
        return layouts._render_nodes(nodes, render_values, source)
    except ProseError:
        raise
    except (LayoutError, RecursionError, TypeError, ValueError) as error:
        if isinstance(values, _NativeValues):
            raise values.adapter.fail("native-template-error", str(error)) from error
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
        adapter = _NativeInputs(CapturedProse("", "<exception names>"), inputs)
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
    """Resolve the generator JSON shape without selecting or deduplicating.

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
        name = _render_native_code_name(code, inputs)
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


def _render_native_code_name(code: CodeRecord, inputs: ProseInputs) -> str:
    prose = code.name_source or CapturedProse(code.name, f"<exception {code.var}>")
    return render_native(prose, native_prose_values(prose, inputs))
