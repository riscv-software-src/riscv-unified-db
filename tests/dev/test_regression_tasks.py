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

ROW_TASK_JOB = (
    (
        "regress-python-extension-documents",
        "test:python:extension-documents",
        "python-docs-headers",
    ),
    ("regress-python-config-headers", "test:python:config-headers", "python-docs-headers"),
    ("regress-python-profile-configs", "test:python:profile-configs", "python-docs-headers"),
    ("regress-python-conditions-parity", "test:python:conditions-parity", "python-parity"),
    ("regress-python-configured-parity", "test:python:configured-parity", "python-parity"),
    ("regress-python-configuration-parity", "test:python:configuration-parity", "python-parity"),
    ("regress-python-domain-parity", "test:python:domain-parity", "python-parity"),
    ("regress-python-versions-parity", "test:python:versions-parity", "python-parity"),
    ("regress-python-resolution-parity", "test:python:resolution-parity", "python-parity"),
    ("regress-python-idl-syntax-parity", "test:python:idl-syntax-parity", "python-idl"),
    ("regress-python-idl-expression-parity", "test:python:idl-expression-parity", "python-idl"),
    ("regress-python-idl-statement-parity", "test:python:idl-statement-parity", "python-idl"),
    ("regress-python-idl-architecture", "test:python:idl-architecture", "python-idl"),
    ("regress-python-idl-pass-parity", "test:python:idl-pass-parity", "python-idl"),
    ("regress-python-idl-condition-parity", "test:python:idl-condition-parity", "python-idl"),
    ("regress-python-layout-drift", "test:python:layout-drift", "python-core"),
    (
        "regress-python-configured-prose-frozen",
        "test:python:configured-prose-frozen",
        "python-core",
    ),
    ("regress-python-query-reports", "test:python:query-reports", "python-core"),
    ("regress-python-unit", "test:python:unit", "python-core"),
    ("regress-scripts-unit", "test:ruby:scripts-unit", "ruby-tools"),
    ("regress-idlc-unit", "test:ruby:idlc-unit", "ruby-tools"),
    ("regress-udb-helpers-unit", "test:ruby:udb-helpers-unit", "ruby-tools"),
    ("regress-udb-gen-unit", "test:ruby:udb-gen-unit", "ruby-tools"),
    ("regress-udb-gen-integration", "test:ruby:udb-gen-integration", "ruby-tools"),
    ("regress-udb-gen-chore", "test:ruby:udb-gen-fixtures", "ruby-tools"),
    ("regress-sorbet", "test:ruby:sorbet", "ruby-tools"),
    ("regress-idl-typecheck-smoke", "test:idl:typecheck:smoke", "idl-typecheck-smoke"),
    ("regress-idl-typecheck-other", "test:idl:typecheck:other", "idl-typecheck-other"),
    (
        "regress-test-inst-encodings",
        "test:validation:instruction-encodings",
        "validation-generation",
    ),
    ("regress-gen-ext-pdf", "test:generation:extension-pdf", "validation-generation"),
    (
        "regress-profile-strict-cfg",
        "test:generation:profile-strict-configs",
        "validation-generation",
    ),
    ("regress-udb-unit-test", "test:ruby:udb-unit", "udb-unit-test"),
    ("regress-gen-go", "test:generation:go", "generic-generators"),
    ("regress-gen-c-header", "test:generation:c-header", "generic-generators"),
    ("regress-gen-sverilog", "test:generation:systemverilog", "generic-generators"),
    ("regress-cfg-headers", "test:fixtures:config-headers", "validation-generation"),
    ("regress-native-bits", "test:ci:native-bits", "native-bits"),
    ("regress-cpp-unit", "test:cpp:unit", "cpp-unit"),
    ("regress-riscv-tests-32", "test:isa:rv32", "riscv-tests-32"),
    ("regress-riscv-tests-64", "test:isa:rv64", "riscv-tests-64"),
    ("regress-riscv-tests-vector", "test:isa:vector", "riscv-tests-vector"),
    ("regress-build-udb-gem", "test:ruby:build-udb-gem", "build-udb-gem"),
    ("regress-regress", "check:all", None),
    ("build-reuse-manifest", "artifact:reuse-manifest", "build-reuse-manifest"),
    ("build-udb-api-docs", "artifact:ruby-api-docs", "build-udb-api-docs"),
    ("resolve-unconfig", "artifact:resolved-unconfigured", "resolve-unconfig"),
    ("regress-schema-versions", "test:schema:versions", "schema"),
    ("regress-schema-docs", "test:schema:docs", "schema"),
    ("build-idl-doc", "artifact:idl-doc", "build-idl-doc"),
    ("check-gem-versions", "test:ruby:gem-versions", "schema"),
    ("regress-smoke-perf", "test:performance:smoke", "smoke-perf"),
    ("build-docs-site", "artifact:docs-site", "build-docs-site"),
)


def _workflow_jobs() -> dict[str, object]:
    return YAML(typ="safe").load(ROOT / ".github/workflows/regress.yml")["jobs"]


def test_every_legacy_row_has_one_unique_task_and_workflow_job() -> None:
    rows = [row for row, _, _ in ROW_TASK_JOB]
    tasks = [task for _, task, _ in ROW_TASK_JOB]
    assert len(rows) == len(set(rows)) == 52
    assert len(tasks) == len(set(tasks)) == 52

    discovered = json.loads(
        subprocess.run(
            ["mise", "tasks", "--json"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "MISE_AUTO_INSTALL": "0"},
        ).stdout
    )
    discovered_names = {task["name"] for task in discovered}
    jobs = _workflow_jobs()
    for _, task, job_name in ROW_TASK_JOB:
        assert task in discovered_names
        if job_name is None:
            continue
        assert job_name in jobs
        commands = "\n".join(
            step.get("run", "") for step in jobs[job_name]["steps"] if isinstance(step, dict)
        )
        assert f"mise run {task}" in commands
    assert "aggregate-all" not in jobs
    assert "aggregate-all" not in jobs["regress-complete"]["needs"]


def test_check_all_contains_every_executable_regression_task() -> None:
    aggregates = tomllib.loads((ROOT / "tools/dev/regression-aggregates.toml").read_text())
    dependencies = {dependency.split()[0] for dependency in aggregates["check:all"]["depends"]}
    expected = {task for _, task, _ in ROW_TASK_JOB if task != "check:all"}
    assert dependencies == expected


def test_removed_regression_generator_interfaces_stay_absent() -> None:
    for path in (
        "bin/regress",
        "tools/test/regress-cli.rb",
        "tools/test/gen_regress.py",
        "tools/test/regress-tests.yaml",
        "tools/test/regress-gh-template.yaml",
        "tools/test/tests-schema.json",
    ):
        assert not (ROOT / path).exists()
