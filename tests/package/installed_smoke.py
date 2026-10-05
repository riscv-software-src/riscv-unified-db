# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Bounded acceptance for an installed wheel or sdist-built wheel.

Run with the installed interpreter from outside the checkout. The parent package
task supplies one explicit full configuration; every database, schema, template,
layout, and C++ runtime resource otherwise comes from the installed package.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

import udb


def command(*arguments: str) -> subprocess.CompletedProcess[str]:
    executable = Path(sys.executable).with_name("udb")
    result = subprocess.run(
        [str(executable), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def check_resources() -> None:
    package = files("udb")
    required = (
        "_data/isa/ext/Zvkg.yaml",
        "_data/schemas/inst_schema.json",
        "_data/layouts/inst/Zaamo/amoadd.SIZE.AQRL.layout",
        "_data/custom_layouts/qc_iu/csr/Xqci/qc.mclicipN.layout",
        "_data/cpp_hart/runtime/CMakeLists.txt",
        "_data/cpp_hart/runtime/cpp/include/udb/bits.hpp",
        "extension_docs/templates/header.adoc",
        "extension_docs/assets/fonts/JetBrainsMono-Regular.ttf",
    )
    assert all(package.joinpath(*Path(path).parts).is_file() for path in required)


def check_api() -> None:
    assert Path(udb.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    assert shutil.which("git") is None
    assert shutil.which("ruby") is None
    database = udb.Database.bundled()
    assert database.extension("Zvkg").name == "Zvkg"
    resolved = database.resolve(validate=True)
    architecture = resolved.configure(udb.Configuration.builtin("rv32"))
    assert architecture.check().status is udb.ArchitectureCheckStatus.VALID
    assert resolved.profile("RVI20U64")["extensions"]["I"]["presence"] == "mandatory"


def check_qc_layout(root: Path) -> None:
    collection = udb.get_layout_collection("qc_iu")
    representative = replace(collection, jobs=(collection.jobs[0],))
    generated = udb.generate_layouts(root, collections=(representative,))
    assert tuple(map(str, generated)) == ("spec/custom/isa/qc_iu/csr/Xqci/qc.mclicip0.yaml",)
    output = root / generated[0]
    packaged = files("udb").joinpath(
        "_data", "custom_isa", "qc_iu", "csr", "Xqci", "qc.mclicip0.yaml"
    )
    assert output.read_bytes() == packaged.read_bytes()


def check_pdf_command(source: Path, output: Path) -> None:
    from udb.extension_docs import pdf

    captured: dict[str, object] = {}

    def renderer(arguments, **options):
        captured["arguments"] = tuple(arguments)
        captured["options"] = options
        result = Path(arguments[arguments.index("-o") + 1])
        result.write_bytes(b"%PDF-1.7\nconstructed-only\n")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    with (
        patch.object(pdf.shutil, "which", return_value="/external/asciidoctor-pdf"),
        patch.object(pdf, "_run_renderer", side_effect=renderer),
    ):
        assert pdf.render_extension_pdf(source, output) == output

    arguments = captured["arguments"]
    assert isinstance(arguments, tuple)
    assert arguments[0] == "asciidoctor-pdf"
    assert "pdf-theme=" in " ".join(arguments)
    assert "pdf-fontsdir=" in " ".join(arguments)
    assert "imagesdir=" in " ".join(arguments)
    assert arguments[-1].endswith("document.adoc")
    options = captured["options"]
    assert isinstance(options, dict)
    assert options["cwd"] == source.parent
    assert Path(options["env"]["TMPDIR"]).parent == output.parent
    assert output.read_bytes().startswith(b"%PDF-")


def check_cli(root: Path, full_config: Path) -> None:
    version = command("--version")
    assert version.stdout.startswith("udb ") and not version.stderr

    listed = command("list", "extension")
    assert "I\n" in listed.stdout and not listed.stderr
    validated = command("validate", "cfg", "-c", "rv32")
    assert validated.stdout == "rv32: valid\n" and not validated.stderr
    evaluated = command("idl", "eval", "8'd1 + 8'd1")
    assert evaluated.stdout == "2\n"

    header = root / "config.h"
    command("generate", "config-c-header", "-c", str(full_config), "-o", str(header))
    assert "#define UDB_MXLEN 32" in header.read_text(encoding="utf-8")

    document_root = root / "extension-document"
    command(
        "generate",
        "extension-document",
        "-e",
        "Zba",
        "--revision",
        "installed-smoke",
        "--date",
        "2026-10-02",
        "-o",
        str(document_root),
    )
    document = document_root / "Zba.adoc"
    assert document.is_file()
    check_pdf_command(document, root / "constructed.pdf")

    check_qc_layout(root / "qc-layout")

    cpp_root = root / "cpp-hart"
    command("generate", "cpp-hart", "-c", "rv32", "-o", str(cpp_root))
    manifest = json.loads((cpp_root / "cpp-hart-manifest.json").read_text(encoding="utf-8"))
    assert manifest["configurations"] == ["rv32"]
    assert (cpp_root / "include/udb/cfgs/rv32/hart.hxx").is_file()
    assert (cpp_root / "include/udb/bits.hpp").is_file()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--full-config", required=True, type=Path)
    arguments = parser.parse_args()
    arguments.root.mkdir(parents=True)
    check_resources()
    check_api()
    check_cli(arguments.root, arguments.full_config.resolve())
    print("installed package smoke passed")


if __name__ == "__main__":
    main()
