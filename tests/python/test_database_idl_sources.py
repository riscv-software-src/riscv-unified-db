# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from pathlib import Path
from shutil import rmtree

import pytest

from udb import Database, DataError
from udb.database import ResolvedDatabase
from udb.idl_environment import condition_symbol_table
from udb.idl_global_environment import global_ast
from udb.source import SourceText


def _write(root: Path, path: str, text: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_resolution_captures_custom_idl_includes_and_yaml(tmp_path: Path) -> None:
    root = tmp_path / "custom"
    yaml = "kind: extension\nname: Xcustom\noperation(): |\n  return 3;\n"
    isa = '%version: 1.0\ninclude "helpers.idl";\n'
    helper = "Bits<8> CUSTOM = 3;\n"
    _write(root, "ext/Xcustom.yaml", yaml)
    _write(root, "isa/globals.isa", isa)
    _write(root, "isa/helpers.idl", helper)

    resolved = Database.from_path(root).resolve()
    assert set(resolved.idl_sources) == {"isa/globals.isa", "isa/helpers.idl"}
    assert resolved.idl_sources["isa/globals.isa"] == SourceText("isa/globals.isa", isa)
    assert resolved.idl_sources["isa/helpers.idl"].text == helper
    assert resolved.source_text("ext/Xcustom.yaml") == yaml

    (root / "isa/helpers.idl").unlink()
    (root / "ext/Xcustom.yaml").write_text("changed: true\n", encoding="utf-8")
    assert resolved.idl_sources["isa/helpers.idl"].text == helper
    assert resolved.source_text("ext/Xcustom.yaml") == yaml


def test_global_ast_calls_never_share_node_caches(tmp_path: Path) -> None:
    root = tmp_path / "custom"
    _write(root, "isa/globals.isa", '%version: 1.0\ninclude "helpers.idl"\nBits<8> TOP = 1;\n')
    _write(root, "isa/helpers.idl", "%version: 1.0\nBits<8> CUSTOM = 3;\n")
    resolved = Database.from_path(root).resolve()

    first, second = global_ast(resolved), global_ast(resolved)
    assert first is not None and second is not None
    names = [item.var_decl_with_init.lhs.name for item in first.globals]
    assert names == [item.var_decl_with_init.lhs.name for item in second.globals]
    assert names == ["CUSTOM", "TOP"]
    for one, other in zip(first.definitions, second.definitions, strict=True):
        assert one is not other
        assert one.parent is first and other.parent is second
    first.globals[0]._cache["architecture"] = "rv32"
    assert "architecture" not in second.globals[0]._cache
    assert resolved.resolve() is resolved


def test_overlay_sources_preserve_layered_yaml_and_replace_idl(tmp_path: Path) -> None:
    base = tmp_path / "base"
    first = tmp_path / "first"
    second = tmp_path / "second"
    original = "kind: extension\nname: Xcustom\noperation(): return 1;\n"
    patch = "operation(): |\n  return 2;\n"
    _write(base, "ext/Xcustom.yaml", original)
    _write(base, "isa/globals.isa", "%version: 1.0\n")
    _write(base, "isa/helpers.idl", "Bits<8> CUSTOM = 1;\n")
    _write(first, "ext/Xcustom.yaml", patch)
    _write(first, "isa/helpers.idl", "Bits<8> CUSTOM = 2;\n")
    _write(second, "isa/helpers.idl", "Bits<8> CUSTOM = 3;\n")

    resolved = Database.from_path(base).resolve(overlays=(first, second))
    span = resolved.source_at("ext/Xcustom.yaml", "operation()")
    assert span is not None
    assert span.layer == "overlay[0]"
    assert resolved.source_text(span.source, layer=span.layer) == patch
    assert resolved.source_text(span.source) == original
    assert resolved.idl_sources["isa/helpers.idl"] == SourceText(
        "isa/helpers.idl", "Bits<8> CUSTOM = 3;\n", "overlay[1]"
    )
    assert resolved.idl_sources["isa/globals.isa"].layer == "source"
    assert resolved.idl_sources["isa/helpers.idl"].label == "overlay[1]:isa/helpers.idl"


def test_captured_sources_are_immutable_and_do_not_alias_input_maps() -> None:
    texts = {("source", "ext/X.yaml"): "name: X\n"}
    idl = {"isa/globals.isa": SourceText("isa/globals.isa", "%version: 1.0\n")}
    resolved = ResolvedDatabase({}, source_texts=texts, idl_sources=idl)
    texts[("source", "ext/X.yaml")] = "changed\n"
    idl.clear()
    assert resolved.source_text("ext/X.yaml") == "name: X\n"
    assert resolved.idl_sources["isa/globals.isa"].text == "%version: 1.0\n"
    with pytest.raises(TypeError):
        resolved.idl_sources["new.idl"] = SourceText("new.idl", "")


def test_missing_original_yaml_source_is_explicit() -> None:
    resolved = ResolvedDatabase({})
    assert not resolved.idl_sources
    with pytest.raises(DataError, match=r"No captured YAML source source:missing\.yaml"):
        resolved.source_text("missing.yaml")


def test_explicit_idl_source_path_must_match_its_origin() -> None:
    with pytest.raises(DataError, match="paths matching"):
        ResolvedDatabase({}, idl_sources={"wrong.idl": SourceText("actual.idl", "")})


@pytest.mark.parametrize(
    "texts",
    [
        {"wrong": "text"},
        {("source", ""): "text"},
        {("source", "x.yaml"): 7},
        {("source", "x.yaml", "extra"): "text"},
    ],
)
def test_invalid_explicit_source_texts_are_rejected(texts) -> None:
    with pytest.raises(DataError, match="Source texts require"):
        ResolvedDatabase({}, source_texts=texts)


def test_invalid_idl_encoding_reports_the_source(tmp_path: Path) -> None:
    root = tmp_path / "custom"
    _write(root, "isa/globals.isa", "")
    (root / "isa/globals.isa").write_bytes(b"\xff")
    with pytest.raises(DataError, match=r"Cannot read UDB IDL source isa/globals\.isa"):
        Database.from_path(root).resolve()


def _cross_root_database(tmp_path: Path, *, base_include: str = "helpers.idl"):
    base = tmp_path / "spec/std/isa"
    overlay = tmp_path / "spec/custom/isa/qc_iu"
    _write(
        base,
        "isa/globals.isa",
        f'%version: 1.0\ninclude "{base_include}"\nU32 INSTR_ENC_SIZE = 32;\n',
    )
    _write(base, "isa/helpers.idl", "%version: 1.0\nU32 BASE = 17;\n")
    _write(
        overlay,
        "isa/globals.isa",
        '%version: 1.0\ninclude "../../../../std/isa/isa/globals.isa"\nU32 CUSTOM = 19;\n',
    )
    _write(overlay, "isa/helpers.idl", "%version: 1.0\nU32 BASE = 99;\n")
    return Database.from_path(base).resolve(overlays=(overlay,))


def test_cross_root_include_retains_base_identity_and_nested_source_origin(tmp_path: Path) -> None:
    resolved = _cross_root_database(tmp_path)
    overlay = resolved.idl_sources["isa/globals.isa"]
    original = resolved.resolve_idl_include(overlay, "../../../../std/isa/isa/globals.isa")
    assert original is resolved.idl_source_layers[("source", "isa/globals.isa")]
    assert original is not overlay
    helper = resolved.resolve_idl_include(original, "helpers.idl")
    assert helper.text.endswith("U32 BASE = 17;\n")
    assert helper.layer == "source"
    assert resolved.idl_sources["isa/helpers.idl"].layer == "overlay[0]"

    ast = global_ast(resolved)
    assert ast is not None
    assert [(item.var_decl_with_init.lhs.name, item.source.label) for item in ast.globals] == [
        ("BASE", "isa/helpers.idl"),
        ("INSTR_ENC_SIZE", "isa/globals.isa"),
        ("CUSTOM", "overlay[0]:isa/globals.isa"),
    ]
    assert condition_symbol_table(resolved).get("INSTR_ENC_SIZE").value == 32


def test_cross_root_source_capture_survives_deleted_trees_without_reopening(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved = _cross_root_database(tmp_path)
    rmtree(tmp_path / "spec")

    def forbidden_open(*args, **kwargs):
        raise AssertionError("Captured source loading must not reopen source paths")

    with monkeypatch.context() as guarded:
        guarded.setattr(Path, "open", forbidden_open)
        ast = global_ast(resolved)
        table = condition_symbol_table(resolved)
    assert ast is not None and len(ast.globals) == 3
    assert table.get("INSTR_ENC_SIZE").value == 32


def test_cross_root_cycle_is_reported_with_distinct_layer_identities(tmp_path: Path) -> None:
    resolved = _cross_root_database(
        tmp_path, base_include="../../../custom/isa/qc_iu/isa/globals.isa"
    )
    with pytest.raises(
        DataError,
        match=r"Cyclic IDL include: overlay\[0\]:isa/globals.isa -> isa/globals.isa -> overlay",
    ):
        global_ast(resolved)


def test_cross_root_include_never_reads_an_uncaptured_existing_file(tmp_path: Path) -> None:
    resolved = _cross_root_database(tmp_path)
    outside = tmp_path / "spec/uncaptured/secret.idl"
    outside.parent.mkdir(parents=True)
    outside.write_text("U32 SECRET = 99;\n", encoding="utf-8")
    owner = resolved.idl_sources["isa/globals.isa"]
    with pytest.raises(DataError, match="escapes"):
        resolved.resolve_idl_include(owner, "../../../../uncaptured/secret.idl")


def test_layered_snapshot_and_root_maps_are_independent_and_immutable() -> None:
    original = SourceText("isa/globals.isa", "%version: 1.0\nU32 BASE = 1;\n")
    overlay = SourceText(
        "isa/globals.isa",
        '%version: 1.0\ninclude "../../base/isa/globals.isa"\n',
        "overlay[0]",
    )
    layers = {("source", original.source): original}
    roots = {"source": "/captured/base", "overlay[0]": "/captured/custom"}
    resolved = ResolvedDatabase(
        {},
        idl_sources={overlay.source: overlay},
        idl_source_layers=layers,
        idl_source_roots=roots,
    )
    layers.clear()
    roots.clear()
    assert resolved.resolve_idl_include(overlay, "../../base/isa/globals.isa") is original
    with pytest.raises(TypeError):
        resolved.idl_source_layers[("source", "new.idl")] = original
    with pytest.raises(TypeError):
        resolved.idl_source_roots["source"] = "/changed"


@pytest.mark.parametrize(
    "layers",
    [
        {"wrong": SourceText("x.idl", "")},
        {("wrong", "x.idl"): SourceText("x.idl", "")},
        {("source", "wrong.idl"): SourceText("x.idl", "")},
    ],
)
def test_invalid_explicit_layered_sources_are_rejected(layers) -> None:
    with pytest.raises(DataError, match="Layered IDL sources require"):
        ResolvedDatabase({}, idl_source_layers=layers)


def test_conflicting_effective_and_layered_source_is_rejected() -> None:
    with pytest.raises(DataError, match="Conflicting captured IDL source"):
        ResolvedDatabase(
            {},
            idl_sources={"x.idl": SourceText("x.idl", "original")},
            idl_source_layers={("source", "x.idl"): SourceText("x.idl", "changed")},
        )


@pytest.mark.parametrize("roots", [{"source": "relative"}, {"": "/absolute"}, {"source": 7}])
def test_invalid_explicit_source_roots_are_rejected(roots) -> None:
    with pytest.raises(DataError, match="absolute POSIX paths"):
        ResolvedDatabase({}, idl_source_roots=roots)


def test_rootless_sources_cannot_escape_or_use_an_uncaptured_owner() -> None:
    owner = SourceText("isa/globals.isa", "%version: 1.0\n")
    resolved = ResolvedDatabase({}, idl_sources={owner.source: owner})
    with pytest.raises(DataError, match="escapes"):
        resolved.resolve_idl_include(owner, "../../outside.idl")
    with pytest.raises(DataError, match="owner must be a captured"):
        resolved.resolve_idl_include(SourceText(owner.source, "different"), "helpers.idl")


def test_same_physical_include_in_multiple_captured_layers_is_explicitly_ambiguous() -> None:
    owner = SourceText("isa/globals.isa", "", "custom")
    first = SourceText("isa/globals.isa", "", "base-first")
    second = SourceText("isa/globals.isa", "", "base-second")
    resolved = ResolvedDatabase(
        {},
        idl_sources={owner.source: owner},
        idl_source_layers={
            ("base-first", first.source): first,
            ("base-second", second.source): second,
        },
        idl_source_roots={
            "custom": "/captured/custom",
            "base-first": "/captured/base",
            "base-second": "/captured/base",
        },
    )
    with pytest.raises(DataError, match="Ambiguous captured IDL include"):
        resolved.resolve_idl_include(owner, "../../base/isa/globals.isa")


def test_genuine_qc_iu_globals_keep_standard_includes_and_encoding_constant() -> None:
    root = Path(__file__).resolve().parents[2]
    resolved = Database.from_path(root / "spec/std/isa").resolve(
        overlays=(root / "spec/custom/isa/qc_iu",)
    )
    ast = global_ast(resolved)
    assert ast is not None
    functions = {function.name: function for function in ast.functions}
    assert functions["delay"].source.label == "overlay[0]:isa/globals.isa"
    assert functions["implemented?"].source.label == "isa/builtin_functions.idl"
    assert condition_symbol_table(resolved).get("INSTR_ENC_SIZE").value == 32
