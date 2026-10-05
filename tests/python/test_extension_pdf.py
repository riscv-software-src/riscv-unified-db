# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from udb.extension_docs.pdf import PdfOptions, PdfRenderError, copy_resources, render_extension_pdf
from udb.extension_docs.render_assets import highlight_idl, prepare_render_source, register_svg


def official_renderer_command():
    prefix = (
        "flock",
        os.environ["UDB_RUBY_LOCK"],
        "mise",
        "exec",
        "--no-deps",
        "--env",
        "UV_NO_SYNC=1",
        "--",
    )
    suffix = (
        ("asciidoctor-pdf",)
        if os.environ.get("UDB_PDF_RENDER_DIRECT") == "1"
        else ("bundle", "exec", "asciidoctor-pdf")
    )
    return (*prefix, *suffix)


def test_register_diagram_preserves_all_bits_and_labels():
    text = register_svg(
        '{"reg":[{"bits":7,"name":0x33,"type":2},'
        '{"bits":5,"name":"xd","type":4},{"bits":20,"name":"imm","type":4}]}'
    )
    assert "xd</text>" in text and "imm</text>" in text
    assert ">31</text>" in text and ">0</text>" in text
    assert "width=" in text


def test_empty_registers_and_literal_hex_labels_are_preserved():
    assert ">31</text>" in register_svg('{"reg":[],"config":{"bits":32,"lanes":2}}')
    text = register_svg(
        '{"reg":[{"bits":32,"name":"0x10","attr":["attribute"]}],"config":{"fontsize":10}}'
    )
    assert "0x10</text>" in text and "attribute</text>" in text
    assert 'font-size="10"' in text


@pytest.mark.parametrize(
    "raw",
    [
        '{"reg":[]}',
        '{"reg":[{"bits":-1}]}',
        '{"reg":[{"bits":129}]}',
        '{"reg":[{"bits":true}]}',
        '{"reg":[{"bits":32}],"config":{"lanes":3}}',
        "__import__('os').system('anything')",
        '{"reg":[{"bits":32}],"config":{"bits":1}}',
    ],
)
def test_bad_diagrams_fail_explicitly(raw):
    with pytest.raises(PdfRenderError.__base__):
        register_svg(raw)


def test_svg_escapes_label_markup():
    svg = register_svg('{"reg":[{"bits":32,"name":"<script>bad</script>","type":4}]}')
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


def test_idl_python_highlighter_preserves_accepted_pass_macros():
    code = "if pass:[(]true) { return xref:#udb-function-f[f]pass:[(]Bits<5>); } # note"
    highlighted = highlight_idl(code)
    assert "[.idl-keyword]##if##" in highlighted
    assert "[.idl-type]##Bits##" in highlighted
    assert "[.idl-comment]#" in highlighted
    assert "xref:#udb-function-f[f]pass:[(]" in highlighted
    assert "[.idl-builtin]##true##" in highlighted


def test_render_preparation_has_no_udb_ruby_require_or_wavedrom_process(tmp_path):
    raw = (
        "[wavedrom, ,svg]\n....\n"
        '{"reg":[{"bits":32,"name":"value","type":4}]}\n....\n'
        '[source,idl,subs="specialchars,macros"]\n----\nreturn 0;\n----\n'
    )
    prepared = prepare_render_source(raw, tmp_path)
    assert "[wavedrom," not in prepared
    assert "image::" in prepared and (tmp_path / "register-1.svg").is_file()
    assert "[.idl-keyword]##return##" in prepared
    assert "idl_highlighter" not in prepared


def test_missing_official_tool_does_not_create_output(tmp_path, monkeypatch):
    monkeypatch.setattr("udb.extension_docs.pdf.shutil.which", lambda command: None)
    source = tmp_path / "source.adoc"
    source.write_text("= Test\n")
    with pytest.raises(PdfRenderError, match="not installed"):
        render_extension_pdf(source, tmp_path / "out.pdf")
    assert not (tmp_path / "out.pdf").exists()
    assert not list(tmp_path.glob(".udb-pdf-*"))


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), 0, -1, "invalid"])
def test_invalid_render_timeout_is_explicit(tmp_path, timeout):
    with pytest.raises(PdfRenderError, match="positive finite timeout"):
        render_extension_pdf(
            "unused.adoc", tmp_path / "unused.pdf", options=PdfOptions(timeout=timeout)
        )


