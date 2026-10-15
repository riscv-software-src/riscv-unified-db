# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Capture real Ruby results; never imported by production or offline tests."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/python/fixtures/configured_prose.json"
RUBY_LOCK = Path(
    "/home/jcarlin/.copilot/session-state/e7cf3328-386d-40d9-b677-2d92e44c2ebb/files/ruby.lock"
)


def ruby_capture(payload: dict, label: str, script: Path | None = None) -> dict | list:
    scratch = ROOT / "gen/handoff/prose-ruby-scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    stem = label
    index = 1
    while (scratch / f"{label}-payload.json").exists():
        index += 1
        label = f"{stem}-{index}"
    (scratch / f"{label}-payload.json").write_text(json.dumps(payload, indent=2) + "\n")
    result = subprocess.run(
        [
            "flock",
            str(RUBY_LOCK),
            "mise",
            "exec",
            "--no-deps",
            "--",
            "bundle",
            "exec",
            "ruby",
            str(script or ROOT / "tests/python/ruby_configured_prose_oracle.rb"),
            str(ROOT),
        ],
        cwd=ROOT,
        env={**os.environ, "TMPDIR": str(scratch)},
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    (scratch / f"{label}-stdout.jsonl").write_text(result.stdout)
    (scratch / f"{label}-stderr.log").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(result.stderr[-12000:] or result.stdout[-12000:])
    return json.loads(result.stdout.splitlines()[-1])


def supplement() -> None:
    """Append new evidence in separate artifacts; never recapture the original."""
    original = json.loads(CORPUS.read_text())
    scratch = ROOT / "gen/handoff/prose-ruby-scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    base = original["configurations"]["cache-small"]["declaration"]
    configurations = {}
    yaml = YAML()
    for name, pmp, pma in (
        ("cache-equal", 6, 8),
        ("cache-above", 7, 8),
        ("cache-below", 5, 8),
        ("cache-second-equal", 8, 6),
        ("cache-second-below", 8, 5),
    ):
        declaration = {
            **base,
            "name": name,
            "params": {**base["params"], "PMP_GRANULARITY": pmp, "PMA_GRANULARITY": pma},
        }
        path = scratch / f"{name}.yaml"
        with path.open("w") as stream:
            yaml.dump(declaration, stream)
        configurations[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "declaration": declaration,
            "source_text": path.read_text(),
        }
    path = ROOT / "cfgs/mc100-32-full-example.yaml"
    configurations["mc100-full"] = {
        "path": path.relative_to(ROOT).as_posix(),
        "declaration": YAML(typ="safe").load(path.read_text()),
        "source_text": path.read_text(),
    }
    payload = {
        "templates": original["templates"],
        "extension_queries": original["extension_queries"],
        "configurations": configurations,
        "capture_validity": True,
    }
    captures = ruby_capture(payload, "supplement")
    data = {
        "baseline": original["baseline"],
        "templates": original["templates"],
        "extension_queries": original["extension_queries"],
        "configurations": configurations,
        "captures": captures,
        "tag_inventory": original["tag_inventory"],
        "corrections": original["corrections"],
    }
    target = CORPUS.with_name("configured_prose_supplement.json")
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    names_count = capture_names(original)
    print(
        f"Captured supplement: {len(captures)} configurations; {names_count} templated-name cases"
    )


def capture_names(original: dict) -> int:
    """Controlled name identities are unrendered inputs to the real wrapper."""
    templates = {
        "Breakpoint": "<% if ext?(:C) %>Compressed<% else %>Base<% end %>Breakpoint",
        "InstructionGuestPageFault": "<% if ext?(:H) %>Guest<% else %>Host<% end %>Fault",
    }
    names_payload = {
        "templates": [],
        "extension_queries": original["extension_queries"],
        "configurations": {
            name: original["configurations"][name] for name in ("_", "h64", "full64", "qc_iu")
        },
        "code_name_templates": templates,
    }
    for config in names_payload["configurations"].values():
        path = ROOT / config["path"]
        if path.suffix == ".yaml" and not path.exists():
            path.write_text(config["source_text"])
    names = ruby_capture(names_payload, "templated-names")
    CORPUS.with_name("configured_prose_names.json").write_text(
        json.dumps(
            {"templates": templates, "captures": names},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    return len(names)


def capture_whitespace() -> None:
    """Recapture the frozen probe inputs, never use their expected text as input."""
    target = CORPUS.with_name("configured_prose_whitespace.json")
    templates = [case["template"] for case in json.loads(target.read_text())]
    raw = ruby_capture({"templates": templates, "whitespace_probe": True}, "whitespace")
    target.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
    print(f"Captured {len(raw)} untouched Tilt/Erubi whitespace outcomes")


def scalars(value: object, path: tuple[str | int, ...] = ()) -> Iterator[tuple[tuple, str]]:
    if isinstance(value, str) and "<%" in value:
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from scalars(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from scalars(item, (*path, index))


def inventory() -> list[dict]:
    yaml = YAML(typ="safe")
    templates = []
    for directory in ("csr", "inst"):
        for source in sorted((ROOT / "spec/std/isa" / directory).rglob("*.yaml")):
            text = source.read_text()
            for path, template in scalars(yaml.load(text)):
                templates.append(
                    {
                        "source": source.relative_to(ROOT).as_posix(),
                        "path": path,
                        "sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "template": template,
                    }
                )
    return templates


def main() -> None:
    scratch = ROOT / "gen/handoff/prose-ruby-scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    base = {
        "$schema": "config_schema.json#",
        "kind": "architecture configuration",
        "type": "fully configured",
        "description": "Captured configured-prose input variant",
        "implemented_extensions": [
            {"name": "Sm", "version": "= 1.13"},
            {"name": "I", "version": "= 2.1"},
        ],
        "params": {"MXLEN": 64},
    }
    variants = {
        "full64": ({}, []),
        "h64": (
            {"SXLEN": [64], "UXLEN": [64], "VSXLEN": [64], "VUXLEN": [64]},
            ["S", "U", "H", "Sv48", "Smaia", "C"],
        ),
        "h64-mixed-sv57": (
            {
                "SXLEN": [32, 64],
                "UXLEN": [64],
                "VSXLEN": [64],
                "VUXLEN": [64],
                "CACHE_BLOCK_SIZE": 64,
                "PMP_GRANULARITY": 8,
                "PMA_GRANULARITY": 8,
            },
            [
                "S",
                "U",
                "H",
                "Sv39",
                "Sv48",
                "Sv57",
                "Smaia",
                "C",
                "Smcdeleg",
                "Smcntrpmf",
                "Ssccfg",
                "Sscofpmf",
                "Sstc",
                "V",
                "Zicntr",
                "Zilsd",
                "Zicbom",
            ],
        ),
        "cache-small": (
            {"CACHE_BLOCK_SIZE": 64, "PMP_GRANULARITY": 8, "PMA_GRANULARITY": 8},
            ["Zicbom"],
        ),
        "cache-large": (
            {"CACHE_BLOCK_SIZE": 64, "PMP_GRANULARITY": 2, "PMA_GRANULARITY": 3},
            ["Zicbom"],
        ),
        "cache-unknown": ({}, ["Zicbom"]),
        "cache-malformed": (
            {"CACHE_BLOCK_SIZE": "bad", "PMP_GRANULARITY": 2, "PMA_GRANULARITY": 3},
            ["Zicbom"],
        ),
        "cache-min-unknown": (
            {"CACHE_BLOCK_SIZE": 64, "NUM_PMP_ENTRIES": 16},
            ["Zicbom"],
        ),
        "cache-min-malformed": (
            {"CACHE_BLOCK_SIZE": 64, "PMP_GRANULARITY": "bad", "PMA_GRANULARITY": 3},
            ["Zicbom"],
        ),
        "cache-min-unavailable": (
            {"CACHE_BLOCK_SIZE": 64, "PMA_GRANULARITY": 8},
            ["Zicbom"],
        ),
    }
    configurations = {name: {"path": name} for name in ("_", "rv32", "rv64", "qc_iu")}
    for name, (params, extensions) in variants.items():
        declaration = {
            **base,
            "name": name,
            "params": {**base["params"], **params},
            "implemented_extensions": [
                *base["implemented_extensions"],
                *({"name": ext, "version": ">= 0"} for ext in extensions),
            ],
        }
        # Full configuration requires an exact selection. Use the latest source version.
        safe = YAML(typ="safe")
        for ext in declaration["implemented_extensions"][2:]:
            data = safe.load((ROOT / f"spec/std/isa/ext/{ext['name']}.yaml").read_text())
            ext["version"] = "= " + data["versions"][-1]["version"]
        file = scratch / f"{name}.yaml"
        with file.open("w") as stream:
            yaml.dump(declaration, stream)
        configurations[name] = {
            "path": file.relative_to(ROOT).as_posix(),
            "declaration": declaration,
            "source_text": file.read_text(),
        }
    safe = YAML(typ="safe")
    for name in ("rv32", "rv64", "qc_iu"):
        text = (ROOT / f"cfgs/{name}.yaml").read_text()
        configurations[name]["declaration"] = safe.load(text)
        configurations[name]["source_text"] = text
    templates = inventory()
    queries = {}
    for item in templates:
        for name, requirement in re.findall(
            r'ext\?\(:([A-Za-z0-9_]+)(?:,\s*"([^"]+)")?\)', item["template"]
        ):
            key = name + (f"@{requirement}" if requirement else "")
            queries[key] = {
                "key": key,
                "name": name,
                "requirements": [requirement] if requirement else [],
            }
    payload = {
        "templates": templates,
        "configurations": configurations,
        "extension_queries": list(queries.values()),
    }
    captures = ruby_capture(payload, "original")
    corpus = {
        "baseline": "d6b06ca3",
        "templates": templates,
        "extension_queries": list(queries.values()),
        "configurations": configurations,
        "captures": captures,
        "tag_inventory": [
            {"body": body, "occurrences": count}
            for body, count in sorted(
                Counter(
                    body
                    for item in templates
                    for body in re.findall(r"<%(.*?)%>", item["template"], re.DOTALL)
                ).items()
            )
        ],
        "corrections": [
            "cfg_arch.rb implemented_interrupt_codes uses exception codes",
            "full cfg_arch.to_condition does not exclude undeclared extensions in code tables",
        ],
    }
    CORPUS.parent.mkdir(parents=True, exist_ok=True)
    CORPUS.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n")
    print(f"Captured {len(templates)} templates in {len(captures)} configurations")


if __name__ == "__main__":
    if sys.argv[1:] == ["--supplement"]:
        supplement()
    elif sys.argv[1:] == ["--names-only"]:
        print(f"Captured {capture_names(json.loads(CORPUS.read_text()))} templated-name cases")
    elif sys.argv[1:] == ["--whitespace"]:
        capture_whitespace()
    elif not sys.argv[1:]:
        main()
    else:
        raise SystemExit("Expected --supplement, --names-only, --whitespace, or no arguments")
