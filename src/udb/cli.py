# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Inspect UDB records and validate configurations from the command line."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .cli_output import write_generated_source as _write_generated_source
from .database import Database, ResolvedDatabase
from .errors import UdbError
from .layout_collections import get_layout_collection, layout_collection_names
from .layouts import generate_layouts
from .schema import SchemaError, SchemaStore
from .serialization import write_resolved_schemas


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="udb")
    parser.add_argument(
        "--path",
        type=Path,
        help="read a raw ISA directory instead of the data bundled with udb",
    )
    parser.add_argument(
        "--schemas",
        type=Path,
        help="schema directory for a custom --path database",
    )
    parser.add_argument(
        "--resolved",
        action="store_true",
        help="resolve inheritance and removals before querying (not a configured architecture)",
    )
    parser.add_argument(
        "--overlay",
        type=Path,
        action="append",
        default=[],
        help="apply an ISA overlay before resolution; repeat in precedence order; requires --resolved",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="validate every resolved document against its declared schema; requires --resolved",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    reports_parser = subparsers.add_parser("inspect", help="configured UDB human reports")
    reports_parser.add_argument(
        "subject", choices=("extension", "parameter", "extensions", "parameters", "csrs")
    )
    reports_parser.add_argument("report_args", nargs=argparse.REMAINDER)
    disasm_parser = subparsers.add_parser("disasm", help="fixed-bit instruction matching")
    disasm_parser.add_argument("encoding")
    disasm_parser.add_argument("report_args", nargs=argparse.REMAINDER)

    list_parser = subparsers.add_parser("list", help="list UDB records")
    list_parser.add_argument("kind", help="record kind, such as extension or instruction")

    show_parser = subparsers.add_parser("show", help="show one UDB record as JSON")
    show_parser.add_argument("kind", help="record kind, such as extension or instruction")
    show_parser.add_argument("name", help="record name")

    resolve_parser = subparsers.add_parser(
        "resolve", help="write the resolved database as a deterministic YAML tree"
    )
    resolve_parser.add_argument("output", type=Path, help="output directory")

    config_parser = subparsers.add_parser(
        "validate-cfg", help="check configuration consistency, including IDL requirements"
    )
    config_parser.add_argument(
        "configuration", help="configuration YAML path or bundled name (_, rv32, rv64)"
    )

    generate_parser = subparsers.add_parser("generate", help="generate source artifacts")
    generators = generate_parser.add_subparsers(dest="generator", required=True)
    table_parser = generators.add_parser(
        "instruction-table", help="generate a table of all database instructions"
    )
    table_parser.add_argument(
        "-c",
        "--config",
        "--cfg",
        default="_",
        help="explicit configuration YAML path or bundled name (_, rv32, rv64)",
    )
    table_parser.add_argument(
        "-o", "--output", "--out", type=Path, help="output file (default: stdout)"
    )
    for language, description in (("c", "C"), ("svh", "SystemVerilog")):
        header_parser = generators.add_parser(
            f"cfg-{language}-header", help=f"generate a fully configured {description} header"
        )
        header_parser.add_argument(
            "-c",
            "--config",
            "--cfg",
            default="_",
            help="explicit configuration YAML path or bundled name (_, rv32, rv64)",
        )
        header_parser.add_argument(
            "-o", "--output", type=Path, help="output file (default: stdout)"
        )

    schemas_parser = subparsers.add_parser(
        "schemas", help="write versioned schemas for publication"
    )
    schemas_parser.add_argument("output", type=Path, help="output directory")

    layouts_parser = subparsers.add_parser(
        "generate-layouts", help="regenerate tracked architecture files from source layouts"
    )
    layouts_parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="output root, also used for source lookup unless --source-root is supplied",
    )
    layouts_parser.add_argument(
        "--collection",
        action="append",
        choices=layout_collection_names(),
        help="layout collection to generate (repeatable; default: standard)",
    )
    layouts_parser.add_argument(
        "--source-root",
        type=Path,
        help="explicit source tree, without bundled-resource fallback",
    )
    layouts_parser.add_argument(
        "--check", action="store_true", help="report generated-file drift without rewriting files"
    )
    profiles_parser = generators.add_parser(
        "profile-configs", help="generate solver-expanded profile configurations"
    )
    profiles_parser.add_argument("-o", "--output", type=Path, required=True)
    profiles_parser.add_argument(
        "--profile",
        action="append",
        help="select a named profile; repeat, or omit for all profiles",
    )
    profiles_parser.add_argument(
        "--check", action="store_true", help="report generated-file drift without rewriting files"
    )
    from .generators.generic_cli import add_options as add_generic_options

    for generator in ("c-encoding", "sv-decode", "go"):
        generic_parser = generators.add_parser(
            generator, help=f"generate generic {generator} source"
        )
        add_generic_options(generic_parser, generator)
    docs_parser = generators.add_parser("schema-docs", help="generate versioned schema MDX")
    docs_parser.add_argument("--schemas", dest="docs_schemas", type=Path)
    docs_parser.add_argument("--out", required=True, type=Path)
    docs_parser.add_argument("--schema", help="one schema filename, including .json")
    docs_parser.add_argument("--output-file", help="single page relative to --out")
    docs_parser.add_argument("--check", action="store_true")
    docs_parser.add_argument("--no-index", action="store_true")
    docs_parser.add_argument("--replace-current", action="store_true")
    docs_parser.add_argument("--diagnostics", action="store_true")
    from .extension_docs.cli import add_extension_document_parser, add_pdf_render_parser

    add_extension_document_parser(generators)
    add_pdf_render_parser(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in ("inspect", "disasm"):
        from .query_reports.cli import main as query_reports_main

        if args.resolved or args.validate:
            parser.error(
                "configured reports resolve their database; --resolved/--validate are raw-query options"
            )
        options = []
        for flag, value in (("--path", args.path), ("--schemas", args.schemas)):
            if value is not None:
                options.extend((flag, str(value)))
        for overlay in args.overlay:
            options.extend(("--overlay", str(overlay)))
        if args.command == "disasm":
            report_args = ["disasm", args.encoding]
        elif args.subject in ("extension", "parameter"):
            report_args = ["show", args.subject]
        else:
            report_args = ["list", args.subject]
        return query_reports_main([*report_args, *options, *args.report_args])
    resolves_database = args.resolved or args.command in ("resolve", "validate-cfg", "generate")
    if args.overlay and not resolves_database:
        parser.error("--overlay requires --resolved")
    if args.validate and not resolves_database:
        parser.error("--validate requires --resolved")
    if args.schemas and not args.path and args.command != "schemas":
        parser.error("--schemas requires --path")
    if args.command == "schemas" and (args.resolved or args.overlay or args.validate):
        parser.error("the schemas command does not accept resolution options")
    try:
        if args.command == "generate" and args.generator in ("c-encoding", "sv-decode", "go"):
            from .generators.generic_cli import load_and_render

            text = load_and_render(args, args.generator)
            _write_generated_source(text, args.output, artifact=args.generator, create_parents=True)
            return 0
        if args.command == "generate" and args.generator == "schema-docs":
            from .schema_docs.__main__ import main as schema_docs_main

            if args.path or args.schemas or args.resolved or args.overlay or args.validate:
                parser.error("schema-docs uses --schemas after the subcommand, not ISA options")
            docs_args = ["--out", str(args.out)]
            for option, value in (
                ("--schemas", args.docs_schemas),
                ("--schema", args.schema),
                ("--output-file", args.output_file),
            ):
                if value is not None:
                    docs_args.extend((option, str(value)))
            for option, enabled in (
                ("--check", args.check),
                ("--replace-current", args.replace_current),
                ("--no-index", args.no_index),
                ("--diagnostics", args.diagnostics),
            ):
                if enabled:
                    docs_args.append(option)
            return schema_docs_main(docs_args)
        if args.command == "render":
            from .extension_docs.cli import run_pdf_render

            if args.path or args.schemas or args.overlay or args.resolved or args.validate:
                parser.error("render pdf accepts explicit rendering inputs, not ISA options")
            run_pdf_render(args)
            return 0
        if args.command == "schemas":
            schema_root = args.schemas
            if schema_root is None:
                schema_root = Database.bundled().schemas_root
            if schema_root is None:
                raise SchemaError("Database has no schema directory")
            write_resolved_schemas(SchemaStore(schema_root), args.output)
            return 0
        if args.command == "generate-layouts":
            if args.resolved or args.overlay or args.validate:
                parser.error("the generate-layouts command does not accept resolution options")
            if args.path or args.schemas:
                parser.error("the generate-layouts command does not accept database paths")
            collections = (
                tuple(get_layout_collection(name) for name in args.collection)
                if args.collection is not None
                else None
            )
            drift = generate_layouts(
                args.root,
                check=args.check,
                collections=collections,
                source_root=args.source_root,
            )
            if args.check and drift:
                for path in drift:
                    print(path)
                return 1
            return 0
        database = (
            Database.from_path(args.path, schemas_path=args.schemas)
            if args.path
            else Database.bundled()
        )
        if resolves_database:
            database = database.resolve(overlays=args.overlay, validate=args.validate)
        if args.command == "generate":
            assert isinstance(database, ResolvedDatabase)
            if args.generator == "profile-configs":
                from .profile_configs import profile_configuration_plan

                plan = profile_configuration_plan(database, args.profile)
                drift = plan.apply(args.output, check=args.check)
                if args.check and drift:
                    for path in drift:
                        print(path)
                    return 1
                return 0

            from .configuration import Configuration

            configuration = (
                Configuration.builtin(args.config)
                if args.config in ("_", "rv32", "rv64")
                else Configuration.from_file(
                    args.config,
                    schema_store=(
                        SchemaStore(database.schemas_root)
                        if database.schemas_root is not None
                        else None
                    ),
                )
            )
            architecture = database.configure(configuration)
            if args.generator == "ext-doc":
                from .extension_docs.cli import run_extension_document

                run_extension_document(architecture, args)
                return 0
            if args.generator == "instruction-table":
                from .instruction_table import render_instruction_table

                text = render_instruction_table(architecture, file_name=args.output)
                _write_generated_source(text, args.output, artifact="instruction table")
                return 0

            from .generators.config_headers import generate_config_header

            language = "c" if args.generator == "cfg-c-header" else "svh"
            header = generate_config_header(architecture, language)
            _write_generated_source(header, args.output, artifact="header", create_parents=True)
            return 0
        if args.command == "validate-cfg":
            from .architecture import ArchitectureCheckStatus
            from .configuration import Configuration
            from .configuration_diagnostics import format_check_diagnostics

            assert isinstance(database, ResolvedDatabase)
            configuration = (
                Configuration.builtin(args.configuration)
                if args.configuration in ("_", "rv32", "rv64")
                else Configuration.from_file(
                    args.configuration,
                    schema_store=(
                        SchemaStore(database.schemas_root)
                        if database.schemas_root is not None
                        else None
                    ),
                )
            )
            architecture = database.configure(configuration)
            result = architecture.check()
            print(f"{configuration.name}: {result.status.value}")
            for line in format_check_diagnostics(architecture, result):
                print(line, file=sys.stderr)
            if result.status is ArchitectureCheckStatus.VALID:
                return 0
            return 1 if result.status is ArchitectureCheckStatus.UNSAT else 2
        if args.command == "list":
            for record in database.objects(args.kind):
                print(record.name)
        elif args.command == "show":
            print(json.dumps(database.get(args.kind, args.name).to_dict(), indent=2, default=str))
        elif args.command == "resolve":
            assert isinstance(database, ResolvedDatabase)
            database.write(args.output)
    except UdbError as error:
        parser.exit(2, f"udb: error: {error}\n")
    return 0
