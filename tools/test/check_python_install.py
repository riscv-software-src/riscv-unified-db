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


def check_config_headers(resolved: udb.ResolvedDatabase) -> None:
    """Use bundled ISA data and an explicit full config, never a checkout path."""
    from udb.generators.config_headers import generate_config_header

    # Explicit values from the reviewed MC100 full-config artifact oracle.
    params = {
        "MXLEN": 32,
        "MARCHID_IMPLEMENTED": True,
        "ARCH_ID_VALUE": 1,
        "MIMPID_IMPLEMENTED": True,
        "IMP_ID_VALUE": 0,
        "VENDOR_ID_BANK": 1,
        "VENDOR_ID_OFFSET": 1,
        "MISALIGNED_LDST": True,
        "MISALIGNED_LDST_EXCEPTION_PRIORITY": "low",
        "MISALIGNED_MAX_ATOMICITY_GRANULE_SIZE": 4,
        "MISALIGNED_SPLIT_STRATEGY": "sequential_bytes",
        "PRECISE_SYNCHRONOUS_EXCEPTIONS": True,
        "TRAP_ON_ECALL_FROM_M": True,
        "TRAP_ON_EBREAK": True,
        "M_MODE_ENDIANNESS": "little",
        "TRAP_ON_ILLEGAL_WLRL": True,
        "TRAP_ON_UNIMPLEMENTED_INSTRUCTION": True,
        "TRAP_ON_RESERVED_INSTRUCTION": True,
        "TRAP_ON_UNIMPLEMENTED_CSR": True,
        "REPORT_VA_IN_MTVAL_ON_BREAKPOINT": True,
        "REPORT_VA_IN_MTVAL_ON_LOAD_MISALIGNED": True,
        "REPORT_VA_IN_MTVAL_ON_STORE_AMO_MISALIGNED": True,
        "REPORT_VA_IN_MTVAL_ON_INSTRUCTION_MISALIGNED": True,
        "REPORT_VA_IN_MTVAL_ON_LOAD_ACCESS_FAULT": True,
        "REPORT_VA_IN_MTVAL_ON_STORE_AMO_ACCESS_FAULT": True,
        "REPORT_VA_IN_MTVAL_ON_INSTRUCTION_ACCESS_FAULT": True,
        "REPORT_ENCODING_IN_MTVAL_ON_ILLEGAL_INSTRUCTION": True,
        "MTVAL_WIDTH": 32,
        "PMA_GRANULARITY": 12,
        "PHYS_ADDR_WIDTH": 32,
        "MISA_CSR_IMPLEMENTED": True,
        "MCOUNTINHIBIT_IMPLEMENTED": True,
        "MTVEC_ACCESS": "rw",
        "MTVEC_ILLEGAL_WRITE_BEHAVIOR": "retain",
        "MTVEC_MODES": [0, 1],
        "MTVEC_BASE_ALIGNMENT_DIRECT": 4,
        "MTVEC_BASE_ALIGNMENT_VECTORED": 4,
        "MUTABLE_MISA_C": False,
        "MUTABLE_MISA_M": False,
        "TIME_CSR_IMPLEMENTED": False,
        "NUM_PMP_ENTRIES": 0,
        "COUNTINHIBIT_EN": [False] * 32,
        "HPM_COUNTER_EN": [False] * 32,
        "MCOUNTENABLE_EN": [False] * 32,
        "MEI_INTR_IMPL": False,
        "MSI_INTR_IMPL": False,
        "MTI_INTR_IMPL": False,
        "WFI_U_MODE": False,
        "WFI_FINITE": True,
        "NON_STANDARD_EXTENSION_IMPLEMENTED": False,
    }
    data = {
        "$schema": "config_schema.json#",
        "kind": "architecture configuration",
        "type": "fully configured",
        "name": "MC100-32-Full",
        "description": "Installed representative full configuration",
        "implemented_extensions": [
            ["Sm", "1.11.0"],
            ["I", "2.1"],
            ["C", "2.0"],
            ["Zca", "1.0"],
            ["M", "2.0"],
            ["Zmmul", "1.0"],
            ["Zicsr", "2.0"],
            ["Zicntr", "2.0"],
            ["Smrnmi", "1.0"],
        ],
        "params": params,
    }
    architecture = resolved.configure(udb.Configuration(data))
    command = str(Path(sys.executable).with_name("udb"))
    config_path = Path("installed-header-config.json")
    config_path.write_text(json.dumps(data), encoding="utf-8")
    outputs = []
    try:
        for language, digest in (
            ("c", "30a017e616ec65efe91f54bf42d4a60c239baa705b60d132b4d2e09b9968a825"),
            ("svh", "f165e1837de0e3caca5532653fb9f3e370104cedd31bed4f5becc4d3a8979030"),
        ):
            expected = generate_config_header(architecture, language).encode()
            assert hashlib.sha256(expected).hexdigest() == digest
            args = [command, "generate", f"cfg-{language}-header", "-c", str(config_path)]
            stdout = subprocess.run(args, check=True, capture_output=True)
            assert stdout.stdout == expected and stdout.stderr == b""
            output = Path(f"installed-config.{language}")
            outputs.append(output)
            written = subprocess.run([*args, "-o", str(output)], check=True, capture_output=True)
            assert written.stdout == written.stderr == b""
            assert output.read_bytes() == expected
        rejected = subprocess.run(
            [command, "generate", "cfg-c-header"], check=False, capture_output=True
        )
        assert rejected.returncode == 2 and rejected.stdout == b""
        assert b"not fully configured" in rejected.stderr
    finally:
        config_path.unlink(missing_ok=True)
        for output in outputs:
            output.unlink(missing_ok=True)


