# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Capture the genuine Ruby IDL CLI; run under the shared Ruby lock."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
FIXTURES = Path("tests/python/fixtures/idl_cli")
CASES = (
    ("integer", ("eval", "1 + 2"), None),
    ("bits", ("eval", "8'hff + 8'1"), None),
    ("boolean", ("eval", "true && !false"), None),
    ("equality", ("eval", "1 == 1"), None),
    ("string", ("eval", '"hello"'), None),
    ("defines", ("eval", "-DA=5", "-DB=A+10", "A+B"), None),
    ("define-equality", ("eval", "-DA=1==1", "A"), None),
    ("unknown", ("eval", "unknown_name"), None),
    ("bad-expression", ("eval", "1 +"), None),
    ("compile-isa", ("compile", str(FIXTURES / "functions.isa")), None),
    (
        "compile-operation",
        ("compile", "--root", "instruction_operation", str(FIXTURES / "operation.idl")),
        None,
    ),
    ("check-stdin", ("tc", "inst", "-"), "X[2] = 15;\n"),
    ("check-stdin-separated", ("tc", "inst", "--", "-"), "X[2] = 15;\n"),
    (
        "check-decodes",
        ("tc", "inst", "-d", "xd=5", "-d", "xs1=5", str(FIXTURES / "operation.idl")),
        None,
    ),
    (
        "check-yaml",
        (
            "tc",
            "inst",
            "-k",
            "operation()",
            "-d",
            "xd=5",
            "-d",
            "xs1=5",
            str(FIXTURES / "operation.yaml"),
        ),
        None,
    ),
    ("check-undefined", ("tc", "inst", str(FIXTURES / "operation.idl")), None),
    ("check-strict", ("tc", "inst", "--strict", "-"), "X[2] = 15;\n"),
    ("check-strict-separated", ("tc", "inst", "--strict", "--", "-"), "X[2] = 15;\n"),
    (
        "check-missing-key",
        ("tc", "inst", "-k", "missing", str(FIXTURES / "operation.yaml")),
        None,
    ),
    (
        "check-nonstring",
        ("tc", "inst", "-k", "invalid", str(FIXTURES / "operation.yaml")),
        None,
    ),
)


def main() -> None:
    captures = []
    for name, arguments, stdin in CASES:
        result = subprocess.run(
            ["bundle", "exec", "idlc", *arguments],
            cwd=ROOT,
            input=stdin,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=90,
            check=False,
        )
        captures.append(
            {
                "name": name,
                "arguments": arguments,
                "stdin": stdin,
                "status": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
    sources = [
        Path("tools/ruby-gems/idlc/lib/idlc/cli.rb"),
        Path("tools/ruby-gems/idlc/bin/idlc"),
        Path("tests/python/capture_idl_cli.py"),
        *sorted(FIXTURES.glob("*")),
    ]
    result = {
        "ruby": subprocess.check_output(["ruby", "--version"], text=True).strip(),
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "sources": {
            str(path): hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in sources
            if path.name != "oracle.json"
        },
        "cases": captures,
    }
    (ROOT / FIXTURES / "oracle.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    for capture in captures:
        print(capture["name"], capture["status"], repr(capture["stdout"][:100]))


if __name__ == "__main__":
    main()
