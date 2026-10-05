# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import pytest

from udb.idl import value_bounds
from udb.idl.errors import IdlSyntaxError
from udb.idl.parser import parse_expression, parse_function_body
from udb.idl.symbols import IdlEnvironment, SymbolTable, Var
from udb.idl.types import BOOL_TYPE
from udb.idl_yaml_source import idl_field_source
from udb.source import parse_yaml


@pytest.mark.parametrize("operator", ["*", "`*"])
def test_multiplication_minimum_includes_cross_products(operator):
    symtab = SymbolTable(
        IdlEnvironment(builtin_global_vars=(Var("a", BOOL_TYPE), Var("b", BOOL_TYPE)))
    )
    node = parse_expression(f"(a ? -4'sd2 : 4'sd3) {operator} (b ? -4'sd5 : 4'sd7)")
    node.type_check(symtab)
    if operator == "*":
        with pytest.warns(UserWarning, match="result is truncated from 21 to 5"):
            assert value_bounds.max_value(node, symtab) == 5
    else:
        assert value_bounds.max_value(node, symtab) == 21
    assert value_bounds.min_value(node, symtab) == (241 if operator == "`*" else 1)


@pytest.mark.parametrize(
    ("document", "line", "column"),
    [
        ("operation(): X[xd] = @;\n", 1, 22),
        ("operation(): |\n  X[xd] = @;\n", 2, 11),
        ("operation(): |\n    X[xd] = @;\n", 2, 13),
        ("operation(): |\n\n    X[xd] = @;\n", 3, 13),
    ],
)
def test_yaml_syntax_errors_identify_original_file_columns(document, line, column):
    parsed = parse_yaml(document, source="custom.yaml")
    value = parsed.value["operation()"]
    source = idl_field_source(
        document, parsed.sources.at("operation()"), value, label="custom.yaml"
    )
    with pytest.raises(IdlSyntaxError) as error:
        parse_function_body(value, source=source)
    assert (error.value.source, error.value.line, error.value.column) == (
        "custom.yaml",
        line,
        column,
    )
