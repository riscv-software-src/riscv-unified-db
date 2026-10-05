# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Build the standalone wheel with a read-only snapshot of standard UDB data."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_ISA_SUFFIXES = frozenset({".adoc", ".idl", ".isa", ".yaml"})
_SCHEMA_SUFFIXES = frozenset({".json", ".yaml"})


def _files_with_suffixes(root: Path, suffixes: frozenset[str]) -> list[Path]:
    if not root.is_dir():
        msg = f"required package data directory is missing: {root}"
        raise RuntimeError(msg)
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix in suffixes)


def package_data(source_root: Path) -> dict[Path, PurePosixPath]:
    """Return source-to-wheel mappings for the packageable raw data snapshot."""
    isa_root = source_root / "spec" / "std" / "isa"
    schema_root = source_root / "spec" / "schemas"
    isa_files = _files_with_suffixes(isa_root, _ISA_SUFFIXES)
    schema_files = _files_with_suffixes(schema_root, _SCHEMA_SUFFIXES)

    mappings: dict[Path, PurePosixPath] = {}
    for path in isa_files:
        mappings[path] = PurePosixPath("udb/_data/isa") / path.relative_to(isa_root).as_posix()
    for path in schema_files:
        mappings[path] = (
            PurePosixPath("udb/_data/schemas") / path.relative_to(schema_root).as_posix()
        )
    return mappings


class CustomBuildHook(BuildHookInterface):
    """Add repository data to wheels without modifying the source tree."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, object]) -> None:
        del version
        if self.target_name != "wheel":
            return
        force_include = build_data.setdefault("force_include", {})
        if not isinstance(force_include, dict):
            msg = "Hatch wheel force_include configuration is not a mapping"
            raise TypeError(msg)
        for source, destination in package_data(Path(self.root)).items():
            force_include[str(source)] = destination.as_posix()
