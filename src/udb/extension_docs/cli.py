# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Owned extension-specific arguments/dispatch; shared CLI wiring is a patch."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from datetime import date
from pathlib import Path

from ..architecture import ConfiguredArchitecture
from .documents import generate_extension_document
from .model import DocumentOptions, ExtensionDocumentError, ProseProvider
from .pdf import PdfOptions, render_extension_pdf
from .xqci import xqci_selectors


def pdf_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--theme", type=Path)
    parser.add_argument("--fonts", type=Path)
    parser.add_argument("--images", type=Path)
    parser.add_argument("--qc-theme", action="store_true")
    parser.add_argument("--render-timeout", type=float, default=600)


def add_pdf_render_parser(commands) -> ArgumentParser:
    render = commands.add_parser("render", help="explicit official external rendering")
    renderers = render.add_subparsers(dest="renderer", required=True)
    parser = renderers.add_parser(
        "pdf", help="render extension AsciiDoc with official Asciidoctor PDF"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--out", required=True, type=Path)
    pdf_arguments(parser)
    return parser


def pdf_options(args: Namespace) -> PdfOptions:
    return PdfOptions(
        theme=args.theme,
        fonts=args.fonts,
        images=args.images,
        qc_theme=args.qc_theme,
        timeout=args.render_timeout,
    )


def run_pdf_render(args: Namespace) -> Path:
    return render_extension_pdf(args.input, args.out, options=pdf_options(args))


def add_extension_document_parser(generators) -> ArgumentParser:
    parser = generators.add_parser("ext-doc", help="generate retained extension AsciiDoc/PDF")
    parser.add_argument(
        "-c",
        "--config",
        "--cfg",
        default="_",
        help="configuration YAML path or bundled generic name (_, rv32, rv64)",
    )
    parser.add_argument("-o", "--out", "--output", required=True, type=Path)
    parser.add_argument("-b", "--output-basename", dest="basename")
    parser.add_argument("-i", "--implied_insts", "--include-implied", action="store_true")
    parser.add_argument("--no-csr-field-desc", action="store_true")
    parser.add_argument("-f", "--format", choices=("adoc", "pdf"), default="adoc")
    parser.add_argument("--extension", action="append", default=[])
    parser.add_argument("extensions", nargs="*")
    parser.add_argument("--xqci-version", help="select original Xqci script components")
    parser.add_argument(
        "--revision", default="unknown", help="explicit provenance, never invokes Git"
    )
    parser.add_argument("--date", type=date.fromisoformat, help="explicit document date")
    pdf_arguments(parser)
    return parser


def run_extension_document(
    architecture: ConfiguredArchitecture,
    args: Namespace,
    *,
    prose: ProseProvider | None = None,
) -> Path:
    selectors = [*args.extension, *args.extensions]
    if args.xqci_version is not None:
        if selectors:
            raise ExtensionDocumentError("--xqci-version cannot be combined with selectors")
        selectors = list(xqci_selectors(architecture.database, args.xqci_version))
    options = DocumentOptions(
        include_implied=args.implied_insts,
        include_csr_field_descriptions=not args.no_csr_field_desc,
        basename=args.basename,
        revision=args.revision,
        today=args.date,
        prose=prose,
    )
    source = generate_extension_document(architecture, selectors, args.out, options=options)
    if args.format == "adoc":
        return source
    return render_extension_pdf(
        source,
        source.with_suffix(".pdf"),
        options=pdf_options(args),
    )
