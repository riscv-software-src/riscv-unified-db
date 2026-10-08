# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Closed standard-library retrieval proof over isolated synthetic pairs."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from specchoice_evidence.canonical import canonical_json_bytes, require_sha256, sha256_bytes
from specchoice_evidence.filesystem import (
    FilesystemPolicyError,
    read_authoritative_file,
    require_relative_posix_path,
)
from specchoice_measurement.strict_json import decode_strict_json

from specchoice_treatments.prompts import PromptBundleError, validate_complete_pair_side_v1

FORBIDDEN_QUERY_FIELDS = frozenset(
    {
        "case_id",
        "fixture_id",
        "gold",
        "gold_label",
        "delegation_frame",
        "frame",
        "primary_family",
        "decisive_axes",
        "relevance",
        "relevant_pair_ids",
        "final_disposition",
        "final_status",
        "parameter_status",
        "rank",
        "score",
        "similarity",
        "top_k",
        "case_identity",
        "family",
        "authority",
    }
)
_CONFIG_KEYS = frozenset(
    {
        "schema_version",
        "unicode_normalization",
        "case_normalization",
        "token_pattern",
        "pair_document_fields",
        "field_separator",
        "term_frequency",
        "inverse_document_frequency",
        "vector_normalization",
        "zero_vector_cosine",
        "ranking",
        "result_count",
        "score_serialization",
        "contract_sha256",
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
_PROMPT_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "contract_sha256",
        "target_sha256",
        "corpus_sha256",
        "prompt_records",
        "response_records",
        "section_hashes",
        "pair_selection",
        "structural_comparison",
        "offline_accounting",
        "provider_input_tokens",
        "provider_output_tokens",
        "maximum_output_tokens",
        "manifest_sha256",
    }
)
_CONFIG_VALUES = {
    "schema_version": "lexical-retrieval-contract-v1",
    "unicode_normalization": "NFC",
    "case_normalization": "casefold",
    "token_pattern": r"(?u)\b\w+\b",
    "pair_document_fields": [
        "shared_structure",
        "positive_source_text",
        "contrast_source_text",
        "discriminating_axes",
    ],
    "field_separator": "LF",
    "term_frequency": "raw_count",
    "inverse_document_frequency": "ln((1+N)/(1+df))+1",
    "vector_normalization": "l2",
    "zero_vector_cosine": 0,
    "ranking": "cosine_desc_pair_id_asc",
    "result_count": 2,
    "score_serialization": ".17g",
}


class RetrievalContractError(ValueError):
    """Stable failure emitted by the closed retrieval contract."""


@dataclass(frozen=True)
class RetrievedPair:
    """One complete ranked pair, retained as an atomic result."""

    pair_id: str
    cosine_score: float
    positive_source_text: str
    contrast_source_text: str


def _canonical_read(root: Path, relative_path: str, code: str) -> tuple[dict[str, object], bytes]:
    try:
        require_relative_posix_path(relative_path)
        _, raw = read_authoritative_file(root, relative_path)
        value = decode_strict_json(raw)
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, ValueError) as error:
        raise RetrievalContractError(code) from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise RetrievalContractError(code)
    return value, raw


def _non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\r" not in value


