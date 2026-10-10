# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Inspect UDB source records or resolved records from the command line."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .database import Database
from .errors import UdbError


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.overlay and not args.resolved:
        parser.error("--overlay requires --resolved")
    if args.validate and not args.resolved:
        parser.error("--validate requires --resolved")
    if args.schemas and not args.path:
        parser.error("--schemas requires --path")
    try:
        database = (
            Database.from_path(args.path, schemas_path=args.schemas)
            if args.path
            else Database.bundled()
        )
        if args.resolved:
            database = database.resolve(overlays=args.overlay, validate=args.validate)
        if args.command == "list":
            for record in database.objects(args.kind):
                print(record.name)
        elif args.command == "show":
            print(json.dumps(database.get(args.kind, args.name).to_dict(), indent=2, default=str))
    except UdbError as error:
        parser.exit(2, f"udb: error: {error}\n")
    return 0
