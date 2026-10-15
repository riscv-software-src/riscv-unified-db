# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Immutable RISC-V version and version-requirement values."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from functools import total_ordering
from itertools import pairwise
from types import MappingProxyType
from typing import Any, Self

_VERSION_RE = re.compile(r"^\s*([0-9]+)(?:\.([0-9]+)(?:\.([0-9]+)(-pre)?)?)?\s*$")
_REQUIREMENT_RE = re.compile(r"^\s*(>=|>|~>|<=|<|!=|=)?\s*(.*?)\s*$")


@total_ordering
@dataclass(frozen=True, slots=True, eq=False)
class Version:
    """A RISC-V version, which is ordered but does not use SemVer rules.

    Omitted minor and patch components have value zero. A ``-pre`` version
    sorts immediately before the release with the same numeric components.
    """

    major: int
    minor: int = 0
    patch: int = 0
    prerelease: bool = False
    _precision: int = field(default=3, repr=False, compare=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("major", self.major),
            ("minor", self.minor),
            ("patch", self.patch),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"Version {name} must be a non-negative integer")
        if not isinstance(self.prerelease, bool):
            raise TypeError("Version prerelease must be a boolean")
        if self._precision not in {1, 2, 3}:
            raise ValueError("Version precision must be 1, 2, or 3")
        if self.prerelease and self._precision != 3:
            raise ValueError("A prerelease version must include major, minor, and patch")

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse ``MAJOR[.MINOR[.PATCH[-pre]]]``."""
        if not isinstance(value, str):
            raise TypeError("Version.parse() requires a string")
        match = _VERSION_RE.fullmatch(value)
        if match is None:
            raise ValueError(f"Invalid RISC-V version {value!r}")
        components = 1 + int(match[2] is not None) + int(match[3] is not None)
        return cls(
            int(match[1]),
            int(match[2] or 0),
            int(match[3] or 0),
            match[4] is not None,
            components,
        )

    @classmethod
    def coerce(cls, value: VersionLike) -> Version:
        """Return *value* as a :class:`Version`."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls.parse(value)
        raise TypeError(f"Expected a Version or string, got {type(value).__name__}")

    @property
    def canonical(self) -> str:
        suffix = "-pre" if self.prerelease else ""
        return f"{self.major}.{self.minor}.{self.patch}{suffix}"

    def to_rvi(self) -> str:
        """Return the compact spelling used in RISC-V document identifiers."""
        result = str(self.major)
        if self._precision >= 2:
            result += f"p{self.minor}"
        if self._precision >= 3:
            result += f"p{self.patch}"
        if self.prerelease:
            result += "-pre"
        return result

    def next_patch(self) -> Version:
        return Version(self.major, self.minor, self.patch + 1, self.prerelease)

    def previous_patch(self) -> Version:
        """Return the preceding representable version using Ruby's 9999 boundary."""
        if self.patch > 0:
            return Version(self.major, self.minor, self.patch - 1, self.prerelease)
        if self.minor > 0:
            return Version(self.major, self.minor - 1, 9999, self.prerelease)
        if self.major > 0:
            return Version(self.major - 1, 9999, 9999, self.prerelease)
        raise ValueError("Cannot decrement version 0.0.0")

    def _sort_key(self) -> tuple[int, int, int, int]:
        return (self.major, self.minor, self.patch, 0 if self.prerelease else 1)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._sort_key() == other._sort_key()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._sort_key() < other._sort_key()

    def __hash__(self) -> int:
        return hash(self._sort_key())

    def __str__(self) -> str:
        return self.canonical


type VersionLike = Version | str


class RequirementOperator(StrEnum):
    EQUAL = "="
    NOT_EQUAL = "!="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    COMPATIBLE = "~>"


