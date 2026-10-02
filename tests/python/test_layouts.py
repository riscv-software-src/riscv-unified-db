# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path, PurePosixPath

import pytest

from udb import cli, layouts
from udb.errors import LayoutError
from udb.layout_collections import LayoutCollection
from udb.layouts import (
    LayoutJob,
    generate_layouts,
    iter_layout_jobs,
    layout_plan,
    layout_sources,
    render_job,
    render_layout,
)

REPOSITORY_ROOT = Path(__file__).parents[2]


def test_all_layouts_reproduce_every_tracked_output_byte_for_byte() -> None:
    jobs = iter_layout_jobs(REPOSITORY_ROOT)
    plan = layout_plan(REPOSITORY_ROOT)

    assert len(jobs) == 532
    assert len(plan.outputs) == 532
    assert len(plan.owned_paths) == 532
    assert len(set(plan.owned_paths)) == 532
    assert len(layout_sources(REPOSITORY_ROOT)) == 31
    assert generate_layouts(REPOSITORY_ROOT, check=True) == ()
    for output in plan.outputs:
        assert output.content == (REPOSITORY_ROOT / output.path).read_bytes()
        assert output.dependencies == (
            PurePosixPath(output.owner.removeprefix("layout:")),
            PurePosixPath("src/udb/layouts.py"),
        )


def test_editable_install_can_generate_from_bundled_layout_resources(tmp_path: Path) -> None:
    assert len(generate_layouts(tmp_path)) == 532
    assert len(tuple(tmp_path.rglob("*.yaml"))) == 532
    assert generate_layouts(tmp_path, check=True) == ()


def test_native_renderer_supports_only_bounded_data_constructs(tmp_path: Path) -> None:
    layout = tmp_path / "example.layout"
    layout.write_text(
        'literal {{ "{% if extensions.H %}" }}runtime configured prose'
        '{{ "{% endif %}" }}\n'
        "{% for number in numbers %}"
        "{% if enabled and number >= 2 %}{{ item.name }}={{ number * 2 }}\n{% endif %}"
        "{% endfor %}",
        encoding="utf-8",
    )

    assert render_layout(
        layout,
        {"numbers": (1, 2, 3), "enabled": True, "item": {"name": "value"}},
    ) == ("literal {% if extensions.H %}runtime configured prose{% endif %}\nvalue=4\nvalue=6\n")


@pytest.mark.parametrize(
    "template,match",
    [
        ('{{ __import__("os") }}', "unsupported layout expression"),
        ("{{ values[0] }}", "unsupported layout expression"),
        ("{% if value is True %}bad{% endif %}", "unsupported layout comparison"),
        ("{% arbitrary code %}", "unsupported layout directive"),
        ("{{ missing", "delimiter"),
        ("{# comment #}", "delimiter"),
    ],
)
def test_renderer_rejects_executable_or_unknown_constructs(
    tmp_path: Path, template: str, match: str
) -> None:
    layout = tmp_path / "unsafe.layout"
    layout.write_text(template, encoding="utf-8")
    with pytest.raises(LayoutError, match=match):
        render_layout(layout, {"values": (1,), "value": True})


def test_renderer_rejects_unbounded_or_non_scalar_loops(tmp_path: Path) -> None:
    layout = tmp_path / "loop.layout"
    layout.write_text("{% for item in items %}{{ item }}{% endfor %}", encoding="utf-8")

    with pytest.raises(LayoutError, match="bounded sequence"):
        render_layout(layout, {"items": {"key": "value"}})
    with pytest.raises(LayoutError, match="exceeds 1024"):
        render_layout(layout, {"items": tuple(range(1025))})
    with pytest.raises(LayoutError, match="loop items must be scalar"):
        render_layout(layout, {"items": ({"key": "value"},)})


def test_renderer_preserves_literal_idl_closing_braces(tmp_path: Path) -> None:
    layout = tmp_path / "idl.layout"
    layout.write_text("value = {WIDTH-1{1'b1}};\n", encoding="utf-8")

    assert render_layout(layout, {}) == "value = {WIDTH-1{1'b1}};\n"


