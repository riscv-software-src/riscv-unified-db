# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Explicit official external PDF rendering, with Python-owned preparation."""

from __future__ import annotations

import json
import math
import os
import shutil
import signal
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from .model import ExtensionDocumentError
from .render_assets import HIGHLIGHT_ROLES, prepare_render_source
from .source_assets import expand_render_includes


class PdfRenderError(ExtensionDocumentError):
    """Missing official renderer/resource, failed rendering or invalid artifact."""


@dataclass(frozen=True, slots=True)
class PdfOptions:
    theme: str | Path | None = None
    fonts: str | Path | None = None
    images: str | Path | None = None
    qc_theme: bool = False
    timeout: float = 600
    command: tuple[str, ...] = ("asciidoctor-pdf",)


def copy_resources(directory: Path) -> None:
    """Copy a manifest-closed resource tree from the package, never a checkout."""
    root = files("udb.extension_docs").joinpath("assets")
    try:
        manifest = json.loads(root.joinpath("manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise PdfRenderError(f"Cannot read packaged PDF resource manifest: {error}") from error
    if not isinstance(manifest, list):
        raise PdfRenderError("Packaged PDF resource manifest must be an array")
    for entry in manifest:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise PdfRenderError("Invalid packaged PDF resource declaration")
        name = entry["path"]
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise PdfRenderError(f"Invalid packaged resource path {name!r}")
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = root.joinpath(*path.parts).read_bytes()
        except OSError as error:
            raise PdfRenderError(f"Cannot read packaged PDF resource {name}: {error}") from error
        import hashlib

        if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
            raise PdfRenderError(f"Packaged rendering resource failed integrity: {name}")
        target.write_bytes(data)


def _explicit_resource(path: str | Path | None, default: Path, *, directory: bool) -> Path:
    result = default if path is None else Path(path).absolute()
    present = result.is_dir() if directory else result.is_file()
    if not present:
        raise PdfRenderError(f"Missing PDF {'directory' if directory else 'file'}: {result}")
    return result


def _run_renderer(args, *, timeout, **kwargs):
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        **kwargs,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        process.communicate()
        raise
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def render_extension_pdf(
    source: str | Path, output: str | Path, *, options: PdfOptions | None = None
) -> Path:
    """Render only on explicit request; existing output survives all failures.

    A caller may wrap the official executable with a serialization command
    (the test/CI Ruby lock). The production default is the official executable
    only. No shell, UDB Ruby require, diagram helper or checkout access occurs.
    """
    options = options or PdfOptions()
    if (
        not options.command
        or not all(isinstance(arg, str) and arg for arg in options.command)
        or not isinstance(options.timeout, (int, float))
        or not math.isfinite(options.timeout)
        or options.timeout <= 0
    ):
        raise PdfRenderError("PDF command and positive finite timeout are required")
    executable = shutil.which(options.command[0])
    if executable is None:
        raise PdfRenderError(
            "Official asciidoctor-pdf is not installed; install it externally "
            "or generate AsciiDoc only"
        )
    source_path = Path(source).absolute()
    target = Path(output).absolute()
    if source_path.resolve() == target.resolve():
        raise PdfRenderError("PDF output must not overwrite its AsciiDoc input")
    try:
        text = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise PdfRenderError(f"Cannot read AsciiDoc input {source_path}: {error}") from error
    target.parent.mkdir(parents=True, exist_ok=True)
    scratch = target.parent / (".udb-pdf-" + uuid4().hex)
    scratch.mkdir()
    try:
        resources = scratch / "resources"
        copy_resources(resources)
        theme = _explicit_resource(
            options.theme,
            resources / "themes" / ("qc-pdf.yml" if options.qc_theme else "riscv-pdf.yml"),
            directory=False,
        )
        fonts = _explicit_resource(options.fonts, resources / "fonts", directory=True)
        images = _explicit_resource(options.images, resources / "images", directory=True)
        prepared = scratch / "document.adoc"
        expanded = expand_render_includes(text, (source_path.parent, resources))
        prepared.write_text(prepare_render_source(expanded, scratch), encoding="utf-8")
        # An official theme overlay supplies our ported lexer colors while
        # retaining caller theme/font/image behavior.
        overlay = scratch / "highlight-theme.yml"
        overlay.write_text(
            "extends:\n  - " + json.dumps(str(theme)) + "\n" + HIGHLIGHT_ROLES,
            encoding="utf-8",
        )
        result = scratch / "result.pdf"
        args: Sequence[str] = (
            *options.command,
            "-w",
            "-a",
            "toc",
            "-a",
            "compress",
            "-a",
            "allow-uri-read!",
            "-a",
            "pdf-theme=" + str(overlay),
            "-a",
            "pdf-fontsdir=" + str(fonts),
            "-a",
            "imagesdir=" + str(images),
            "-a",
            "docdir=" + str(source_path.parent),
            "-o",
            str(result),
            str(prepared),
        )
        environment = dict(os.environ)
        environment["TMPDIR"] = str(scratch)
        try:
            completed = _run_renderer(
                args,
                cwd=source_path.parent,
                env=environment,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=options.timeout,
            )
        except (OSError, ValueError, OverflowError, subprocess.TimeoutExpired) as error:
            raise PdfRenderError(f"Official PDF renderer could not complete: {error}") from error
        if completed.returncode:
            raise PdfRenderError(
                f"Official PDF renderer exited {completed.returncode}:\n"
                + (completed.stderr or completed.stdout)[-8000:]
            )
        if not result.is_file() or not result.read_bytes().startswith(b"%PDF-"):
            raise PdfRenderError("Official renderer did not produce a valid PDF artifact")
        result.replace(target)
        return target
    finally:
        shutil.rmtree(scratch)
