# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Exercise an installed Python package outside the checkout, without Ruby/Git."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

import udb
from udb import idl


def tree_digest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def check_install() -> None:
    assert shutil.which("ruby") is None
    assert shutil.which("git") is None
    assert Path(udb.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    resources = files("udb").joinpath("_data")
    assert resources.is_dir()
    database = udb.Database.bundled()
    raw_records = database.objects()
    resolved = database.resolve(validate=True)
    assert len(raw_records) == len(resolved.documents) == 2306
    assert resolved.profile("RVI20U64")["extensions"]["I"]["presence"] == "mandatory"
    sm_versions = database.extension("Sm").version_set
    assert tuple(version.canonical for version in sm_versions) == (
        "1.11.0",
        "1.12.0",
        "1.13.0",
    )
    assert udb.Version.parse("1.12").canonical == "1.12.0"
    assert udb.VersionRequirement.parse(">= 1.11").matches("1.12")
    synthetic = udb.ExtensionVersionSet.from_metadata(
        "Xinstalled",
        [
            {"version": "1.0"},
            {"version": "2.0", "breaking": True},
            {"version": "3.0"},
        ],
    )
    assert tuple(item.canonical for item in synthetic.compatible_versions("2.0")) == (
        "2.0.0",
        "3.0.0",
    )
    for name, width in (("_", None), ("rv32", 32), ("rv64", 64)):
        config = udb.Configuration.builtin(name)
        assert config.mxlen == width
        assert udb.Configuration(config.to_dict()) == config
    domain_schemas = udb.SchemaStore(database.schemas_root)
    domains = {
        record.name: udb.ParameterDomain.from_schema(
            record["schema"],
            schema_store=domain_schemas,
            source=str(record.path),
        )
        for record in resolved.objects("parameter")
    }
    assert len(domains) == 271
    assert all(not domain.is_empty for domain in domains.values())
    assert domains["MXLEN"].enumerate_values(limit=2) == (32, 64)
    assert domains["SUPPORTED_PMLEN_SMMPM"].accepts([0, 7])
    assert not domains["SUPPORTED_PMLEN_SMMPM"].accepts([7])
    assert not domains["SUPPORTED_PMLEN_SMMPM"].accepts([0, 0])

    condition = udb.parse_condition(
        {
            "allOf": [
                {"extension": {"name": "I"}},
                {"param": {"name": "MXLEN", "equal": 64}},
            ]
        }
    )
    assert condition.evaluate(udb.EvaluationContext(xlen=64)) is udb.TruthValue.UNKNOWN
    assert (
        condition.evaluate(
            udb.EvaluationContext(extensions={"I": "2.1.0"}, parameters={"MXLEN": 64})
        )
        is udb.TruthValue.TRUE
    )
    closed_ctx = udb.EvaluationContext(
        xlen=64, closed_world_extensions=True, closed_world_parameters=True
    )
    assert condition.evaluate(closed_ctx) is udb.TruthValue.FALSE

    solver_ctx = udb.SolverContext(
        xlen=64,
        extension_versions={"I": ["2.1.0"]},
        parameter_domains={"MXLEN": domains["MXLEN"]},
        fixed_extensions={"I": "2.1.0"},
    )
    solver = udb.ConditionSolver(solver_ctx)
    solver.add(condition)
    assert solver.check() is udb.SolverStatus.SAT
    solver.add(udb.parse_condition({"param": {"name": "MXLEN", "equal": 32}}))
    assert solver.check() is udb.SolverStatus.UNSAT

    rv64_arch = resolved.configure(udb.Configuration.builtin("rv64"))
    assert rv64_arch.extension_presence("I") is udb.QueryPresence.MANDATORY
    # Some rv64 extensions and parameters are gated by idl() conditions until Stage 4.
    assert rv64_arch.check().status is udb.ArchitectureCheckStatus.DEFERRED
    assert "add" in [inst.name for inst in rv64_arch.possible_instructions]

    data_references = schema_references = source_values = 0
    source_documents: set[str] = set()

    def visit(document: str, value: object, path: tuple[str | int, ...] = ()) -> None:
        nonlocal data_references, schema_references, source_values
        span = resolved.source_at(document, *path)
        assert span is not None, (document, path)
        assert all(
            isinstance(coordinate, int) and coordinate > 0
            for coordinate in (span.start_line, span.start_column, span.end_line, span.end_column)
        ), (document, path, span)
        assert (span.end_line, span.end_column) >= (span.start_line, span.start_column)
        source_documents.add(span.source)
        source_values += 1
        if isinstance(value, Mapping):
            if "$ref" in value:
                reference = resolved.reference_at(document, *path)
                if isinstance(reference, udb.DataReference):
                    assert reference.target.source is not None
                    _ = reference.target.value
                    data_references += 1
                else:
                    assert isinstance(reference, udb.SchemaReference)
                    schema_references += 1
            for key, child in value.items():
                visit(document, child, (*path, key))
        elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
            for index, child in enumerate(value):
                visit(document, child, (*path, index))

    for document, value in resolved.documents.items():
        visit(document, value)
    assert data_references == 59
    assert schema_references == 3
    assert all(resources.joinpath("isa", source).is_file() for source in source_documents)
    for document, path, expected_source, expected_text in (
        ("ext/I.yaml", ("name",), "ext/I.yaml", "I"),
        (
            "profile/RVI20U64.yaml",
            ("extensions", "I", "presence"),
            "profile/RVI20U32.yaml",
            "mandatory",
        ),
    ):
        span = resolved.source_at(document, *path)
        assert span is not None and span.source == expected_source
        assert span.start_line == span.end_line
        line = (
            resources.joinpath("isa", span.source)
            .read_text(encoding="utf-8")
            .splitlines()[span.start_line - 1]
        )
        assert line[span.start_column - 1 : span.end_column - 1] == expected_text

    with TemporaryDirectory(prefix="udb-installed-") as temporary:
        root = Path(temporary)
        first, second = root / "first", root / "second"
        resolved.write(first)
        resolved.write(second)
        assert tree_digest(first) == tree_digest(second)
        assert json.loads((first / "index.json").read_text()) == sorted(resolved.documents)
        schemas = udb.SchemaStore(database.schemas_root)
        udb.write_resolved_schemas(schemas, root / "schemas-first")
        udb.write_resolved_schemas(schemas, root / "schemas-second")
        assert tree_digest(root / "schemas-first") == tree_digest(root / "schemas-second")

        authoring_root = root / "authoring"
        outputs = udb.generate_layouts(authoring_root)
        assert len(outputs) == 532
        for relative in outputs:
            bundled_path = relative.relative_to("spec/std/isa")
            assert (
                authoring_root.joinpath(relative).read_bytes()
                == resources.joinpath("isa", *bundled_path.parts).read_bytes()
            ), relative
        assert udb.generate_layouts(authoring_root, check=True) == ()

        for arguments in (
            ["show", "instruction", "add"],
            ["generate-layouts", "--root", str(authoring_root), "--check"],
        ):
            subprocess.run(
                [sys.executable, "-I", "-m", "udb", *arguments],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        subprocess.run(["udb", "show", "instruction", "add"], check=True, stdout=subprocess.DEVNULL)

    function_body = idl.parse_function_body("XReg a = X[rs1] + X[rs2];\nreturn a;\n")
    assert isinstance(function_body, idl.FunctionBody)
    isa_snippet = idl.parse_isa(
        "%version: 1.0\n"
        "XReg counter = 0;\n"
        "function f {\n"
        "  returns XReg\n"
        "  description { Increment and return the global counter. }\n"
        "  body {\n"
        "    counter = counter + 1;\n"
        "    return counter;\n"
        "  }\n"
        "}\n"
    )
    assert isinstance(isa_snippet, idl.Isa)

    isa_dir = resources.joinpath("isa", "isa")
    bundled_isa_files = sorted(entry.name for entry in isa_dir.iterdir() if entry.is_file())
    assert bundled_isa_files == [
        "builtin_functions.idl",
        "fetch.idl",
        "fp.idl",
        "globals.isa",
        "interrupts.idl",
        "util.idl",
        "vec.idl",
    ]
    for name in bundled_isa_files:
        text = isa_dir.joinpath(name).read_text(encoding="utf-8")
        node = idl.parse_isa(text, label=name)
        assert isinstance(node, idl.Isa)

    from udb.idl.symbols import IdlEnvironment, SymbolTable

    expression_symtab = SymbolTable(IdlEnvironment())
    expression_node = idl.parse_expression("4'b1010 + 1")
    expression_node.type_check(expression_symtab, strict=False)
    expression_type = expression_node.type(expression_symtab)
    assert str(expression_type) == "const known Bits<4>"
    assert expression_node.value(expression_symtab) == 11

    from udb.idl.types import Type, TypeKind

    statement_symtab = SymbolTable(IdlEnvironment(mxlen=64))
    statement_isa = idl.parse_isa(
        "%version: 1.0\n"
        "function increment { returns Bits<8> arguments Bits<8> value "
        "description { Increment a value. } body { return value + 1; } }\n"
    )
    statement_isa.type_check(statement_symtab)
    statement_symtab.push(None)
    statement_symtab.add("__expected_return_type", Type(TypeKind.BITS, width=8))
    statement_body = idl.parse_function_body(
        "Bits<8> values[2]; "
        "for (Bits<8> i = 0; i < 2; i++) { values[i] = increment(i); } "
        "return values[1];"
    )
    statement_body.type_check(statement_symtab)
    assert statement_body.return_value(statement_symtab) == 2
    statement_symtab.pop()

    print(
        f"Installed package passed: {len(raw_records)} records, {source_values} source spans, "
        f"{data_references} data / {schema_references} schema references, "
        f"{len(sm_versions)} Sm versions, 532 layout outputs, condition solving & configured queries, "
        f"IDL syntax parsing ({len(bundled_isa_files)} bundled isa/*.{{idl,isa}} files), "
        "IDL statement typing & execution"
    )


if __name__ == "__main__":
    check_install()
