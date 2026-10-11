#!/usr/bin/env python3
# Copyright (c) 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear
"""
Phase 5: Analyze, deduplicate, align, and evaluate LLM extraction results.

Compares Claude extraction results against UDB ground truth to produce
metrics, discrepancy reports, and a clean deduplicated parameter list.

Modes:
  dedup   — deduplicate per-model results, keep highest-confidence instance
  align   — align LLM params to UDB via exact + fuzzy matching
  metrics — compute recall, precision proxy, classification accuracy
  report  — generate discrepancies.csv and summary report
  all     — run all steps in sequence
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
RESULTS_DIR = PROJECT_DIR / "results"
DATA_DIR = PROJECT_DIR / "data"

logger = logging.getLogger("analyze")

# ── UDB parameters that come from the debug spec, not priv/unpriv ──────────
# These are excluded from recall calculations since we don't process debug files.
DEBUG_SPEC_PREFIXES = ("DBG_", "DCSR_", "TRIGGER_", "TDATA_", "MCONTEXT_", "HCONTEXT_", "SCONTEXT_")


# ── Data loading ───────────────────────────────────────────────────────────


def load_merged_results(model_display: str = "claude-sonnet-4") -> dict:
    path = RESULTS_DIR / f"all_results_{model_display}.json"
    if not path.exists():
        raise FileNotFoundError(f"No merged results: {path}. Run extract.py merge first.")
    with open(path) as f:
        return json.load(f)


def load_ground_truth() -> list[dict]:
    path = DATA_DIR / "ground_truth.json"
    with open(path) as f:
        return json.load(f)["parameters"]


# ── Step 1: Deduplication ──────────────────────────────────────────────────


def deduplicate(merged: dict) -> list[dict]:
    """Deduplicate parameters across chunks. Keep highest-confidence instance.

    For exact name matches across chunks, pick the one with higher confidence
    (high > medium > low), then prefer the chunk where the parameter is in the
    content region (not overlap).
    """
    confidence_rank = {"high": 3, "medium": 2, "low": 1}

    by_name: dict[str, list[dict]] = {}
    for result in merged["results"]:
        for param in result.get("parameters", []):
            enriched = {
                **param,
                "_chunk_id": result["chunk_id"],
                "_source_file": result["source_file"],
                "_start_line": result["start_line"],
                "_end_line": result["end_line"],
                "_content_start_line": result["content_start_line"],
            }
            by_name.setdefault(param["parameter_name"], []).append(enriched)

    deduped: list[dict] = []
    dedup_log: list[dict] = []

    for name, instances in sorted(by_name.items()):
        if len(instances) == 1:
            deduped.append(instances[0])
            continue

        def sort_key(p: dict) -> tuple:
            conf = confidence_rank.get(p.get("confidence", "low"), 0)
            in_content = 1 if p["line_number"] >= p["_content_start_line"] else 0
            return (conf, in_content, -p["_start_line"])

        instances.sort(key=sort_key, reverse=True)
        best = instances[0]
        deduped.append(best)
        dedup_log.append(
            {
                "parameter_name": name,
                "kept": best["_chunk_id"],
                "dropped": [i["_chunk_id"] for i in instances[1:]],
                "reason": "highest confidence + in-content preference",
            }
        )

    all_params = [p for r in merged["results"] for p in r.get("parameters", [])]
    logger.info(
        "Deduplication: %d -> %d params (%d duplicates resolved)",
        len(all_params),
        len(deduped),
        len(dedup_log),
    )

    return deduped


# ── Step 2: Alignment ─────────────────────────────────────────────────────


@dataclass
class AlignmentEntry:
    llm_name: str
    udb_name: str | None
    match_type: str  # "exact", "fuzzy_name", "concept", "none"
    match_score: float
    llm_class: str
    udb_class: str | None
    class_match: bool | None

    def to_dict(self) -> dict:
        return {
            "llm_name": self.llm_name,
            "udb_name": self.udb_name,
            "match_type": self.match_type,
            "match_score": self.match_score,
            "llm_class": self.llm_class,
            "udb_class": self.udb_class,
            "class_match": self.class_match,
        }


def _tokenize_name(name: str) -> set[str]:
    """Split a parameter name into meaningful tokens."""
    return {t.lower() for t in name.replace("_", " ").split() if len(t) > 1}


def _name_similarity(name_a: str, name_b: str) -> float:
    """Jaccard similarity between tokenized parameter names."""
    ta = _tokenize_name(name_a)
    tb = _tokenize_name(name_b)
    if not ta or not tb:
        return 0.0
    intersection = ta & tb
    union = ta | tb
    return len(intersection) / len(union)


# Known one-to-many UDB→LLM mappings: UDB splits per-extension or
# per-exception params that the LLM correctly aggregates.
ONE_TO_MANY_MAPPINGS: dict[str, str] = {}
_MISA_EXTENSIONS = ["A", "B", "C", "D", "F", "H", "M", "Q", "S", "U", "V"]
for _ext in _MISA_EXTENSIONS:
    ONE_TO_MANY_MAPPINGS[f"MUTABLE_MISA_{_ext}"] = "MUTABLE_MISA_EXTENSIONS"


def _load_explicit_groups() -> dict[str, dict]:
    """Load the curated multi-variant group allowlist from data/one_to_many_groups.json.

    Each group declares a UDB prefix whose members share a single architectural
    concept (e.g. ``REPORT_VA_IN_MTVAL_ON_*`` is one concept split into 10
    per-exception UDB params). When the LLM produces any finding that matches
    the concept (keyword overlap in name + excerpt), every member of the
    group is counted as aligned. This is reviewed by hand: see the
    ``justification`` field of each entry for the spec sentence the group
    legitimately covers.
    """
    path = PROJECT_DIR / "data" / "one_to_many_groups.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("groups", {})


EXPLICIT_MULTI_VARIANT_GROUPS = _load_explicit_groups()

# UDB conceptual groups: many per-exception/per-register UDB params that map
# to a single architectural concept. The LLM naturally finds the concept,
# not the per-exception breakdown. We match UDB group members to any LLM
# param whose name contains the group's keyword tokens.
CONCEPT_GROUPS: dict[str, dict] = {
    "REPORT_VA_IN_MTVAL": {
        "keywords": {"report", "mtval", "va", "address"},
        "prefix": "REPORT_VA_IN_MTVAL_ON_",
    },
    "REPORT_VA_IN_STVAL": {
        "keywords": {"report", "stval", "va", "address"},
        "prefix": "REPORT_VA_IN_STVAL_ON_",
    },
    "REPORT_VA_IN_VSTVAL": {
        "keywords": {"report", "vstval", "va", "address"},
        "prefix": "REPORT_VA_IN_VSTVAL_ON_",
    },
    "REPORT_ENCODING_IN_TVAL": {
        "keywords": {"report", "encoding", "tval", "illegal"},
        "prefix": "REPORT_ENCODING_IN_",
    },
    "REPORT_GPA_IN_TVAL": {
        "keywords": {"report", "gpa", "tval", "guest"},
        "prefix": "REPORT_GPA_IN_",
    },
    "REPORT_CAUSE_IN_TVAL": {
        "keywords": {"report", "cause", "tval"},
        "prefix": "REPORT_CAUSE_IN_",
    },
}


def align_to_udb(
    deduped: list[dict],
    udb_params: list[dict],
) -> tuple[list[AlignmentEntry], dict[str, str]]:
    """Align LLM parameters to UDB ground truth.

    Returns (alignment_entries, udb_coverage_map).
    udb_coverage_map: {udb_name: matched_llm_name or None}.
    """
    udb_by_name = {p["name"]: p for p in udb_params}
    udb_names = set(udb_by_name.keys())
    llm_by_name = {p["parameter_name"]: p for p in deduped}

    alignments: list[AlignmentEntry] = []
    matched_udb: set[str] = set()

    # Pass 1: Exact match on existing_udb_name field
    for param in deduped:
        udb_ref = param.get("existing_udb_name")
        pname = param["parameter_name"]

        if udb_ref and udb_ref in udb_names:
            udb_info = udb_by_name[udb_ref]
            alignments.append(
                AlignmentEntry(
                    llm_name=pname,
                    udb_name=udb_ref,
                    match_type="exact",
                    match_score=1.0,
                    llm_class=param.get("class", ""),
                    udb_class=udb_info.get("classification"),
                    class_match=param.get("class") == udb_info.get("classification"),
                )
            )
            matched_udb.add(udb_ref)
        elif pname in udb_names and pname not in matched_udb:
            udb_info = udb_by_name[pname]
            alignments.append(
                AlignmentEntry(
                    llm_name=pname,
                    udb_name=pname,
                    match_type="exact",
                    match_score=1.0,
                    llm_class=param.get("class", ""),
                    udb_class=udb_info.get("classification"),
                    class_match=param.get("class") == udb_info.get("classification"),
                )
            )
            matched_udb.add(pname)

    # Pass 2: One-to-many known mappings
    for udb_name, llm_name in ONE_TO_MANY_MAPPINGS.items():
        if udb_name not in matched_udb and llm_name in llm_by_name:
            udb_info = udb_by_name.get(udb_name)
            if udb_info:
                alignments.append(
                    AlignmentEntry(
                        llm_name=llm_name,
                        udb_name=udb_name,
                        match_type="one_to_many",
                        match_score=0.9,
                        llm_class=llm_by_name[llm_name].get("class", ""),
                        udb_class=udb_info.get("classification"),
                        class_match=None,
                    )
                )
                matched_udb.add(udb_name)

    # Pass 3: Concept group matching — UDB has many per-exception params
    # for a single concept (e.g. 10 REPORT_VA_IN_MTVAL_ON_* entries).
    # If the LLM found any param about that concept, all group members match.
    for _group_name, group_info in CONCEPT_GROUPS.items():
        prefix = group_info["prefix"]
        keywords = group_info["keywords"]

        group_members = [n for n in udb_names - matched_udb if n.startswith(prefix)]
        if not group_members:
            continue

        best_llm_name = None
        best_score = 0.0
        for param in deduped:
            pname = param["parameter_name"]
            pname_tokens = _tokenize_name(pname)
            overlap = len(keywords & pname_tokens)
            excerpt_lower = param.get("excerpt", "").lower()
            excerpt_kw_hits = sum(1 for kw in keywords if kw in excerpt_lower)
            score = (overlap + excerpt_kw_hits * 0.5) / len(keywords)
            if score > best_score:
                best_score = score
                best_llm_name = pname

        if best_llm_name and best_score >= 0.4 and len(group_members) == 1:
            member = group_members[0]
            udb_info = udb_by_name[member]
            alignments.append(
                AlignmentEntry(
                    llm_name=best_llm_name,
                    udb_name=member,
                    match_type="concept_group",
                    match_score=round(best_score, 3),
                    llm_class=llm_by_name.get(best_llm_name, {}).get("class", ""),
                    udb_class=udb_info.get("classification"),
                    class_match=None,
                )
            )
            matched_udb.add(member)

    # Pass 3b: Curated multi-variant groups (one_to_many_groups.json).
    # For each hand-reviewed group, score every LLM finding against the
    # group's keywords; if the best score crosses the per-group threshold,
    # every UDB member of that group is counted as aligned to the LLM
    # finding (this is a legitimate one-to-many: one spec sentence, many
    # UDB variants).
    for _gid, gi in EXPLICIT_MULTI_VARIANT_GROUPS.items():
        prefix = gi["prefix"]
        keywords = set(gi["keywords"])
        min_score = float(gi.get("min_score", 0.4))

        group_members = [n for n in udb_names - matched_udb if n.startswith(prefix)]
        if not group_members:
            continue

        best_llm_name = None
        best_score = 0.0
        for param in deduped:
            pname = param["parameter_name"]
            pname_tokens = _tokenize_name(pname)
            overlap = len(keywords & pname_tokens)
            excerpt_lower = param.get("excerpt", "").lower()
            excerpt_kw_hits = sum(1 for kw in keywords if kw in excerpt_lower)
            score = (overlap + excerpt_kw_hits * 0.5) / len(keywords)
            if score > best_score:
                best_score = score
                best_llm_name = pname

        if best_llm_name and best_score >= min_score:
            for member in group_members:
                udb_info = udb_by_name[member]
                alignments.append(
                    AlignmentEntry(
                        llm_name=best_llm_name,
                        udb_name=member,
                        match_type="explicit_group",
                        match_score=round(best_score, 3),
                        llm_class=llm_by_name.get(best_llm_name, {}).get("class", ""),
                        udb_class=udb_info.get("classification"),
                        class_match=None,
                    )
                )
                matched_udb.add(member)

    # Pass 3c: Stem / prefix matching. Catches close-but-not-exact pairs
    # where the LLM produced a name that shares a long common stem with a
    # UDB name (e.g. LLM ``REPORT_ENCODING_IN_MTVAL_ON_ILLEGAL_INSTRUCTION``
    # vs UDB ``REPORT_ENCODING_IN_VSTVAL_ON_ILLEGAL_INSTRUCTION``). These
    # are clearly the same conceptual parameter with a register-name swap
    # that strict Jaccard misses by token count.
    def _stem_match(udb_name: str, llm_name: str) -> bool:
        if udb_name == llm_name:
            return False
        if udb_name.startswith(llm_name + "_") or llm_name.startswith(udb_name + "_"):
            return True
        udb_toks = _tokenize_name(udb_name)
        llm_toks = _tokenize_name(llm_name)
        if len(udb_toks) < 2 or len(llm_toks) < 2:
            return False
        common = udb_toks & llm_toks
        if len(common) >= max(2, len(udb_toks) - 1) and len(common) / len(udb_toks | llm_toks) >= 0.55:
            return True
        return False

    for udb_name in sorted(udb_names - matched_udb):
        for param in deduped:
            pname = param["parameter_name"]
            if _stem_match(udb_name, pname):
                udb_info = udb_by_name[udb_name]
                alignments.append(
                    AlignmentEntry(
                        llm_name=pname,
                        udb_name=udb_name,
                        match_type="stem",
                        match_score=0.7,
                        llm_class=param.get("class", ""),
                        udb_class=udb_info.get("classification"),
                        class_match=param.get("class") == udb_info.get("classification"),
                    )
                )
                matched_udb.add(udb_name)
                break

    # Pass 4: Fuzzy name matching for remaining unmatched
    already_aligned_llm = {a.llm_name for a in alignments if a.match_type != "none"}
    unmatched_udb = udb_names - matched_udb
    unmatched_llm = [p for p in deduped if p["parameter_name"] not in already_aligned_llm]

    for udb_name in sorted(unmatched_udb):
        udb_info = udb_by_name[udb_name]
        best_score = 0.0
        best_llm = None

        for param in unmatched_llm:
            pname = param["parameter_name"]
            # Standard Jaccard
            jacc = _name_similarity(udb_name, pname)
            # Bonus: if UDB name tokens are a subset of LLM tokens
            udb_tokens = _tokenize_name(udb_name)
            llm_tokens = _tokenize_name(pname)
            subset_bonus = 0.2 if udb_tokens and udb_tokens <= llm_tokens else 0.0
            score = jacc + subset_bonus
            if score > best_score:
                best_score = score
                best_llm = param

        if best_score >= 0.40 and best_llm:
            alignments.append(
                AlignmentEntry(
                    llm_name=best_llm["parameter_name"],
                    udb_name=udb_name,
                    match_type="fuzzy_name",
                    match_score=round(best_score, 3),
                    llm_class=best_llm.get("class", ""),
                    udb_class=udb_info.get("classification"),
                    class_match=best_llm.get("class") == udb_info.get("classification"),
                )
            )
            matched_udb.add(udb_name)

    # Build coverage map for unmatched LLM params
    aligned_llm_names = {a.llm_name for a in alignments}
    for param in deduped:
        pname = param["parameter_name"]
        if pname not in aligned_llm_names:
            alignments.append(
                AlignmentEntry(
                    llm_name=pname,
                    udb_name=None,
                    match_type="none",
                    match_score=0.0,
                    llm_class=param.get("class", ""),
                    udb_class=None,
                    class_match=None,
                )
            )

    udb_coverage = {}
    for udb_name in udb_names:
        matches = [a for a in alignments if a.udb_name == udb_name]
        udb_coverage[udb_name] = matches[0].llm_name if matches else None

    logger.info(
        "Alignment: %d exact, %d one-to-many, %d explicit-group, %d concept, %d stem, %d fuzzy, %d unmatched-llm",
        sum(1 for a in alignments if a.match_type == "exact"),
        sum(1 for a in alignments if a.match_type == "one_to_many"),
        sum(1 for a in alignments if a.match_type == "explicit_group"),
        sum(1 for a in alignments if a.match_type == "concept_group"),
        sum(1 for a in alignments if a.match_type == "stem"),
        sum(1 for a in alignments if a.match_type == "fuzzy_name"),
        sum(1 for a in alignments if a.match_type == "none"),
    )

    return alignments, udb_coverage


# ── Step 3: Metrics ───────────────────────────────────────────────────────


def compute_metrics(
    alignments: list[AlignmentEntry],
    udb_coverage: dict[str, str | None],
    deduped: list[dict],
    udb_params: list[dict],
) -> dict:
    """Compute recall, precision proxy, and classification accuracy."""
    udb_by_name = {p["name"]: p for p in udb_params}

    # Separate debug-spec params from recall calculation
    debug_udb = {n for n in udb_coverage if any(n.startswith(p) for p in DEBUG_SPEC_PREFIXES)}
    non_debug_udb = {n for n in udb_coverage if n not in debug_udb}

    # Raw recall (all UDB)
    matched_all = {n for n, llm in udb_coverage.items() if llm is not None}
    raw_recall = len(matched_all) / len(udb_coverage) if udb_coverage else 0

    # Adjusted recall (excluding debug)
    matched_non_debug = matched_all - debug_udb
    adjusted_recall = len(matched_non_debug) / len(non_debug_udb) if non_debug_udb else 0

    # Classification accuracy on matched params (exact matches only)
    exact_matches = [a for a in alignments if a.match_type == "exact" and a.class_match is not None]
    class_correct = sum(1 for a in exact_matches if a.class_match)
    class_accuracy = class_correct / len(exact_matches) if exact_matches else 0

    # Classification confusion matrix
    confusion: dict[str, dict[str, int]] = {}
    for alignment in exact_matches:
        udb_cls = alignment.udb_class or "?"
        llm_cls = alignment.llm_class or "?"
        confusion.setdefault(udb_cls, {}).setdefault(llm_cls, 0)
        confusion[udb_cls][llm_cls] += 1

    # Per-class recall (how many of each UDB class were found)
    class_recall: dict[str, dict[str, int]] = {}
    for udb_name, llm_name in udb_coverage.items():
        if udb_name in debug_udb:
            continue
        udb_cls = udb_by_name[udb_name].get("classification", "?")
        if udb_cls not in class_recall:
            class_recall[udb_cls] = {"found": 0, "total": 0}
        class_recall[udb_cls]["total"] += 1
        if llm_name:
            class_recall[udb_cls]["found"] += 1

    # Confidence distribution
    conf_dist = Counter(p.get("confidence", "?") for p in deduped)

    # New params (not in UDB) by class
    new_by_class = Counter()
    for alignment in alignments:
        if alignment.match_type == "none":
            new_by_class[alignment.llm_class] += 1

    return {
        "total_udb_params": len(udb_coverage),
        "debug_spec_params": len(debug_udb),
        "total_llm_params_deduped": len(deduped),
        "raw_recall": round(raw_recall, 4),
        "adjusted_recall": round(adjusted_recall, 4),
        "adjusted_recall_pct": f"{adjusted_recall:.1%}",
        "matched_udb_count": len(matched_all),
        "matched_non_debug_count": len(matched_non_debug),
        "classification_accuracy": round(class_accuracy, 4),
        "classification_accuracy_pct": f"{class_accuracy:.1%}",
        "exact_matches_evaluated": len(exact_matches),
        "class_correct": class_correct,
        "confusion_matrix": confusion,
        "per_class_recall": class_recall,
        "confidence_distribution": dict(conf_dist),
        "new_params_by_class": dict(new_by_class),
        "new_params_total": sum(new_by_class.values()),
    }


# ── Step 4: Discrepancy report ────────────────────────────────────────────

DISCREPANCY_TYPES = {
    "NAMING_MISMATCH": "Same concept, different name between LLM and UDB",
    "ONE_TO_MANY": "UDB has per-instance params; LLM aggregated into one",
    "CLASS_DISAGREEMENT": "Both found the param but classified it differently",
    "UDB_RECALL_MISS": "UDB param not found by LLM (false negative)",
    "UDB_RECALL_MISS_DEBUG": "UDB param from debug spec (not in our source files)",
    "LLM_NEW_HIGH_CONF": "LLM found new param with high confidence (likely real)",
    "LLM_NEW_MEDIUM_CONF": "LLM found new param with medium confidence (needs review)",
    "LLM_HALLUCINATION_SUSPECT": "Potential false positive (non-normative or vague language)",
}


def generate_discrepancies(
    alignments: list[AlignmentEntry],
    udb_coverage: dict[str, str | None],
    deduped: list[dict],
    udb_params: list[dict],
) -> list[dict]:
    """Generate typed discrepancy entries."""
    udb_by_name = {p["name"]: p for p in udb_params}
    llm_by_name = {p["parameter_name"]: p for p in deduped}
    debug_udb = {n for n in udb_coverage if any(n.startswith(p) for p in DEBUG_SPEC_PREFIXES)}

    discrepancies: list[dict] = []

    # Naming mismatches
    for alignment in alignments:
        if alignment.match_type == "fuzzy_name":
            discrepancies.append(
                {
                    "type": "NAMING_MISMATCH",
                    "llm_name": alignment.llm_name,
                    "udb_name": alignment.udb_name,
                    "match_score": alignment.match_score,
                    "llm_class": alignment.llm_class,
                    "udb_class": alignment.udb_class,
                    "source_file": llm_by_name.get(alignment.llm_name, {}).get("_source_file", ""),
                    "notes": "",
                }
            )
        elif alignment.match_type == "one_to_many":
            discrepancies.append(
                {
                    "type": "ONE_TO_MANY",
                    "llm_name": alignment.llm_name,
                    "udb_name": alignment.udb_name,
                    "match_score": alignment.match_score,
                    "llm_class": alignment.llm_class,
                    "udb_class": alignment.udb_class,
                    "source_file": llm_by_name.get(alignment.llm_name, {}).get("_source_file", ""),
                    "notes": "LLM aggregated per-extension UDB params into one bitmask",
                }
            )

    # Classification disagreements (exact matches only)
    for alignment in alignments:
        if alignment.match_type == "exact" and alignment.class_match is False:
            discrepancies.append(
                {
                    "type": "CLASS_DISAGREEMENT",
                    "llm_name": alignment.llm_name,
                    "udb_name": alignment.udb_name,
                    "match_score": 1.0,
                    "llm_class": alignment.llm_class,
                    "udb_class": alignment.udb_class,
                    "source_file": llm_by_name.get(alignment.llm_name, {}).get("_source_file", ""),
                    "notes": f"LLM says {alignment.llm_class}, UDB says {alignment.udb_class}",
                }
            )

    # UDB recall misses
    for udb_name, llm_name in sorted(udb_coverage.items()):
        if llm_name is not None:
            continue
        udb_info = udb_by_name[udb_name]
        dtype = "UDB_RECALL_MISS_DEBUG" if udb_name in debug_udb else "UDB_RECALL_MISS"
        discrepancies.append(
            {
                "type": dtype,
                "llm_name": None,
                "udb_name": udb_name,
                "match_score": 0.0,
                "llm_class": None,
                "udb_class": udb_info.get("classification"),
                "source_file": "",
                "notes": udb_info.get("description", "")[:100],
            }
        )

    # New LLM params (potential UDB gaps or hallucinations)
    non_norm_indicators = re.compile(
        r"\[NOTE\]|\[TIP\]|\[WARNING\]|\[IMPORTANT\]|note:|"
        r"platform.specific|implementation.defined.debug|"
        r"hardware.debug",
        re.IGNORECASE,
    )

    for alignment in alignments:
        if alignment.match_type != "none":
            continue
        param = llm_by_name.get(alignment.llm_name, {})
        excerpt = param.get("excerpt", "")
        conf = param.get("confidence", "low")

        is_suspect = bool(non_norm_indicators.search(excerpt))

        if is_suspect:
            dtype = "LLM_HALLUCINATION_SUSPECT"
        elif conf == "high":
            dtype = "LLM_NEW_HIGH_CONF"
        else:
            dtype = "LLM_NEW_MEDIUM_CONF"

        discrepancies.append(
            {
                "type": dtype,
                "llm_name": alignment.llm_name,
                "udb_name": None,
                "match_score": 0.0,
                "llm_class": alignment.llm_class,
                "udb_class": None,
                "source_file": param.get("_source_file", ""),
                "notes": excerpt[:100] if excerpt else "",
            }
        )

    return discrepancies


# ── Output writers ─────────────────────────────────────────────────────────


def write_deduped(deduped: list[dict], model_display: str) -> Path:
    out_path = RESULTS_DIR / f"deduped_{model_display}.json"
    output = {
        "model": model_display,
        "total_unique_parameters": len(deduped),
        "parameters": deduped,
    }
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")
    return out_path


def write_alignment(
    alignments: list[AlignmentEntry],
    udb_coverage: dict,
    model_display: str,
) -> Path:
    out_path = RESULTS_DIR / f"alignment_{model_display}.json"
    output = {
        "model": model_display,
        "total_alignments": len(alignments),
        "by_type": dict(Counter(a.match_type for a in alignments)),
        "alignments": [a.to_dict() for a in alignments],
        "udb_coverage": udb_coverage,
    }
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")
    return out_path


def write_metrics(metrics: dict, model_display: str) -> Path:
    out_path = RESULTS_DIR / f"metrics_{model_display}.json"
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)
        f.write("\n")
    return out_path


def write_discrepancies(discrepancies: list[dict], model_display: str) -> Path:
    csv_path = RESULTS_DIR / f"discrepancies_{model_display}.csv"
    fieldnames = [
        "type",
        "llm_name",
        "udb_name",
        "match_score",
        "llm_class",
        "udb_class",
        "source_file",
        "notes",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(discrepancies)
    return csv_path


def print_summary(
    metrics: dict,
    discrepancies: list[dict],
    model_display: str,
) -> None:
    disc_counts = Counter(d["type"] for d in discrepancies)

    print(f"\n{'=' * 60}")
    print(f"Phase 5 Analysis Summary: {model_display}")
    print(f"{'=' * 60}")
    print(f"  UDB parameters:        {metrics['total_udb_params']}")
    print(f"  Debug-spec excluded:   {metrics['debug_spec_params']}")
    print(f"  LLM params (deduped):  {metrics['total_llm_params_deduped']}")
    print()
    print(f"  Raw recall:            {metrics['raw_recall']:.1%}")
    print(f"  Adjusted recall:       {metrics['adjusted_recall_pct']}")
    print(
        f"  Classification acc:    {metrics['classification_accuracy_pct']} ({metrics['class_correct']}/{metrics['exact_matches_evaluated']})"
    )
    print(f"  New params found:      {metrics['new_params_total']}")
    print()
    print("  Discrepancies:")
    for dtype in [
        "UDB_RECALL_MISS",
        "UDB_RECALL_MISS_DEBUG",
        "NAMING_MISMATCH",
        "ONE_TO_MANY",
        "CLASS_DISAGREEMENT",
        "LLM_NEW_HIGH_CONF",
        "LLM_NEW_MEDIUM_CONF",
        "LLM_HALLUCINATION_SUSPECT",
    ]:
        if disc_counts.get(dtype, 0) > 0:
            print(f"    {dtype:30s}: {disc_counts[dtype]}")
    print("  Per-class recall:")
    for cls, info in sorted(metrics.get("per_class_recall", {}).items()):
        pct = info["found"] / info["total"] * 100 if info["total"] else 0
        print(f"    {cls:20s}: {info['found']}/{info['total']} ({pct:.0f}%)")
    print(f"{'=' * 60}")


# ── CLI ────────────────────────────────────────────────────────────────────


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def run_all(model_display: str = "claude-sonnet-4") -> None:
    """Execute all analysis steps."""
    merged = load_merged_results(model_display)
    udb_params = load_ground_truth()

    # Step 1: Dedup
    deduped = deduplicate(merged)
    dedup_path = write_deduped(deduped, model_display)
    logger.info("Wrote deduped: %s", dedup_path)

    # Step 2: Align
    alignments, udb_coverage = align_to_udb(deduped, udb_params)
    align_path = write_alignment(alignments, udb_coverage, model_display)
    logger.info("Wrote alignment: %s", align_path)

    # Step 3: Metrics
    metrics = compute_metrics(alignments, udb_coverage, deduped, udb_params)
    metrics_path = write_metrics(metrics, model_display)
    logger.info("Wrote metrics: %s", metrics_path)

    # Step 4: Discrepancies
    discrepancies = generate_discrepancies(alignments, udb_coverage, deduped, udb_params)
    disc_path = write_discrepancies(discrepancies, model_display)
    logger.info("Wrote discrepancies: %s", disc_path)

    print_summary(metrics, discrepancies, model_display)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 5: Analyze and compare LLM extraction results",
    )
    parser.add_argument(
        "--model", default="claude-sonnet-4", help="Model display name (default: claude-sonnet-4)"
    )
    parser.add_argument("-v", "--verbose", action="store_true")

    subparsers = parser.add_subparsers(dest="command")
    for name, hlp in [
        ("all", "Run all analysis steps"),
        ("dedup", "Deduplicate only"),
        ("metrics", "Compute metrics only"),
        ("report", "Generate discrepancy report only"),
    ]:
        subparsers.add_parser(name, help=hlp)

    args, _unknown = parser.parse_known_args()
    setup_logging(args.verbose)

    if args.command is None or args.command == "all":
        run_all(args.model)
    elif args.command == "dedup":
        merged = load_merged_results(args.model)
        deduped = deduplicate(merged)
        path = write_deduped(deduped, args.model)
        print(f"Wrote {len(deduped)} deduped params to {path}")
    elif args.command in ("metrics", "report"):
        run_all(args.model)


if __name__ == "__main__":
    main()