def _contains_forbidden_query_field(value: object) -> bool:
    if isinstance(value, Mapping):
        return bool(FORBIDDEN_QUERY_FIELDS & set(value)) or any(
            _contains_forbidden_query_field(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_query_field(item) for item in value)
    return False


def _self_hash_valid(value: Mapping[str, object], field: str) -> bool:
    return value.get(field) == sha256_bytes(
        canonical_json_bytes({key: item for key, item in value.items() if key != field})
    )


def _validate_retrieval_contract_v1(value: object) -> dict[str, object]:
    if set(value) != _CONFIG_KEYS or any(
        value.get(key) != expected for key, expected in _CONFIG_VALUES.items()
    ):
        raise RetrievalContractError("RETRIEVAL_CONFIG_INVALID")
    try:
        require_sha256(value.get("contract_sha256"))
    except (TypeError, ValueError) as error:
        raise RetrievalContractError("RETRIEVAL_CONFIG_INVALID") from error
    if not _self_hash_valid(value, "contract_sha256"):
        raise RetrievalContractError("RETRIEVAL_CONFIG_INVALID")
    return value


def load_retrieval_contract_v1(root: Path, relative_path: str) -> dict[str, object]:
    """Read and validate the immutable lexical algorithm declaration."""
    value, _ = _canonical_read(root, relative_path, "RETRIEVAL_CONFIG_INVALID")
    return _validate_retrieval_contract_v1(value)


def validate_test_only_target_v1(target: object) -> dict[str, object]:
    """Reject non-isolated or authority-bearing target material before tokenization."""
    if not isinstance(target, dict):
        raise RetrievalContractError("RETRIEVAL_TARGET_INVALID")
    if _contains_forbidden_query_field(target):
        raise RetrievalContractError("RETRIEVAL_QUERY_FIELD_FORBIDDEN")
    if set(target) != _TARGET_KEYS:
        raise RetrievalContractError("RETRIEVAL_TARGET_INVALID")
    if (
        target.get("schema_version") != "synthetic-treatment-target-v1"
        or target.get("test_only") is not True
        or target.get("count_eligible") is not False
    ):
        raise RetrievalContractError("RETRIEVAL_TEST_ONLY_REQUIRED")
    if not _non_empty_text(target.get("target_id")) or not _non_empty_text(
        target.get("source_text")
    ):
        raise RetrievalContractError("RETRIEVAL_TARGET_INVALID")
    try:
        require_sha256(target.get("source_sha256"))
        require_sha256(target.get("record_sha256"))
    except (TypeError, ValueError) as error:
        raise RetrievalContractError("RETRIEVAL_TARGET_INVALID") from error
    source_text = target["source_text"]
    assert isinstance(source_text, str)
    if target.get("source_sha256") != sha256_bytes(
        source_text.encode("utf-8")
    ) or not _self_hash_valid(target, "record_sha256"):
        raise RetrievalContractError("RETRIEVAL_TARGET_INVALID")
    return target


def _validate_side(value: object, status: str) -> dict[str, object]:
    try:
        validate_complete_pair_side_v1(value, status)
    except PromptBundleError as error:
        raise RetrievalContractError("RETRIEVAL_PAIR_INCOMPLETE") from error
    if not isinstance(value, dict):
        raise RetrievalContractError("RETRIEVAL_PAIR_INCOMPLETE")
    return value


def validate_test_only_corpus_v1(corpus: object) -> tuple[dict[str, object], ...]:
    """Validate complete, sorted synthetic pairs without silently deduplicating them."""
    if (
        not isinstance(corpus, dict)
        or set(corpus) != _CORPUS_KEYS
        or corpus.get("schema_version") != "synthetic-complete-pair-corpus-v1"
    ):
        raise RetrievalContractError("RETRIEVAL_CORPUS_INVALID")
    if corpus.get("test_only") is not True or corpus.get("count_eligible") is not False:
        raise RetrievalContractError("RETRIEVAL_TEST_ONLY_REQUIRED")
    try:
        require_sha256(corpus.get("corpus_sha256"))
    except (TypeError, ValueError) as error:
        raise RetrievalContractError("RETRIEVAL_CORPUS_INVALID") from error
    if not _self_hash_valid(corpus, "corpus_sha256"):
        raise RetrievalContractError("RETRIEVAL_CORPUS_INVALID")
    pairs = corpus.get("pairs")
    if not isinstance(pairs, list):
        raise RetrievalContractError("RETRIEVAL_CORPUS_INVALID")
    pair_ids: list[str] = []
    complete: list[dict[str, object]] = []
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != _PAIR_KEYS:
            raise RetrievalContractError("RETRIEVAL_CORPUS_INVALID")
        pair_id = pair.get("pair_id")
        shared_structure = pair.get("shared_structure")
        axes = pair.get("discriminating_axes")
        if (
            not _non_empty_text(pair_id)
            or not isinstance(shared_structure, list)
            or not shared_structure
            or any(not _non_empty_text(item) for item in shared_structure)
            or len(shared_structure) != len(set(shared_structure))
            or not isinstance(axes, list)
            or not axes
            or any(not _non_empty_text(item) for item in axes)
            or axes != sorted(set(axes))
        ):
            raise RetrievalContractError("RETRIEVAL_CORPUS_INVALID")
        if pair.get("test_only") is not True or pair.get("count_eligible") is not False:
            raise RetrievalContractError("RETRIEVAL_TEST_ONLY_REQUIRED")
        _validate_side(pair.get("positive"), "accept")
        _validate_side(pair.get("contrast"), "classify_out")
        assert isinstance(pair_id, str)
        pair_ids.append(pair_id)
        complete.append(pair)
    if len(pair_ids) != len(set(pair_ids)):
        raise RetrievalContractError("RETRIEVAL_PAIR_ID_DUPLICATE")
    if len(complete) < 2:
        raise RetrievalContractError("INSUFFICIENT_RETRIEVAL_PAIRS")
    return tuple(complete)


def tokenize_retrieval_text_v1(text: str, config: Mapping[str, object]) -> tuple[str, ...]:
    """Apply exactly the frozen NFC/casefold/regex lexical contract."""
    if not isinstance(text, str) or config.get("token_pattern") != _CONFIG_VALUES["token_pattern"]:
        raise RetrievalContractError("RETRIEVAL_CONFIG_INVALID")
    normalized = unicodedata.normalize("NFC", text).casefold()
    return tuple(re.findall(str(config["token_pattern"]), normalized))


def construct_pair_document_v1(pair: Mapping[str, object], config: Mapping[str, object]) -> str:
    """Join only frozen pair fields, never their frames or authority metadata."""
    if (
        config.get("pair_document_fields") != _CONFIG_VALUES["pair_document_fields"]
        or config.get("field_separator") != "LF"
    ):
        raise RetrievalContractError("RETRIEVAL_CONFIG_INVALID")
    positive = pair.get("positive")
    contrast = pair.get("contrast")
    if not isinstance(positive, Mapping) or not isinstance(contrast, Mapping):
        raise RetrievalContractError("RETRIEVAL_PAIR_INCOMPLETE")
    shared_structure = pair.get("shared_structure")
    axes = pair.get("discriminating_axes")
    if not isinstance(shared_structure, list) or not isinstance(axes, list):
        raise RetrievalContractError("RETRIEVAL_PAIR_INCOMPLETE")
    values = (
        "\n".join(str(item) for item in shared_structure),
        positive.get("source_text"),
        contrast.get("source_text"),
        "\n".join(sorted(str(item) for item in axes)),
    )
    if any(not isinstance(value, str) for value in values):
        raise RetrievalContractError("RETRIEVAL_PAIR_INCOMPLETE")
    return "\n".join(values)


def _cosine(query: Counter[str], document: Counter[str], idf: Mapping[str, float]) -> float:
    query_norm = math.sqrt(
        sum((count * idf.get(token, 0.0)) ** 2 for token, count in query.items())
    )
    document_norm = math.sqrt(
        sum((count * idf.get(token, 0.0)) ** 2 for token, count in document.items())
    )
    if query_norm == 0.0 or document_norm == 0.0:
        return 0.0
    numerator = sum(
        query_count * idf.get(token, 0.0) * document.get(token, 0) * idf.get(token, 0.0)
        for token, query_count in query.items()
    )
    return numerator / (query_norm * document_norm)


def rank_complete_pairs_v1(
    *,
    target: Mapping[str, object],
    corpus: object,
    config: Mapping[str, object],
) -> tuple[RetrievedPair, ...]:
    """Rank complete isolated pairs using frozen raw TF-IDF and full-float ties."""
    validated_target = validate_test_only_target_v1(dict(target))
    pairs = validate_test_only_corpus_v1(corpus)
    _validate_retrieval_contract_v1(dict(config))
    documents = {
        str(pair["pair_id"]): Counter(
            tokenize_retrieval_text_v1(construct_pair_document_v1(pair, config), config)
        )
        for pair in pairs
    }
    document_frequency = Counter(token for document in documents.values() for token in document)
    idf = {
        token: math.log((1 + len(documents)) / (1 + frequency)) + 1
        for token, frequency in document_frequency.items()
    }
    source_text = validated_target["source_text"]
    assert isinstance(source_text, str)
    query = Counter(tokenize_retrieval_text_v1(source_text, config))
    scored: list[RetrievedPair] = []
    for pair in pairs:
        pair_id = pair["pair_id"]
        positive = pair["positive"]
        contrast = pair["contrast"]
        assert (
            isinstance(pair_id, str)
            and isinstance(positive, Mapping)
            and isinstance(contrast, Mapping)
        )
        positive_source_text = positive["source_text"]
        contrast_source_text = contrast["source_text"]
        assert isinstance(positive_source_text, str) and isinstance(contrast_source_text, str)
        scored.append(
            RetrievedPair(
                pair_id,
                _cosine(query, documents[pair_id], idf),
                positive_source_text,
                contrast_source_text,
            )
        )
    return tuple(sorted(scored, key=lambda item: (-item.cosine_score, item.pair_id))[:2])


def _validate_prompt_manifest_v1(
    manifest: object,
    *,
    target: Mapping[str, object],
    corpus: Mapping[str, object],
) -> list[str]:
    if not isinstance(manifest, dict) or set(manifest) != _PROMPT_MANIFEST_KEYS:
        raise RetrievalContractError("RETRIEVAL_PROMPT_SELECTION_MISMATCH")
    if manifest.get("schema_version") != "offline-prompt-bundle-v1":
        raise RetrievalContractError("RETRIEVAL_PROMPT_SELECTION_MISMATCH")
    try:
        for field in ("contract_sha256", "target_sha256", "corpus_sha256", "manifest_sha256"):
            require_sha256(manifest.get(field))
    except (TypeError, ValueError) as error:
        raise RetrievalContractError("RETRIEVAL_PROMPT_SELECTION_MISMATCH") from error
    if not _self_hash_valid(manifest, "manifest_sha256"):
        raise RetrievalContractError("RETRIEVAL_PROMPT_SELECTION_MISMATCH")
    if manifest.get("target_sha256") != target.get("source_sha256") or manifest.get(
        "corpus_sha256"
    ) != corpus.get("corpus_sha256"):
        raise RetrievalContractError("RETRIEVAL_PROMPT_SELECTION_MISMATCH")
    selection = manifest.get("pair_selection")
    if (
        not isinstance(selection, Mapping)
        or set(selection) != {"A", "B", "C"}
        or not isinstance(selection.get("C"), list)
        or len(selection["C"]) != 2
        or any(not _non_empty_text(pair_id) for pair_id in selection["C"])
        or len(set(selection["C"])) != 2
    ):
        raise RetrievalContractError("RETRIEVAL_PROMPT_SELECTION_MISMATCH")
    return list(selection["C"])


def load_prompt_manifest_v1(
    root: Path,
    relative_path: str,
    *,
    target: Mapping[str, object],
    corpus: Mapping[str, object],
) -> dict[str, object]:
    """Read the declared prompt manifest through the experiment-root descriptor."""
    manifest, _ = _canonical_read(root, relative_path, "RETRIEVAL_PROMPT_SELECTION_MISMATCH")
    _validate_prompt_manifest_v1(manifest, target=target, corpus=corpus)
    return manifest


def build_retrieval_report_v1(
    *,
    target: Mapping[str, object],
    corpus: Mapping[str, object],
    config: Mapping[str, object],
    prompt_manifest: Mapping[str, object],
) -> dict[str, object]:
    """Build the canonical non-authoritative report from four declared inputs."""
    results = rank_complete_pairs_v1(target=target, corpus=corpus, config=config)
    target_valid = validate_test_only_target_v1(dict(target))
    corpus_valid = validate_test_only_corpus_v1(dict(corpus))
    config_valid = _validate_retrieval_contract_v1(dict(config))
    prompt_selection = _validate_prompt_manifest_v1(
        dict(prompt_manifest),
        target=target_valid,
        corpus=dict(corpus),
    )
    result_values = [
        {
            "pair_id": item.pair_id,
            "cosine_score": format(item.cosine_score, ".17g"),
            "positive_source_text": item.positive_source_text,
            "contrast_source_text": item.contrast_source_text,
        }
        for item in results
    ]
    report = {
        "schema_version": "test-only-retrieval-contract-report-v1",
        "test_only": True,
        "count_eligible": False,
        "config_file_sha256": sha256_bytes(canonical_json_bytes(config_valid)),
        "config_contract_sha256": config_valid["contract_sha256"],
        "target_file_sha256": sha256_bytes(canonical_json_bytes(target_valid)),
        "target_record_sha256": target_valid["record_sha256"],
        "target_source_sha256": target_valid["source_sha256"],
        "corpus_file_sha256": sha256_bytes(canonical_json_bytes(dict(corpus))),
        "corpus_content_sha256": corpus["corpus_sha256"],
        "prompt_manifest_file_sha256": sha256_bytes(canonical_json_bytes(dict(prompt_manifest))),
        "query_source_field": "source_text",
        "eligible_pair_count": len(corpus_valid),
        "results": result_values,
        "ordering_rule": str(config["ranking"]),
        "prompt_c_pair_ids_match": [item.pair_id for item in results] == prompt_selection,
    }
    if not report["prompt_c_pair_ids_match"]:
        raise RetrievalContractError("RETRIEVAL_PROMPT_SELECTION_MISMATCH")
    report["report_sha256"] = sha256_bytes(canonical_json_bytes(report))
    return report


def verify_retrieval_contract_v1(
    *,
    target: Mapping[str, object],
    corpus: Mapping[str, object],
    config: Mapping[str, object],
    prompt_manifest: Mapping[str, object],
) -> tuple[RetrievedPair, ...]:
    """Verify the closed contract and return only the two ranked whole pairs."""
    build_retrieval_report_v1(
        target=target,
        corpus=corpus,
        config=config,
        prompt_manifest=prompt_manifest,
    )
    return rank_complete_pairs_v1(target=target, corpus=corpus, config=config)