def test_pdf_output_cannot_overwrite_source_through_directory_symlink(tmp_path, monkeypatch):
    monkeypatch.setattr("udb.extension_docs.pdf.shutil.which", lambda command: "/official/tool")
    directory = tmp_path / "input"
    directory.mkdir()
    source = directory / "source.adoc"
    source.write_text("= Source\n")
    alias = tmp_path / "alias"
    alias.symlink_to(directory, target_is_directory=True)
    with pytest.raises(PdfRenderError, match="overwrite"):
        render_extension_pdf(source, alias / "source.adoc")
    assert source.read_text() == "= Source\n"


@pytest.mark.parametrize("mode", ["failure", "timeout", "no-output", "invalid-output"])
def test_renderer_failure_preserves_old_output_and_cleans_resources(tmp_path, monkeypatch, mode):
    source = tmp_path / "document.adoc"
    source.write_text("= Test\n")
    target = tmp_path / "result.pdf"
    target.write_bytes(b"old output")
    monkeypatch.setattr("udb.extension_docs.pdf.shutil.which", lambda command: "/official/tool")

    def run(args, **kwargs):
        assert "-r" not in args
        assert "idl_highlighter" not in " ".join(args)
        assert kwargs["env"]["TMPDIR"].startswith(str(tmp_path))
        if mode == "timeout":
            raise subprocess.TimeoutExpired(args, 1)
        if mode == "invalid-output":
            Path(args[args.index("-o") + 1]).write_bytes(b"not pdf")
        return SimpleNamespace(returncode=1 if mode == "failure" else 0, stderr="failed", stdout="")

    monkeypatch.setattr("udb.extension_docs.pdf._run_renderer", run)
    with pytest.raises(PdfRenderError):
        render_extension_pdf(source, target)
    assert target.read_bytes() == b"old output"
    assert not list(tmp_path.glob(".udb-pdf-*"))


def test_pdf_command_is_a_sequence_not_a_shell_and_commits_complete_output(tmp_path, monkeypatch):
    source = tmp_path / "input with spaces.adoc"
    source.write_text("= Test\n\n[source,idl]\n----\nreturn 0;\n----\n")
    target = tmp_path / "output with spaces.pdf"
    monkeypatch.setattr("udb.extension_docs.pdf.shutil.which", lambda command: "/official/tool")

    def run(args, **kwargs):
        assert kwargs.get("shell") is None
        assert "-o" in args and "-r" not in args
        assert "pdf-fontsdir=" in " ".join(args)
        Path(args[args.index("-o") + 1]).write_bytes(b"%PDF-1.7\ncomplete")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr("udb.extension_docs.pdf._run_renderer", run)
    assert render_extension_pdf(source, target) == target
    assert target.read_bytes() == b"%PDF-1.7\ncomplete"
    assert not list(tmp_path.glob(".udb-pdf-*"))


def test_renderer_timeout_terminates_private_wrapper_process_group(monkeypatch):
    from udb.extension_docs.pdf import _run_renderer

    calls = []

    class Process:
        pid = 12345
        returncode = -9

        def communicate(self, timeout=None):
            calls.append(("communicate", timeout))
            if timeout is not None:
                raise subprocess.TimeoutExpired("official-renderer", timeout)
            return "", ""

    def start(args, **kwargs):
        assert kwargs["start_new_session"]
        return Process()

    monkeypatch.setattr("udb.extension_docs.pdf.subprocess.Popen", start)
    monkeypatch.setattr(
        "udb.extension_docs.pdf.os.killpg", lambda pid, sig: calls.append(("killpg", pid))
    )
    with pytest.raises(subprocess.TimeoutExpired):
        _run_renderer(("flock", "lock", "official-renderer"), timeout=1)
    assert calls == [("communicate", 1), ("killpg", 12345), ("communicate", None)]


def test_resource_manifest_has_no_checkout_links_or_unmapped_fonts(tmp_path):
    copy_resources(tmp_path)
    assert not any(path.is_symlink() for path in tmp_path.rglob("*"))
    assert (tmp_path / "themes/qc-pdf.yml").read_text().startswith("# Copyright")
    assert (tmp_path / "fonts/Petrona-Light.ttf").is_file()
    assert (tmp_path / "images/draft.png").is_file()
    assert not (tmp_path / "riscv-unified-db").exists()


