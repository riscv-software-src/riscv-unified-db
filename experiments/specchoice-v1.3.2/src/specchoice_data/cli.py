# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Local-only CLI for the Phase 3 authority-to-review tracer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.filesystem import FilesystemPolicyError, read_authoritative_file, write_new_descriptor_file
from specchoice_evidence.runtime_closure import (
    build_phase2_lifecycle_successor_v1,
    load_phase2_lifecycle_successor_v1,
)
from specchoice_measurement.strict_json import decode_strict_json

from .admission import DataAdmissionError, admit_pair_candidate_v1, freeze_candidate_inventory_v1
from .review import (
    build_pair_review_packet_v1,
    build_pair_review_readiness_v1,
    render_pair_review_markdown_v1,
    validate_pair_review_decision_v1,
)


_EXPERIMENT = Path(__file__).parents[2]
_REPOSITORY = Path(__file__).parents[4]
_LEGACY_PLANNING = "." + "planning/"


def _canonical(path: Path, code: str) -> tuple[dict[str, object], bytes]:
    try:
        _, raw = read_authoritative_file(path.parent, path.name)
        value = decode_strict_json(raw)
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, ValueError) as error:
        raise DataAdmissionError(code) from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise DataAdmissionError(code)
    return value, raw


def require_phase2_local_closure() -> dict[str, object]:
    """Verify the forward-only Phase 2 lifecycle successor or fail closed."""
    try:
        decision, decision_raw = _canonical(_EXPERIMENT / "reviews/h1-source-gold-decision-v6.json", "PHASE2_AUTHORITY_NOT_CLOSED")
        successor, _ = _canonical(
            _EXPERIMENT / "receipts/phase2-lifecycle-successor-v1.json",
            "PHASE2_AUTHORITY_NOT_CLOSED",
        )
        validated_successor = load_phase2_lifecycle_successor_v1(_REPOSITORY, successor)
        authority_path = _EXPERIMENT / "phase2/source-authority.json"
        authority, authority_raw = _canonical(authority_path, "PHASE2_AUTHORITY_NOT_CLOSED")
        evidence = {
            str(item["path"]): item
            for item in validated_successor["evidence_bindings"]
        }
        decision_binding = evidence[
            "experiments/specchoice-v1.3.2/reviews/h1-source-gold-decision-v6.json"
        ]
        summary_binding = evidence[
            _LEGACY_PLANNING
            + "phases/02-deterministic-measurement-spine/02-22-SUMMARY.md"
        ]
        if (
            decision.get("aggregate_disposition") != "approved"
            or decision_binding.get("sha256") != sha256_bytes(decision_raw)
            or evidence["experiments/specchoice-v1.3.2/phase2/source-authority.json"].get("sha256")
            != sha256_bytes(authority_raw)
        ):
            raise DataAdmissionError("PHASE2_AUTHORITY_NOT_CLOSED")
    except Exception as error:
        if isinstance(error, KeyboardInterrupt):
            raise
        raise DataAdmissionError("PHASE2_AUTHORITY_NOT_CLOSED") from error
    return {
        "accepted_root": _EXPERIMENT / "bundles/accepted" / str(authority["generation"]),
        "authority_sha256": sha256_bytes(authority_raw),
        "decision_sha256": decision["decision_sha256"],
        "terminal_sha256": summary_binding["sha256"],
        "approved": True,
        "decision_file_sha256": sha256_bytes(decision_raw),
    }


def _build_phase2_successor(args: argparse.Namespace) -> int:
    expected_output = _EXPERIMENT / "receipts/phase2-lifecycle-successor-v1.json"
    if args.output.absolute() != expected_output.absolute():
        raise DataAdmissionError("PHASE2_LIFECYCLE_OUTPUT_PATH_INVALID")
    successor = build_phase2_lifecycle_successor_v1(
        _REPOSITORY,
        code_freeze_commit=args.code_freeze_commit,
    )
    raw = canonical_json_bytes(successor)
    _write(args.output, raw)
    load_phase2_lifecycle_successor_v1(_REPOSITORY, successor)
    sys.stdout.buffer.write(
        canonical_json_bytes(
            {
                "receipt_sha256": sha256_bytes(raw),
                "status": "written",
                "successor_sha256": successor["successor_sha256"],
            }
        )
    )
    return 0


def _write(path: Path, raw: bytes) -> None:
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise DataAdmissionError("PHASE3_OUTPUT_PARENT_INVALID")
    try:
        write_new_descriptor_file(path.parent, path.name, raw)
    except FilesystemPolicyError as error:
        raise DataAdmissionError("PHASE3_OUTPUT_INVALID") from error


