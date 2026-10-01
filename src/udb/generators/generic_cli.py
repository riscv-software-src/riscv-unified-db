# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Offline module commands for generic C, SV and Go source generation."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from udb import Configuration, Database, UdbError
from udb.cli import _write_generated_source

from .c_encoding import generate_c_encoding
from .encoding_inputs import GO_EXTENSIONS, EncodingGeneratorError, ExceptionRecord
from .go import generate_go
from .sv_decode import generate_sv_decode

type GeneratorName = Literal["c-encoding", "sv-decode", "go"]


def add_options(parser: argparse.ArgumentParser, generator: GeneratorName) -> None:
    """Add generator-specific options; shared CLI integration reuses this."""
    parser.add_argument(
        "-c", "--config", "--cfg", default="_", help="_, rv32, rv64, or explicit config YAML"
    )
    parser.add_argument(
        "-o", "--output", "--out", type=Path, help="output file (default: UTF-8 stdout)"
    )
    parser.add_argument(
        "--arch", choices=("RV32", "RV64", "BOTH"), default="RV64" if generator == "go" else "BOTH"
    )
    parser.add_argument(
        "--extensions",
        "-e",
        nargs="*",
        default=None,
        help="extension names, separated by spaces or commas; original name-only filter",
    )
    parser.add_argument("--include-all", "-a", action="store_true")
    parser.add_argument(
        "--overlay-root",
        type=Path,
        help="explicit custom ISA root for a config's arch_overlay; never discover a checkout",
    )
    if generator != "go":
        parser.add_argument(
            "--exception-records",
            type=Path,
            help="explicit JSON array of fully rendered num/name/var/ext rows",
        )
    if generator == "sv-decode":
        parser.add_argument(
            "--package-name", help="default: output file stem, or riscv_decode_package"
        )


def render(architecture, args: argparse.Namespace, generator: GeneratorName) -> str:
    """Render without writing; all failures occur before output replacement."""
    options = {
        "arch": args.arch,
        "extensions": (
            GO_EXTENSIONS
            if generator == "go" and args.extensions is None
            else args.extensions or ()
        ),
        "include_all": args.include_all or (generator != "go" and args.extensions is None),
    }
    if generator == "go":
        return generate_go(architecture, **options)
    path = args.exception_records
    if path is not None:
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise EncodingGeneratorError(
                f"{path}: cannot read exception records: {error}"
            ) from error
        if not isinstance(rows, list):
            raise EncodingGeneratorError(f"{path}: exception records must be a JSON array")
        options["exception_records"] = tuple(ExceptionRecord.from_mapping(row) for row in rows)
    if generator == "c-encoding":
        return generate_c_encoding(architecture, **options)
    options["package_name"] = args.package_name or (
        args.output.stem if args.output is not None else "riscv_decode_package"
    )
    return generate_sv_decode(architecture, **options)


def load_and_render(args: argparse.Namespace, generator: GeneratorName) -> str:
    """Use bundled data or caller resources and the existing overlay resolver."""
    configuration = (
        Configuration.builtin(args.config)
        if args.config in ("_", "rv32", "rv64")
        else Configuration.from_file(args.config)
    )
    overlays = list(args.overlay)
    if configuration.overlay is not None and not overlays:
        if args.overlay_root is None:
            raise EncodingGeneratorError(
                "configuration declares arch_overlay; supply --overlay or --overlay-root"
            )
        root = args.overlay_root.resolve()
        overlay = (root / configuration.overlay).resolve()
        if overlay == root or root not in overlay.parents:
            raise EncodingGeneratorError("configuration arch_overlay escapes --overlay-root")
        overlays.append(overlay)
    database = (
        Database.from_path(args.path, schemas_path=args.schemas)
        if args.path is not None
        else Database.bundled()
    ).resolve(overlays=overlays, validate=getattr(args, "validate", False))
    return render(database.configure(configuration), args, generator)


def main(generator: GeneratorName, argv: Sequence[str] | None = None) -> int:
    """Generate solely from packaged resources or explicitly supplied inputs."""
    parser = argparse.ArgumentParser(description=f"Generate generic {generator} source")
    parser.add_argument("--path", type=Path, help="explicit ISA directory; default: bundled data")
    parser.add_argument("--schemas", type=Path, help="schemas for an explicit ISA directory")
    parser.add_argument("--overlay", type=Path, action="append", default=[])
    add_options(parser, generator)
    args = parser.parse_args(argv)
    if args.schemas is not None and args.path is None:
        parser.error("--schemas requires --path")
    try:
        text = load_and_render(args, generator)
        _write_generated_source(text, args.output, artifact=generator, create_parents=True)
        return 0
    except (UdbError, OSError, UnicodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