@pytest.mark.skipif(
    os.environ.get("UDB_RUN_PDF_ACCEPTANCE") != "1",
    reason="explicit external Ruby renderer boundary: run separately from the heavy Python lock",
)
def test_actual_official_pdf_text_metadata_and_rendered_page(tmp_path):
    import pypdf
    import pypdfium2

    source = tmp_path / "acceptance.adoc"
    source.write_text(
        "= Extension rendering acceptance\n:doctype: book\n:reproducible:\n\n"
        "== Instruction encoding\n\n"
        "[wavedrom, ,svg]\n....\n"
        '{"reg":[{"bits":7,"name":0x33,"type":2},{"bits":5,"name":"xd","type":4},'
        '{"bits":20,"name":"immediate","type":4}]}\n....\n\n'
        "== IDL operation\n\n[source,idl]\n----\n"
        "if (true) {\n  Bits<5> result = 3;\n  return result;\n}\n----\n",
        encoding="utf-8",
    )
    result = render_extension_pdf(
        source,
        tmp_path / "acceptance.pdf",
        options=PdfOptions(command=official_renderer_command()),
    )
    document = pypdf.PdfReader(result)
    text = "\n".join(page.extract_text() for page in document.pages)
    assert "Extension rendering acceptance" in text
    assert "Instruction encoding" in text and "immediate" in text and "xd" in text
    assert "Bits<5>" in text and "return result;" in text
    assert "[.idl-" not in text, "IDL color markup leaked into visible PDF content"
    assert "Asciidoctor PDF" in document.metadata.producer
    assert document.metadata.title == "Extension rendering acceptance"
    pdf = pypdfium2.PdfDocument(result)
    page = pdf[len(pdf) - 1]
    image = page.render(scale=1).to_pil().convert("RGB")
    image.save(tmp_path / "acceptance-page.png")
    colored = sum(
        1
        for red, green, blue in image.get_flattened_data()
        if max(red, green, blue) - min(red, green, blue) > 25
    )
    assert colored > 100, "Register fills and Python IDL syntax colors must render visibly"
    evidence = {
        "pages": len(document.pages),
        "title": document.metadata.title,
        "producer": document.metadata.producer,
        "colored_pixels": colored,
        "page_text": text,
    }
    (tmp_path / "acceptance.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")


@pytest.mark.skipif(
    os.environ.get("UDB_RUN_PDF_ACCEPTANCE") != "1",
    reason="external renderer boundary is separately serialized",
)
def test_actual_official_complete_zba_pdf_compares_native_source(tmp_path):
    import hashlib
    import re
    from datetime import date

    import pypdf
    import pypdfium2

    from udb import Configuration, Database
    from udb.extension_docs import DocumentOptions, generate_extension_document

    root = Path(__file__).parents[2]
    fixtures = Path(__file__).parent / "fixtures/extension_docs"
    manifest = json.loads((fixtures / "manifest.json").read_text())
    arch = (
        Database.from_path(root / "spec/std/isa", schemas_path=root / "spec/schemas")
        .resolve()
        .configure(Configuration.builtin("_"))
    )
    generated = generate_extension_document(
        arch,
        ["Zba"],
        tmp_path,
        options=DocumentOptions(revision=manifest["head"], today=date(2026, 10, 1)),
    )
    options = PdfOptions(command=official_renderer_command())
    documents = {}
    evidence = {}
    for label, source in (
        ("native-source", fixtures / "zba-all/zba-all.adoc"),
        ("python-source", generated),
    ):
        output = render_extension_pdf(source, tmp_path / (label + ".pdf"), options=options)
        pdf = pypdf.PdfReader(output)
        texts = [page.extract_text() for page in pdf.pages]
        combined = "\n".join(texts)
        assert "[.idl-" not in combined
        assert ".udb-pdf-" not in combined, "A register image macro leaked into visible page text"
        assert "Address generation" in combined and "Decode Variables" in combined
        assert "creg2reg" in combined and "IDL Functions" in combined
        assert pdf.metadata.title == "Address generation"
        assert "Asciidoctor PDF" in pdf.metadata.producer
        raster = pypdfium2.PdfDocument(output)
        samples = [
            0,
            next(index for index, text in enumerate(texts) if "Encoding" in text),
            next(
                index
                for index, text in enumerate(texts)
                if "creg2reg" in text and "Arguments" in text
            ),
        ]
        page_images = []
        for index in samples:
            image = raster[index].render(scale=1).to_pil().convert("RGB")
            path = tmp_path / f"{label}-page-{index + 1}.png"
            image.save(path)
            page_images.append(
                {
                    "page": index + 1,
                    "width": image.width,
                    "height": image.height,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "nonwhite_pixels": sum(
                        pixel != (255, 255, 255) for pixel in image.get_flattened_data()
                    ),
                }
            )
        assert all(image["nonwhite_pixels"] > 100 for image in page_images)
        evidence[label] = {
            "pages": len(pdf.pages),
            "title": pdf.metadata.title,
            "producer": pdf.metadata.producer,
            "rendered_pages": page_images,
            "text_sha256": hashlib.sha256(combined.encode()).hexdigest(),
        }
        documents[label] = combined

    # Pagination and footer page numbers can differ due repaired native xrefs.
    # Compare every content word while only removing exact theme footer lines.
    def content(text):
        lines = [
            line
            for line in text.splitlines()
            if not re.search(r"(?:\| Page \d+|© RISC-V International)$", line)
        ]
        return re.findall(r"\S+", "\n".join(lines))

    assert content(documents["native-source"]) == content(documents["python-source"])
    (tmp_path / "complete-product-acceptance.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8"
    )