def _freeze(args: argparse.Namespace) -> int:
    gate = require_phase2_local_closure()
    declarations, _ = _canonical(args.declarations, "CANDIDATE_DECLARATIONS_INVALID")
    entries = declarations.get("entries")
    if not isinstance(entries, list):
        raise DataAdmissionError("CANDIDATE_DECLARATIONS_INVALID")
    pairs = tuple((item["path"], item["kind"]) for item in entries if isinstance(item, dict) and set(item) == {"kind", "path"})
    if len(pairs) != len(entries):
        raise DataAdmissionError("CANDIDATE_DECLARATIONS_INVALID")
    _, schema_raw = _canonical(args.schema, "PHASE3_DATA_SCHEMA_INVALID")
    inventory = freeze_candidate_inventory_v1(
        candidate_root=args.candidate_root, declarations=pairs,
        phase2_authority_sha256=str(gate["authority_sha256"]),
        h1_decision_sha256=str(gate["decision_sha256"]), schema_raw=schema_raw,
    )
    _write(args.output, canonical_json_bytes(inventory))
    sys.stdout.buffer.write(canonical_json_bytes({"inventory_sha256": inventory["inventory_sha256"], "status": "written"}))
    return 0


def _build_review(args: argparse.Namespace) -> int:
    gate = require_phase2_local_closure()
    inventory, _ = _canonical(args.inventory, "CANDIDATE_INVENTORY_INVALID")
    _, schema_raw = _canonical(args.schema, "PHASE3_DATA_SCHEMA_INVALID")
    admission = admit_pair_candidate_v1(
        candidate_root=args.candidate_root, candidate_path=args.candidate_path,
        inventory=inventory, accepted_root=gate["accepted_root"], schema_raw=schema_raw,
    )
    packet = build_pair_review_packet_v1(admission=admission, inventory=inventory)
    if not admission.valid:
        raise DataAdmissionError("PAIR_CANDIDATE_STRUCTURALLY_INVALID")
    markdown = render_pair_review_markdown_v1(packet)
    readiness = build_pair_review_readiness_v1(packet=packet, markdown=markdown)
    for path, raw in ((args.packet, canonical_json_bytes(packet)), (args.markdown, markdown), (args.readiness, canonical_json_bytes(readiness))):
        _write(path, raw)
    sys.stdout.buffer.write(canonical_json_bytes({"packet_sha256": packet["packet_sha256"], "readiness_sha256": readiness["readiness_sha256"], "status": "written"}))
    return 0


def _validate_decision(args: argparse.Namespace) -> int:
    require_phase2_local_closure()
    decision, _ = _canonical(args.decision, "PAIR_REVIEW_DECISION_INVALID")
    packet, _ = _canonical(args.packet, "PAIR_REVIEW_PACKET_INVALID")
    readiness, _ = _canonical(args.readiness, "PAIR_REVIEW_READINESS_INVALID")
    validated = validate_pair_review_decision_v1(decision=decision, packet=packet, readiness=readiness)
    sys.stdout.buffer.write(canonical_json_bytes({"decision_sha256": validated["decision_sha256"], "status": "valid"}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="specchoice-data")
    commands = parser.add_subparsers(dest="command", required=True)
    successor = commands.add_parser("build-phase2-lifecycle-successor-v1")
    successor.add_argument("--code-freeze-commit", required=True)
    successor.add_argument("--output", type=Path, required=True)
    successor.set_defaults(handler=_build_phase2_successor)
    freeze = commands.add_parser("freeze-candidate-inventory-v1")
    freeze.add_argument("--candidate-root", type=Path, required=True)
    freeze.add_argument("--declarations", type=Path, required=True)
    freeze.add_argument("--schema", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.set_defaults(handler=_freeze)
    review = commands.add_parser("build-pair-review-v1")
    review.add_argument("--candidate-root", type=Path, required=True)
    review.add_argument("--candidate-path", required=True)
    review.add_argument("--inventory", type=Path, required=True)
    review.add_argument("--schema", type=Path, required=True)
    review.add_argument("--packet", type=Path, required=True)
    review.add_argument("--markdown", type=Path, required=True)
    review.add_argument("--readiness", type=Path, required=True)
    review.set_defaults(handler=_build_review)
    decision = commands.add_parser("validate-pair-review-decision-v1")
    decision.add_argument("--decision", type=Path, required=True)
    decision.add_argument("--packet", type=Path, required=True)
    decision.add_argument("--readiness", type=Path, required=True)
    decision.set_defaults(handler=_validate_decision)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.handler(args))
    except (DataAdmissionError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
