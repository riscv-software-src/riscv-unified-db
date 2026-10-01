# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Offline manifest closure and bounded explicit source-resource inputs."""

import json
from importlib.resources import files
from pathlib import Path

import pytest

from udb.extension_docs import ExtensionDocumentError
from udb.extension_docs.pdf import copy_resources
from udb.extension_docs.render_assets import prepare_render_source
from udb.extension_docs.source_assets import (
    expand_render_includes,
    safe_relative,
    source_asset_closure,
    write_source_assets,
)


def test_float_csr_include_is_packaged_and_renderable_offline(tmp_path):
    source = "include::images/wavedrom/float-csr.adoc[]\n"
    assets = source_asset_closure(source)
    assert set(assets) == {Path("images/wavedrom/float-csr.adoc")}
    write_source_assets(assets, tmp_path)
    expanded = expand_render_includes(source, (tmp_path,))
    assert "include::" not in expanded and '"name":"Rounding Mode"' in expanded
    prepared = prepare_render_source(expanded, tmp_path)
    assert "[wavedrom," not in prepared and "image::" in prepared
    assert len(list(tmp_path.glob("register-*.svg"))) == 1


def test_every_packaged_resource_has_a_valid_hash(tmp_path):
    copy_resources(tmp_path)
    manifest = json.loads(
        files("udb.extension_docs").joinpath("assets", "manifest.json").read_text()
    )
    assert {entry["path"] for entry in manifest} == {
        path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()
    }
    assert (tmp_path / "themes/qc-pdf.yml").is_file()
    assert len(list((tmp_path / "fonts").glob("*.ttf"))) >= 20


@pytest.mark.parametrize("path", ["/etc/passwd", "../outside", "x/../../y", r"x\y", "{docdir}/x"])
def test_asset_paths_do_not_escape_declared_roots(path):
    with pytest.raises(ExtensionDocumentError, match="relative path"):
        safe_relative(path)


def test_caller_assets_are_explicit_bytes_not_checkout_discovery(tmp_path):
    source = "include::prose.adoc[]\n"
    with pytest.raises(ExtensionDocumentError, match="No declared packaged"):
        source_asset_closure(source)
    supplied = {
        "prose.adoc": b"Caller prose.\nimage::diagram.svg[]\n",
        "images/diagram.svg": b"<svg/>",
    }
    assets = source_asset_closure(source, supplied=supplied)
    assert assets == {Path(name): data for name, data in supplied.items()}
    write_source_assets(assets, tmp_path)
    assert "Caller prose." in expand_render_includes(source, (tmp_path,))


def test_include_cycles_and_nonempty_options_are_errors(tmp_path):
    supplied = {"a.adoc": b"include::b.adoc[]\n", "b.adoc": b"include::a.adoc[]\n"}
    with pytest.raises(ExtensionDocumentError, match="Cyclic"):
        source_asset_closure("include::a.adoc[]\n", supplied=supplied)
    for name, data in supplied.items():
        (tmp_path / name).write_bytes(data)
    with pytest.raises(ExtensionDocumentError, match="Cyclic"):
        expand_render_includes("include::a.adoc[]\n", (tmp_path,))
    with pytest.raises(ExtensionDocumentError, match="include options"):
        source_asset_closure("include::a.adoc[tag=hidden]\n", supplied=supplied)


def test_source_asset_conflicts_and_parent_symlinks_preserve_inputs(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    target = output / "prose.adoc"
    target.write_text("Original", encoding="utf-8")
    with pytest.raises(ExtensionDocumentError, match="conflicts"):
        write_source_assets({Path("prose.adoc"): b"Replacement"}, output)
    assert target.read_text() == "Original"
    outside = tmp_path / "outside"
    outside.mkdir()
    (output / "images").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ExtensionDocumentError, match="escapes output"):
        write_source_assets({Path("images/test.svg"): b"<svg/>"}, output)
    assert not (outside / "test.svg").exists()


def test_remote_images_and_missing_inputs_fail_without_fetching(tmp_path):
    with pytest.raises(ExtensionDocumentError, match="Offline source"):
        source_asset_closure("image::https://example.com/test.svg[]")
    with pytest.raises(ExtensionDocumentError, match="Missing explicit"):
        expand_render_includes("include::missing.adoc[]\n", (tmp_path,))


def test_declared_include_limits_reject_unbounded_inputs():
    with pytest.raises(ExtensionDocumentError, match="bounded budget"):
        source_asset_closure("include::big.adoc[]", supplied={"big.adoc": b"x" * 5_000_001})
    with pytest.raises(ExtensionDocumentError, match="bytes"):
        source_asset_closure("include::x.adoc[]", supplied={"x.adoc": "not bytes"})


def test_nested_include_paths_remain_relative_to_the_included_file(tmp_path):
    source = "include::nested/first.adoc[]\n"
    supplied = {
        "nested/first.adoc": b"First\ninclude::second.adoc[]\n",
        "nested/second.adoc": b"Second\n",
    }
    assets = source_asset_closure(source, supplied=supplied)
    assert set(assets) == {Path(name) for name in supplied}
    write_source_assets(assets, tmp_path)
    assert expand_render_includes(source, (tmp_path,)) == "First\nSecond\n\n\n"


def test_invalid_utf8_includes_have_typed_errors(tmp_path):
    source = "include::invalid.adoc[]\n"
    with pytest.raises(ExtensionDocumentError, match="not UTF-8"):
        source_asset_closure(source, supplied={"invalid.adoc": b"\xff"})
    (tmp_path / "invalid.adoc").write_bytes(b"\xff")
    with pytest.raises(ExtensionDocumentError, match="UTF-8 render include"):
        expand_render_includes(source, (tmp_path,))