def check_configuration_diagnostics(resolved: udb.ResolvedDatabase) -> None:
    from udb.configuration_diagnostics import explain_conflict, format_check_diagnostics

    data = udb.Configuration.builtin("rv32").to_dict()
    data["name"] = "installed-conflict"
    data["requirements"] = {
        "param": {
            "name": "MXLEN",
            "equal": 64,
            "reason": "This fixture requires a different machine width.",
        },
    }
    text = json.dumps(data)
    configuration = udb.Configuration.from_yaml(text, source="installed-conflict.yaml")
    architecture = resolved.configure(configuration)
    result = architecture.check()
    assert result.status is udb.ArchitectureCheckStatus.UNSAT
    assert set(result.conflict) == {
        "configuration parameter MXLEN=32",
        "configuration requirements",
    }
    explanations = explain_conflict(architecture, result)
    assert tuple(entry.label for entry in explanations) == result.conflict
    assert all(entry.source is not None and not entry.raw for entry in explanations)
    output = "\n".join(format_check_diagnostics(architecture, result))
    for expected in (
        "jointly inconsistent",
        "Configuration supplies MXLEN = 32",
        "requirement: MXLEN = 64",
        "reason: This fixture requires a different machine width.",
        "installed-conflict.yaml:1:",
    ):
        assert expected in output
    with TemporaryDirectory(prefix="udb-installed-conflict-") as temporary:
        path = Path(temporary) / "installed-conflict.yaml"
        path.write_text(text, encoding="utf-8")
        checked = subprocess.run(
            [str(Path(sys.executable).with_name("udb")), "validate-cfg", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert checked.returncode == 1, checked
        assert checked.stdout == "installed-conflict: unsat\n"
        assert "jointly inconsistent" in checked.stderr
        assert "reason: This fixture requires a different machine width." in checked.stderr


def check_configured_prose(resolved: udb.ResolvedDatabase) -> None:
    from udb.prose import (
        CapturedProse,
        ProseError,
        ProseInputs,
        render_legacy,
        render_native,
        resolve_all_exception_records,
    )

    inputs = ProseInputs.from_database(resolved, udb.Configuration.builtin("rv64"))
    stvec = CapturedProse.from_record(
        resolved, resolved.csr("stvec"), "fields", "BASE", "description"
    )
    rendered_stvec = render_legacy(stvec, inputs)
    assert "[SXLEN-1:39]" in rendered_stvec and "bit 38" in rendered_stvec
    assert "<%" not in rendered_stvec and stvec.span is not None
    assert stvec.source_text is not None

    load_reserved = CapturedProse.from_record(resolved, resolved.instruction("lr.w"), "description")
    rendered_load_reserved = render_legacy(load_reserved, inputs)
    assert "The 32-bit load result is sign-extended to 64-bits." in rendered_load_reserved
    assert "<%" not in rendered_load_reserved

    assert render_native(CapturedProse("{{ params.MXLEN }}"), {"params": {"MXLEN": 64}}) == "64"
    names = resolve_all_exception_records(resolved, inputs)
    assert names and all(isinstance(item["ext"], str) for item in names)
    json.dumps([dict(item) for item in names])

    cache = CapturedProse.from_record(resolved, resolved.instruction("cbo.flush"), "description")
    try:
        render_legacy(cache, inputs)
    except ProseError as error:
        assert error.diagnostic.legacy_error_class == "NoMethodError"
        assert error.diagnostic.prose is cache
        assert error.diagnostic.tag in cache.text
    else:
        raise AssertionError("unknown cache parameters must not become successful prose")


def check_profile_configurations(resolved: udb.ResolvedDatabase) -> None:
    from udb.profile_configs import profile_configuration, profile_configuration_plan

    config = profile_configuration(resolved, "RVI20U32")
    data = config.to_dict()
    assert data["params"] == {}
    assert data["mandatory_extensions"] == [{"name": "I", "version": "~> 2.1.0"}]
    assert {entry["name"] for entry in data["non_mandatory_extensions"]} == {
        "A",
        "C",
        "D",
        "F",
        "M",
        "Zca",
        "Zcd",
        "Zcf",
        "Zicntr",
        "Zifencei",
        "Zihpm",
    }
    assert data["requirements"] == {
        "param": {
            "allOf": [
                {"name": "U_MODE_ENDIANNESS", "equal": "little"},
                {"name": "UXLEN", "includes": 32},
            ]
        }
    }
    with TemporaryDirectory(prefix="udb-installed-profile-") as temporary:
        root = Path(temporary)
        expected = root / "api"
        profile_configuration_plan(resolved, ["RVI20U32"]).apply(expected)
        output = root / "cli"
        command = [
            str(Path(sys.executable).with_name("udb")),
            "generate",
            "profile-configs",
            "--profile",
            "RVI20U32",
            "-o",
            str(output),
        ]
        for arguments in (command, [*command, "--check"]):
            result = subprocess.run(arguments, check=True, capture_output=True, text=True)
            assert not result.stdout and not result.stderr
        assert (output / "RVI20U32.yaml").read_bytes() == (expected / "RVI20U32.yaml").read_bytes()
        assert udb.Configuration.from_file(output / "RVI20U32.yaml").to_dict() == data


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
    assert rv64_arch.check().status is udb.ArchitectureCheckStatus.VALID
    assert "add" in [inst.name for inst in rv64_arch.possible_instructions]
    check_configuration_diagnostics(resolved)
    check_configured_prose(resolved)
    check_config_headers(resolved)
    check_profile_configurations(resolved)

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

    from udb.idl.value_bounds import max_value, min_value
    from udb.idl_architecture import ArchitectureCompiler
    from udb.idl_conditions import compile_idl_condition
    from udb.idl_environment import condition_symbol_table

    configured = rv64_arch
    compiler = ArchitectureCompiler(configured)
    operation = compiler.compile_instruction("addi", effective_xlen=64)
    assert operation.effective_xlen == 64
    assert operation.symtab.get("__effective_xlen").value == 64
    assert operation.symtab.get("imm").decode_var
    assert operation.source.label.endswith("inst/I/addi.yaml")
    assert "X[xd]" in operation.source.text
    bootstrap = condition_symbol_table(resolved)
    assert bootstrap.get("INSTR_ENC_SIZE").value == 32
    before = bootstrap.snapshot_values()
    constraint = next(
        record for record in resolved.objects("parameter") if record.name == "SXLEN"
    ).data["requirements"]["idl()"]
    translated = compile_idl_condition(constraint, bootstrap)
    assert translated == udb.parse_condition(
        {
            "if": {"param": {"name": "MXLEN", "equal": 32}},
            "then": {"not": {"param": {"name": "SXLEN", "includes": 64}}},
        }
    )
    assert not translated.has_unresolved
    assert bootstrap.snapshot_values() == before
    rv32_arch = resolved.configure(udb.Configuration.builtin("rv32"))
    assert rv32_arch.check().status is udb.ArchitectureCheckStatus.VALID
    assert rv32_arch.extension_presence("Sv39") is udb.QueryPresence.ABSENT
    checked_config = subprocess.run(
        [str(Path(sys.executable).with_name("udb")), "validate-cfg", "rv32"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert checked_config.stdout == "rv32: valid\n"
    assert not checked_config.stderr
    assert (
        configured.instruction_operation("addi", effective_xlen=64).source.text
        == operation.source.text
    )
    csr = configured.csr_behavior("misa", effective_xlen=64)
    assert csr.source.label.endswith("csr/misa.yaml")
    assert csr.effective_xlen == 64
    assert csr.expected_return_type == Type(TypeKind.BITS, width=128)
    literal = idl.parse_expression("6'd3")
    assert min_value(literal, operation.symtab) == max_value(literal, operation.symtab) == 3
    symbolic_compiler = ArchitectureCompiler(resolved.configure(udb.Configuration.builtin("_")))
    symbolic_xlen = symbolic_compiler.compile_function("xlen")
    assert symbolic_xlen.effective_xlen is None
    assert symbolic_xlen.symtab.get("MXLEN").value is None
    assert symbolic_xlen.expected_return_type.width == 8

    from udb.idl.passes import (
        DecodeEncoding,
        DecodeGenerator,
        build_decode_tree,
        destination_registers,
        prune,
        reachable_exceptions,
        source_registers,
        to_adoc,
    )

    optimized = prune(operation.ast, operation.symtab)
    assert optimized is not operation.ast
    idl.parse_instruction_operation(optimized.to_idl()).type_check(operation.symtab.deep_clone())
    assert {ref.file for ref in source_registers(operation.ast, operation.symtab)} == {"X"}
    assert {ref.file for ref in destination_registers(operation.ast, operation.symtab)} == {"X"}
    assert reachable_exceptions(operation.ast, operation.symtab) == 0
    assert to_adoc(operation.ast)
    encodings = (DecodeEncoding("installed", "10--"),)
    decoder = build_decode_tree(encodings)
    assert decoder.decode(8) == encodings[0]
    assert decoder.decode(0) is None
    assert "return true;" in DecodeGenerator().generate(encodings, 64)

    print(
        f"Installed package passed: {len(raw_records)} records, {source_values} source spans, "
        f"{data_references} data / {schema_references} schema references, "
        f"{len(sm_versions)} Sm versions, 532 layout outputs, condition solving & configured queries, "
        f"IDL syntax parsing ({len(bundled_isa_files)} bundled isa/*.{{idl,isa}} files), "
        "IDL statement typing & execution, captured architecture compilation & value bounds, "
        "standalone analysis and source-generation passes, symbolic IDL conditions & genuine hooks"
    )


if __name__ == "__main__":
    check_install()
