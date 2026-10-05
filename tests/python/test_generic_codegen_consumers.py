# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Compile complete artifacts using the real C, SV and Go consumer interfaces."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from udb import Database
from udb.generators.c_encoding import generate_c_encoding
from udb.generators.encoding_inputs import ExceptionRecord
from udb.generators.go import generate_go
from udb.generators.sv_decode import generate_sv_decode

FIXTURES = Path(__file__).parent / "fixtures/generic_codegen"
pytestmark = pytest.mark.skipif(
    os.environ.get("UDB_TEST_GENERIC_TOOLS") != "1",
    reason="generic native consumer checks are opt-in",
)


@pytest.fixture(scope="module")
def database():
    return Database.from_path("spec/std/isa", schemas_path="spec/schemas").resolve()


@pytest.fixture
def output_dir():
    path = Path("gen/test-generic-consumers") / str(uuid4())
    path.mkdir(parents=True)
    try:
        yield path.resolve()
    finally:
        shutil.rmtree(path)


def command(arguments, *, cwd, env=None):
    result = subprocess.run(
        arguments, cwd=cwd, env=env, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def exception_rows():
    return tuple(
        ExceptionRecord.from_mapping(row)
        for row in json.loads((FIXTURES / "all/exceptions.json").read_text())
    )


def test_c_all_instruction_csr_cause_consumer(database, output_dir):
    native = (FIXTURES / "all/encoding.out.h").read_text()
    matches = dict(re.findall(r"#define MATCH_(\w+) (0x[0-9a-f]+)", native))
    masks = dict(re.findall(r"#define MASK_(\w+) (0x[0-9a-f]+)", native))
    insns = re.findall(r"DECLARE_INSN\((\w+), MATCH_(\w+), MASK_\w+\)", native)
    csrs = re.findall(r"#define CSR_(\w+) (0x[0-9a-f]+)", native)
    causes = re.findall(r"#define CAUSE_(\w+) (0x[0-9a-f]+)", native)
    (output_dir / "encoding.h").write_text(
        generate_c_encoding(database, exception_records=exception_rows())
    )
    expected_insns = ",\n".join(
        f'{{"{name}", {matches[constant]}, {masks[constant]}}}' for name, constant in insns
    )
    expected_csrs = ",\n".join(f'{{"{name.lower()}", {value}}}' for name, value in csrs)
    expected_causes = ",\n".join(f'{{"{name.lower()}", {value}}}' for name, value in causes)
    source = f"""#include <stdint.h>
#include <string.h>
#include "encoding.h"
struct insn {{ const char *name; uint32_t match, mask; }};
struct reg {{ const char *name; unsigned num; }};
static const struct insn actual_insns[] = {{
#define DECLARE_INSN(name, match, mask) {{#name, match, mask}},
#include "encoding.h"
#undef DECLARE_INSN
}};
static const struct reg actual_csrs[] = {{
#define DECLARE_CSR(name, num) {{#name, num}},
#include "encoding.h"
#undef DECLARE_CSR
}};
static const struct reg actual_causes[] = {{
#define DECLARE_CAUSE(name, num) {{name, num}},
#include "encoding.h"
#undef DECLARE_CAUSE
}};
static const struct insn expected_insns[] = {{ {expected_insns} }};
static const struct reg expected_csrs[] = {{ {expected_csrs} }};
static const struct reg expected_causes[] = {{ {expected_causes} }};
_Static_assert(sizeof actual_insns == sizeof expected_insns, "all instruction declarations");
_Static_assert(sizeof actual_csrs == sizeof expected_csrs, "all CSR declarations");
_Static_assert(sizeof actual_causes == sizeof expected_causes, "all cause declarations");
_Static_assert(INSN_FIELD_OPCODE == 0x7f, "public field masks");
int main(void) {{
  for (unsigned i = 0; i < sizeof actual_insns / sizeof *actual_insns; ++i)
    if (strcmp(actual_insns[i].name, expected_insns[i].name) ||
        actual_insns[i].match != expected_insns[i].match ||
        actual_insns[i].mask != expected_insns[i].mask) return 1;
  for (unsigned i = 0; i < sizeof actual_csrs / sizeof *actual_csrs; ++i)
    if (strcmp(actual_csrs[i].name, expected_csrs[i].name) ||
        actual_csrs[i].num != expected_csrs[i].num) return 2;
  for (unsigned i = 0; i < sizeof actual_causes / sizeof *actual_causes; ++i)
    if (strcmp(actual_causes[i].name, expected_causes[i].name) ||
        actual_causes[i].num != expected_causes[i].num) return 3;
  return 0;
}}
"""
    (output_dir / "consumer.c").write_text(source)
    command(
        ["gcc", "-std=c11", "-Wall", "-Wextra", "-Werror", "consumer.c", "-o", "consumer"],
        cwd=output_dir,
    )
    command([str(output_dir / "consumer")], cwd=output_dir)
    assert len(insns) == 1394 and len(csrs) == 413 and len(causes) == 22


def test_sv_complete_decode_package_lints(database, output_dir):
    verilator = shutil.which("verilator")
    assert verilator is not None, "SV acceptance requires verilator (mise tool environment)"
    native = (FIXTURES / "all/riscv_decode_package.svh").read_text()
    actual = generate_sv_decode(database, exception_records=exception_rows())
    (output_dir / "riscv_decode_package.svh").write_text(actual)
    # Every real declaration is a reference in a consumer, including the
    # compressed masks. Wildcards remain 4-state values rather than zeros.
    declarations = re.findall(r"localparam logic \[(\d+):0\] (\w+)\s+= ([^;]+);", native)
    references = "\n".join(
        f"    if (riscv_decode_package::{name} !== {value}) $fatal(1);"
        for _, name, value in declarations
    )
    (output_dir / "consumer.sv").write_text(f"""`include "riscv_decode_package.svh"
module generic_consumer;
  initial begin
{references}
  end
endmodule
""")
    command(
        [verilator, "--lint-only", "--top-module", "generic_consumer", "consumer.sv"],
        cwd=output_dir,
    )
    assert len(declarations) == 1394 + 413 + 22


def test_go_complete_real_obj_package_adaptor(database, output_dir):
    go = shutil.which("go")
    assert go is not None, "Go acceptance requires Go on PATH"
    native = (FIXTURES / "all/inst.go").read_text()
    cases = re.findall(r"case (\w+):\s+return &inst\{([^}]+)\}", native)
    csrs = re.findall(r'(0x[0-9a-f]+) : "(\w+)",', native)
    # The old output is a cmd/internal/obj assembler fragment, not an
    # independent package. Use the real standard-library obj.As type and supply
    # only the downstream assembler opcode enumeration it intentionally omits.
    (output_dir / "inst.go").write_text(generate_go(database))
    constants = "\n".join(f"\t{name}" for name, _ in cases)
    (output_dir / "opcodes.go").write_text(f"""package riscv
import "cmd/internal/obj"
const (
\tAUNDEFINED obj.As = iota
{constants}
)
""")
    expected = ",\n".join(f"{{{name}, inst{{{values}}}}}" for name, values in cases)
    expected_csrs = ",\n".join(f'{address}: "{name}"' for address, name in csrs)
    (output_dir / "verify.go").write_text(f"""package riscv
import "cmd/internal/obj"
func VerifyAllNativeEncodings() bool {{
  expected := []struct {{ as obj.As; value inst }} {{ {expected}, }}
  for _, row := range expected {{
    got := encode(row.as)
    if got == nil || *got != row.value {{ return false }}
  }}
  if encode(AUNDEFINED) != nil {{ return false }}
  wantCSRs := map[uint16]string {{ {expected_csrs}, }}
  if len(csrs) != len(wantCSRs) {{ return false }}
  for address, name := range wantCSRs {{
    if csrs[address] != name {{ return false }}
  }}
  return true
}}
""")
    env = {
        **os.environ,
        "GOWORK": "off",
        "GOTOOLCHAIN": "local",
        "GOPROXY": "off",
        "GOSUMDB": "off",
        "GOFLAGS": "-p=1",
        "GOCACHE": str(output_dir / "go-cache"),
        "GOTMPDIR": str(output_dir / "go-scratch"),
    }
    (output_dir / "go-scratch").mkdir()
    # `go test` outside GOROOT rightly refuses cmd/internal/obj. Compile and
    # link against Go's *actual* exported obj archive via the compiler's normal
    # importcfg interface, without rewriting imports, copying a toolchain,
    # symlinking dependencies or writing into the shared GOROOT.
    exports = command(
        [go, "list", "-deps", "-export", "-json", "cmd/internal/obj"], cwd=output_dir, env=env
    )
    decoder = json.JSONDecoder()
    packages = []
    while exports.strip():
        package, end = decoder.raw_decode(exports.lstrip())
        packages.append(package)
        exports = exports.lstrip()[end:]
    imports = [
        f"packagefile {package['ImportPath']}={package['Export']}"
        for package in packages
        if package.get("Export")
    ]
    (output_dir / "importcfg").write_text("\n".join(imports) + "\n")
    command(
        [
            go,
            "tool",
            "compile",
            "-p",
            "cmd/udb_generic_codegen",
            "-importcfg",
            "importcfg",
            "-pack",
            "-o",
            "inst.a",
            "inst.go",
            "opcodes.go",
            "verify.go",
        ],
        cwd=output_dir,
        env=env,
    )
    with (output_dir / "importcfg").open("a") as stream:
        stream.write(f"packagefile cmd/udb_generic_codegen={output_dir / 'inst.a'}\n")
    (output_dir / "main.go").write_text("""package main
import riscv "cmd/udb_generic_codegen"
func main() {
  if !riscv.VerifyAllNativeEncodings() { panic("native encoder/CSR parity failure") }
}
""")
    command(
        [
            go,
            "tool",
            "compile",
            "-p",
            "main",
            "-importcfg",
            "importcfg",
            "-pack",
            "-o",
            "main.a",
            "main.go",
        ],
        cwd=output_dir,
        env=env,
    )
    command(
        [
            go,
            "tool",
            "link",
            "-importcfg",
            "importcfg",
            "-o",
            "consumer",
            "main.a",
        ],
        cwd=output_dir,
        env=env,
    )
    command([str(output_dir / "consumer")], cwd=output_dir, env=env)
    assert len(cases) == 1236 and len(csrs) == 165
