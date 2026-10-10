# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from udb import Configuration, Database, ResolvedDatabase, parse_version_requirements
from udb.profile_configs import profile_configuration, profile_configuration_plan

ROOT = Path(__file__).parents[2]
ORACLE = Path(__file__).with_name("data") / "profile-configs.json"
PROFILES = tuple(sorted(path.stem for path in (ROOT / "cfgs/profile").glob("*.yaml")))


def canonical_configuration(data):
    data = json.loads(json.dumps(data))
    for key in ("mandatory_extensions", "non_mandatory_extensions"):
        for selection in data[key]:
            original = selection["version"]
            normalized = [str(requirement) for requirement in parse_version_requirements(original)]
            selection["version"] = normalized if isinstance(original, list) else normalized[0]
    return data


@pytest.fixture(scope="module")
def database():
    return Database.bundled().resolve()


def test_oracle_covers_every_bundled_and_tracked_profile(database):
    expected = json.loads(ORACLE.read_text(encoding="utf-8"))
    assert set(expected) == {profile.name for profile in database.profiles} == set(PROFILES)
    assert len(expected) == 10


@pytest.mark.parametrize("name", PROFILES)
def test_bundled_profile_configuration_matches_native_oracle(database, name):
    expected = json.loads(ORACLE.read_text(encoding="utf-8"))[name]
    before = database.profile(name).to_dict()
    for mode in ("declared", "strict"):
        actual = profile_configuration(database, name, strict=mode == "strict")
        assert canonical_configuration(actual.to_dict()) == canonical_configuration(expected[mode])
    tracked = Configuration.from_file(ROOT / "cfgs/profile" / f"{name}.yaml")
    assert canonical_configuration(tracked.to_dict()) == canonical_configuration(expected["strict"])
    assert database.profile(name).to_dict() == before


def synthetic(*, extensions=None, requirements=None, profiles=None):
    records = {
        "ext/A.yaml": {
            "kind": "extension",
            "name": "A",
            "versions": [{"version": "1.0", "state": "ratified"}],
            "requirements": {"extension": {"name": "B", "version": ">= 2"}},
        },
        "ext/B.yaml": {
            "kind": "extension",
            "name": "B",
            "versions": [
                {"version": "1.0", "state": "ratified"},
                {"version": "2.0", "state": "ratified", "breaking": True},
                {"version": "3.0", "state": "ratified"},
            ],
        },
        "profile/P.yaml": {
            "kind": "profile",
            "name": "P",
            "base": 32,
            "extensions": {"A": {"presence": "mandatory", "version": ">= 1"}},
        },
    }
    if extensions is not None:
        records["profile/P.yaml"]["extensions"] = extensions
    if requirements is not None:
        records["profile/P.yaml"]["requirements"] = requirements
    if profiles:
        records.update(profiles)
    return ResolvedDatabase(records)


def test_strict_expansion_anchors_at_lowest_satisfiable_version():
    database = synthetic()
    declared = profile_configuration(database, "P", strict=False).to_dict()
    strict = profile_configuration(database, "P").to_dict()
    assert declared["mandatory_extensions"] == [{"name": "A", "version": ">= 1.0.0"}]
    assert strict["mandatory_extensions"] == [
        {"name": "A", "version": ">= 1.0.0"},
        {"name": "B", "version": "~> 2.0.0"},
    ]
    assert strict["params"] == {}
    assert strict["additional_extensions"] is True
    assert strict["description"] == ""


@pytest.mark.parametrize("subcategory", ["expansion", "localized", "development", "transitory"])
def test_optional_subcategories_and_independently_mandatory_extension(subcategory):
    database = synthetic(
        extensions={
            "A": {"presence": "mandatory", "version": ">= 1"},
            "B": {"presence": {"optional": subcategory}, "version": [">= 1", "<= 3"]},
        }
    )
    data = profile_configuration(database, "P").to_dict()
    assert data["mandatory_extensions"][-1] == {"name": "B", "version": "~> 2.0.0"}
    assert data["non_mandatory_extensions"] == [{"name": "B", "version": [">= 1.0.0", "<= 3.0.0"]}]


