# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Repository wrappers with an explicit caller-supplied source root.

The installed source API and normal CLI do not discover a repository. This
adapter exists solely for wrappers that explicitly pass their known root.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..configuration import Configuration
from ..database import Database
from ..errors import UdbError
from ..schema import SchemaStore
from .cli import add_extension_document_parser, run_extension_document
from .source_assets import safe_relative
from .xqci import xqci_selectors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    subcommands = parser.add_subparsers(dest="command", required=True)
    extension = add_extension_document_parser(subcommands)
    extension.set_defaults(format="pdf")
    extension.add_argument(
        "-d", "--debug", choices=("debug", "info", "warn", "error", "fatal"), default="info"
    )
    xqci = subcommands.add_parser("xqci", help="preserve the original Xqci script selection")
    xqci.add_argument("-v", "--version", default="latest")
    xqci.add_argument("-d", "--debug", choices=("debug", "info", "warn", "error", "fatal"))
    xqci.add_argument("-f", "--format", choices=("adoc", "pdf"), default="pdf")
    return parser


def repository_inputs(root: Path, config: str):
    """Resolve only paths within a root explicitly provided by the wrapper."""
    schemas = SchemaStore(root / "spec/schemas")
    if config in ("_", "rv32", "rv64"):
        configuration = Configuration.builtin(config)
    else:
        candidate = Path(config)
        if not candidate.is_file():
            candidate = root / "cfgs" / (safe_relative(config).as_posix() + ".yaml")
        configuration = Configuration.from_file(candidate, schema_store=schemas)
    overlays = (
        (root / "spec/custom/isa" / safe_relative(configuration.overlay),)
        if configuration.overlay
        else ()
    )
    database = Database.from_path(
        root / "spec/std/isa", schemas_path=root / "spec/schemas"
    ).resolve(overlays=overlays)
    return database, configuration


def xqci_arguments(database, version: str, output_format: str) -> list[str]:
    selectors = xqci_selectors(database, version)
    spelling = selectors[0].partition("@")[2]
    return [
        "-c",
        "qc_iu",
        "-o",
        f"gen/ext-doc/pdf/Xqci-{spelling}.pdf",
        "--format",
        output_format,
        "--qc-theme",
        "-i",
        "--no-csr-field-desc",
        *selectors,
    ]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        database, configuration = repository_inputs(
            args.root, "qc_iu" if args.command == "xqci" else args.config
        )
        if args.command == "xqci":
            args = parser.parse_args(
                [
                    "--root",
                    str(args.root),
                    "ext-doc",
                    *xqci_arguments(database, args.version, args.format),
                ]
            )
        run_extension_document(database.configure(configuration), args)
    except (UdbError, OSError, ValueError) as error:
        print(f"udb extension documents: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