@dataclass(frozen=True, slots=True)
class VersionRequirement:
    """One comparison against a RISC-V version."""

    operator: RequirementOperator
    version: Version

    def __post_init__(self) -> None:
        if not isinstance(self.operator, RequirementOperator):
            raise TypeError("VersionRequirement.operator must be a RequirementOperator")
        if not isinstance(self.version, Version):
            raise TypeError("VersionRequirement.version must be a Version")

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a requirement, treating a bare version as exact equality."""
        if not isinstance(value, str):
            raise TypeError("VersionRequirement.parse() requires a string")
        match = _REQUIREMENT_RE.fullmatch(value)
        if match is None or not match[2]:
            raise ValueError(f"Invalid version requirement {value!r}")
        try:
            operator = RequirementOperator(match[1] or "=")
            version = Version.parse(match[2])
        except ValueError as error:
            raise ValueError(f"Invalid version requirement {value!r}") from error
        return cls(operator, version)

    @classmethod
    def exact(cls, value: VersionLike) -> Self:
        return cls(RequirementOperator.EQUAL, Version.coerce(value))

    def matches(
        self,
        candidate: VersionLike,
        *,
        versions: ExtensionVersionSet | None = None,
    ) -> bool:
        candidate_version = Version.coerce(candidate)
        match self.operator:
            case RequirementOperator.EQUAL:
                return candidate_version == self.version
            case RequirementOperator.NOT_EQUAL:
                return candidate_version != self.version
            case RequirementOperator.LESS_THAN:
                return candidate_version < self.version
            case RequirementOperator.LESS_THAN_OR_EQUAL:
                return candidate_version <= self.version
            case RequirementOperator.GREATER_THAN:
                return candidate_version > self.version
            case RequirementOperator.GREATER_THAN_OR_EQUAL:
                return candidate_version >= self.version
            case RequirementOperator.COMPATIBLE:
                if versions is None:
                    raise ValueError("The ~> operator requires extension version metadata")
                return versions.is_compatible(self.version, candidate_version)

    def __str__(self) -> str:
        return f"{self.operator.value} {self.version.canonical}"


type RequirementLike = VersionRequirement | str


def parse_version_requirements(
    value: RequirementLike | Sequence[RequirementLike] | None,
) -> tuple[VersionRequirement, ...]:
    """Normalize conjunctive requirement input to an immutable tuple.

    Missing and empty requirements mean every non-negative version (``>= 0``),
    matching the UDB configuration and condition schemas.
    """
    if value is None:
        return (VersionRequirement.parse(">= 0"),)
    if isinstance(value, VersionRequirement):
        return (value,)
    if isinstance(value, str):
        return (VersionRequirement.parse(value),)
    if not isinstance(value, Sequence):
        raise TypeError("Version requirements must be a string or sequence")
    if not value:
        return (VersionRequirement.parse(">= 0"),)
    return tuple(
        item if isinstance(item, VersionRequirement) else VersionRequirement.parse(item)
        for item in value
    )


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze(item) for item in value)
    return value


@total_ordering
@dataclass(frozen=True, slots=True, eq=False)
class ExtensionVersion:
    """Version metadata for one extension release."""

    extension: str
    version: Version
    state: str | None = None
    breaking: bool = False
    ratification_date: str | None = None
    release_date: str | None = None
    changes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.extension, str) or not self.extension:
            raise ValueError("Extension name must be a non-empty string")
        if not isinstance(self.version, Version):
            raise TypeError("ExtensionVersion.version must be a Version")
        if not isinstance(self.breaking, bool):
            raise TypeError("ExtensionVersion.breaking must be a boolean")
        object.__setattr__(self, "changes", tuple(self.changes))
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    @classmethod
    def from_metadata(cls, extension: str, value: Mapping[str, Any]) -> Self:
        if not isinstance(value, Mapping):
            raise TypeError("Extension version metadata must be a mapping")
        raw_version = value.get("version")
        if not isinstance(raw_version, str):
            raise TypeError("Extension version metadata requires a string 'version'")
        state = value.get("state")
        if state is not None and not isinstance(state, str):
            raise TypeError("Extension version 'state' must be a string")
        breaking = value.get("breaking", False)
        if not isinstance(breaking, bool):
            raise TypeError("Extension version 'breaking' must be a boolean")
        changes = value.get("changes", ())
        if not isinstance(changes, Sequence) or isinstance(changes, str | bytes):
            raise TypeError("Extension version 'changes' must be a sequence of strings")
        if not all(isinstance(change, str) for change in changes):
            raise TypeError("Extension version 'changes' must contain only strings")
        for field_name in ("ratification_date", "release_date"):
            field_value = value.get(field_name)
            if field_value is not None and not isinstance(field_value, str):
                raise TypeError(f"Extension version {field_name!r} must be a string or null")
        return cls(
            extension=extension,
            version=Version.parse(raw_version),
            state=state,
            breaking=breaking,
            ratification_date=value.get("ratification_date"),
            release_date=value.get("release_date"),
            changes=tuple(changes),
            metadata=value,
        )

    @property
    def canonical(self) -> str:
        return self.version.canonical

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ExtensionVersion)
            and self.extension == other.extension
            and self.version == other.version
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ExtensionVersion):
            return NotImplemented
        return (self.extension, self.version) < (other.extension, other.version)

    def __hash__(self) -> int:
        return hash((self.extension, self.version))

    def __str__(self) -> str:
        return f"{self.extension}@{self.version.canonical}"


@dataclass(frozen=True, slots=True)
class ExtensionVersionSet(Sequence[ExtensionVersion]):
    """The ordered releases and compatibility boundaries of one extension."""

    extension: str
    versions: tuple[ExtensionVersion, ...]

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.versions, key=lambda item: item.version))
        if any(item.extension != self.extension for item in ordered):
            raise ValueError("All extension versions must have the same extension name")
        for left, right in pairwise(ordered):
            if left.version == right.version:
                raise ValueError(
                    f"Duplicate version {left.version.canonical} for extension {self.extension}"
                )
        object.__setattr__(self, "versions", ordered)

    @classmethod
    def from_metadata(
        cls, extension: str, values: Iterable[Mapping[str, Any]]
    ) -> ExtensionVersionSet:
        return cls(
            extension,
            tuple(ExtensionVersion.from_metadata(extension, value) for value in values),
        )

    def __getitem__(self, index: int | slice) -> ExtensionVersion | tuple[ExtensionVersion, ...]:
        return self.versions[index]

    def __len__(self) -> int:
        return len(self.versions)

    def __iter__(self) -> Iterator[ExtensionVersion]:
        return iter(self.versions)

    def get(self, value: VersionLike) -> ExtensionVersion | None:
        version = Version.coerce(value)
        return next((item for item in self.versions if item.version == version), None)

    def compatible_versions(self, base: VersionLike) -> tuple[ExtensionVersion, ...]:
        """Return known releases compatible with *base*.

        If *base* is not a known release, the next greater release is the
        compatibility anchor, matching existing UDB requirement behavior.
        A later release marked ``breaking`` starts a new compatibility range
        and is excluded; a breaking anchor remains compatible with later
        releases until the next breaking boundary.
        """
        base_version = Version.coerce(base)
        anchor = next(
            (index for index, item in enumerate(self.versions) if item.version >= base_version),
            None,
        )
        if anchor is None:
            return ()
        compatible: list[ExtensionVersion] = []
        for index, item in enumerate(self.versions[anchor:], start=anchor):
            if index > anchor and item.breaking:
                break
            compatible.append(item)
        return tuple(compatible)

    def is_compatible(self, base: VersionLike, candidate: VersionLike) -> bool:
        candidate_version = Version.coerce(candidate)
        return any(item.version == candidate_version for item in self.compatible_versions(base))


__all__ = [
    "ExtensionVersion",
    "ExtensionVersionSet",
    "RequirementOperator",
    "Version",
    "VersionLike",
    "VersionRequirement",
    "parse_version_requirements",
]
