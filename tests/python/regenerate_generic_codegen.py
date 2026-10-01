# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Development-only native loader/renderer matrix; run after the Ruby witness.

The SV script's filtered CLI crashes on list.split; its real library renderer
and loader are captured instead, without changing either. The C script has no
--arch: only its genuine BOTH CLI artifacts are byte oracles; other XLEN cases
capture the native loader's complete instruction/CSR semantics.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/python/fixtures/generic_codegen"
SCRATCH = ROOT / "gen/handoff/generic-matrix"
SCRATCH.mkdir(parents=True, exist_ok=True)
logging.disable(logging.CRITICAL)


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


native = load("generator", "backends/generators/generator.py")
sv = load("native_sv", "backends/generators/sverilog/sverilog_generator.py")
go = load("native_go", "backends/generators/Go/go_generator.py")
sources = [
    "backends/generators/tasks.rake",
    "backends/generators/generator.py",
    "backends/generators/c_header/generate_encoding.py",
    "backends/generators/sverilog/sverilog_generator.py",
    "backends/generators/Go/go_generator.py",
]
payload = {
    "sources": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sources},
    "artifacts": {},
    "cases": [],
    "errors": {},
}


def artifact(text: str) -> str:
    digest = hashlib.sha256(text.encode()).hexdigest()
    payload["artifacts"][digest] = text
    return digest


for config in ("all", "rv32", "rv64", "full"):
    directory = FIXTURES / config
    manifest = json.loads((directory / "manifest.json").read_text())
    resolved = Path(manifest["resolved_path"])
    causes = native.load_exception_codes(
        resolved / "ext", resolved_codes_file=directory / "exceptions.json"
    )
    for arch in ("RV32", "RV64", "BOTH"):
        for mode, extensions, include_all in (
            ("all", (), True),
            ("filtered", ("I", "C", "Zicsr"), False),
            ("empty", (), False),
            (
                "go-default",
                (
                    "A",
                    "D",
                    "F",
                    "I",
                    "M",
                    "Q",
                    "Zba",
                    "Zbb",
                    "Zbs",
                    "S",
                    "System",
                    "V",
                    "Zicsr",
                    "Sm",
                    "H",
                    "U",
                    "Zicntr",
                    "Zihpm",
                ),
                False,
            ),
        ):
            instructions = native.load_instructions(
                resolved / "inst", extensions, include_all, arch
            )
            csrs = native.load_csrs(resolved / "csr", extensions, include_all, arch)
            sv_path = SCRATCH / "riscv_decode_package.svh"
            sv.generate_sverilog(instructions, csrs, causes, sv_path)
            go_path = SCRATCH / "inst.go"
            go.make_go(instructions, csrs, go_path)
            row = {
                "config": config,
                "arch": arch,
                "mode": mode,
                "extensions": extensions,
                "include_all": include_all,
                "instructions": {name: value["match"] for name, value in instructions.items()},
                "csrs": {str(address): name for address, name in sorted(csrs.items())},
                "sv": artifact(sv_path.read_text()),
                "go": artifact(go_path.read_text()),
            }
            if arch == "BOTH":
                output = SCRATCH / "encoding.out.h"
                command = [
                    sys.executable,
                    str(ROOT / sources[2]),
                    "--inst-dir",
                    str(resolved / "inst"),
                    "--csr-dir",
                    str(resolved / "csr"),
                    "--ext-dir",
                    str(resolved / "ext"),
                    "--resolved-codes",
                    str(directory / "exceptions.json"),
                    "--output",
                    str(output),
                ]
                if include_all:
                    command.append("--include-all")
                elif extensions:
                    command.extend(("--extensions", *extensions))
                subprocess.run(command, capture_output=True, text=True, check=True)
                row["c"] = artifact(output.read_text())
            payload["cases"].append(row)

command = [
    sys.executable,
    str(ROOT / sources[3]),
    "--extensions",
    "I",
    "--inst-dir",
    str(resolved / "inst"),
    "--output",
    str(SCRATCH / "unused.svh"),
]
failed = subprocess.run(command, capture_output=True, text=True, check=False)
payload["errors"]["sv_filtered_cli"] = {
    "returncode": failed.returncode,
    "stderr": failed.stderr,
    "classification": "original argparse nargs list passed to str.split",
}
(FIXTURES / "matrix.json").write_text(json.dumps(payload, separators=(",", ":")) + "\n")
print(f"Captured {len(payload['cases'])} cases and {len(payload['artifacts'])} complete artifacts")
