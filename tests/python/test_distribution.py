# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import hashlib
import importlib.util
import os
import subprocess
import sys
import sysconfig
import tarfile
import zipfile
from pathlib import Path

from udb import Database

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
    assert not any(destination.endswith(".erb") for destination in destinations)


def _wheel_data(wheel: Path) -> dict[str, str]:
    with zipfile.ZipFile(wheel) as archive:
        return {
            name: hashlib.sha256(archive.read(name)).hexdigest()
            for name in archive.namelist()
            if name.startswith("udb/_data/")
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
        assert any(name.endswith("amoadd.SIZE.AQRL.layout") for name in names)
        assert not any(name.endswith(".erb") for name in names)
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
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(rebuilt_wheel)
    subprocess.run(
        [sys.executable, "-c", check_script],
        cwd=tmp_path,
        env=environment,
        check=True,
    )

    # Run the CI installed-package gate against the rebuilt wheel so drift in
    # that script fails locally instead of only in the package workflow.
    venv = tmp_path / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        check=True,
    )
    venv_python = venv / "bin" / "python"
    purelib = subprocess.run(
        [str(venv_python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--quiet",
            "--no-deps",
            "--no-index",
            "--no-cache-dir",
            str(rebuilt_wheel),
        ],
        check=True,
    )
    # Reuse this environment's runtime dependencies after the installed wheel.
    # A plain path entry does not process the editable-install .pth files there.
    (Path(purelib) / "udb_test_dependencies.pth").write_text(
        sysconfig.get_path("purelib") + "\n", encoding="utf-8"
    )
    gate_environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "UDB_ROOT", "VIRTUAL_ENV"}
    }
    gate_environment["PATH"] = str(venv / "bin")
    subprocess.run(
        [str(venv_python), "-I", str(REPOSITORY_ROOT / "tools/test/check_python_install.py")],
        cwd=tmp_path,
        env=gate_environment,
        check=True,
    )
