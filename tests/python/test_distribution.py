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
    assert "udb/_data/isa/csr/Zihpm/mhpmcounter3.yaml" in destinations
    assert "udb/_data/isa/isa/globals.isa" in destinations
    assert "udb/_data/isa/prose/interrupts.adoc" in destinations
    assert "udb/_data/schemas/inst_schema.json" in destinations
    assert not any(destination.endswith((".erb", ".layout")) for destination in destinations)


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
        assert not any(name.endswith((".erb", ".layout")) for name in names)
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
    assert not any(name.endswith((".erb", ".layout")) for name in direct_data)
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
import udb

assert '.whl/udb/' in udb.__file__
assert (files('udb') / '_data' / 'isa' / 'ext' / 'Zvkg.yaml').is_file()
assert (files('udb') / '_data' / 'schemas' / 'inst_schema.json').is_file()
assert udb.Database.bundled().extension('Zvkg').name == 'Zvkg'
resolved = udb.Database.bundled().resolve()
assert resolved.profile('RVI20U64')['extensions']['I']['presence'] == 'mandatory'
assert '$inherits' not in resolved.profile('RVI20U64')
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(rebuilt_wheel)
    subprocess.run(
        [sys.executable, "-c", check_script],
        cwd=tmp_path,
        env=environment,
        check=True,
    )
