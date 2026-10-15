# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Command-line interface for the raw Python UDB package."""

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
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="list raw UDB records")
    list_parser.add_argument("kind", help="record kind, such as extension or instruction")

    show_parser = subparsers.add_parser("show", help="show one raw UDB record as JSON")
    show_parser.add_argument("kind", help="record kind, such as extension or instruction")
    show_parser.add_argument("name", help="record name")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        database = Database.from_path(args.path) if args.path else Database.bundled()
        if args.command == "list":
            for record in database.objects(args.kind):
                print(record.name)
        elif args.command == "show":
            print(json.dumps(database.get(args.kind, args.name).to_dict(), indent=2, default=str))
    except UdbError as error:
        parser.exit(2, f"udb: error: {error}\n")
    return 0
