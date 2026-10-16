# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Raw-byte A/B/C prompt rendering for the offline treatment contract."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from pathlib import Path

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.filesystem import FilesystemPolicyError, write_exact_descriptor_files
from specchoice_measurement.strict_json import decode_strict_json

from specchoice_treatments.schema import (
    FRAME_ENUMS,
    REQUIRED_FRAME_AXES,
    ParsedTreatmentResponse,
    TreatmentContractError,
    parse_treatment_response_v1,
)

PROMPT_SECTION_ORDER = (
    "shared_guidance",
    "demonstrations",
    "target",
    "frame_instructions",
    "adjudication_instructions",
    "output_schema",
    "evidence_rules",
)
_TREATMENTS_ROOT = Path(__file__).resolve().parents[2]
_PROMPT_CONTRACT_PATH = _TREATMENTS_ROOT / "config/treatments/prompt-contract-v1.json"
_SYNTHETIC_TARGET_PATH = _TREATMENTS_ROOT / "fixtures/treatments/synthetic-target-v1.json"
_SYNTHETIC_PAIR_CORPUS_PATH = (
    _TREATMENTS_ROOT / "fixtures/treatments/synthetic-complete-pairs-v1.json"
)
_SYNTHETIC_RETRIEVAL_RECEIPT_PATH = (
    _TREATMENTS_ROOT / "fixtures/treatments/synthetic-retrieval-receipt-v1.json"
)
_CONTRACT_RESPONSE_PATHS = {
    system: _TREATMENTS_ROOT / f"fixtures/treatments/contract-response-{system.lower()}-v1.json"
    for system in ("A", "B", "C")
}
_PROMPT_CONTRACT_KEYS = frozenset(
    {
        "schema_version",
        "section_order",
        "shared_guidance",
        "frame_instructions",
        "adjudication_instructions",
        "output_schema",
        "evidence_rules",
        "demonstration_count",
        "fixed_pair_selection",
        "retrieval_contract_id",
        "retrieval_receipt_sha256",
        "allowed_differences",
        "offline_lexical_rule",
        "provider_fields",
    }
)
_TARGET_KEYS = frozenset(
    {
        "schema_version",
        "target_id",
        "source_text",
        "source_sha256",
        "record_sha256",
        "test_only",
        "count_eligible",
    }
)
_FIXED_SELECTION_KEYS = frozenset(
    {
        "selection_id",
        "target_source_sha256",
        "corpus_sha256",
        "ordered_pair_ids",
        "test_only",
        "count_eligible",
    }
)
_CORPUS_KEYS = frozenset(
    {"schema_version", "test_only", "count_eligible", "pairs", "corpus_sha256"}
)
_PAIR_KEYS = frozenset(
    {
        "pair_id",
        "positive",
        "contrast",
        "shared_structure",
        "discriminating_axes",
        "test_only",
        "count_eligible",
    }
)
_PAIR_SIDE_KEYS = frozenset(
    {"source_text", "source_sha256", "frame", "evidence_spans", "final_status"}
)
_PAIR_FRAME_AXIS_KEYS = frozenset({"value", "evidence_span"})
_SPAN_KEYS = frozenset({"source_sha256", "start_byte", "end_byte", "text"})
_RETRIEVAL_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "test_only",
        "count_eligible",
        "target_source_sha256",
        "corpus_sha256",
        "ranking",
        "ordering_rule",
        "query_rule",
        "lexical_rule",
        "retrieval_contract_id",
        "receipt_sha256",
    }
)
_RANKING_ITEM_KEYS = frozenset({"rank", "pair_id", "cosine_score"})
_CONTRACT_RESPONSE_ISOLATION_KEYS = frozenset({"test_only", "count_eligible"})
_CONTRACT_RESPONSE_BASE_KEYS = frozenset(
    {
        "schema_version",
        "system",
        "origin",
        "model_generated",
        "target_sha256",
        "adjudication",
    }
)
_FORBIDDEN_CORPUS_FIELD_NAMES = frozenset(
    {
        "accepted_path",
        "candidate_inventory",
        "final_disposition",
        "gold",
        "primary_family",
        "relevance",
    }
)


