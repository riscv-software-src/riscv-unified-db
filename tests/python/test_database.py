# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from udb import (
    Csr,
    Database,
    DataError,
    Extension,
    Instruction,
    ObjectNotFoundError,
    Profile,
    UnknownKindError,
)
from udb.cli import main

REPO_ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def real_database() -> Database:
    return Database.from_path(REPO_ROOT / "spec" / "std" / "isa")


def write_record(root: Path, directory: str, name: str, body: str) -> Path:
    path = root / directory / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_real_database_lists_typed_records_in_name_order(real_database: Database) -> None:
    assert len(real_database.extensions) > 100
    assert all(isinstance(record, Extension) for record in real_database.extensions)
    assert [record.name for record in real_database.extensions] == sorted(
        record.name for record in real_database.extensions
    )
    assert isinstance(real_database.extension("Zvkg"), Extension)
    assert isinstance(real_database.instruction("add"), Instruction)
    assert isinstance(real_database.csr("mstatus"), Csr)
    assert isinstance(real_database.profile("RVA23U64"), Profile)


def test_real_database_loads_generated_records(real_database: Database) -> None:
    generated = real_database.csr("mhpmcounter3")
    assert generated.path == Path("csr/Zihpm/mhpmcounter3.yaml")
    assert generated["name"] == "mhpmcounter3"


def test_all_standard_yaml_records_are_accessible(real_database: Database) -> None:
    isa_root = REPO_ROOT / "spec" / "std" / "isa"
    expected_paths = {path.relative_to(isa_root).as_posix() for path in isa_root.rglob("*.yaml")}
    actual_paths = {record.path.as_posix() for record in real_database.objects()}

    assert actual_paths == expected_paths


def test_custom_database_preserves_yaml_12_scalars_and_is_immutable(tmp_path: Path) -> None:
    write_record(
        tmp_path,
        "ext",
        "Xdemo",
        """\
$schema: ext_schema.json#
kind: extension
name: Xdemo
enabled: true
absent: null
count: 0x10
legacy_boolean: yes
nested:
  values: [1, false]
""",
    )

    record = Database.from_path(tmp_path).extension("Xdemo")
    assert record["enabled"] is True
    assert record["absent"] is None
    assert record["count"] == 16
    assert record["legacy_boolean"] == "yes"
    assert record["nested"]["values"] == (1, False)

    with pytest.raises(TypeError):
        record.data["enabled"] = False  # type: ignore[index]
    with pytest.raises(TypeError):
        record["nested"]["values"][0] = 2  # type: ignore[index]


def test_public_record_constructor_defensively_freezes_data() -> None:
    source = {
        "kind": "extension",
        "name": "Xdirect",
        "nested": {"values": [1, 2]},
    }
    record = Extension(
        name="Xdirect",
        kind="extension",
        path=PurePosixPath("ext/Xdirect.yaml"),
        data=source,
    )

    source["nested"]["values"].append(3)
    assert record["nested"]["values"] == (1, 2)
    with pytest.raises(TypeError):
        record["nested"]["new"] = True


def test_public_record_constructor_enforces_identity_fields() -> None:
    with pytest.raises(DataError, match="does not match data name"):
        Extension(
            name="Xwrong",
            kind="extension",
            path=PurePosixPath("ext/Xwrong.yaml"),
            data={"kind": "extension", "name": "Xother"},
        )


def test_data_is_loaded_lazily(tmp_path: Path) -> None:
    bad_path = write_record(tmp_path, "csr", "bad", "kind: [not, valid\n")
    database = Database.from_path(tmp_path)

    assert database.objects("extension") == ()
    with pytest.raises(DataError, match="Cannot parse"):
        database.objects("csr")
    assert bad_path.exists()


def test_relative_source_path_survives_working_directory_change(
    tmp_path: Path, monkeypatch
) -> None:
    isa_root = tmp_path / "isa"
    write_record(isa_root, "ext", "Xrelative", "kind: extension\nname: Xrelative\n")
    monkeypatch.chdir(tmp_path)
    database = Database.from_path("isa")

    monkeypatch.chdir(tmp_path.parent)

    assert database.extension("Xrelative").name == "Xrelative"


