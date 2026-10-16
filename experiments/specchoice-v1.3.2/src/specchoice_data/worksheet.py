# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Decision-free authoring worksheet over the complete accepted Phase 2 tree."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
import sys

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.filesystem import FilesystemPolicyError, read_authoritative_file
from specchoice_measurement.strict_json import decode_strict_json

from .schema import load_phase3_schema_v1


class WorksheetError(ValueError):
    """Stable failure for the non-writing candidate authoring projection."""


def _placeholder(name: str) -> str:
    return f"<HUMAN_REQUIRED:{name}>"


def _span(role: str) -> dict[str, object]:
    return {
        "end_byte": _placeholder(f"{role}.end_byte"),
        "span_id": _placeholder(f"{role}.span_id"),
        "start_byte": _placeholder(f"{role}.start_byte"),
        "text": _placeholder(f"{role}.exact_utf8_text"),
    }


def _claims(role: str) -> list[dict[str, object]]:
    return [
        {
            "axis": axis,
            "claim_id": _placeholder(f"{role}.{axis}.claim_id"),
            "span_ids": [_placeholder(f"{role}.{axis}.supporting_span_id")],
            "value": _placeholder(f"{role}.{axis}.value"),
        }
        for axis in ("authority", "choice_object", "choice_space_origin", "final_status", "rationale")
    ]


def _side(role: str) -> dict[str, object]:
    return {
        "claims": _claims(role),
        "example_id": _placeholder(f"{role}.example_id"),
        "role": role,
        "source_kind": "authoritative",
        "source_path": _placeholder(f"{role}.accepted_source_path"),
        "source_sha256": _placeholder(f"{role}.accepted_source_sha256"),
        "spans": [_span(role)],
    }


def candidate_templates_v1() -> dict[str, object]:
    """Return structural blanks; every semantic value remains human-required."""
    relationship = {
        "discriminating_axes": [_placeholder("relationship.discriminating_axis")],
        "expected_delta": {
            "frame_axes": [_placeholder("relationship.expected_frame_axis_delta")],
            "final_status": {
                "from": _placeholder("relationship.positive_final_status"),
                "to": _placeholder("relationship.contrast_final_status"),
            },
        },
        "rationale": _placeholder("relationship.rationale"),
        "shared_structure": [_placeholder("relationship.shared_structure")],
    }
    held_out = _side("held_out")
    held_out.pop("role")
    return {
        "held_out": {
            "candidate_id": _placeholder("held_out.candidate_id"),
            "candidate_kind": "held_out",
            **held_out,
            "schema_version": "phase3-held-out-candidate-v1",
        },
        "metamorphic_authoritative": {
            "candidate_id": _placeholder("metamorphic.candidate_id"),
            "candidate_kind": "metamorphic",
            "direction_id": _placeholder("metamorphic.required_direction_id"),
            "presentation_order": ["source_a", "source_b"],
            "relationship": relationship,
            "schema_version": "phase3-metamorphic-candidate-v1",
            "sources": [_side("source_a"), _side("source_b")],
        },
        "pair": {
            "candidate_id": _placeholder("pair.candidate_id"),
            "candidate_kind": "pair",
            "presentation_order": ["positive", "contrast"],
            "relationship": relationship,
            "schema_version": "phase3-pair-candidate-v1",
            "sides": [_side("positive"), _side("contrast")],
        },
    }


def build_candidate_authoring_worksheet_v1(
    *, accepted_root: Path, registry_name: str, schema_raw: bytes,
    phase2_authority_sha256: str, h1_decision_sha256: str,
) -> dict[str, object]:
    """Read all 29 accepted leaves through descriptors and render no decision fields."""
    schema = load_phase3_schema_v1(schema_raw)
    try:
        _, registry_raw = read_authoritative_file(accepted_root, registry_name)
        registry = decode_strict_json(registry_raw)
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, ValueError) as error:
        raise WorksheetError("CANDIDATE_WORKSHEET_REGISTRY_INVALID") from error
    if (
        not isinstance(registry, Mapping)
        or canonical_json_bytes(registry) != registry_raw
        or registry.get("schema_version") != "6"
        or registry.get("fixture_count") != 11
        or registry.get("raw_file_count") != 29
        or not isinstance(registry.get("file_entries"), list)
    ):
        raise WorksheetError("CANDIDATE_WORKSHEET_REGISTRY_INVALID")
    accepted_files: list[dict[str, object]] = []
    for entry in registry["file_entries"]:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("fixture_id"), str) or not isinstance(entry.get("path"), str):
            raise WorksheetError("CANDIDATE_WORKSHEET_REGISTRY_INVALID")
        accepted_path = f"raw/evaluation_fixtures/{entry['fixture_id']}/{PurePosixPath(entry['path']).name}"
        try:
            evidence, raw = read_authoritative_file(accepted_root, accepted_path)
            text = raw.decode("utf-8")
        except (FilesystemPolicyError, OSError, UnicodeDecodeError) as error:
            raise WorksheetError("CANDIDATE_WORKSHEET_SOURCE_INVALID") from error
        if evidence.byte_length != entry.get("byte_length") or evidence.sha256 != entry.get("sha256"):
            raise WorksheetError("CANDIDATE_WORKSHEET_SOURCE_INVALID")
        accepted_files.append({
            "byte_length": len(raw),
            "fixture_id": entry["fixture_id"],
            "origin": entry.get("origin"),
            "path": accepted_path,
            "role": entry.get("role"),
            "sha256": sha256_bytes(raw),
            "text": text,
        })
    if [item["path"] for item in accepted_files] != sorted(item["path"] for item in accepted_files):
        raise WorksheetError("CANDIDATE_WORKSHEET_ORDER_INVALID")
    payload = {
        "accepted_files": accepted_files,
        "bindings": {
            "h1_decision_sha256": h1_decision_sha256,
            "phase2_authority_sha256": phase2_authority_sha256,
            "registry_sha256": sha256_bytes(registry_raw),
            "schema_sha256": sha256_bytes(schema_raw),
        },
        "candidate_templates": candidate_templates_v1(),
        "human_action": {
            "candidate_kinds": schema["candidate_kinds"],
            "instruction": "Author every semantic field and exact byte span; do not use model-generated labels, rationales, families, pairs, or transformations.",
            "required_metamorphic_directions": schema["metamorphic_directions"],
            "resume_signal": "FREEZE CANDIDATE INVENTORY V1",
        },
        "schema_version": "candidate-authoring-worksheet-v1",
    }
    return {**payload, "worksheet_sha256": sha256_bytes(canonical_json_bytes(payload))}


def main(argv: list[str] | None = None) -> int:
    """Render the worksheet to stdout only after the frozen production gate passes."""
    parser = argparse.ArgumentParser(prog="specchoice-data-worksheet")
    parser.add_argument("--schema", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from .cli import require_phase2_local_closure

        gate = require_phase2_local_closure()
        _, schema_raw = read_authoritative_file(args.schema.parent, args.schema.name)
        accepted_root = gate["accepted_root"]
        if not isinstance(accepted_root, Path):
            raise WorksheetError("PHASE2_AUTHORITY_NOT_CLOSED")
        worksheet = build_candidate_authoring_worksheet_v1(
            accepted_root=accepted_root,
            registry_name="fixture-registry-pr2164-v6.json",
            schema_raw=schema_raw,
            phase2_authority_sha256=str(gate["authority_sha256"]),
            h1_decision_sha256=str(gate["decision_sha256"]),
        )
    except (FilesystemPolicyError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    sys.stdout.buffer.write(canonical_json_bytes(worksheet))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