@pytest.mark.parametrize(
    ("template", "values", "expected"),
    [
        ('{{ "}}" }}', {}, "}}"),
        ('{% if value == "%}" %}yes{% endif %}', {"value": "%}"}, "yes"),
    ],
)
def test_renderer_ignores_closing_delimiters_inside_quoted_strings(
    tmp_path: Path, template: str, values: dict[str, object], expected: str
) -> None:
    layout = tmp_path / "quoted.layout"
    layout.write_text(template, encoding="utf-8")

    assert render_layout(layout, values) == expected


def test_renderer_limits_expression_size(tmp_path: Path) -> None:
    layout = tmp_path / "expression.layout"
    layout.write_text("{{ " + "1 + " * 5000 + "1 }}", encoding="utf-8")
    with pytest.raises(LayoutError, match="expression exceeds"):
        render_layout(layout, {})

    layout.write_text("{{ " + " + ".join("1" for _ in range(200)) + " }}", encoding="utf-8")
    with pytest.raises(LayoutError, match="AST nodes"):
        render_layout(layout, {})


def test_packaged_layout_reports_invalid_utf8(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_root = tmp_path / "package"
    resource = package_root / "layouts/test/bad.layout"
    resource.parent.mkdir(parents=True)
    resource.write_bytes(b"\xff")
    monkeypatch.setattr(layouts, "package_data_root", lambda: package_root)
    job = LayoutJob(
        PurePosixPath("spec/std/isa/test/bad.layout"),
        PurePosixPath("spec/std/isa/test/bad.yaml"),
        {},
    )

    with pytest.raises(
        LayoutError,
        match=r"spec/std/isa/test/bad\.layout: layout source is not valid UTF-8",
    ):
        render_job(job, tmp_path, repository_sources=False)


def test_renderer_limits_nested_work_and_control_depth(tmp_path: Path) -> None:
    layout = tmp_path / "expensive.layout"
    layout.write_text(
        "{% for first in items %}{% for second in items %}x{% endfor %}{% endfor %}",
        encoding="utf-8",
    )
    with pytest.raises(LayoutError, match="rendering exceeds"):
        render_layout(layout, {"items": tuple(range(400))})

    layout.write_text(
        "".join("{% if enabled %}" for _ in range(65))
        + "x"
        + "".join("{% endif %}" for _ in range(65)),
        encoding="utf-8",
    )
    with pytest.raises(LayoutError, match="nesting exceeds"):
        render_layout(layout, {"enabled": True})


def test_layout_recipe_rejects_out_of_domain_values() -> None:
    source = REPOSITORY_ROOT / "spec/std/isa/inst/Zalrsc/lr.SIZE.AQRL.layout"
    with pytest.raises(LayoutError, match="size 'q' is not valid"):
        render_layout(source, {"size": "q", "aq": False, "rl": False})
    with pytest.raises(LayoutError, match="must be booleans"):
        render_layout(source, {"size": "w", "aq": 1, "rl": False})


def test_layout_plan_rejects_a_partial_repository_source_set(tmp_path: Path) -> None:
    source = tmp_path / "spec/std/isa/csr/Zihpm/hpmcounterN.layout"
    source.parent.mkdir(parents=True)
    source.write_text("name: hpmcounter{{ hpm_num }}\n", encoding="utf-8")

    with pytest.raises(LayoutError, match="repository layout source does not exist"):
        layout_plan(tmp_path)


def test_cli_check_reports_drift_without_rewriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    drift = (PurePosixPath("spec/std/isa/out.yaml"),)
    calls: list[tuple[Path, bool]] = []

    def fake_generate(
        root: Path,
        *,
        check: bool = False,
        collections: Sequence[LayoutCollection] | None = None,
        source_root: Path | None = None,
        progress=None,
    ) -> tuple[PurePosixPath, ...]:
        assert collections is not None
        assert tuple(collection.name for collection in collections) == ("standard",)
        assert source_root is None
        assert progress is None
        calls.append((root, check))
        return drift

    monkeypatch.setattr("udb.layouts.generate_layouts", fake_generate)
    assert cli.main(["author", "layouts", "--root", str(tmp_path), "--check"]) == 1
    assert calls == [(tmp_path, True)]
    assert capsys.readouterr().out == "spec/std/isa/out.yaml\n"
