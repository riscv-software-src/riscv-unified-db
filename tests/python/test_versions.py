# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from udb import (
    Database,
    DataError,
    ExtensionVersion,
    ExtensionVersionSet,
    ObjectNotFoundError,
    RequirementOperator,
    SchemaError,
    SchemaStore,
    Version,
    VersionRequirement,
    parse_version_requirements,
)

REPO_ROOT = Path(__file__).parents[2]

VALID_VERSIONS = {
    "0": ("0.0.0", "0", (0, 0, 0, False)),
    "1": ("1.0.0", "1", (1, 0, 0, False)),
    "01": ("1.0.0", "1", (1, 0, 0, False)),
    "1.2": ("1.2.0", "1p2", (1, 2, 0, False)),
    "01.002": ("1.2.0", "1p2", (1, 2, 0, False)),
    "1.2.3": ("1.2.3", "1p2p3", (1, 2, 3, False)),
    "1.2.3-pre": ("1.2.3-pre", "1p2p3-pre", (1, 2, 3, True)),
    "  12.34.56-pre  ": ("12.34.56-pre", "12p34p56-pre", (12, 34, 56, True)),
}

INVALID_VERSIONS = (
    "",
    " ",
    ".1",
    "1.",
    "1.2.",
    "1.2-pre",
    "1.2.3-rc1",
    "v1.2.3",
    "+1",
    "-1",
    "1..2",
    "1.2.3.4",
    "1 2",
)


@pytest.mark.parametrize(
    ("source", "canonical", "rvi", "parts"),
    (tuple((source, *expected) for source, expected in VALID_VERSIONS.items())),
)
def test_version_parsing_and_canonicalization(
    source: str, canonical: str, rvi: str, parts: tuple[int, int, int, bool]
) -> None:
    version = Version.parse(source)
    assert version.canonical == canonical
    assert str(version) == canonical
    assert version.to_rvi() == rvi
    assert (version.major, version.minor, version.patch, version.prerelease) == parts
    assert Version.coerce(version) is version


@pytest.mark.parametrize("source", INVALID_VERSIONS)
def test_invalid_versions_are_rejected(source: str) -> None:
    with pytest.raises(ValueError, match="Invalid RISC-V version"):
        Version.parse(source)


def test_versions_are_immutable_and_canonical_equality_is_hash_consistent() -> None:
    short = Version.parse("1")
    full = Version.parse("1.0.0")
    assert short == full
    assert short != "1.0"
    assert hash(short) == hash(full)
    assert len({short, full}) == 1
    assert {short: "release"}[full] == "release"
    with pytest.raises(TypeError):
        _ = short < "2"  # type: ignore[operator]
    with pytest.raises(FrozenInstanceError):
        short.major = 2  # type: ignore[misc]


def test_version_ordering_is_total_and_prerelease_precedes_release() -> None:
    versions = [
        Version(major, minor, patch, prerelease)
        for major in range(3)
        for minor in range(3)
        for patch in range(3)
        for prerelease in (True, False)
    ]
    ordered = sorted(versions)
    assert ordered == versions
    for left_index, left in enumerate(ordered):
        for right_index, right in enumerate(ordered):
            assert (left < right) == (left_index < right_index)
            assert (left <= right) == (left_index <= right_index)
            assert (left == right) == (left_index == right_index)
            assert (left >= right) == (left_index >= right_index)
            assert (left > right) == (left_index > right_index)


def test_patch_boundaries_create_new_self_consistent_values() -> None:
    original = Version.parse("1.2.3")
    assert original.next_patch() == Version.parse("1.2.4")
    assert original.previous_patch() == Version.parse("1.2.2")
    assert Version.parse("1.2.0").previous_patch() == Version.parse("1.1.9999")
    assert Version.parse("1.0.0").previous_patch() == Version.parse("0.9999.9999")
    assert Version.parse("1.2.3-pre").next_patch() == Version.parse("1.2.4-pre")
    assert Version.parse("1.2.3-pre").previous_patch() == Version.parse("1.2.2-pre")
    with pytest.raises(ValueError, match="Cannot decrement"):
        Version.parse("0").previous_patch()


@pytest.mark.parametrize(
    ("requirement", "below", "equal", "above"),
    [
        ("= 1.2", False, True, False),
        ("!= 1.2", True, False, True),
        ("< 1.2", True, False, False),
        ("<= 1.2", True, True, False),
        ("> 1.2", False, False, True),
        (">= 1.2", False, True, True),
    ],
)
def test_all_comparison_requirement_boundaries(
    requirement: str, below: bool, equal: bool, above: bool
) -> None:
    parsed = VersionRequirement.parse(requirement)
    assert parsed.matches("1.1.9999") is below
    assert parsed.matches("1.2.0") is equal
    assert parsed.matches("1.2.1-pre") is above


def test_requirement_parsing_normalizes_bare_versions_and_conjunctions() -> None:
    exact = VersionRequirement.parse(" 1.2 ")
    assert exact.operator is RequirementOperator.EQUAL
    assert str(exact) == "= 1.2.0"
    assert VersionRequirement.exact(Version.parse("1.2")) == exact
    assert parse_version_requirements(None) == (VersionRequirement.parse(">= 0"),)
    assert parse_version_requirements([]) == (VersionRequirement.parse(">= 0"),)
    assert parse_version_requirements([">= 1", "< 2"]) == (
        VersionRequirement.parse(">= 1"),
        VersionRequirement.parse("< 2"),
    )


