# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Extract structural observations without modifying genuine Ruby raw artifacts."""

import argparse
import hashlib
import json
import re
from pathlib import Path

CLASS = re.compile(r"(?:class|struct)\s+(\w+)\s*(?::[^;{}]+)?\{")
INST = re.compile(r"class\s+(\w+_Inst)\s*:")
FIELD = re.compile(r"Bits\s*<\s*(\d+)\s*>\s+(\w+)\s*\([^)]*\)\s*const")
RUBY_GEMS = re.compile(r"/(?:[^/\s]+/)+mise/installs/ruby/[^/]+/lib/ruby/gems/[^/]+/gems")


def sanitize_paths(value, root: str):
    if isinstance(value, str):
        return RUBY_GEMS.sub("<ruby-gems>", value.replace(root, "<repository>"))
    if isinstance(value, list):
        return [sanitize_paths(item, root) for item in value]
    if isinstance(value, dict):
        return {
            sanitize_paths(key, root): sanitize_paths(item, root) for key, item in value.items()
        }
    return value


def interface(text, *, prefix):
    classes = sorted(
        {
            name
            for name in CLASS.findall(text)
            if name.startswith(prefix) or name.endswith("_Parameter")
        }
    )
    locations = list(INST.finditer(text))
    fields = {}
    for index, match in enumerate(locations):
        end = locations[index + 1].start() if index + 1 < len(locations) else len(text)
        fields[match.group(1)] = sorted(
            {(name, int(width)) for width, name in FIELD.findall(text[match.end() : end])}
        )
    return {"classes": classes, "decode_fields": fields}


def extract(capture: Path, config: str, prefix: str):
    manifest = json.loads((capture / "manifest.json").read_text())
    observations = {}
    hashes = {}
    for logical, expected in manifest["outputs"].items():
        path = capture / logical
        content = path.read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected:
            raise ValueError(f"Raw capture hash mismatch: {logical}")
        if path.parent.name == config:
            hashes[path.name] = actual
            observations[path.name] = interface(content.decode(), prefix=prefix)
    return {
        "capture_selectors": sanitize_paths(manifest["selectors"], manifest["root"]),
        "ruby": manifest["ruby"],
        "input_hashes": manifest["inputs"],
        "raw_output_hashes": hashes,
        "raw_errors": sanitize_paths(manifest["errors"], manifest["root"]),
        "uncapturable_native_artifacts": {
            "types.hxx": "The standalone capture lacks the native task-local symtab binding."
        },
        "config": config,
        "prefix": prefix,
        "observations": observations,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(extract(args.capture, args.config, args.prefix), sort_keys=True, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