def test_invalid_profile_configuration_is_not_emitted():
    from udb.errors import DataError

    with pytest.raises(DataError, match="profile configuration is unsat"):
        profile_configuration(synthetic(requirements={"not": {"extension": {"name": "B"}}}), "P")


@pytest.mark.parametrize("presence", [None, "prohibited", {"optional": "other"}])
def test_invalid_presence_is_explicit(presence):
    from udb.errors import DataError

    with pytest.raises(DataError, match="unsupported profile presence"):
        profile_configuration(synthetic(extensions={"A": {"presence": presence}}), "P")


def test_plan_is_deterministic_read_only_and_nonmutating_in_check_mode(tmp_path):
    database = synthetic()
    plan = profile_configuration_plan(database)
    assert tuple(str(path) for path in plan.owned_paths) == ("P.yaml",)
    assert plan.apply(tmp_path, check=True) == plan.owned_paths
    assert not list(tmp_path.iterdir())
    assert plan.apply(tmp_path) == plan.owned_paths
    generated = tmp_path / "P.yaml"
    first = generated.read_bytes()
    assert generated.stat().st_mode & 0o222 == 0
    assert (
        Configuration.from_file(generated).to_dict()
        == profile_configuration(database, "P").to_dict()
    )
    assert profile_configuration_plan(database).apply(tmp_path, check=True) == ()
    assert generated.read_bytes() == first


def test_minimum_compatible_versions_must_be_jointly_consistent():
    from udb.errors import DataError

    original = synthetic()
    documents = {name: dict(value) for name, value in original.documents.items()}
    documents["ext/A.yaml"] = {
        "kind": "extension",
        "name": "A",
        "versions": [
            {"version": "1.0", "state": "ratified"},
            {"version": "2.0", "state": "ratified", "breaking": True},
        ],
    }
    documents["ext/B.yaml"] = {
        "kind": "extension",
        "name": "B",
        "versions": [
            {"version": "1.0", "state": "ratified"},
            {"version": "2.0", "state": "ratified", "breaking": True},
        ],
    }
    documents["profile/P.yaml"] = {
        "kind": "profile",
        "name": "P",
        "extensions": {},
        "requirements": {
            "anyOf": [
                {
                    "allOf": [
                        {"extension": {"name": "A", "version": "= 1"}},
                        {"extension": {"name": "B", "version": "= 2"}},
                    ]
                },
                {
                    "allOf": [
                        {"extension": {"name": "A", "version": "= 2"}},
                        {"extension": {"name": "B", "version": "= 1"}},
                    ]
                },
            ]
        },
    }
    database = ResolvedDatabase(documents)
    from udb import ArchitectureCheckStatus

    assert (
        database.configure(profile_configuration(database, "P", strict=False)).check().status
        is ArchitectureCheckStatus.VALID
    )
    with pytest.raises(DataError, match="profile configuration is unsat"):
        profile_configuration(database, "P")


def test_idl_requirements_survive_plan_write_and_reload(tmp_path):
    database = synthetic(requirements={"idl()": "-> implemented?(ExtensionName::B);\n"})
    plan = profile_configuration_plan(database)
    plan.apply(tmp_path)
    text = (tmp_path / "P.yaml").read_text(encoding="utf-8")
    assert "idl(): |" in text
    assert Configuration.from_file(tmp_path / "P.yaml").requirements == {
        "idl()": "-> implemented?(ExtensionName::B);\n"
    }
    from udb import ArchitectureCheckStatus

    assert (
        database.configure(Configuration.from_file(tmp_path / "P.yaml")).check().status
        is ArchitectureCheckStatus.VALID
    )


@pytest.mark.parametrize(
    "names",
    [
        ["P", "P"],
        ["P", "p"],
        ["../P"],
        ["P/Q"],
        ["P\\Q"],
        [None],
        ["P\x00"],
        ["P\n"],
        ["*"],
        ["P?"],
        ["P."],
        ["P "],
        ["NUL.yaml"],
    ],
)
def test_unsafe_or_duplicate_selection_is_explicit(names):
    from udb.errors import DataError

    with pytest.raises(DataError):
        profile_configuration_plan(synthetic(), names)


def test_plan_rejects_string_selection():
    with pytest.raises(TypeError, match="sequence of names"):
        profile_configuration_plan(synthetic(), "P")


