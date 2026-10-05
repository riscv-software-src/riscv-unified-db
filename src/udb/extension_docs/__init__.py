# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Retained extension source generation, independent of retired publications."""

from .documents import generate_extension_document, render_extension_document
from .model import DocumentOptions, ExtensionDocumentError, ProseProvider, select_extensions
from .pdf import PdfOptions, PdfRenderError, render_extension_pdf
from .xqci import xqci_selectors

__all__ = [
    "DocumentOptions",
    "ExtensionDocumentError",
    "PdfOptions",
    "PdfRenderError",
    "ProseProvider",
    "generate_extension_document",
    "render_extension_document",
    "render_extension_pdf",
    "select_extensions",
    "xqci_selectors",
]
