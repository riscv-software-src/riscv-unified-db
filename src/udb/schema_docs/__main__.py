# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Standalone CLI; the unified CLI calls the same public API."""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

from ..errors import AuthoringError
from ..schema import SchemaError, SchemaStore
from ..serialization import dumps_json
from . import SchemaDocsError, SchemaDocumentation


def _write_stdout(text: str) -> None:
    binary = getattr(sys.stdout, "buffer", None)
    # Avoid leaving failed writes buffered for an interpreter-shutdown retry.
    stream = getattr(binary, "raw", binary) if binary is not None else sys.stdout
    payload = text.encode("utf-8") if binary is not None else text
    if stream.write(payload) != len(payload):
        raise OSError("short write to schema documentation stdout")
    stream.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate offline versioned JSON Schema MDX")
    parser.add_argument("--schemas", type=Path, help="explicit SchemaStore root; default: bundled")
    parser.add_argument("--out", required=True, type=Path, help="documentation output root")
    parser.add_argument("--schema", help="render only the named .json schema")
    parser.add_argument("--output-file", help="single-schema file relative to --out")
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    parser.add_argument("--no-index", action="store_true")
    parser.add_argument(
        "--replace-current",
        action="store_true",
        help="explicitly allow replacing current-version pages; never deletes history",
    )
    parser.add_argument(
        "--diagnostics", action="store_true", help="print all projection notices as JSON"
    )
    args = parser.parse_args(argv)
    try:
        docs = SchemaDocumentation(SchemaStore(args.schemas) if args.schemas else None)
        plan = docs.plan(
            args.out,
            schema=args.schema,
            output_file=args.output_file,
            generate_index=not args.no_index,
        )
        drift = plan.apply(
            args.out,
            check=args.check,
            replace_current=args.replace_current,
        )
        if args.diagnostics:
            _write_stdout(
                dumps_json(
                    {
                        "status": ("drift" if args.check else "generated")
                        if drift
                        else "unchanged",
                        "check": args.check,
                        "paths": [str(path) for path in drift],
                        "notices": [asdict(notice) for notice in plan.notices],
                    }
                )
            )
        else:
            _write_stdout(
                "".join(f"{'drift' if args.check else 'generated'}: {path}\n" for path in drift)
            )
        return 1 if args.check and drift else 0
    except (SchemaDocsError, SchemaError, AuthoringError, OSError, UnicodeError) as error:
        if args.diagnostics:
            try:
                _write_stdout(dumps_json({"status": "error", "error": str(error)}))
            except (OSError, UnicodeError) as report_error:
                print(
                    f"schema-docs: cannot write diagnostics to stdout: {report_error}",
                    file=sys.stderr,
                )
        print(f"schema-docs: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
