# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from udb.idl.cli import main

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/python/fixtures/idl_cli"
ORACLE = json.loads((FIXTURES / "oracle.json").read_text(encoding="utf-8"))
CORRECTED = {
    "define-equality": "equality",
    "check-stdin": "check-stdin-separated",
    "check-strict": "check-strict-separated",
}


def _run(arguments, *, stdin=None, cwd=ROOT, environment=None):
    env = os.environ | {"PYTHONPATH": str(ROOT / "src")}
    if environment:
        env.update(environment)
    return subprocess.run(
        [sys.executable, "-m", "udb.idl.cli", *arguments],
        input=None if stdin is None else stdin.encode("utf-8"),
        cwd=cwd,
        env=env,
        capture_output=True,
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize("case", ORACLE["cases"], ids=lambda case: case["name"])
def test_standalone_cli_matches_native_contract(case):
    result = _run(case["arguments"], stdin=case["stdin"])
    expected = case
    if case["name"] in CORRECTED:
        expected = next(item for item in ORACLE["cases"] if item["name"] == CORRECTED[case["name"]])
    assert result.returncode == expected["status"], result.stderr.decode("utf-8")
    if case["name"].startswith("compile-"):
        assert YAML(typ="safe").load(result.stdout.decode("utf-8")) == YAML(typ="safe").load(
            expected["stdout"]
        )
    elif expected["status"] == 0:
        assert result.stdout == expected["stdout"].encode("utf-8")
        if case["name"] in ("bits", "defines"):
            assert b"A value was truncated" in result.stderr
            assert b"<expression>" in result.stderr
        else:
            assert result.stderr == b""
    else:
        assert result.stderr
        assert result.stdout == b""


def test_native_capture_sources_are_unchanged():
    for path, digest in ORACLE["sources"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path


def test_compile_json_and_yaml_have_identical_complete_trees(tmp_path):
    source = FIXTURES / "functions.isa"
    json_result = _run(["compile", "--format", "json", str(source)])
    yaml_result = _run(["compile", str(source)])
    assert json_result.returncode == yaml_result.returncode == 0
    assert json.loads(json_result.stdout) == YAML(typ="safe").load(
        yaml_result.stdout.decode("utf-8")
    )
    output = tmp_path / "tree.json"
    written = _run(["compile", "-f", "json", "-o", str(output), str(source)])
    assert written.returncode == 0 and written.stdout == b""
    assert output.read_bytes() == json_result.stdout


def test_source_errors_do_not_truncate_existing_output(tmp_path):
    source = tmp_path / "bad.idl"
    source.write_text("X[2] = ;\n", encoding="utf-8")
    output = tmp_path / "existing.yaml"
    output.write_bytes(b"preserve me\n")
    result = _run(["compile", "-r", "instruction_operation", "-o", str(output), str(source)])
    assert result.returncode == 1 and str(source).encode() in result.stderr
    assert output.read_bytes() == b"preserve me\n"


@pytest.mark.parametrize("binding", ("bad", "=3", "A=", "_A=1", "1A=1"))
def test_define_options_require_an_identifier_and_expression(binding):
    result = _run(["eval", "-D", binding, "1"])
    assert result.returncode == 2 and b"identifier" in result.stderr
    assert result.stdout == b""


@pytest.mark.parametrize("binding", ("xd=0", "xd=-1", "xd=foo", "xd=1_0"))
def test_decode_variables_require_positive_decimal_widths(binding):
    result = _run(["tc", "inst", "-d", binding, "-"], stdin="X[2] = 1;\n")
    assert result.returncode == 2 and b"positive decimal integer" in result.stderr


def test_yaml_diagnostic_points_to_actual_literal_location(tmp_path):
    source = tmp_path / "instruction.yaml"
    source.write_text("name: bad\noperation(): |\n  X[2] = ;\n", encoding="utf-8")
    result = _run(["tc", "inst", "-k", "operation()", str(source)])
    assert result.returncode == 1
    assert f"{source}:3:10".encode() in result.stderr


@pytest.mark.parametrize("style", ("'X[2] = 15;'", '"X[2] = 15;"', ">\n  X[2] = 15;\n"))
def test_cli_yaml_extraction_preserves_legacy_string_styles(tmp_path, style):
    source = tmp_path / "operation.yaml"
    source.write_text(f"operation(): {style}\n", encoding="utf-8")
    result = _run(["tc", "inst", "-k", "operation()", str(source)])
    assert result.returncode == 0, result.stderr.decode("utf-8")


def test_reflowed_yaml_diagnostic_identifies_decoded_scalar(tmp_path):
    source = tmp_path / "operation.yaml"
    source.write_text('operation(): "X[2] = ;"\n', encoding="utf-8")
    result = _run(["tc", "inst", "-k", "operation()", str(source)])
    assert result.returncode == 1 and b"decoded YAML scalar" in result.stderr


@pytest.mark.parametrize(
    "scalar",
    ("X[2] = 1;\n  X[3] = ;", "\n  X[2] = 1;\n  X[3] = ;"),
)
def test_multiline_plain_yaml_is_reported_as_a_decoded_scalar(tmp_path, scalar):
    source = tmp_path / "multiline.yaml"
    source.write_text(f"a: 1\noperation(): {scalar}\n", encoding="utf-8")
    result = _run(["tc", "inst", "-k", "operation()", str(source)])
    assert result.returncode == 1
    assert f"{source} [operation(): decoded YAML scalar]:1:".encode() in result.stderr


def test_single_line_plain_value_after_key_keeps_actual_source_coordinates(tmp_path):
    source = tmp_path / "plain.yaml"
    source.write_text("a: 1\noperation():\n  X[2] = ;\n", encoding="utf-8")
    result = _run(["tc", "inst", "-k", "operation()", str(source)])
    assert result.returncode == 1 and f"{source}:3:10".encode() in result.stderr
    assert b"decoded YAML scalar" not in result.stderr


def test_module_runs_outside_checkout_without_native_tools_and_with_ascii_stdout(tmp_path):
    result = _run(
        ["eval", '"caf\u00e9"'],
        cwd=tmp_path,
        environment={"PATH": "", "PYTHONIOENCODING": "ascii"},
    )
    assert result.returncode == 0 and result.stdout == "caf\u00e9\n".encode("utf-8")


def test_no_state_leaks_between_evaluations(capfd):
    assert main(["eval", "-DA=1", "A"]) == 0
    assert capfd.readouterr().out == "1\n"
    assert main(["eval", "A"]) == 1
    captured = capfd.readouterr()
    assert captured.out == "" and "A" in captured.err


def test_missing_input_and_output_fail_explicitly(tmp_path):
    missing = _run(["compile", str(tmp_path / "missing.isa")])
    assert missing.returncode == 1 and b"missing.isa" in missing.stderr
    output = _run(["eval", "-o", str(tmp_path / "missing" / "result"), "1"])
    assert output.returncode == 1 and b"cannot write IDL output" in output.stderr
    assert not (tmp_path / "missing").exists()
