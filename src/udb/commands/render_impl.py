# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Implement installed PDF rendering."""

from __future__ import annotations

from pathlib import Path

from ..progress import ProgressCallback
from .common import ExternalToolError


def run_render(
    input: Path,
    output: Path,
    *,
    theme: Path | None,
    fonts: Path | None,
    images: Path | None,
    qc_theme: bool,
    timeout: float,
    progress: ProgressCallback | None = None,
) -> int:
    from ..extension_docs.pdf import PdfOptions, PdfRenderError, render_extension_pdf

    try:
        render_extension_pdf(
            input,
            output,
            options=PdfOptions(
                theme=theme,
                fonts=fonts,
                images=images,
                qc_theme=qc_theme,
                timeout=timeout,
            ),
            progress=progress,
        )
    except PdfRenderError as error:
        text = str(error)
        if (
            "asciidoctor-pdf is not installed" in text
            or "renderer could not complete" in text
            or "renderer exited" in text
            or "renderer did not produce" in text
        ):
            raise ExternalToolError(text) from error
        raise
    return 0