def test_selected_generation_preserves_unselected_files(tmp_path):
    target = tmp_path / "other.yaml"
    target.write_text("user-owned\n", encoding="utf-8")
    profile_configuration_plan(synthetic(), ["P"]).apply(tmp_path)
    assert target.read_text(encoding="utf-8") == "user-owned\n"


@pytest.mark.parametrize("check", [False, True])
def test_plan_refuses_to_overwrite_source_profiles(cli_database, check):
    from udb.errors import AuthoringError

    root = cli_database / "profile"
    source = root / "P.yaml"
    before = source.read_bytes()
    database = Database.from_path(cli_database).resolve()
    with pytest.raises(AuthoringError, match="refusing to overwrite"):
        profile_configuration_plan(database).apply(root, check=check)
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    ("control", "error"),
    [
        ("\u0085", "does not round-trip through YAML"),
        ("\x01", "cannot parse configuration: unacceptable character"),
        ("\r\n", "does not round-trip through YAML"),
    ],
)
def test_plan_rejects_lossy_idl_serialization_before_writing(control, error, tmp_path):
    from udb.errors import DataError

    database = synthetic(requirements={"idl()": f"# comment{control}\n-> true;\n"})
    profile_configuration(database, "P")
    with pytest.raises(DataError, match=error):
        profile_configuration_plan(database).apply(tmp_path)
    assert not list(tmp_path.iterdir())


def test_plan_preserves_lossless_unicode_in_valid_idl(tmp_path):
    database = synthetic(requirements={"idl()": "# comment\u2028\n-> true;\n"})
    expected = profile_configuration(database, "P")
    profile_configuration_plan(database).apply(tmp_path)
    assert Configuration.from_file(tmp_path / "P.yaml").to_dict() == expected.to_dict()


def test_unknown_presence_cannot_be_silently_omitted(monkeypatch):
    from udb import QueryPresence
    from udb.architecture import ConfiguredArchitecture
    from udb.errors import DataError

    monkeypatch.setattr(
        ConfiguredArchitecture,
        "extension_presence",
        lambda *args: QueryPresence.DEFERRED,
    )
    with pytest.raises(DataError, match="cannot decide presence of B"):
        profile_configuration(synthetic(), "P")


@pytest.fixture
def cli_database(tmp_path):
    from udb.serialization import dumps_yaml

    root = tmp_path / "source"
    for name, document in synthetic().documents.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps_yaml(document), encoding="utf-8")
    return root


def test_cli_writes_selected_profiles_and_checks_without_changes(cli_database, tmp_path, capsys):
    from udb.cli import main

    output = tmp_path / "output"
    args = [
        "--path",
        str(cli_database),
        "generate",
        "profile-configs",
        "-o",
        str(output),
        "--profile",
        "P",
    ]
    assert main([*args, "--check"]) == 1
    assert capsys.readouterr().out == "P.yaml\n"
    assert not output.exists()
    assert main(args) == 0
    before = (output / "P.yaml").read_bytes()
    assert main([*args, "--check"]) == 0
    assert capsys.readouterr().out == ""
    assert (output / "P.yaml").read_bytes() == before


def test_cli_reports_bad_selection_without_partial_output(cli_database, tmp_path, capsys):
    from udb.cli import main

    output = tmp_path / "output"
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--path",
                str(cli_database),
                "generate",
                "profile-configs",
                "-o",
                str(output),
                "--profile",
                "P",
                "--profile",
                "missing",
            ]
        )
    assert error.value.code == 2
    assert "missing" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.skipif(
    os.environ.get("UDB_TEST_RUBY") != "1",
    reason="set UDB_TEST_RUBY=1 to refresh the genuine profile configuration oracle",
)
def test_live_profile_configuration_oracle_is_unchanged():
    mise = shutil.which("mise")
    if mise is None:
        pytest.fail("UDB_TEST_RUBY=1 requires mise and the repository Ruby toolchain")
    result = subprocess.run(
        [
            mise,
            "exec",
            "--no-deps",
            "--",
            "bundle",
            "exec",
            "ruby",
            "-Itools/ruby-gems/udb/lib",
            str(Path(__file__).with_name("ruby_profile_config_oracle.rb")),
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == json.loads(ORACLE.read_text(encoding="utf-8"))
