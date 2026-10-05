# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Standalone resource mapping; package builders need no runtime dependencies."""

from pathlib import Path, PurePosixPath

RUNTIME_SOURCE = PurePosixPath("src/udb/cpp_hart/runtime")
GROUPS = {
    "cpp/include/udb": ("include/udb", {".hpp"}),
    "c/include/udb": ("include/udb", {".h"}),
    "cpp/src": ("src", {".cpp"}),
    "cpp/test": ("test", {".cmake", ".cpp", ".hpp"}),
    "gdb": ("gdb", {".xml"}),
    "renode": ("renode", {".cs", ".repl", ".resc"}),
}
SUPPORT = (
    "LICENSE-BSD-3-Clause-Clear.txt",
    "LICENSE-MIT.txt",
    "LICENSE-CC-BY.txt",
    "LICENSES/BSD-2-Clause.txt",
    "NOTICE",
    ".toolchain/check_cxx.cmake",
    ".toolchain/.build-elfutils.sh",
    "cfgs/rv64-riscv-tests.yaml",
    "tests/data/fp/directed/f32_fpgen_expanded.jsonl",
)


def resource_entries(root, runtime=RUNTIME_SOURCE):
    """Yield (generated relative path, mode, declared relative source path)."""
    runtime_root = root.joinpath(str(runtime))
    if not runtime_root.joinpath("CMakeLists.txt").is_file():
        raise ValueError(f"Runtime resources lack {runtime}/CMakeLists.txt")
    yield PurePosixPath("CMakeLists.txt"), 0o644, runtime / "CMakeLists.txt"
    for source, (destination, suffixes) in GROUPS.items():
        directory = runtime_root.joinpath(source)
        if not directory.is_dir():
            raise ValueError(f"Runtime resources lack {runtime / source}")
        for file in sorted(directory.iterdir(), key=lambda file: file.name):
            if file.is_file() and PurePosixPath(file.name).suffix in suffixes:
                yield PurePosixPath(destination) / file.name, 0o644, runtime / source / file.name
    for source in SUPPORT:
        if not root.joinpath(source).is_file():
            raise ValueError(f"Runtime resources lack {source}")
        yield (
            PurePosixPath(source),
            0o755 if source.endswith(".sh") else 0o644,
            PurePosixPath(source),
        )


def package_mapping(source_root: Path) -> dict[Path, PurePosixPath]:
    mapping = {}
    for _, _, source in resource_entries(source_root):
        packaged = (
            PurePosixPath("runtime") / source.relative_to(RUNTIME_SOURCE)
            if source.is_relative_to(RUNTIME_SOURCE)
            else source
        )
        mapping[source_root / source] = PurePosixPath("udb/_data/cpp_hart") / packaged
    notice = source_root / "src/udb/cpp_hart/NOTICE"
    if not notice.is_file():
        raise ValueError(f"C++ generator attribution notice is missing: {notice}")
    mapping[notice] = PurePosixPath("udb/cpp_hart/NOTICE")
    return mapping
