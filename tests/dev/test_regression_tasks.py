# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).parents[2]

SLOW_TASKS = {
    "test:slow:idl",
    "test:slow:idl-passes",
    "test:slow:idl-conditions",
    "test:slow:idl-environment",
    "test:slow:architecture",
    "test:slow:prose",
    "test:slow:generators",
    "test:slow:extension-pdf",
    "test:slow:layouts",
}

TASK_JOBS = {
    "test": "python-fast",
    "test:slow:idl": "python-slow-idl",
    "test:slow:idl-passes": "python-slow-idl-passes",
    "test:slow:idl-conditions": "python-slow-idl-conditions",
    "test:slow:idl-environment": "python-slow-idl-environment",
    "test:slow:architecture": "python-slow-architecture",
    "test:slow:prose": "python-slow-prose",
    "test:slow:generators": "python-slow-generators",
    "test:slow:extension-pdf": "python-slow-extension-pdf",
    "test:slow:layouts": "python-slow-layouts",
    "test:package": "python-package",
}

RETAINED_JOBS = {
    "llvm",
    "java-tests",
    "vscode-tests",
    "native-bits",
    "softfloat",
    "schema",
    "build-reuse-manifest",
    "resolve-unconfig",
    "build-docs-site",
}

RETAINED_TASK_JOBS = (
    ("check:pre-commit", "pre-commit"),
    ("test:llvm", "llvm"),
    ("test:java", "java-tests"),
    ("test:vscode", "vscode-tests"),
    ("test:cpp-hart", "cpp-hart"),
    ("test:native-bits", "native-bits"),
    ("test:softfloat", "softfloat"),
    ("test:riscv-tests", "riscv-tests-32"),
    ("test:riscv-tests", "riscv-tests-64"),
    ("test:riscv-vector-tests", "riscv-tests-vector"),
    ("check:schema-versions", "schema"),
    ("gen:schema-docs", "schema"),
    ("artifact:reuse-manifest", "build-reuse-manifest"),
    ("artifact:resolved-unconfigured", "resolve-unconfig"),
    ("docs:build", "build-docs-site"),
)


def _task_definitions() -> dict[str, object]:
    return tomllib.loads((ROOT / "tools/dev/tasks.toml").read_text(encoding="utf-8"))


def _discovered_tasks() -> set[str]:
    result = subprocess.run(
        ["mise", "tasks", "--json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "MISE_AUTO_INSTALL": "0"},
    )
    return {task["name"] for task in json.loads(result.stdout)}


def _workflow_jobs() -> dict[str, object]:
    return YAML(typ="safe").load(ROOT / ".github/workflows/regress.yml")["jobs"]


def test_python_test_layers_are_discoverable_and_use_uv() -> None:
    expected = {*TASK_JOBS, "test:slow", "check:all"}
    assert expected <= _discovered_tasks()

    definitions = _task_definitions()
    for name in TASK_JOBS.keys() - {"test:package"}:
        command = definitions[name]["run"]
        assert "uv run python -m pytest" in command
        assert "PYTHONPATH" not in command
        assert "UV_NO_SYNC" not in command
        assert ".venv/bin/python" not in command

    assert "test:python" not in _discovered_tasks()

    package = definitions["test:package"]["run"]
    assert package == "uv run python -m tools.dev.package test"


def test_slow_and_all_aggregates_cover_each_layer_once() -> None:
    definitions = _task_definitions()
    slow_dependencies = definitions["test:slow"]["depends"]
    assert {dependency.split()[0] for dependency in slow_dependencies} == SLOW_TASKS
    assert {
        dependency.rsplit(" ", 1)[-1]
        for dependency in slow_dependencies
        if dependency.startswith("test:slow:idl --config ")
    } == {"_", "rv32", "rv64", "qc_iu"}
    all_dependencies = {dependency.split()[0] for dependency in definitions["check:all"]["depends"]}
    assert all_dependencies == {
        "test",
        "check:pre-commit",
        "test:llvm",
        "test:java",
        "test:vscode",
        "test:slow",
        "test:package",
        "test:cpp-hart",
        "test:native-bits",
        "test:softfloat",
        "test:riscv-tests",
        "test:riscv-vector-tests",
        "check:schema-versions",
        "gen:schema-docs",
        "artifact:reuse-manifest",
        "artifact:resolved-unconfigured",
        "docs:build",
    }
    assert {
        dependency.rsplit(" ", 1)[-1]
        for dependency in definitions["check:all"]["depends"]
        if dependency.startswith("test:riscv-tests -c ")
    } == {"rv32", "rv64"}


def test_slow_idl_config_selector_collects_only_requested_variant() -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "pytest",
            "-n",
            "0",
            "-m",
            "slow",
            "--collect-only",
            "-q",
            "tests/python/test_idl_architecture_real.py",
            "--config",
            "rv32",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "test_actual_architecture_bodies_and_unavailable_coverage[rv32]" in result.stdout
    for other in ("_", "rv64", "qc_iu"):
        assert (
            f"test_actual_architecture_bodies_and_unavailable_coverage[{other}]"
            not in result.stdout
        )


def test_ci_runs_each_parallel_python_layer() -> None:
    jobs = _workflow_jobs()
    assert RETAINED_JOBS <= jobs.keys()
    for task, job_name in (*TASK_JOBS.items(), *RETAINED_TASK_JOBS):
        assert job_name in jobs
        commands = "\n".join(
            step.get("run", "") for step in jobs[job_name]["steps"] if isinstance(step, dict)
        )
        assert f"mise run {task}" in commands


def test_llvm_task_builds_metadata_before_running_encoding_checks() -> None:
    command = _task_definitions()["test:llvm"]["run"]
    assert "tools.dev.native.cli test llvm" in command
    assert "llvm-tblgen" in command and "--dump-json" in command
    assert "-o ext/llvm-project/riscv.json" in command
    assert "uv run python -m pytest -n 0 tools/python/auto-inst/test_parsing.py" in command


def test_legacy_regression_and_ruby_task_interfaces_stay_absent() -> None:
    assert not (ROOT / "tools/dev/regression-aggregates.toml").exists()
    legacy_tasks = ROOT / "tools/dev/regression-tasks"
    assert not any(path.is_file() for path in legacy_tasks.rglob("*"))
    for path in (
        "bin/regress",
        "tools/test/regress-cli.rb",
        "tools/test/gen_regress.py",
        "tools/test/regress-tests.yaml",
        "tools/test/regress-gh-template.yaml",
        "tools/test/tests-schema.json",
    ):
        assert not (ROOT / path).exists()
    assert not any(
        name.startswith("test:ruby:") or "sorbet" in name for name in _discovered_tasks()
    )
