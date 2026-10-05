# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Bounded testing interface; permanent installed CLI spelling is a separate decision."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO

from ..configuration import Configuration
from ..database import Database
from ..errors import UdbError
from .formatting import ReportError
from .matching import InstructionMatcher, parse_encoding
from .reports import ReportBuilder, render_extension, render_names, render_parameter


def _options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--path", "--arch", "-a", type=Path, help="explicit ISA tree; default: bundled standard ISA"
    )
    parser.add_argument("--schemas", type=Path, help="schemas for an explicit ISA tree")
    parser.add_argument(
        "--overlay",
        type=Path,
        action="append",
        default=[],
        help="explicit overlay; repeat in precedence order",
    )
    parser.add_argument(
        "--arch-overlay",
        "--arch_overlay",
        type=Path,
        help="base directory for config-declared arch_overlay",
    )
    parser.add_argument(
        "--config",
        "-c",
        default="_",
        help="explicit YAML file, config-dir name, or bundled _, rv32, rv64",
    )
    parser.add_argument("--config-dir", "--config_dir", type=Path)
    parser.add_argument(
        "--gen",
        type=Path,
        help="accepted legacy compatibility argument; Python reports need no disk cache",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m udb.query_reports")
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("show").add_subparsers(dest="subject", required=True)
    for subject in ("extension", "parameter"):
        leaf = show.add_parser(subject)
        leaf.add_argument("name")
        _options(leaf)
    listing = commands.add_parser("list").add_subparsers(dest="subject", required=True)
    for subject in ("extensions", "parameters", "csrs"):
        leaf = listing.add_parser(subject)
        _options(leaf)
        if subject in ("extensions", "parameters"):
            leaf.add_argument("--output", "-o", type=Path, default=Path("-"))
        if subject == "parameters":
            leaf.add_argument("--extensions", "-e", nargs="*")
            leaf.add_argument(
                "--output-format",
                "--output_format",
                "-f",
                choices=("ascii", "yaml", "json"),
                default="ascii",
            )
        if subject == "csrs":
            leaf.add_argument(
                "--selection", choices=("catalog", "possible", "mandatory"), default="catalog"
            )
    disasm = commands.add_parser("disasm")
    disasm.add_argument("encoding")
    _options(disasm)
    disasm.add_argument(
        "--width",
        type=int,
        choices=(16, 32),
        help="strict descriptor width, unlike legacy mask-only matching",
    )
    disasm.add_argument("--xlen", type=int, choices=(32, 64))
    disasm.add_argument(
        "--selection", choices=("catalog", "possible", "mandatory"), default="catalog"
    )
    return parser


def load_architecture(args):
    """Only explicitly supplied paths or packaged resources are opened."""
    path = Path(args.config)
    if path.is_file():
        configuration = Configuration.from_file(path)
    elif args.config_dir is not None and (args.config_dir / f"{args.config}.yaml").is_file():
        configuration = Configuration.from_file(args.config_dir / f"{args.config}.yaml")
    elif args.config_dir is None and args.config in ("_", "rv32", "rv64"):
        configuration = Configuration.builtin(args.config)
    else:
        raise ReportError(f"Cannot find config: {args.config}")
    overlays = list(args.overlay)
    declaration = configuration.to_dict().get("arch_overlay")
    if declaration is not None and args.arch_overlay is not None:
        overlay = Path(declaration)
        overlays.insert(0, overlay if overlay.is_absolute() else args.arch_overlay / overlay)
    elif declaration is not None and not overlays:
        raise ReportError(
            "config declares arch_overlay; supply --arch-overlay or explicit --overlay"
        )
    database = (
        Database.from_path(args.path, schemas_path=args.schemas)
        if args.path is not None
        else Database.bundled()
    )
    return database.resolve(overlays=overlays).configure(configuration)


def render_command(args, architecture) -> str:
    if args.command == "disasm":
        return (
            InstructionMatcher(architecture)
            .match(
                args.encoding,
                width=args.width,
                xlen=args.xlen,
                selection=args.selection,
            )
            .render()
        )
    builder = ReportBuilder(architecture)
    if args.command == "show":
        if args.subject == "extension":
            return render_extension(builder.extension(args.name), args.name)
        return render_parameter(builder.parameter(args.name), args.name)
    if args.subject == "extensions":
        return render_names(builder.extensions())
    if args.subject == "csrs":
        return render_names(builder.csrs(selection=args.selection))
    return builder.parameters(args.extensions).render(args.output_format)


def write_report(text: str, stream: BinaryIO) -> None:
    """Portable UTF-8/LF and short-write-safe output, including redirected stdout."""
    payload = text.encode("utf-8")
    offset = 0
    while offset < len(payload):
        count = stream.write(payload[offset:])
        if type(count) is not int or count <= 0 or count > len(payload) - offset:
            raise OSError("output stream did not accept the complete report")
        offset += count
    stream.flush()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.schemas is not None and args.path is None:
        parser.error("--schemas requires an explicit --path/--arch")
    output = None
    try:
        if args.path is not None and not args.path.is_dir():
            raise ReportError(f"Arch directory does not exist: {args.path}")
        if args.path is not None and args.schemas is None:
            raise ReportError("Explicit --path/--arch requires --schemas")
        if args.command == "disasm":
            parse_encoding(args.encoding)
        destination = getattr(args, "output", Path("-"))
        if destination != Path("-"):
            # The native extension/parameter lists open/truncate before resolving
            # config, including leaving an empty file on later config errors.
            output = destination.open("wb")
        architecture = load_architecture(args)
        text = render_command(args, architecture)
        if output is not None:
            write_report(text, output)
        elif hasattr(sys.stdout, "buffer"):
            write_report(text, sys.stdout.buffer)
        else:
            sys.stdout.write(text)
            sys.stdout.flush()
        return 0
    except (UdbError, OSError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        if output is not None:
            output.close()