@pytest.mark.parametrize("source", ["", "~ 1", "=> 1", "== 1", ">=", "!= pre"])
def test_invalid_requirements_are_rejected(source: str) -> None:
    with pytest.raises(ValueError, match="Invalid version requirement"):
        VersionRequirement.parse(source)


def _breaking_series() -> ExtensionVersionSet:
    return ExtensionVersionSet.from_metadata(
        "Xdemo",
        [
            {"version": "4.0", "state": "development", "breaking": True},
            {"version": "1.1", "state": "ratified", "changes": ["one"]},
            {"version": "3.0", "state": "frozen"},
            {"version": "1.0", "state": "ratified"},
            {"version": "2.0", "state": "ratified", "breaking": True},
        ],
    )


def test_extension_metadata_is_sorted_immutable_and_preserved() -> None:
    series = _breaking_series()
    assert [item.canonical for item in series] == ["1.0.0", "1.1.0", "2.0.0", "3.0.0", "4.0.0"]
    release = series.get("1.1")
    assert release is not None
    assert release.state == "ratified"
    assert release.changes == ("one",)
    assert str(release) == "Xdemo@1.1.0"
    with pytest.raises(TypeError):
        release.metadata["state"] = "development"  # type: ignore[index]


def test_breaking_releases_form_compatibility_ranges() -> None:
    series = _breaking_series()
    expected = {
        "0.9": ("1.0.0", "1.1.0"),
        "1.0": ("1.0.0", "1.1.0"),
        "1.1": ("1.1.0",),
        "1.5": ("2.0.0", "3.0.0"),
        "2.0": ("2.0.0", "3.0.0"),
        "3.0": ("3.0.0",),
        "4.0": ("4.0.0",),
        "5.0": (),
    }
    for base, compatible in expected.items():
        assert tuple(item.canonical for item in series.compatible_versions(base)) == compatible
        for candidate in ("1.0", "1.1", "2.0", "3.0", "4.0", "9.0"):
            assert series.is_compatible(base, candidate) == (
                Version.parse(candidate).canonical in compatible
            )

    false_marker = ExtensionVersionSet.from_metadata(
        "X", [{"version": "1"}, {"version": "2", "breaking": False}, {"version": "3"}]
    )
    assert tuple(item.canonical for item in false_marker.compatible_versions("1")) == (
        "1.0.0",
        "2.0.0",
        "3.0.0",
    )


def test_compatible_requirement_uses_extension_metadata() -> None:
    series = _breaking_series()
    requirement = VersionRequirement.parse("~> 2.0")
    assert requirement.matches("2.0", versions=series)
    assert requirement.matches("3.0", versions=series)
    assert not requirement.matches("1.1", versions=series)
    assert not requirement.matches("4.0", versions=series)
    with pytest.raises(ValueError, match="requires extension version metadata"):
        requirement.matches("2.0")


def test_extension_record_exposes_version_queries() -> None:
    extension = Database.bundled().extension("Sm")
    assert tuple(item.canonical for item in extension.versions) == (
        "1.11.0",
        "1.12.0",
        "1.13.0",
    )
    assert extension.version("1.12").canonical == "1.12.0"
    assert extension.min_version.canonical == "1.11.0"
    assert extension.max_version.canonical == "1.13.0"
    assert extension.min_ratified_version is not None
    with pytest.raises(ObjectNotFoundError, match="has no version"):
        extension.version("99")


def test_every_bundled_extension_version_parses_and_is_ordered() -> None:
    extensions = Database.bundled().extensions
    source_versions = 0
    for extension in extensions:
        metadata = extension["versions"]
        source_versions += len(metadata)
        assert tuple(item.version for item in extension.versions) == tuple(
            sorted(Version.parse(item["version"]) for item in metadata)
        )
        assert all(extension.version(item.version) is not None for item in extension.versions)
    assert source_versions > 100


def test_extension_schema_accepts_breaking_metadata() -> None:
    extension = Database.bundled().extension("I").to_dict()
    extension["versions"][0]["breaking"] = True
    extension["requirements"] = {"extension": {"name": "M", "version": "!= 1.0.0-pre"}}
    store = SchemaStore(REPO_ROOT / "spec" / "schemas")
    store.validate(extension, source="I.yaml")
    extension["requirements"]["extension"]["version"] = "~> 1.0-pre"
    with pytest.raises(SchemaError, match="schema validation failed"):
        store.validate(extension, source="I.yaml")


def test_invalid_extension_version_metadata_is_rejected() -> None:
    with pytest.raises(ValueError, match="Duplicate version"):
        ExtensionVersionSet.from_metadata("X", [{"version": "1"}, {"version": "1.0"}])
    with pytest.raises(TypeError, match="breaking"):
        ExtensionVersion.from_metadata("X", {"version": "1", "breaking": "yes"})
    with pytest.raises(DataError, match="invalid version metadata"):
        record = Database.bundled().extension("I")
        bad = type(record)(record.name, record.kind, record.path, {**record.data, "versions": [{}]})
        _ = bad.versions
