# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Immutable configuration inputs, independent of architecture solving."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from ruamel.yaml.error import YAMLError

from .database import _freeze, _thaw
from .errors import DataError
from .resources import package_data_root
from .schema import SchemaStore
from .source import SourceMap, parse_yaml, synthetic_source_map
from .versions import Version, VersionRequirement, parse_version_requirements


class ConfigurationError(DataError):
    """A configuration input is invalid."""


class ConfigurationKind(StrEnum):
    UNCONFIGURED = "unconfigured"
    PARTIAL = "partially configured"
    FULL = "fully configured"


class Presence(StrEnum):
    MANDATORY = "mandatory"
    OPTIONAL = "optional"
    PROHIBITED = "prohibited"


@dataclass(frozen=True, slots=True)
class ExtensionSelection:
    name: str
    requirements: tuple[VersionRequirement, ...]
    presence: Presence


@dataclass(frozen=True, slots=True, init=False)
class Configuration:
    """A validated configuration declaration; satisfiability is a separate step.

    All filesystem inputs are explicit. ``arch_overlay`` and ``compatible``
    are retained declarations; opening a config never follows either implicitly.
    """

    name: str
    kind: ConfigurationKind
    extensions: tuple[ExtensionSelection, ...]
    params: Mapping[str, Any]
    requirements: Any
    additional_extensions: bool
    sources: SourceMap = field(repr=False, compare=False)
    _data: Mapping[str, Any] = field(repr=False)

    def __init__(
        self,
        data: Mapping[str, Any],
        *,
        source: str | SourceMap = "<configuration>",
        schema_store: SchemaStore | None = None,
    ) -> None:
        if not isinstance(data, Mapping):
            raise ConfigurationError(f"{source}: configuration must be a mapping")
        sources = source if isinstance(source, SourceMap) else synthetic_source_map(source, data)
        copied = _thaw(_freeze(data))

        def fail(message: str, *path: str | int) -> None:
            span = sources.nearest(*path)
            location = span.label if span is not None else sources.document
            raise ConfigurationError(f"{location}: {message}")

        # Ruby also accepts legacy [name, exact-version] pairs in full configs.
        implemented = copied.get("implemented_extensions")
        if isinstance(implemented, list):
            copied["implemented_extensions"] = [
                {"name": item[0], "version": item[1]}
                if isinstance(item, list) and len(item) == 2
                else item
                for item in implemented
            ]
        try:
            store = schema_store or SchemaStore(package_data_root().joinpath("schemas"))
            store.validate(copied, source=sources)
        except DataError as error:
            raise ConfigurationError(str(error)) from error
        kind = ConfigurationKind(copied["type"])
        params = copied.get("params", {})
        for name, value in params.items():
            if not isinstance(name, str) or not name:
                fail("parameter names must be non-empty strings", "params")
            if not _parameter_value(value):
                fail(
                    "parameter value must be an integer, boolean, string, or flat array",
                    "params",
                    name,
                )
        if "MXLEN" in params and (
            type(params["MXLEN"]) is not int or params["MXLEN"] not in (32, 64)
        ):
            fail("MXLEN must be 32 or 64", "params", "MXLEN")
        if kind is ConfigurationKind.FULL and "MXLEN" not in params:
            fail("fully configured architectures require MXLEN", "params")

        selections: list[ExtensionSelection] = []
        groups = (
            (("implemented_extensions", Presence.MANDATORY),)
            if kind is ConfigurationKind.FULL
            else (
                ("mandatory_extensions", Presence.MANDATORY),
                ("non_mandatory_extensions", Presence.OPTIONAL),
                ("prohibited_extensions", Presence.PROHIBITED),
            )
        )
        for key, presence in groups:
            seen: set[str] = set()
            for index, item in enumerate(copied.get(key, [])):
                name = item["name"]
                if name in seen:
                    fail(f"duplicate extension {name!r} in {key}", key, index)
                seen.add(name)
                try:
                    if kind is ConfigurationKind.FULL:
                        text = item["version"].strip()
                        version = Version.parse(text[1:].strip() if text.startswith("=") else text)
                        requirements = parse_version_requirements(f"= {version}")
                    else:
                        requirements = parse_version_requirements(item.get("version"))
                except (ValueError, TypeError) as error:
                    fail(str(error), key, index, "version")
                selections.append(ExtensionSelection(name, requirements, presence))

        object.__setattr__(self, "name", copied["name"])
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "extensions", tuple(selections))
        object.__setattr__(self, "params", _freeze(params))
        object.__setattr__(self, "requirements", _freeze(copied.get("requirements", True)))
        object.__setattr__(
            self,
            "additional_extensions",
            kind is not ConfigurationKind.FULL and copied.get("additional_extensions", True),
        )
        object.__setattr__(self, "sources", sources)
        object.__setattr__(self, "_data", _freeze(copied))

    @classmethod
    def from_yaml(
        cls, text: str, *, source: str = "<configuration>", schema_store: SchemaStore | None = None
    ) -> Configuration:
        try:
            parsed = parse_yaml(text, source=source)
            return cls(parsed.value, source=parsed.sources, schema_store=schema_store)
        except DataError as error:
            raise ConfigurationError(str(error)) from error
        except (YAMLError, ValueError) as error:
            raise ConfigurationError(f"{source}: cannot parse configuration: {error}") from error

    @classmethod
    def from_file(
        cls, path: str | Path, *, schema_store: SchemaStore | None = None
    ) -> Configuration:
        path = Path(path)
        try:
            return cls.from_yaml(
                path.read_text(encoding="utf-8"), source=str(path), schema_store=schema_store
            )
        except (OSError, UnicodeError) as error:
            raise ConfigurationError(f"{path}: cannot read configuration: {error}") from error

    @classmethod
    def builtin(cls, name: str = "_") -> Configuration:
        """Load one of the bundled generic configurations: ``_``, ``rv32``, ``rv64``."""
        if name not in ("_", "rv32", "rv64"):
            raise ConfigurationError(f"Unknown bundled configuration {name!r}")
        return cls.from_yaml(
            package_data_root().joinpath("configs", f"{name}.yaml").read_text(encoding="utf-8"),
            source=f"configs/{name}.yaml",
        )

    @property
    def mxlen(self) -> int | None:
        """Declared or necessarily inferred machine width, otherwise unknown."""
        explicit = self.params.get("MXLEN")
        if explicit is not None:
            return explicit
        for name in ("UXLEN", "SXLEN", "VSXLEN", "VUXLEN"):
            value = self.params.get(name)
            if value == 64 or (isinstance(value, tuple) and 64 in value):
                return 64
        return 64 if _requires_64(self.requirements) else None

    @property
    def overlay(self) -> str | None:
        return self._data.get("arch_overlay")

    @property
    def compatible(self) -> tuple[str, ...]:
        value = self._data.get("compatible", ())
        return (value,) if isinstance(value, str) else tuple(value)

    def to_dict(self) -> dict[str, Any]:
        return _thaw(self._data)


def _parameter_value(value: Any) -> bool:
    return type(value) in (str, int, bool) or (
        isinstance(value, list) and all(type(item) in (str, int, bool) for item in value)
    )


def _requires_64(condition: Any) -> bool:
    if not isinstance(condition, Mapping):
        return False
    if "allOf" in condition:
        return any(_requires_64(child) for child in condition["allOf"])
    if "anyOf" in condition:
        children = condition["anyOf"]
        return bool(children) and all(_requires_64(child) for child in children)
    if "param" in condition:
        return _requires_64(condition["param"])
    return condition.get("name") in ("UXLEN", "SXLEN", "VSXLEN", "VUXLEN") and (
        condition.get("equal") == 64 or condition.get("includes") == 64
    )
