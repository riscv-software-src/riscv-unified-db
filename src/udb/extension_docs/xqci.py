# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Retained original Xqci script's ordered extension/version selection."""

from __future__ import annotations

from collections.abc import Mapping

from ..database import Database
from ..versions import Version, VersionRequirement
from .model import ExtensionDocumentError


def xqci_selectors(database: Database, version: str = "latest") -> tuple[str, ...]:
    extension = database.extension("Xqci")
    if version == "latest":
        selected = extension.versions[-1]
    else:
        # The native script requires exact metadata spelling, not equivalent
        # abbreviated versions. Preserve that genuine script boundary.
        selected = next(
            (item for item in extension.versions if item.metadata["version"] == version), None
        )
        if selected is None:
            raise ExtensionDocumentError(
                f"Xqci version {version!r} does not exist (must be exact match)"
            )
    requirements = selected.metadata.get("requirements", {})
    declaration = requirements.get("extension", {}).get("allOf", ())
    if not declaration:
        raise ExtensionDocumentError(f"{selected}: missing declared component requirements")
    result = [f"Xqci@{selected.metadata['version']}"]
    for component in declaration:
        if not isinstance(component, Mapping) or not isinstance(component.get("name"), str):
            raise ExtensionDocumentError(f"{selected}: malformed component requirement")
        raw = component.get("version")
        if not isinstance(raw, str):
            raise ExtensionDocumentError(f"{selected}: component requires an exact version")
        requirement = VersionRequirement.parse(raw)
        if requirement.operator.value != "=":
            raise ExtensionDocumentError(f"{selected}: non-exact component requirement {raw!r}")
        # Retain the declared version spelling (native removes only '=' and
        # surrounding whitespace), not a reconstructed/canonical version.
        spelling = raw.replace("=", "").strip()
        Version.parse(spelling)
        result.append(f"{component['name']}@{spelling}")
    return tuple(result)
