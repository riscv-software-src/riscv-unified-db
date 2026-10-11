#!/usr/bin/env python3
# Copyright (c) 2026 Hitesh Sai
# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Emit and validate UDB architectural parameter YAML.

Parameters in ``spec/std/isa/param`` are currently written by hand. Any tool that
proposes new parameters -- for example an extraction flow reading the ISA manual --
has to reproduce the file shape by hand as well, with nothing checking the result
beyond a reviewer's eye.

This module provides that missing piece: a ``ParamCandidate`` describing a
parameter, a validator that rejects anything ``param_schema.json`` would reject,
and an emitter that writes a file matching the conventions of the existing
hand-written set.

Emission always validates first, so a candidate that would produce an invalid file
raises rather than writing it.

Two checks here are deliberately stricter than the schema as it stands on main:

* ``schema`` keys are restricted to JSON Schema draft-07 keywords. ``param_schema``
  sets ``additionalProperties: false`` on that subschema, but the keyword sits as a
  sibling of ``$ref``, and draft-07 ignores siblings of ``$ref``, so the constraint
  is currently inert and typos such as ``minimun`` pass silently (issue #2173).
* An integer ``schema`` with neither bounds nor an enum is reported. The schema
  permits it, but an unbounded integer parameter is almost always an oversight
  (issues #2170, #2102).

Both are advisory in the sense that they describe intent rather than current
enforcement, and both are reported through the same mechanism as hard schema
errors so a caller cannot silently ignore them.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

# --------------------------------------------------------------------------- #
# Repository layout
# --------------------------------------------------------------------------- #

# tools/python/param_emitter/param_emitter.py -> repository root
REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_DIR = REPO_ROOT / "spec" / "schemas"
PARAM_DIR = REPO_ROOT / "spec" / "std" / "isa" / "param"

LICENSE_HEADER = (
    "# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.\n"
    "# SPDX-License-Identifier: BSD-3-Clause-Clear\n"
    "\n"
    "# yaml-language-server: $schema=../../../schemas/param_schema.json\n"
    "\n"
)

# Key order used when emitting. Existing files are not consistent about this --
# most lead with `name` then `description`, a few put `long_name` or `definedBy`
# earlier -- so a single order is chosen for newly emitted files rather than
# trying to reproduce the variation.
KEY_ORDER = (
    "$schema",
    "kind",
    "name",
    "long_name",
    "description",
    "schema",
    "definedBy",
    "requirements",
)

# JSON Schema draft-07 keywords, read from the metaschema the repository vendors
# so this list cannot drift from the one actually in use.
_METASCHEMA = SCHEMAS_DIR / "json-schema-draft-07.json"


def draft7_keywords() -> frozenset[str]:
    """Return the set of draft-07 keywords, from the vendored metaschema."""
    with _METASCHEMA.open(encoding="utf-8") as f:
        return frozenset(json.load(f)["properties"].keys())


def _block(text: str) -> Any:
    """Render multi-line prose as a literal block scalar, matching existing files.

    Most hand-written parameter descriptions use ``|``. Single-line values are left
    as plain scalars, which is also what the existing set does.
    """
    if isinstance(text, str) and "\n" in text.strip():
        return LiteralScalarString(text if text.endswith("\n") else text + "\n")
    return text


def _yaml() -> YAML:
    y = YAML()
    y.default_flow_style = False
    y.width = 4096  # do not wrap; prettier owns line breaking for YAML
    y.indent(mapping=2, sequence=4, offset=2)
    y.preserve_quotes = True
    return y


# --------------------------------------------------------------------------- #
# Candidate
# --------------------------------------------------------------------------- #


@dataclass
class ParamCandidate:
    """A proposed architectural parameter, prior to validation or emission.

    ``name``, ``long_name``, ``description``, ``schema`` and ``defined_by`` map
    directly onto the fields of ``param_schema.json``. ``requirements`` is
    optional and carries either an IDL condition or a YAML condition structure.

    ``source_excerpt`` is not part of the schema and is never emitted. It exists so
    that a caller extracting parameters from specification prose can carry the
    supporting quotation alongside the candidate for review.
    """

    name: str
    long_name: str
    description: str
    schema: dict[str, Any]
    defined_by: dict[str, Any]
    requirements: dict[str, Any] | None = None
    source_excerpt: str | None = field(default=None, repr=False)

    def to_yaml_dict(self) -> dict[str, Any]:
        """Return the ordered mapping that will be written to file."""
        doc: dict[str, Any] = {
            "$schema": "param_schema.json#",
            "kind": "parameter",
            "name": self.name,
            "long_name": self.long_name,
            "description": _block(self.description),
            "schema": self.schema,
            "definedBy": self.defined_by,
        }
        if self.requirements is not None:
            doc["requirements"] = self.requirements
        return {k: doc[k] for k in KEY_ORDER if k in doc}


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


class ParamValidationError(Exception):
    """Raised when a candidate would produce a file the database should reject."""

    def __init__(self, name: str, problems: Sequence[str]) -> None:
        self.name = name
        self.problems = list(problems)
        detail = "\n".join(f"  - {p}" for p in self.problems)
        super().__init__(f"{name}: {len(self.problems)} problem(s)\n{detail}")


def _schema_validator():
    """Build a Draft-07 validator for param_schema.json with local $ref resolution."""
    from jsonschema import Draft7Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT7

    resources = []
    for path in SCHEMAS_DIR.glob("*.json"):
        with path.open(encoding="utf-8") as f:
            contents = json.load(f)
        resource = Resource.from_contents(contents, default_specification=DRAFT7)
        # Files reference each other both with and without a trailing '#'.
        resources.append((path.name, resource))
        resources.append((path.name + "#", resource))

    registry = Registry().with_resources(resources)
    with (SCHEMAS_DIR / "param_schema.json").open(encoding="utf-8") as f:
        param_schema = json.load(f)
    return Draft7Validator(param_schema, registry=registry)


def validate_doc(doc: dict[str, Any], *, strict: bool = True) -> list[str]:
    """Return a list of problems with ``doc``. Empty means valid.

    ``strict`` adds the two checks described in the module docstring, which the
    schema does not currently enforce.
    """
    problems: list[str] = []

    for error in sorted(_schema_validator().iter_errors(doc), key=str):
        location = "/".join(str(p) for p in error.absolute_path) or "<root>"
        problems.append(f"schema: {location}: {error.message}")

    if not strict:
        return problems

    subschema = doc.get("schema")
    if isinstance(subschema, dict):
        unknown = sorted(set(subschema) - draft7_keywords())
        if unknown:
            problems.append(
                f"schema: unknown draft-07 keyword(s) {unknown}. "
                "param_schema cannot currently reject these (see issue #2173), "
                "but they are silently ignored by every validator."
            )

        if subschema.get("type") == "integer" and not (
            {"enum", "const", "minimum", "maximum", "$ref"} & set(subschema)
        ):
            problems.append(
                "schema: integer with no enum, const, bounds or $ref is unconstrained; "
                "give it a range or an enum (compare issues #2170 and #2102)."
            )

    return problems


def validate_candidate(candidate: ParamCandidate, *, strict: bool = True) -> list[str]:
    """Return a list of problems with ``candidate``. Empty means valid."""
    return validate_doc(candidate.to_yaml_dict(), strict=strict)


# --------------------------------------------------------------------------- #
# Emission
# --------------------------------------------------------------------------- #


def render(candidate: ParamCandidate, *, strict: bool = True) -> str:
    """Return the YAML text for ``candidate``, validating first.

    Raises ``ParamValidationError`` rather than returning text that would not
    validate.
    """
    problems = validate_candidate(candidate, strict=strict)
    if problems:
        raise ParamValidationError(candidate.name, problems)

    buf = StringIO()
    _yaml().dump(candidate.to_yaml_dict(), buf)
    return LICENSE_HEADER + buf.getvalue()


def emit(
    candidate: ParamCandidate,
    *,
    out_dir: Path | None = None,
    strict: bool = True,
    overwrite: bool = False,
) -> Path:
    """Write ``candidate`` to ``<out_dir>/<NAME>.yaml`` and return the path."""
    target_dir = PARAM_DIR if out_dir is None else out_dir
    path = target_dir / f"{candidate.name}.yaml"
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; pass overwrite=True to replace it")

    text = render(candidate, strict=strict)
    target_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


# --------------------------------------------------------------------------- #
# Auditing existing files
# --------------------------------------------------------------------------- #


def audit(paths: Iterable[Path] | None = None, *, strict: bool = True) -> dict[str, list[str]]:
    """Validate parameter files already in the database.

    Returns a mapping of file name to problems, containing only files with at
    least one problem.
    """
    targets = sorted(PARAM_DIR.glob("*.yaml")) if paths is None else list(paths)
    yaml = YAML(typ="safe")
    results: dict[str, list[str]] = {}
    for path in targets:
        with path.open(encoding="utf-8") as f:
            doc = yaml.load(f)
        problems = validate_doc(doc, strict=strict)
        if problems:
            results[path.name] = problems
    return results


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _cmd_audit(args: argparse.Namespace) -> int:
    results = audit(strict=not args.schema_only)
    total = len(sorted(PARAM_DIR.glob("*.yaml")))
    if not results:
        print(f"{total} parameter file(s) checked, no problems found.")
        return 0

    for name in sorted(results):
        print(name)
        for problem in results[name]:
            print(f"  - {problem}")
    print(f"\n{len(results)} of {total} parameter file(s) have problems.")
    return 1 if args.fail_on_problem else 0


def _cmd_emit(args: argparse.Namespace) -> int:
    yaml = YAML(typ="safe")
    with Path(args.input).open(encoding="utf-8") as f:
        raw = yaml.load(f)

    entries = raw if isinstance(raw, list) else [raw]
    candidates = [
        ParamCandidate(
            name=e["name"],
            long_name=e["long_name"],
            description=e["description"],
            schema=e["schema"],
            defined_by=e["definedBy"],
            requirements=e.get("requirements"),
            source_excerpt=e.get("source_excerpt"),
        )
        for e in entries
    ]

    out_dir = Path(args.out_dir) if args.out_dir else None
    failures = 0
    for candidate in candidates:
        try:
            if args.dry_run:
                render(candidate)
                print(f"would emit {candidate.name}.yaml")
            else:
                print(f"wrote {emit(candidate, out_dir=out_dir, overwrite=args.overwrite)}")
        except (ParamValidationError, FileExistsError) as exc:
            failures += 1
            print(f"FAILED {candidate.name}: {exc}", file=sys.stderr)
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser("audit", help="validate the parameter files already in the database")
    p_audit.add_argument(
        "--schema-only",
        action="store_true",
        help="apply only param_schema.json, skipping the stricter advisory checks",
    )
    p_audit.add_argument(
        "--fail-on-problem",
        action="store_true",
        help="exit non-zero when any problem is found",
    )
    p_audit.set_defaults(func=_cmd_audit)

    p_emit = sub.add_parser("emit", help="emit parameter YAML from a candidate file")
    p_emit.add_argument("input", help="YAML file holding one candidate or a list of them")
    p_emit.add_argument("--out-dir", help="destination directory (default: spec/std/isa/param)")
    p_emit.add_argument("--overwrite", action="store_true", help="replace existing files")
    p_emit.add_argument("--dry-run", action="store_true", help="validate without writing")
    p_emit.set_defaults(func=_cmd_emit)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
