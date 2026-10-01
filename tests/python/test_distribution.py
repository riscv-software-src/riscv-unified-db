# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import hashlib
import importlib.util
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from udb import Database, get_layout_collection

REPOSITORY_ROOT = Path(__file__).parents[2]
BUILD_HOOK_SPEC = importlib.util.spec_from_file_location(
    "hatch_build", REPOSITORY_ROOT / "hatch_build.py"
)
assert BUILD_HOOK_SPEC is not None and BUILD_HOOK_SPEC.loader is not None
BUILD_HOOK = importlib.util.module_from_spec(BUILD_HOOK_SPEC)
BUILD_HOOK_SPEC.loader.exec_module(BUILD_HOOK)
package_data = BUILD_HOOK.package_data


def test_editable_install_finds_bundled_data() -> None:
    assert Database.bundled().extension("Zvkg").name == "Zvkg"


def test_package_data_contains_raw_sources_and_schemas() -> None:
    mappings = package_data(REPOSITORY_ROOT)
    destinations = {destination.as_posix() for destination in mappings.values()}

    assert "udb/_data/isa/inst/Zaamo/amoadd.w.yaml" in destinations
    assert "udb/_data/isa/inst/Zalrsc/lr.w.yaml" in destinations
    assert "udb/_data/isa/csr/Zihpm/mhpmcounter3.yaml" in destinations
    assert "udb/_data/isa/csr/stvec.yaml" in destinations
    assert "udb/_data/isa/exception_code/IllegalInstruction.yaml" in destinations
    assert "udb/_data/isa/isa/globals.isa" in destinations
    assert "udb/_data/isa/prose/interrupts.adoc" in destinations
    assert "udb/_data/schemas/inst_schema.json" in destinations
    assert "udb/_data/layouts/inst/Zaamo/amoadd.SIZE.AQRL.layout" in destinations
    assert "udb/extension_docs/assets/manifest.json" in destinations
    assert "udb/extension_docs/assets/fonts/JetBrainsMono-Regular.ttf" in destinations
    assert "udb/extension_docs/assets/images/wavedrom/float-csr.adoc" in destinations
    assert "udb/extension_docs/templates/header.adoc" in destinations
    assert "udb/_data/cpp_hart/backends/cpp_hart_gen/CMakeLists.txt" in destinations
    assert "udb/_data/cpp_hart/backends/cpp_hart_gen/cpp/include/udb/bits.hpp" in destinations
    assert (
        "udb/_data/cpp_hart/backends/cpp_hart_gen/cpp/test/test_bits_properties_small.cpp"
        in destinations
    )
    assert "udb/_data/cpp_hart/backends/cpp_hart_gen/cpp/test/bits-tests.cmake" in destinations
    assert "udb/_data/cpp_hart/backends/cpp_hart_gen/cpp/test/bits_property.hpp" in destinations
    assert not any(destination.endswith(".erb") for destination in destinations)


def _wheel_data(wheel: Path) -> dict[str, str]:
    with zipfile.ZipFile(wheel) as archive:
        for source in (
            "src/udb/cpp_hart/NOTICE",
            "src/udb/schema_docs/NOTICE",
            "src/udb/extension_docs/assets/NOTICE.txt",
            "src/udb/extension_docs/assets/fonts/OFL-M.txt",
            "src/udb/extension_docs/assets/fonts/OFL-P.txt",
            "src/udb/extension_docs/assets/fonts/LICENSE-mplus.txt",
            "LICENSES/BSD-2-Clause.txt",
            "LICENSES/OFL-1.1.txt",
            "LICENSES/mplus.txt",
            "LICENSE-MIT.txt",
        ):
            packaged = next(
                (
                    name
                    for name in archive.namelist()
                    if name.endswith(f".dist-info/licenses/{source}")
                ),
                None,
            )
            assert packaged is not None, f"{wheel.name}: missing license {source}"
            assert archive.read(packaged) == (REPOSITORY_ROOT / source).read_bytes()
        metadata = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        assert (
            b"License-Expression: BSD-3-Clause-Clear AND CC-BY-4.0 AND BSD-2-Clause AND MIT AND OFL-1.1 AND mplus\n"
            in archive.read(metadata)
        )
        assert any(name.endswith("udb/query_reports/matching.py") for name in archive.namelist())
        return {
            name: hashlib.sha256(archive.read(name)).hexdigest()
            for name in archive.namelist()
            if name.startswith(
                ("udb/_data/", "udb/extension_docs/assets/", "udb/extension_docs/templates/")
            )
        }