class PromptBundleError(ValueError):
    """Stable failure emitted before an offline prompt bundle can be trusted."""


def _contains_forbidden_corpus_field(value: object) -> bool:
    if isinstance(value, Mapping):
        return bool(_FORBIDDEN_CORPUS_FIELD_NAMES & set(value)) or any(
            _contains_forbidden_corpus_field(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_corpus_field(item) for item in value)
    return False


def _load_canonical_json(path: Path, code: str) -> object:
    raw = path.read_bytes()
    try:
        value = decode_strict_json(raw)
    except (UnicodeDecodeError, ValueError) as error:
        raise PromptBundleError(code) from error
    if canonical_json_bytes(value) != raw:
        raise PromptBundleError(code)
    return value


def _require_text(value: object, code: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value) or "\r" in value:
        raise PromptBundleError(code)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise PromptBundleError(code) from error
    return value


def _require_pair_ids(value: object, code: str) -> tuple[str, str]:
    if not isinstance(value, list) or len(value) != 2:
        raise PromptBundleError(code)
    pair_ids = tuple(value)
    if any(not isinstance(item, str) or not item for item in pair_ids) or len(set(pair_ids)) != 2:
        raise PromptBundleError(code)
    return pair_ids  # type: ignore[return-value]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_prompt_contract_v1(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != _PROMPT_CONTRACT_KEYS:
        raise PromptBundleError("PROMPT_CONTRACT_INVALID")
    if (
        value.get("schema_version") != "prompt-contract-v1"
        or tuple(value.get("section_order", ())) != PROMPT_SECTION_ORDER
    ):
        raise PromptBundleError("PROMPT_CONTRACT_INVALID")
    if (
        value.get("demonstration_count") != 2
        or value.get("provider_fields") != "not_applicable_red"
    ):
        raise PromptBundleError("PROMPT_CONTRACT_INVALID")
    if value.get("offline_lexical_rule") != "python_re_findall_unicode_word_boundaries_v1":
        raise PromptBundleError("PROMPT_CONTRACT_INVALID")
    for field in (
        "shared_guidance",
        "frame_instructions",
        "adjudication_instructions",
        "evidence_rules",
        "retrieval_contract_id",
        "retrieval_receipt_sha256",
    ):
        _require_text(value.get(field), "PROMPT_CONTRACT_INVALID")
    output_schema = value.get("output_schema")
    if not isinstance(output_schema, dict) or set(output_schema) != {"A", "BC"}:
        raise PromptBundleError("PROMPT_CONTRACT_INVALID")
    _require_text(output_schema.get("A"), "PROMPT_CONTRACT_INVALID")
    _require_text(output_schema.get("BC"), "PROMPT_CONTRACT_INVALID")
    selection = value.get("fixed_pair_selection")
    if not isinstance(selection, dict) or set(selection) != _FIXED_SELECTION_KEYS:
        raise PromptBundleError("PROMPT_CONTRACT_INVALID")
    if (
        selection.get("selection_id") != "fixed-synthetic-pairs-v1"
        or selection.get("test_only") is not True
        or selection.get("count_eligible") is not False
    ):
        raise PromptBundleError("PROMPT_CONTRACT_INVALID")
    _require_text(selection.get("target_source_sha256"), "PROMPT_CONTRACT_INVALID")
    _require_text(selection.get("corpus_sha256"), "PROMPT_CONTRACT_INVALID")
    _require_pair_ids(selection.get("ordered_pair_ids"), "PROMPT_CONTRACT_INVALID")
    allowed = value.get("allowed_differences")
    if allowed != {"A_B": ["frame_instructions", "output_schema"], "B_C": ["demonstrations"]}:
        raise PromptBundleError("PROMPT_CONTRACT_INVALID")
    return value


def _validate_synthetic_target_v1(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != _TARGET_KEYS:
        raise PromptBundleError("PROMPT_TARGET_INVALID")
    if value.get("schema_version") != "synthetic-treatment-target-v1":
        raise PromptBundleError("PROMPT_TARGET_INVALID")
    _require_text(value.get("target_id"), "PROMPT_TARGET_INVALID")
    source_text = _require_text(value.get("source_text"), "PROMPT_TARGET_INVALID")
    if value.get("test_only") is not True or value.get("count_eligible") is not False:
        raise PromptBundleError("PROMPT_TARGET_INVALID")
    if value.get("source_sha256") != sha256_bytes(source_text.encode("utf-8")):
        raise PromptBundleError("PROMPT_TARGET_INVALID")
    expected = {key: item for key, item in value.items() if key != "record_sha256"}
    if value.get("record_sha256") != sha256_bytes(canonical_json_bytes(expected)):
        raise PromptBundleError("PROMPT_TARGET_INVALID")
    if not source_text.endswith("\n") or source_text.endswith("\n\n"):
        raise PromptBundleError("PROMPT_TARGET_INVALID")
    return value


def _closed_contract_and_target(
    config: object, target: object
) -> tuple[dict[str, object], dict[str, object]]:
    canonical_config = _load_canonical_json(_PROMPT_CONTRACT_PATH, "PROMPT_CONTRACT_INVALID")
    canonical_target = _load_canonical_json(_SYNTHETIC_TARGET_PATH, "PROMPT_TARGET_INVALID")
    if canonical_json_bytes(config) != canonical_json_bytes(canonical_config):
        raise PromptBundleError("PROMPT_CONTRACT_INVALID")
    if canonical_json_bytes(target) != canonical_json_bytes(canonical_target):
        raise PromptBundleError("PROMPT_TARGET_INVALID")
    contract = _validate_prompt_contract_v1(config)
    closed_target = _validate_synthetic_target_v1(target)
    selection = contract["fixed_pair_selection"]
    assert isinstance(selection, dict)
    if selection["target_source_sha256"] != closed_target["source_sha256"]:
        raise PromptBundleError("PROMPT_CONTRACT_INVALID")
    return contract, closed_target


def _validate_pair_span(value: object, source_raw: bytes) -> None:
    if not isinstance(value, dict) or set(value) != _SPAN_KEYS:
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    start = value.get("start_byte")
    end = value.get("end_byte")
    if (
        value.get("source_sha256") != sha256_bytes(source_raw)
        or not _is_int(start)
        or not _is_int(end)
        or not 0 <= start < end <= len(source_raw)
    ):
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    try:
        text = source_raw[start:end].decode("utf-8")
    except UnicodeDecodeError as error:
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID") from error
    if value.get("text") != text:
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")


def validate_complete_pair_side_v1(value: object, expected_final_status: str) -> None:
    """Validate one atomic synthetic pair side against the Wave 2 contract."""
    if not isinstance(value, dict) or set(value) != _PAIR_SIDE_KEYS:
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    source_text = _require_text(value.get("source_text"), "PROMPT_PAIR_CORPUS_INVALID")
    if value.get("final_status") != expected_final_status:
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    if not source_text.endswith("\n") or source_text.endswith("\n\n"):
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    source_raw = source_text.encode("utf-8")
    if value.get("source_sha256") != sha256_bytes(source_raw):
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    spans = value.get("evidence_spans")
    if not isinstance(spans, list) or not spans:
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    for span in spans:
        _validate_pair_span(span, source_raw)
    frame = value.get("frame")
    if not isinstance(frame, dict) or tuple(frame) != REQUIRED_FRAME_AXES:
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    for axis in REQUIRED_FRAME_AXES:
        item = frame[axis]
        if (
            not isinstance(item, dict)
            or set(item) != _PAIR_FRAME_AXIS_KEYS
            or item.get("value") not in FRAME_ENUMS[axis]
        ):
            raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
        _validate_pair_span(item.get("evidence_span"), source_raw)


def _load_complete_pair_corpus_v1() -> dict[str, object]:
    corpus = _load_canonical_json(_SYNTHETIC_PAIR_CORPUS_PATH, "PROMPT_PAIR_CORPUS_INVALID")
    if (
        not isinstance(corpus, dict)
        or set(corpus) != _CORPUS_KEYS
        or _contains_forbidden_corpus_field(corpus)
    ):
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    if (
        corpus.get("schema_version") != "synthetic-complete-pair-corpus-v1"
        or corpus.get("test_only") is not True
        or corpus.get("count_eligible") is not False
    ):
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    expected = {key: item for key, item in corpus.items() if key != "corpus_sha256"}
    if corpus.get("corpus_sha256") != sha256_bytes(canonical_json_bytes(expected)):
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    pairs = corpus.get("pairs")
    if not isinstance(pairs, list) or len(pairs) < 3:
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    pair_ids: list[str] = []
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != _PAIR_KEYS:
            raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
        pair_id = pair.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id.startswith("SYNTH_PAIR_"):
            raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
        pair_ids.append(pair_id)
        if pair.get("test_only") is not True or pair.get("count_eligible") is not False:
            raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
        structure = pair.get("shared_structure")
        axes = pair.get("discriminating_axes")
        if (
            not isinstance(structure, list)
            or not structure
            or any(not isinstance(item, str) or not item for item in structure)
            or not isinstance(axes, list)
            or not axes
            or len(axes) != len(set(axes))
            or any(axis not in REQUIRED_FRAME_AXES for axis in axes)
        ):
            raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
        validate_complete_pair_side_v1(pair.get("positive"), "accept")
        validate_complete_pair_side_v1(pair.get("contrast"), "classify_out")
    if len(pair_ids) != len(set(pair_ids)):
        raise PromptBundleError("PROMPT_PAIR_ID_DUPLICATE")
    return corpus


def validate_contract_response_origin_v1(
    raw: bytes,
    target_raw: bytes,
    *,
    evidence_kind: str = "contract_fixture",
) -> ParsedTreatmentResponse:
    """Validate one canonical human fixture without creating evidence usable by a run."""
    if evidence_kind != "contract_fixture":
        raise PromptBundleError("CONTRACT_FIXTURE_EVIDENCE_FORBIDDEN")
    try:
        envelope = decode_strict_json(raw)
    except (UnicodeDecodeError, ValueError) as error:
        raise PromptBundleError("PROMPT_RESPONSE_INVALID") from error
    if canonical_json_bytes(envelope) != raw or not isinstance(envelope, dict):
        raise PromptBundleError("PROMPT_RESPONSE_INVALID")
    system = envelope.get("system")
    expected = _CONTRACT_RESPONSE_BASE_KEYS | _CONTRACT_RESPONSE_ISOLATION_KEYS
    if system in {"B", "C"}:
        expected |= {"delegation_frame"}
    if set(envelope) != expected:
        raise PromptBundleError("PROMPT_RESPONSE_INVALID")
    if (
        envelope.get("origin") != "contract_fixture"
        or envelope.get("model_generated") is not False
        or envelope.get("test_only") is not True
        or envelope.get("count_eligible") is not False
    ):
        raise PromptBundleError("PROMPT_RESPONSE_INVALID")
    projection = {
        key: value
        for key, value in envelope.items()
        if key not in _CONTRACT_RESPONSE_ISOLATION_KEYS
    }
    try:
        return parse_treatment_response_v1(canonical_json_bytes(projection), target_raw)
    except TreatmentContractError as error:
        raise PromptBundleError("PROMPT_RESPONSE_INVALID") from error


def _resolve_pairs(
    pair_ids: tuple[str, str], corpus: Mapping[str, object]
) -> tuple[dict[str, object], dict[str, object]]:
    pairs = corpus["pairs"]
    assert isinstance(pairs, list)
    by_id = {pair["pair_id"]: pair for pair in pairs if isinstance(pair, dict)}
    if set(pair_ids) - set(by_id):
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    resolved = tuple(by_id[pair_id] for pair_id in pair_ids)
    if any(
        pair["test_only"] is not True or pair["count_eligible"] is not False for pair in resolved
    ):
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    return resolved  # type: ignore[return-value]


def _load_retrieval_receipt_v1(
    contract: Mapping[str, object], target: Mapping[str, object], corpus: Mapping[str, object]
) -> tuple[str, str]:
    receipt = _load_canonical_json(_SYNTHETIC_RETRIEVAL_RECEIPT_PATH, "PROMPT_PAIR_CORPUS_INVALID")
    if not isinstance(receipt, dict) or set(receipt) != _RETRIEVAL_RECEIPT_KEYS:
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    expected = {key: item for key, item in receipt.items() if key != "receipt_sha256"}
    if (
        receipt.get("schema_version") != "synthetic-retrieval-receipt-v1"
        or receipt.get("test_only") is not True
        or receipt.get("count_eligible") is not False
        or receipt.get("receipt_sha256") != sha256_bytes(canonical_json_bytes(expected))
        or receipt.get("receipt_sha256") != contract["retrieval_receipt_sha256"]
        or receipt.get("target_source_sha256") != target["source_sha256"]
        or receipt.get("corpus_sha256") != corpus["corpus_sha256"]
        or receipt.get("retrieval_contract_id") != contract["retrieval_contract_id"]
        or receipt.get("ordering_rule") != "score_desc_pair_id_asc"
        or receipt.get("query_rule") != "source_text_only"
        or receipt.get("lexical_rule") != "python_re_findall_unicode_word_boundaries_v1"
    ):
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    ranking = receipt.get("ranking")
    if not isinstance(ranking, list) or len(ranking) != 2:
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    pair_ids: list[str] = []
    scores: list[float] = []
    for expected_rank, item in enumerate(ranking, start=1):
        if (
            not isinstance(item, dict)
            or set(item) != _RANKING_ITEM_KEYS
            or item.get("rank") != expected_rank
        ):
            raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
        pair_id = item.get("pair_id")
        score = item.get("cosine_score")
        if (
            not isinstance(pair_id, str)
            or not pair_id
            or isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or score < 0
        ):
            raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
        pair_ids.append(pair_id)
        scores.append(float(score))
    if (
        len(set(pair_ids)) != 2
        or scores[0] < scores[1]
        or (scores[0] == scores[1] and pair_ids[0] >= pair_ids[1])
    ):
        raise PromptBundleError("PROMPT_PAIR_CORPUS_INVALID")
    return tuple(pair_ids)  # type: ignore[return-value]


def _raw_section(text: str, *, allow_empty: bool = False) -> bytes:
    value = _require_text(text, "PROMPT_RAW_BYTES_INVALID", allow_empty=allow_empty)
    raw = value.encode("utf-8")
    if not allow_empty and (not raw or not raw.endswith(b"\n") or raw.endswith(b"\n\n")):
        raise PromptBundleError("PROMPT_RAW_BYTES_INVALID")
    return raw


def render_prompt_sections_v1(config: object, target: object, system: str) -> dict[str, bytes]:
    """Render one closed system prompt as ordered, unhashed raw-byte sections."""
    contract, closed_target = _closed_contract_and_target(config, target)
    if system not in {"A", "B", "C"}:
        raise PromptBundleError("PROMPT_CONTRACT_INVALID")
    corpus = _load_complete_pair_corpus_v1()
    selection = contract["fixed_pair_selection"]
    assert isinstance(selection, dict)
    if selection["corpus_sha256"] != corpus["corpus_sha256"]:
        raise PromptBundleError("PROMPT_CONTRACT_INVALID")
    pair_ids = (
        _load_retrieval_receipt_v1(contract, closed_target, corpus)
        if system == "C"
        else _require_pair_ids(selection["ordered_pair_ids"], "PROMPT_CONTRACT_INVALID")
    )
    pairs = _resolve_pairs(pair_ids, corpus)
    selection_label = "retrieved contract pair" if system == "C" else "fixed synthetic pair"
    demonstrations = "".join(
        f"Demonstration {index}: {selection_label} {pair_id} canonical complete-pair payload:\n"
        f"{canonical_json_bytes(pair).decode('utf-8')}"
        for index, (pair_id, pair) in enumerate(zip(pair_ids, pairs, strict=True), start=1)
    )
    output_schema = contract["output_schema"]
    assert isinstance(output_schema, Mapping)
    target_text = closed_target["source_text"]
    assert isinstance(target_text, str)
    section_text = {
        "shared_guidance": contract["shared_guidance"],
        "demonstrations": demonstrations,
        "target": f"Target source text:\n{target_text}",
        "frame_instructions": "" if system == "A" else contract["frame_instructions"],
        "adjudication_instructions": contract["adjudication_instructions"],
        "output_schema": output_schema["A" if system == "A" else "BC"],
        "evidence_rules": contract["evidence_rules"],
    }
    sections = {
        name: _raw_section(text, allow_empty=name == "frame_instructions" and system == "A")
        for name, text in section_text.items()
    }
    if tuple(sections) != PROMPT_SECTION_ORDER:
        raise PromptBundleError("PROMPT_RAW_BYTES_INVALID")
    raw = b"".join(sections.values())
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PromptBundleError("PROMPT_RAW_BYTES_INVALID") from error
    if not raw or b"\r" in raw or not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise PromptBundleError("PROMPT_RAW_BYTES_INVALID")
    return sections


def render_treatment_prompt_v1(config: object, target: object) -> dict[str, bytes]:
    """Render all three exact offline system prompts without publishing files."""
    return {
        system: b"".join(render_prompt_sections_v1(config, target, system).values())
        for system in ("A", "B", "C")
    }


def _validate_raw_prompt_bytes(raw: bytes) -> str:
    if (
        not isinstance(raw, bytes)
        or not raw
        or b"\r" in raw
        or not raw.endswith(b"\n")
        or raw.endswith(b"\n\n")
    ):
        raise PromptBundleError("PROMPT_RAW_BYTES_INVALID")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PromptBundleError("PROMPT_RAW_BYTES_INVALID") from error


def offline_lexical_token_count_v1(raw: bytes) -> int:
    """Count frozen standard-library lexical tokens over unnormalised prompt bytes."""
    return len(re.findall(r"(?u)\b\w+\b", _validate_raw_prompt_bytes(raw)))


def count_prompt_bytes_v1(raw: bytes) -> dict[str, int]:
    """Return raw UTF-8/LF accounting without canonicalising the prompt authority."""
    text = _validate_raw_prompt_bytes(raw)
    return {
        "utf8_byte_count": len(raw),
        "unicode_code_point_count": len(text),
        "logical_line_count": raw.count(b"\n"),
        "offline_lexical_token_count": offline_lexical_token_count_v1(raw),
    }


def _validate_demo_order(raw: bytes) -> None:
    first = raw.find(b"Demonstration 1:")
    second = raw.find(b"Demonstration 2:")
    if first != 0 or second <= first or raw.count(b"Demonstration ") != 2:
        raise PromptBundleError("TREATMENT_DIFF_NOT_ALLOWLISTED")


def validate_treatment_diffs_v1(
    sections: Mapping[str, Mapping[str, bytes]],
) -> dict[str, dict[str, list[str]]]:
    """Accept only the frozen A/B and B/C named-section treatment deltas."""
    if set(sections) != {"A", "B", "C"}:
        raise PromptBundleError("TREATMENT_DIFF_NOT_ALLOWLISTED")
    for system in ("A", "B", "C"):
        if (
            not isinstance(sections[system], Mapping)
            or tuple(sections[system]) != PROMPT_SECTION_ORDER
        ):
            raise PromptBundleError("TREATMENT_DIFF_NOT_ALLOWLISTED")
        for name, raw in sections[system].items():
            if name == "frame_instructions" and system == "A" and raw == b"":
                continue
            _validate_raw_prompt_bytes(raw)
        _validate_demo_order(sections[system]["demonstrations"])

    comparisons: dict[str, dict[str, list[str]]] = {}
    for label, left, right, allowed in (
        ("A_B", "A", "B", ["frame_instructions", "output_schema"]),
        ("B_C", "B", "C", ["demonstrations"]),
    ):
        observed = [
            name for name in PROMPT_SECTION_ORDER if sections[left][name] != sections[right][name]
        ]
        if observed != allowed:
            raise PromptBundleError("TREATMENT_DIFF_NOT_ALLOWLISTED")
        comparisons[label] = {"allowed_differences": allowed, "observed_differences": observed}
    return comparisons


def _response_records_v1(target_raw: bytes) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for system, path in _CONTRACT_RESPONSE_PATHS.items():
        try:
            raw = path.read_bytes()
        except OSError as error:
            raise PromptBundleError("PROMPT_RESPONSE_INVALID") from error
        parsed = validate_contract_response_origin_v1(raw, target_raw)
        if parsed.system != system:
            raise PromptBundleError("PROMPT_RESPONSE_INVALID")
        records[system] = {
            "path": f"fixtures/treatments/contract-response-{system.lower()}-v1.json",
            "sha256": sha256_bytes(raw),
            "origin": parsed.origin,
            "model_generated": parsed.model_generated,
            "test_only": True,
            "count_eligible": False,
        }
    return records


def _prompt_bundle_v1(config: object, target: object) -> tuple[dict[str, bytes], dict[str, object]]:
    contract, closed_target = _closed_contract_and_target(config, target)
    corpus = _load_complete_pair_corpus_v1()
    prompts = render_treatment_prompt_v1(config, target)
    sections = {
        system: render_prompt_sections_v1(config, target, system) for system in ("A", "B", "C")
    }
    comparisons = validate_treatment_diffs_v1(sections)
    selection = contract["fixed_pair_selection"]
    assert isinstance(selection, Mapping)
    retrieved = _load_retrieval_receipt_v1(contract, closed_target, corpus)
    target_raw = closed_target["source_text"]
    assert isinstance(target_raw, str)
    manifest: dict[str, object] = {
        "schema_version": "offline-prompt-bundle-v1",
        "contract_sha256": sha256_bytes(canonical_json_bytes(contract)),
        "target_sha256": closed_target["source_sha256"],
        "corpus_sha256": corpus["corpus_sha256"],
        "prompt_records": {
            system: {
                "path": f"prompts/treatments/system-{system.lower()}-v1.txt",
                "sha256": sha256_bytes(raw),
                "counts": count_prompt_bytes_v1(raw),
            }
            for system, raw in prompts.items()
        },
        "response_records": _response_records_v1(target_raw.encode("utf-8")),
        "section_hashes": {
            system: {name: sha256_bytes(raw) for name, raw in system_sections.items()}
            for system, system_sections in sections.items()
        },
        "pair_selection": {
            "A": list(_require_pair_ids(selection["ordered_pair_ids"], "PROMPT_CONTRACT_INVALID")),
            "B": list(_require_pair_ids(selection["ordered_pair_ids"], "PROMPT_CONTRACT_INVALID")),
            "C": list(retrieved),
        },
        "structural_comparison": comparisons,
        "offline_accounting": {
            system: count_prompt_bytes_v1(raw) for system, raw in prompts.items()
        },
        "provider_input_tokens": "not_applicable_red",
        "provider_output_tokens": "not_applicable_red",
        "maximum_output_tokens": "not_applicable_red",
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    return prompts, manifest


def build_prompt_bundle_manifest_v1(config: object, target: object) -> dict[str, object]:
    """Build the canonical projection for closed inputs without publishing artifacts."""
    _, manifest = _prompt_bundle_v1(config, target)
    return manifest


def write_offline_prompt_bundle_v1(
    output_root: Path, config: object, target: object
) -> dict[str, object]:
    """Publish exact prompt authority and its manifest together, permitting exact resume only."""
    if not isinstance(output_root, Path):
        raise PromptBundleError("PROMPT_BUNDLE_WRITE_INVALID")
    prompts, manifest = _prompt_bundle_v1(config, target)
    payloads = {
        **{
            f"prompts/treatments/system-{system.lower()}-v1.txt": raw
            for system, raw in prompts.items()
        },
        "prompts/treatments/prompt-bundle-manifest-v1.json": canonical_json_bytes(manifest),
    }
    try:
        write_exact_descriptor_files(output_root, payloads)
    except (FilesystemPolicyError, OSError, ValueError) as error:
        raise PromptBundleError("PROMPT_BUNDLE_WRITE_INVALID") from error
    return manifest
