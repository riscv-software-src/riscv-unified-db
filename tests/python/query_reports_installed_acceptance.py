# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Run with the *installed* interpreter, outside checkout; no pytest dependency.

    python query_reports_installed_acceptance.py /explicit/frozen/fixtures

Only the explicit evidence/overlay files are opened outside package resources.
The parent package gate should copy this helper and the query_reports fixtures
into its acceptance area, with PYTHONPATH removed and an empty executable PATH.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ruamel.yaml import YAML

import udb
from udb import Configuration, Database
from udb.query_reports import (
    InstructionMatcher,
    ReportBuilder,
    render_extension,
    render_names,
    render_parameter,
)
from udb.query_reports.cli import main


def _forbidden(*args, **kwargs):
    raise AssertionError(
        "installed reports must not discover a checkout, execute tools, or access the network"
    )


def run(fixtures: Path, *, require_installed: bool = True) -> dict[str, int]:
    if require_installed:
        assert Path(udb.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), udb.__file__
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    auxiliary = json.loads((fixtures / "native-auxiliary-manifest.json").read_text())
    for name, expected in auxiliary["outputs"].items():
        assert hashlib.sha256((fixtures / name).read_bytes()).hexdigest() == expected

    def native(name):
        observation = manifest["cases"][name]
        output = (fixtures / f"{name}.stdout.txt").read_bytes()
        assert hashlib.sha256(output).hexdigest() == observation["stdout_sha256"]
        return output

    with (
        patch.object(Database, "from_path", _forbidden),
        patch("subprocess.Popen", _forbidden),
        patch("socket.socket.connect", _forbidden),
        patch("socket.create_connection", _forbidden),
        patch("shutil.which", _forbidden),
    ):
        database = Database.bundled().resolve()
        builders = {
            name: ReportBuilder(database.configure(Configuration.builtin(name)))
            for name in ("_", "rv32", "rv64")
        }
        full_config = fixtures / "native-full-config.yaml"
        assert (
            hashlib.sha256(full_config.read_bytes()).hexdigest()
            == manifest["sources"]["cfgs/mc100-32-full-example.yaml"]
        )
        builders["full"] = ReportBuilder(database.configure(Configuration.from_file(full_config)))
        builder = builders["_"]
        artifacts = 0
        for name in ("I", "Zicsr", "C"):
            assert render_extension(builder.extension(name), name).encode() == native(
                f"show-extension-{name}"
            )
            artifacts += 1
        for name in ("MXLEN", "SXLEN", "ARCH_ID_VALUE", "NUM_PMP_ENTRIES"):
            assert render_parameter(builder.parameter(name), name).encode() == native(
                f"show-parameter-{name}"
            )
            artifacts += 1
        assert render_extension(
            builder.extension("NoSuchExtension"), "NoSuchExtension"
        ).encode() == native("show-extension-missing")
        assert render_parameter(
            builder.parameter("NO_SUCH_PARAMETER"), "NO_SUCH_PARAMETER"
        ).encode() == native("show-parameter-missing")
        for config, suffix in (("_", "all"), ("rv32", "rv32"), ("full", "full")):
            assert render_names(builders[config].extensions()).encode() == native(
                f"list-extensions-{suffix}"
            )
            artifacts += 1
        assert render_names(builder.csrs()).encode() == native("list-csrs-all")
        for extension in ("I", "Sm"):
            report = builder.parameters([extension])
            assert report.render().encode() == native(f"list-parameters-{extension}-ascii")
            assert report.to_data() == json.loads(native(f"list-parameters-{extension}-json"))
            assert YAML(typ="safe").load(report.render("yaml")) == YAML(typ="safe").load(
                native(f"list-parameters-{extension}-yaml")
            )
            artifacts += 3
        expected = json.loads(native("list-parameters-all-json"))
        corrections = json.loads((fixtures / "native-description-observations.json").read_text())
        for row in expected:
            if row["name"] in corrections:
                evidence = corrections[row["name"]]
                assert row["description"] == evidence["psych_native_resolved_description"]
                row["description"] = evidence["psych_source_description"]
        assert builder.parameters().to_data() == expected
        full_rows = json.loads(native("list-parameters-full-json"))
        for row in full_rows:
            if row["name"] in corrections:
                evidence = corrections[row["name"]]
                assert row["description"] == evidence["psych_native_resolved_description"]
                row["description"] = evidence["psych_source_description"]
        assert builders["full"].parameters().to_data() == full_rows
        assert render_names(builders["full"].csrs()).encode() == native("list-csrs-full")
        assert builders["full"].parameter("MXLEN").render().encode() == native(
            "show-parameter-full-MXLEN"
        )
        artifacts += 3
        matcher = InstructionMatcher(builder.architecture)
        for name, encoding in (
            ("addi", "fff10093"),
            ("compressed", "0001"),
            ("xlen-dependent", "2081"),
            ("rv64-only", "00003003"),
            ("illegal", "ffffffff"),
            ("zero", "0"),
            ("overwide", "100000013"),
        ):
            assert matcher.match(encoding).render().encode() == native(f"disasm-{name}")
            artifacts += 1
        variables = matcher.match("fff10093", width=32).results[0].matches[0].variables
        assert [(field.name, field.value) for field in variables] == [
            ("imm", -1),
            ("xs1", 2),
            ("xd", 1),
        ]
        for config in ("rv32", "rv64"):
            assert InstructionMatcher(builders[config].architecture).match(
                "00003003"
            ).render().encode() == native(f"disasm-{config}")
            artifacts += 1
        full_matcher = InstructionMatcher(builders["full"].architecture)
        assert full_matcher.match("00003003").render().encode() == native("disasm-full-catalog")
        assert full_matcher.match("00003003", selection="possible").results[0].illegal
        artifacts += 1
        overlay = Database.bundled().resolve(overlays=[fixtures / "overlay"])
        report = InstructionMatcher(overlay.configure(Configuration.builtin("_"))).match("13")
        assert report.render().encode() == native("disasm-custom-ambiguous")
        assert report.results[1].ambiguous
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            assert main(["show", "parameter", "MXLEN"]) == 0
            assert main(["disasm", "0xz"]) == 1
        assert stdout.getvalue().encode() == native("show-parameter-MXLEN")
        assert stderr.getvalue().encode() == (fixtures / "disasm-malformed.stderr.txt").read_bytes()
    return {
        "native_artifacts": artifacts + 6,
        "unfiltered_parameter_rows": len(expected),
        "scalar_corrections": len(corrections),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("fixtures", type=Path)
    parser.add_argument(
        "--allow-source",
        action="store_true",
        help="development validation only; never use in installed package gates",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.fixtures.resolve(), require_installed=not args.allow_source), sort_keys=True
        )
    )
