# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Capture original C/SV scripts using the genuine Ruby interpolation rows."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/python/fixtures/generic_codegen"
SCRATCH = ROOT / "gen/handoff/generic-names"
SCRATCH.mkdir(parents=True, exist_ok=True)
for label in () if "--order-only" in sys.argv else ("all", "rv32", "rv64", "full"):
    fixture = FIXTURES / label
    resolved = Path(json.loads((fixture / "manifest.json").read_text())["resolved_path"])
    for script, output, destination in (
        ("c_header/generate_encoding.py", "encoding.out.h", "interpolated-encoding.out.h"),
        ("sverilog/sverilog_generator.py", "riscv_decode_package.svh", "interpolated-decode.svh"),
    ):
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "backends/generators" / script),
                "--inst-dir",
                str(resolved / "inst"),
                "--csr-dir",
                str(resolved / "csr"),
                "--ext-dir",
                str(resolved / "ext"),
                "--resolved-codes",
                str(fixture / "interpolated-exceptions.json"),
                "--include-all",
                "--output",
                str(SCRATCH / output),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        shutil.copyfile(SCRATCH / output, fixture / destination)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "backends/generators/Go/go_generator.py"),
            "--inst-dir",
            str(resolved / "inst"),
            "--csr-dir",
            str(resolved / "csr"),
            "--extensions",
            "",
            "--arch",
            "BOTH",
            "--output",
            str(SCRATCH / "inst.go"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    shutil.copyfile(SCRATCH / "inst.go", fixture / "empty-extension-inst.go")
order = SCRATCH / "name-order"
(order / "inst").mkdir(parents=True, exist_ok=True)
(order / "csr").mkdir(exist_ok=True)
(order / "ext").mkdir(exist_ok=True)
(order / "exceptions.json").write_text("[]")
for name in ("a.rv32", "a0"):
    (order / "inst" / f"{name}.yaml").write_text(
        json.dumps(
            {
                "kind": "instruction",
                "name": name,
                "encoding": {
                    "match": "0000000----------000-----0110011",
                    "variables": [
                        {"name": "x", "location": "24-15"},
                        {"name": "rd", "location": "11-7"},
                    ],
                },
            }
        )
    )
subprocess.run(
    [
        sys.executable,
        str(ROOT / "backends/generators/c_header/generate_encoding.py"),
        "--inst-dir",
        str(order / "inst"),
        "--csr-dir",
        str(order / "csr"),
        "--ext-dir",
        str(order / "ext"),
        "--resolved-codes",
        str(order / "exceptions.json"),
        "--include-all",
        "--output",
        str(order / "encoding.out.h"),
    ],
    capture_output=True,
    text=True,
    check=True,
)
shutil.copyfile(order / "encoding.out.h", FIXTURES / "native-c-suffix-order.h")
print(
    "Captured genuine C suffix-order artifact"
    if "--order-only" in sys.argv
    else "Captured 8 interpolated C/SV, 4 empty-filter Go, and genuine C suffix-order artifacts"
)
