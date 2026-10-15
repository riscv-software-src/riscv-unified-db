# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Derive explicit profile configurations using the public architecture queries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any

from ruamel.yaml.scalarstring import LiteralScalarString

from .architecture import ArchitectureCheckStatus, ConfiguredArchitecture, QueryPresence
from .authoring import AuthoringPlan, GeneratedFile
from .configuration import Configuration
from .configuration_diagnostics import format_check_diagnostics
from .database import ResolvedDatabase
from .errors import DataError
from .serialization import dumps_yaml
from .versions import parse_version_requirements

_BANNER = """# SPDX-License-Identifier: CC0-1.0

# AUTO-GENERATED FILE. DO NOT EDIT
# To regenerate, run `udb generate profile-configs -o cfgs/profile`
# The data comes from the resolved UDB profile definitions.

"""


def _check(architecture: ConfiguredArchitecture, source: str) -> None:
    checked = architecture.check()
    if checked.status is not ArchitectureCheckStatus.VALID:
        reasons = "\n".join(format_check_diagnostics(architecture, checked))
        raise DataError(f"{source}: profile configuration is {checked.status.value}:\n{reasons}")


def profile_configuration(
    database: ResolvedDatabase, name: str, *, strict: bool = True
) -> Configuration:
    """Return a profile's declared or solver-expanded partial configuration."""

    if not isinstance(database, ResolvedDatabase):
        raise TypeError("profile_configuration requires a ResolvedDatabase")
    profile = database.profile(name)
    declared = profile.to_dict()
    extensions = declared.get("extensions", {})
    if not isinstance(extensions, Mapping):
        raise DataError(f"{profile.path}#/extensions: expected a mapping")
    if any(not isinstance(key, str) or not key for key in extensions):
        raise DataError(f"{profile.path}#/extensions: expected nonempty string names")
    mandatory: list[dict[str, Any]] = []
    optional: list[dict[str, Any]] = []
    for extension_name, declaration in sorted(extensions.items()):
        if extension_name.startswith("$"):
            continue
        database.extension(extension_name)
        if not isinstance(declaration, Mapping):
            raise DataError(f"{profile.path}#/extensions/{extension_name}: expected a mapping")
        presence = declaration.get("presence")
        if presence == "mandatory":
            target = mandatory
        elif presence == "optional" or (
            isinstance(presence, Mapping)
            and set(presence) == {"optional"}
            and presence["optional"] in ("expansion", "localized", "development", "transitory")
        ):
            target = optional
        else:
            raise DataError(
                f"{profile.path}#/extensions/{extension_name}/presence: "
                f"unsupported profile presence {presence!r}"
            )
        requirements = declaration.get("version")
        try:
            parsed = parse_version_requirements(requirements)
        except (TypeError, ValueError) as error:
            raise DataError(
                f"{profile.path}#/extensions/{extension_name}/version: {error}"
            ) from error
        rendered = [str(requirement) for requirement in parsed]
        target.append(
            {
                "name": extension_name,
                "version": rendered[0] if len(rendered) == 1 else rendered,
            }
        )
    description = declared.get("description")
    if description is not None and not isinstance(description, str):
        raise DataError(f"{profile.path}#/description: expected a string")
    data: dict[str, Any] = {
        "$schema": "config_schema.json#",
        "kind": "architecture configuration",
        "type": "partially configured",
        "name": name,
        "description": "" if description is None else description,
        "params": {},
        "mandatory_extensions": mandatory,
        "non_mandatory_extensions": optional,
        "additional_extensions": True,
    }
    if "requirements" in declared:
        data["requirements"] = declared["requirements"]
    source = f"{profile.path} (generated configuration)"
    configuration = Configuration(data, source=source)
    if not strict:
        return configuration
    architecture = database.configure(configuration)
    _check(architecture, str(profile.path))
    explicit = {selection["name"] for selection in mandatory}
    for extension in database.extensions:
        if extension.name in explicit:
            continue
        presence = architecture.extension_presence(extension.name)
        if presence is QueryPresence.DEFERRED:
            raise DataError(f"{profile.path}: cannot decide presence of {extension.name}")
        if presence is not QueryPresence.MANDATORY:
            continue
        minimum = None
        for version in extension.versions:
            presence = architecture.extension_presence(extension.name, f"= {version.canonical}")
            if presence is QueryPresence.DEFERRED:
                raise DataError(
                    f"{profile.path}: cannot decide version {extension.name}@{version.canonical}"
                )
            if presence is not QueryPresence.ABSENT:
                minimum = version
                break
        if minimum is None:
            raise DataError(f"{profile.path}: mandatory {extension.name} has no possible version")
        mandatory.append({"name": extension.name, "version": f"~> {minimum.canonical}"})
    mandatory.sort(key=lambda selection: selection["name"])
    result = Configuration(data, source=source)
    if len(mandatory) != len(explicit):
        _check(database.configure(result), str(profile.path))
    return result


def _literal_idl(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: LiteralScalarString(child)
            if isinstance(key, str) and key.endswith("()") and isinstance(child, str) and child
            else _literal_idl(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_literal_idl(child) for child in value]
    return value


def profile_configuration_plan(
    database: ResolvedDatabase, names: Sequence[str] | None = None
) -> AuthoringPlan:
    """Plan deterministic profile YAML output without modifying the input database."""

    if isinstance(names, (str, bytes)):
        raise TypeError("Profile names must be a sequence of names, not a string")
    selected = (
        sorted(profile.name for profile in database.profiles) if names is None else list(names)
    )
    if any(not isinstance(name, str) for name in selected):
        raise DataError("Profile selection must contain string names")
    if len({name.casefold() for name in selected}) != len(selected):
        raise DataError("Profile selection contains duplicate or case-colliding names")
    outputs = []
    for name in sorted(selected):
        reserved = {"CON", "PRN", "AUX", "NUL"} | {
            f"{prefix}{index}" for prefix in ("COM", "LPT") for index in range(1, 10)
        }
        if (
            not name
            or name.endswith((".", " "))
            or name.split(".")[0].upper() in reserved
            or any(ord(char) < 32 or char in '<>:"/\\|?*' for char in name)
        ):
            raise DataError(f"Unsafe profile output name {name!r}")
        profile = database.profile(name)
        configuration = profile_configuration(database, name)
        content = _BANNER + dumps_yaml(
            _literal_idl(configuration.to_dict()), source=str(profile.path)
        )
        restored = Configuration.from_yaml(content, source=f"{name}.yaml")
        if restored.to_dict() != configuration.to_dict():
            raise DataError(
                f"{profile.path}: generated configuration does not round-trip through YAML"
            )
        outputs.append(
            GeneratedFile(
                PurePosixPath(f"{name}.yaml"),
                content.encode("utf-8"),
                owner=f"profile:{name}",
                dependencies=(PurePosixPath(profile.path),),
                overwrite_prefixes=(
                    b"# SPDX-License-Identifier: CC0-1.0\n\n# AUTO-GENERATED FILE. DO NOT EDIT\n",
                ),
            )
        )
    return AuthoringPlan(tuple(outputs))
