# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Inspect UDB source records or resolved records from the command line."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .database import Database, ResolvedDatabase
from .errors import UdbError
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

    list_parser = subparsers.add_parser("list", help="list UDB records")
    list_parser.add_argument("kind", help="record kind, such as extension or instruction")

    show_parser = subparsers.add_parser("show", help="show one UDB record as JSON")
    show_parser.add_argument("kind", help="record kind, such as extension or instruction")
    show_parser.add_argument("name", help="record name")

    resolve_parser = subparsers.add_parser(
        "resolve", help="write the resolved database as a deterministic YAML tree"
    )
    resolve_parser.add_argument("output", type=Path, help="output directory")

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
        help="repository root containing spec/std/isa (default: current directory)",
    )
    layouts_parser.add_argument(
        "--check", action="store_true", help="report generated-file drift without rewriting files"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    resolves_database = args.resolved or args.command == "resolve"
    if args.overlay and not resolves_database:
        parser.error("--overlay requires --resolved")
    if args.validate and not resolves_database:
        parser.error("--validate requires --resolved")
    if args.schemas and not args.path and args.command != "schemas":
        parser.error("--schemas requires --path")
    if args.command == "schemas" and (args.resolved or args.overlay or args.validate):
        parser.error("the schemas command does not accept resolution options")
    try:
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
            drift = generate_layouts(args.root, check=args.check)
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