@pytest.mark.parametrize(
    ("directory", "name", "body", "message"),
    [
        ("ext", "not_a_map", "- one\n- two\n", "must contain a mapping"),
        ("ext", "missing_name", "kind: extension\n", "has no non-empty string 'name'"),
        ("ext", "wrong_kind", "kind: csr\nname: wrong_kind\n", "expected 'extension'"),
        ("ext", "filename", "kind: extension\nname: Other\n", "must match its filename"),
    ],
)
def test_malformed_documents_are_descriptive(
    tmp_path: Path, directory: str, name: str, body: str, message: str
) -> None:
    write_record(tmp_path, directory, name, body)
    with pytest.raises(DataError, match=message):
        Database.from_path(tmp_path).objects("extension")


def test_duplicate_names_are_rejected(tmp_path: Path) -> None:
    write_record(tmp_path, "ext/a", "Same", "kind: extension\nname: Same\n")
    write_record(tmp_path, "ext/b", "Same", "kind: extension\nname: Same\n")

    with pytest.raises(DataError, match="Duplicate 'extension' name 'Same'"):
        _ = Database.from_path(tmp_path).extensions


def test_recursive_yaml_alias_is_rejected(tmp_path: Path) -> None:
    write_record(
        tmp_path,
        "ext",
        "Recursive",
        "kind: extension\nname: Recursive\nloop: &loop [*loop]\n",
    )

    with pytest.raises(DataError, match=r"ext/Recursive\.yaml.*Recursive YAML aliases"):
        _ = Database.from_path(tmp_path).extensions


def test_unsafe_python_yaml_tags_are_rejected_with_source_path(tmp_path: Path) -> None:
    write_record(
        tmp_path,
        "ext",
        "Unsafe",
        "kind: extension\nname: Unsafe\nvalue: !!python/object/apply:os.system ['false']\n",
    )

    with pytest.raises(DataError, match=r"ext/Unsafe\.yaml"):
        _ = Database.from_path(tmp_path).extensions


def test_unknown_kind_and_name_are_descriptive(real_database: Database) -> None:
    with pytest.raises(UnknownKindError, match="Unknown object kind"):
        real_database.objects("frobnicator")
    with pytest.raises(ObjectNotFoundError, match="No 'extension' object named 'NotReal'"):
        real_database.extension("NotReal")


def test_cli_lists_and_shows_bundled_records(monkeypatch, capsys) -> None:
    database = Database.from_path(REPO_ROOT / "spec" / "std" / "isa")
    monkeypatch.setattr(Database, "bundled", classmethod(lambda cls: database))

    assert main(["list", "extension"]) == 0
    assert "Zvkg" in capsys.readouterr().out.splitlines()

    assert main(["show", "extension", "Zvkg"]) == 0
    output = capsys.readouterr().out
    assert '"name": "Zvkg"' in output


def test_cli_reports_data_errors_without_a_traceback(tmp_path: Path, capsys) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--path", str(tmp_path / "missing"), "list", "extension"])

    assert error.value.code == 2
    stderr = capsys.readouterr().err
    assert stderr.startswith("udb: error:")
    assert "Traceback" not in stderr


def test_cli_reports_invalid_utf8_without_a_traceback(tmp_path: Path, capsys) -> None:
    invalid_path = tmp_path / "ext" / "Invalid.yaml"
    invalid_path.parent.mkdir(parents=True)
    invalid_path.write_bytes(b"kind: extension\nname: Invalid\nvalue: \xff\n")

    with pytest.raises(SystemExit) as error:
        main(["--path", str(tmp_path), "list", "extension"])

    assert error.value.code == 2
    stderr = capsys.readouterr().err
    assert "ext/Invalid.yaml" in stderr
    assert "Traceback" not in stderr