@pytest.mark.skipif(
    os.environ.get("UDB_RUN_PDF_ACCEPTANCE") != "1",
    reason="explicit official renderer: separate from the heavy Python lock",
)
def test_actual_official_qc_csr_theme_and_declared_float_include(tmp_path):
    import hashlib
    from datetime import date

    import pypdf
    import pypdfium2
    from extension_documents_helpers import configured_prose_provider
    from test_extension_fidelity import corrected_native

    from udb import Configuration, Database, SchemaStore
    from udb.extension_docs import DocumentOptions, generate_extension_document
    from udb.extension_docs.source_assets import source_asset_closure, write_source_assets

    root = Path(__file__).parents[2]
    fixtures = root / "tests/python/fixtures/extension_docs"
    manifest = json.loads((fixtures / "manifest.json").read_text())
    case = next(item for item in manifest["outcomes"] if item["id"] == "qcicsr")
    configuration = Configuration.from_file(
        root / "cfgs/qc_iu.yaml", schema_store=SchemaStore(root / "spec/schemas")
    )
    database = Database.from_path(
        root / "spec/std/isa", schemas_path=root / "spec/schemas"
    ).resolve(overlays=(root / "spec/custom/isa" / configuration.overlay,))
    architecture = database.configure(configuration)
    generated = generate_extension_document(
        architecture,
        case["selectors"],
        tmp_path,
        options=DocumentOptions(
            revision=manifest["head"],
            today=date(2026, 10, 1),
            prose=configured_prose_provider(architecture),
        ),
    )
    native_csrs = corrected_native("zicsr-all", preserve_format=True)
    start = native_csrs.index("[#udb-csr-fcsr]")
    end = native_csrs.index("[#udb-csr-fflags]", start)
    complete_csr = native_csrs[start:end].rsplit(":leveloffset: -2", 1)[0]
    supplement = (
        "\n== Complete captured floating-point CSR\n\n:leveloffset: +2\n\n"
        + complete_csr
        + "\n:leveloffset: -2\n\n"
        "== Floating-point CSR bit layout\n\ninclude::images/wavedrom/float-csr.adoc[]\n"
    )
    write_source_assets(source_asset_closure(supplement), tmp_path)
    originals = {
        "native-source": corrected_native("qcicsr", preserve_format=True),
        "python-source": generated.read_text(),
    }
    evidence, texts = {}, {}
    for label, text in originals.items():
        source = tmp_path / f"{label}.adoc"
        source.write_text(text + supplement, encoding="utf-8")
        output = render_extension_pdf(
            source,
            tmp_path / f"{label}.pdf",
            options=PdfOptions(qc_theme=True, command=official_renderer_command()),
        )
        document = pypdf.PdfReader(output)
        pages = [page.extract_text() for page in document.pages]
        combined = "\n".join(pages)
        assert "Field Summary" in combined and "Reset value" in combined
        assert "Rounding Mode" in combined and "Reserved" in combined
        assert "image::" not in combined and "[.idl-" not in combined
        assert "Asciidoctor PDF" in document.metadata.producer
        font_names = sorted(
            {
                str(font.get_object().get("/BaseFont", ""))
                for page in document.pages
                for font in page["/Resources"]["/Font"].values()
            }
        )
        assert any("Petrona" in name for name in font_names)
        raster = pypdfium2.PdfDocument(output)
        index = next(i for i, text in enumerate(pages) if "Rounding Mode" in text)
        image = raster[index].render(scale=1).to_pil().convert("RGB")
        page_path = tmp_path / f"{label}-float-csr.png"
        image.save(page_path)
        colored_pixels = sum(max(pixel) - min(pixel) > 25 for pixel in image.get_flattened_data())
        assert colored_pixels > 50
        texts[label] = combined.split()
        evidence[label] = {
            "pages": len(document.pages),
            "title": document.metadata.title,
            "producer": document.metadata.producer,
            "fonts": font_names,
            "text_sha256": hashlib.sha256(combined.encode()).hexdigest(),
            "rendered_float_csr_page": index + 1,
            "rendered_page_sha256": hashlib.sha256(page_path.read_bytes()).hexdigest(),
            "colored_pixels": colored_pixels,
        }
    assert texts["native-source"] == texts["python-source"]
    (tmp_path / "qc-csr-rendering-acceptance.json").write_text(json.dumps(evidence, indent=2))
