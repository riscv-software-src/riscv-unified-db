# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Testing entry point pending integration into the unified generator CLI."""

import argparse
import sys
from pathlib import Path

from udb import Configuration, Database
from udb.errors import DataError
from udb.idl.errors import IdlError
from udb.schema import SchemaStore

from .generator import CppHartGenerator
from .resources import RuntimeResources
from .types import CppGenerationError


def configuration_overlays(configs, paths):
    by_name = {}
    for path in paths:
        name = path.name
        if name in by_name:
            raise CppGenerationError(f"Duplicate --overlay input named {name!r}")
        by_name[name] = path
    required = {config.overlay for config in configs if config.overlay is not None}
    missing = required - by_name.keys()
    if missing:
        raise CppGenerationError(
            "Missing explicit --overlay input for " + ", ".join(sorted(missing))
        )
    unused = by_name.keys() - required
    if unused:
        raise CppGenerationError(
            "Unused --overlay input does not match a selected configuration: "
            + ", ".join(sorted(unused))
        )
    return tuple(
        (by_name[config.overlay],) if config.overlay is not None else () for config in configs
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", action="append", required=True)
    parser.add_argument("--configs-directory", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--schemas", type=Path)
    parser.add_argument("--overlay", type=Path, action="append", default=[])
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--build-name")
    parser.add_argument("--build-type", default="RelWithDebInfo")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.schemas is not None and args.source is None:
            raise CppGenerationError("--schemas requires an explicit --source")
        selectors = [selector for group in args.config for selector in group.split(",")]
        if "all" in selectors:
            if selectors != ["all"]:
                raise CppGenerationError("'all' cannot be combined with other configurations")
            selectors = (
                [str(file) for file in sorted(args.configs_directory.glob("*.yaml"))]
                if args.configs_directory
                else ["_", "rv32", "rv64"]
            )
        if not selectors or any(not selector for selector in selectors):
            raise CppGenerationError("No configurations selected")
        configs = []
        store = SchemaStore(args.schemas) if args.schemas is not None else None
        for selector in selectors:
            if selector in {"_", "rv32", "rv64"} and args.configs_directory is None:
                configs.append(Configuration.builtin(selector))
            else:
                path = Path(selector)
                if args.configs_directory and not path.is_file():
                    path = args.configs_directory / f"{selector}.yaml"
                configs.append(Configuration.from_file(path, schema_store=store))
        database = (
            Database.from_path(args.source, schemas_path=args.schemas)
            if args.source
            else Database.bundled()
        )
        overlay_groups = configuration_overlays(configs, args.overlay)
        resolved_databases = {}
        architectures = []
        for config, overlays in zip(configs, overlay_groups, strict=True):
            resolved = resolved_databases.get(overlays)
            if resolved is None:
                resolved = database.resolve(overlays=overlays)
                resolved_databases[overlays] = resolved
            architectures.append(resolved.configure(config))
        generator = CppHartGenerator(
            architectures,
            resources=RuntimeResources.from_path(args.runtime_root) if args.runtime_root else None,
            build_name=args.build_name,
            build_type=args.build_type,
        )
        changed = generator.generate(args.out, check=args.check)
        return 1 if args.check and changed else 0
    except (CppGenerationError, DataError, IdlError, OSError, ValueError) as error:
        print(f"cpp-hart: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