def test_wheel_rebuilt_from_sdist_is_standalone(tmp_path: Path) -> None:
    direct_dist = tmp_path / "direct"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--sdist",
            "--wheel",
            "--outdir",
            str(direct_dist),
            str(REPOSITORY_ROOT),
        ],
        check=True,
    )

    sdist = next(direct_dist.glob("*.tar.gz"))
    extracted = tmp_path / "extracted"
    with tarfile.open(sdist) as archive:
        names = archive.getnames()
        assert any(name.endswith("/doc/stage5-configured-prose.md") for name in names)
        for source in (
            "src/udb/cpp_hart/NOTICE",
            "src/udb/schema_docs/NOTICE",
            "src/udb/extension_docs/assets/NOTICE.txt",
            "src/udb/extension_docs/assets/fonts/OFL-M.txt",
            "src/udb/extension_docs/assets/fonts/OFL-P.txt",
            "src/udb/extension_docs/assets/fonts/LICENSE-mplus.txt",
            "LICENSES/BSD-2-Clause.txt",
            "LICENSES/OFL-1.1.txt",
            "LICENSES/mplus.txt",
            "LICENSE-MIT.txt",
        ):
            assert any(name.endswith(f"/{source}") for name in names), source
        assert any(name.endswith("amoadd.SIZE.AQRL.layout") for name in names)
        assert any(
            name.endswith("/tests/python/query_reports_installed_acceptance.py") for name in names
        )
        assert any(
            name.endswith("/tests/python/fixtures/query_reports/manifest.json") for name in names
        )
        assert any(name.endswith("backends/cpp_hart_gen/CMakeLists.txt") for name in names)
        assert any(
            name.endswith("tests/data/fp/directed/f32_fpgen_expanded.jsonl") for name in names
        )
        assert not any(name.endswith(".erb") for name in names)
        qc_sources = {
            name.split("/spec/custom/isa/qc_iu/", 1)[1]
            for name in names
            if "/spec/custom/isa/qc_iu/" in name
        }
        qc = get_layout_collection("qc_iu")
        assert qc_sources == {job.source.as_posix() for job in qc.jobs} | {
            job.target.as_posix() for job in qc.jobs
        }
        archive.extractall(extracted, filter="data")

    sdist_root = next(extracted.iterdir())
    rebuilt_dist = tmp_path / "rebuilt"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--wheel",
            "--outdir",
            str(rebuilt_dist),
            str(sdist_root),
        ],
        check=True,
    )

    direct_wheel = next(direct_dist.glob("*.whl"))
    rebuilt_wheel = next(rebuilt_dist.glob("*.whl"))
    direct_data = _wheel_data(direct_wheel)
    assert direct_data == _wheel_data(rebuilt_wheel)
    assert len(direct_data) == len(package_data(REPOSITORY_ROOT))
    assert any(name.endswith("amoadd.SIZE.AQRL.layout") for name in direct_data)
    assert not any(name.endswith(".erb") for name in direct_data)
    isa_root = REPOSITORY_ROOT / "spec" / "std" / "isa"
    expected_yaml = {
        f"udb/_data/isa/{path.relative_to(isa_root).as_posix()}": hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in isa_root.rglob("*.yaml")
    }
    assert {
        name: digest
        for name, digest in direct_data.items()
        if name.startswith("udb/_data/isa/") and name.endswith(".yaml")
    } == expected_yaml

    check_script = """
from importlib.resources import files
from pathlib import Path
import udb

assert '.whl/udb/' in udb.__file__
assert (files('udb') / '_data' / 'isa' / 'ext' / 'Zvkg.yaml').is_file()
assert (files('udb') / '_data' / 'schemas' / 'inst_schema.json').is_file()
assert (files('udb') / '_data' / 'layouts' / 'inst' / 'Zaamo' / 'amoadd.SIZE.AQRL.layout').is_file()
assert (files('udb') / 'extension_docs' / 'assets' / 'fonts' / 'JetBrainsMono-Regular.ttf').is_file()
assert (files('udb') / 'extension_docs' / 'templates' / 'header.adoc').is_file()
assert (files('udb') / '_data' / 'cpp_hart' / 'backends' / 'cpp_hart_gen' / 'CMakeLists.txt').is_file()
assert (files('udb') / '_data' / 'cpp_hart' / 'backends' / 'cpp_hart_gen' / 'cpp' / 'include' / 'udb' / 'bits.hpp').is_file()
assert udb.Database.bundled().extension('Zvkg').name == 'Zvkg'
resolved = udb.Database.bundled().resolve(validate=True)
assert resolved.profile('RVI20U64')['extensions']['I']['presence'] == 'mandatory'
assert '$inherits' not in resolved.profile('RVI20U64')
sm = udb.Database.bundled().extension('Sm')
assert [version.canonical for version in sm.versions] == ['1.11.0', '1.12.0', '1.13.0']
assert udb.VersionRequirement.parse('>= 1.11').matches(sm.version('1.12').version)
series = udb.ExtensionVersionSet.from_metadata('X', [
    {'version': '1.0'}, {'version': '2.0', 'breaking': True}, {'version': '3.0'}
])
assert [version.canonical for version in series.compatible_versions('2.0')] == ['2.0.0', '3.0.0']
authoring_root = Path('authoring')
assert len(udb.generate_layouts(authoring_root)) == 532
generated = authoring_root / 'spec/std/isa/inst/Zaamo/amoadd.w.yaml'
bundled = files('udb') / '_data/isa/inst/Zaamo/amoadd.w.yaml'
assert generated.read_bytes() == bundled.read_bytes()
assert udb.generate_layouts(authoring_root, check=True) == ()
from udb.prose import CapturedProse, ProseInputs, render_legacy, resolve_all_exception_records
inputs = ProseInputs.from_database(resolved, udb.Configuration.builtin('rv64'))
stvec = CapturedProse.from_record(resolved, resolved.csr('stvec'), 'fields', 'BASE', 'description')
assert '[SXLEN-1:39]' in render_legacy(stvec, inputs)
lr_w = CapturedProse.from_record(resolved, resolved.instruction('lr.w'), 'description')
assert 'sign-extended to 64-bits' in render_legacy(lr_w, inputs)
names = resolve_all_exception_records(resolved, inputs)
assert names and all(isinstance(item['ext'], str) for item in names)
qc = udb.get_layout_collection('qc_iu')
assert len(udb.generate_layouts(authoring_root, collections=(qc,))) == 56
assert udb.generate_layouts(authoring_root, collections=(qc,), check=True) == ()
for job in qc.jobs:
    generated = authoring_root / qc.output_root / job.target
    bundled = files('udb').joinpath('_data', 'custom_isa', 'qc_iu', *job.target.parts)
    assert generated.read_bytes() == bundled.read_bytes()
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(rebuilt_wheel)
    subprocess.run(
        [sys.executable, "-c", check_script],
        cwd=tmp_path,
        env=environment,
        check=True,
    )
