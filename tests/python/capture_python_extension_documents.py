# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Bounded development capture of whole emitted artifacts against frozen native cases."""

from __future__ import annotations

import argparse
import faulthandler
import hashlib
import json
import time
from datetime import date
from pathlib import Path

from extension_documents_helpers import configured_prose_provider

from udb import Configuration, Database, SchemaStore
from udb.extension_docs import DocumentOptions, generate_extension_document
from udb.extension_docs.csrs import CsrSections


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append")
    parser.add_argument("--out", type=Path, default=Path("gen/extension-emitted"))
    args = parser.parse_args()
    root = Path(__file__).parents[2]
    fixture = Path(__file__).parent / "fixtures/extension_docs/manifest.json"
    native = json.loads(fixture.read_text())
    outcomes = []
    original_render = CsrSections.render

    def progress(self, csr):
        print("CSR", csr.name, flush=True)
        return original_render(self, csr)

    CsrSections.render = progress
    faulthandler.dump_traceback_later(120, repeat=True)
    for case in native["outcomes"]:
        if not case["ok"] or (args.case and case["id"] not in args.case):
            continue
        start = time.monotonic()
        cfg = case["cfg"]
        if cfg in ("_", "rv32", "rv64"):
            configuration = Configuration.builtin(cfg)
        else:
            configuration = Configuration.from_file(
                root / "cfgs" / ("qc_iu.yaml" if cfg == "qc_iu" else Path(cfg).name),
                schema_store=SchemaStore(root / "spec/schemas"),
            )
        overlays = (
            (root / "spec/custom/isa" / configuration.overlay,) if configuration.overlay else ()
        )
        database = Database.from_path(
            root / "spec/std/isa", schemas_path=root / "spec/schemas"
        ).resolve(overlays=overlays)
        architecture = database.configure(configuration)
        selectors = case.get("selectors")
        if selectors is None:
            argv = case["argv"]
            selectors = argv[argv.index("--no-csr-field-desc") + 1 :]
        print("Generating", case["id"], selectors, flush=True)
        options = DocumentOptions(
            basename=case["id"],
            revision=native["head"],
            today=date(2026, 10, 1),
            include_implied="-i" in case["argv"],
            # Preserve the native complete field content for the parity artifact.
            # The separately tested field-summary flag now does what it promises.
            include_csr_field_descriptions=True,
            prose=configured_prose_provider(architecture),
        )
        try:
            target = generate_extension_document(architecture, selectors, args.out, options=options)
            data = target.read_bytes()
            outcomes.append(
                {
                    "id": case["id"],
                    "ok": True,
                    "artifact": str(target),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                    "elapsed": time.monotonic() - start,
                }
            )
            print("Wrote", target, len(data), "bytes", flush=True)
        except Exception as error:
            outcomes.append(
                {
                    "id": case["id"],
                    "ok": False,
                    "error": repr(error),
                    "elapsed": time.monotonic() - start,
                }
            )
            print("FAILED", case["id"], repr(error), flush=True)
            raise
        finally:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / "manifest.json").write_text(
                json.dumps(outcomes, indent=2), encoding="utf-8"
            )
    faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    main()
