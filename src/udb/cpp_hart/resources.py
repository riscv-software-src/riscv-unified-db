# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Explicit static-runtime resources, with a build-time packaging mapping."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from udb.resources import package_data_root

from .asset_manifest import RUNTIME_SOURCE, package_mapping, resource_entries
from .types import CppGenerationError

__all__ = ["RuntimeResources", "package_mapping", "renode_repl", "standalone_cmake"]


@dataclass(frozen=True)
class RuntimeResources:
    """A bundled or caller-declared root; never searched for a checkout."""

    root: Any
    runtime: PurePosixPath = RUNTIME_SOURCE

    @classmethod
    def bundled(cls):
        return cls(package_data_root().joinpath("cpp_hart"), PurePosixPath("runtime"))

    @classmethod
    def from_path(cls, root: str | Path):
        path = Path(root)
        if not path.is_dir():
            raise CppGenerationError(f"Missing explicit runtime resource root: {root}")
        return cls(path)

    def files(self):
        try:
            for output, mode, source in resource_entries(self.root, self.runtime):
                origin = (
                    RUNTIME_SOURCE / source.relative_to(self.runtime)
                    if source.is_relative_to(self.runtime)
                    else source
                )
                yield output, self.root.joinpath(str(source)).read_bytes(), mode, origin
        except ValueError as error:
            raise CppGenerationError(str(error)) from error


def standalone_cmake(
    content: bytes, config_names: tuple[str, ...], build_type: str = "RelWithDebInfo"
) -> bytes:
    text = content.decode("utf-8")
    old = """if(NOT DEFINED UDB_ROOT OR UDB_ROOT STREQUAL "")
  get_filename_component(UDB_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
endif()"""
    new = """if(NOT DEFINED UDB_ROOT OR UDB_ROOT STREQUAL "")
  if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/.toolchain/check_cxx.cmake")
    set(UDB_ROOT "${CMAKE_CURRENT_LIST_DIR}")
  else()
    get_filename_component(UDB_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
  endif()
endif()"""
    if old not in text:
        raise CppGenerationError("Unrecognized runtime CMake UDB_ROOT contract")
    text = text.replace(old, new, 1)
    build_default = "SET(CMAKE_BUILD_TYPE RelWithDebInfo"
    if build_default not in text:
        raise CppGenerationError("Unrecognized runtime CMake build-type contract")
    if build_type not in {"Debug", "RelWithDebInfo", "Release", "Asan"}:
        raise CppGenerationError(f"Unsupported runtime CMake build type {build_type!r}")
    text = text.replace(build_default, f"SET(CMAKE_BUILD_TYPE {build_type}", 1)
    configs = ";".join(config_names)
    text = f'if(NOT DEFINED CONFIG_LIST)\n  set(CONFIG_LIST "{configs}")\nendif()\n' + text
    return text.encode("utf-8")


def renode_repl(content: bytes, config: str) -> bytes:
    """Bind the portable Renode example to the first generated model."""
    text = content.decode("utf-8")
    for marker in ("@UDB_MODEL@", "@UDB_CONFIG@"):
        if text.count(marker) != 1:
            raise CppGenerationError(f"Renode platform must contain exactly one {marker}")
        text = text.replace(marker, config)
    return text.encode("utf-8")
