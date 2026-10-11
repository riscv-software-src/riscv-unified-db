#!/usr/bin/env python3
"""
Phase 1, Step 2: Map UDB parameters to their source locations in the RISC-V spec.

For each parameter, searches the spec .adoc files for sentences that describe
the implementation choice that parameter represents. Uses multiple search
strategies: keyword matching from descriptions, CSR name references,
known WARL/implementation-defined language patterns, and exact name matches.

Reads:  data/ground_truth.json
Output: data/spec_mappings.json
"""

import json
import re
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SPEC_DIR = REPO_ROOT / "ext" / "riscv-isa-manual" / "src"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# Spec file loading and indexing
# ---------------------------------------------------------------------------

def load_spec_files():
    """Load all .adoc files from the spec directory, returning {filename: [lines]}."""
    spec_files = {}
    for adoc in sorted(SPEC_DIR.glob("*.adoc")):
        with open(adoc, encoding="utf-8") as f:
            spec_files[adoc.name] = f.readlines()
    return spec_files


def is_note_block(lines, line_idx):
    """
    Check if a given line is inside a NOTE/TIP/WARNING block (non-normative).
    AsciiDoc NOTE blocks are delimited by '===='.
    Also checks for explicit [NOTE]/[TIP]/[WARNING] markers.
    """
    note_markers = {"[NOTE]", "[TIP]", "[WARNING]", "[IMPORTANT]", "[CAUTION]"}

    # Look backwards from this line for the nearest block marker
    depth = 0
    for i in range(line_idx - 1, max(line_idx - 30, -1), -1):
        if i < 0:
            break
        stripped = lines[i].strip()
        if stripped == "====":
            depth += 1
            if depth == 1:
                # Check if the line before this ==== is a note marker
                for j in range(i - 1, max(i - 3, -1), -1):
                    if j >= 0 and lines[j].strip() in note_markers:
                        return True
                return False
    return False


# ---------------------------------------------------------------------------
# Search strategy: build search terms from parameter metadata
# ---------------------------------------------------------------------------

def build_search_terms(param):
    """
    Build a list of (pattern, weight, reason) tuples to search for this parameter.
    Higher weight = more likely to be a relevant match.
    """
    name = param["name"]
    desc = param.get("description", "")
    long_name = param.get("long_name", "")
    csr_refs = param.get("csr_references", [])
    defined_by = param.get("defined_by", {})
    value_type = param.get("value_type", {})

    terms = []

    # Strategy 0: The parameter name itself (may appear verbatim in spec)
    # Match as a whole word, case-sensitive for ALL_CAPS names
    if name == name.upper() and len(name) >= 3:
        terms.append((
            re.compile(rf'\b{re.escape(name)}\b'),
            6,
            f"Exact parameter name '{name}'",
        ))
    # Also search for the name in italic/emphasis form: _NAME_
    terms.append((
        re.compile(rf'_{re.escape(name)}_'),
        6,
        f"Parameter name in emphasis '_{name}_'",
    ))

    # Strategy 0b: Search for key segments of multi-word param names
    name_segments = name.split('_')
    # For short distinctive segments (>=4 chars, not common words), search directly
    common_words = {'MODE', 'TYPE', 'VALUE', 'WIDTH', 'LEGAL', 'VALUES', 'READ',
                    'ONLY', 'WHEN', 'ZERO', 'BASE', 'TRAP', 'REPORT'}
    for seg in name_segments:
        if len(seg) >= 4 and seg not in common_words:
            terms.append((
                re.compile(rf'\b{re.escape(seg)}\b', re.IGNORECASE),
                1,
                f"Name segment '{seg}'",
            ))

    # Strategy 1: CSR name + field name (for CSR-related params)
    # Cap to avoid score inflation for params with hundreds of CSR refs
    csr_names_seen = set()
    fields_seen = set()
    MAX_CSR_TERMS = 10
    csr_term_count = 0
    for ref in csr_refs:
        if csr_term_count >= MAX_CSR_TERMS:
            break
        csr = ref["csr"]
        field = ref["field"]
        if csr not in csr_names_seen:
            terms.append((
                re.compile(rf'`{re.escape(csr)}`', re.IGNORECASE),
                3,
                f"CSR name '{csr}' in backticks",
            ))
            csr_names_seen.add(csr)
            csr_term_count += 1
        if field != "(csr-level)" and field not in fields_seen:
            terms.append((
                re.compile(rf'\b{re.escape(field)}\b', re.IGNORECASE),
                2,
                f"CSR field name '{field}'",
            ))
            fields_seen.add(field)
            csr_term_count += 1

    # Strategy 2: Extract key nouns/phrases from parameter description (cap to avoid noise)
    desc_keywords = _extract_description_keywords(name, desc)
    for kw, weight in desc_keywords[:12]:
        terms.append((
            re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE),
            weight,
            f"Description keyword '{kw}'",
        ))

    # Strategy 3: Look for WARL near CSR names (for WARL params)
    if param.get("classification") in ("NORM_CSR_WARL", "NORM_CSR_RW"):
        for csr in csr_names_seen:
            terms.append((
                re.compile(rf'WARL.*`{re.escape(csr)}`|`{re.escape(csr)}`.*WARL', re.IGNORECASE),
                5,
                f"WARL + CSR '{csr}'",
            ))

    # Strategy 4: Specific value mentions for enum/binary params
    if value_type.get("type") == "binary":
        choices = value_type.get("details", {}).get("choices", [])
        if choices == [True, False]:
            # For boolean params, look for "may" / "optionally" / "read-only" patterns
            terms.append((
                re.compile(r'\b(may\s+optionally|optionally|read-only\s+zero|read-only\s+0)\b', re.IGNORECASE),
                1,
                "Optional/read-only pattern for boolean param",
            ))

    return terms


def _extract_description_keywords(name, description):
    """
    Extract meaningful search keywords from the parameter's description.
    Returns list of (keyword, weight) tuples.
    """
    keywords = []

    # Extract CSR names from description (things in backticks)
    backtick_refs = re.findall(r'`([a-zA-Z][a-zA-Z0-9_.]*)`', description)
    for ref in backtick_refs:
        keywords.append((ref, 3))

    # Look for capitalized CSR field references like MODE, BASE, etc.
    field_refs = re.findall(r'\b([A-Z]{2,}(?:\.[A-Z]+)?)\b', description)
    for ref in field_refs:
        if ref not in ('WARL', 'WLRL', 'CSR', 'ISA', 'RISC', 'TODO', 'XLEN',
                       'MXLEN', 'AND', 'NOT', 'THE', 'FOR', 'WHEN', 'SXLEN',
                       'UXLEN', 'ALL', 'PMP', 'HPM', 'AMO', 'NMI'):
            keywords.append((ref, 2))

    # Extract meaningful phrases based on parameter name segments
    name_parts = name.split('_')
    # Find multi-word concepts in the name
    name_to_phrase = {
        'ENDIANNESS': 'endian',
        'MISALIGNED': 'misaligned',
        'ALIGNMENT': 'align',
        'TRANSLATION': 'translation',
        'RESERVATION': 'reservation',
        'GRANULARITY': 'granularity',
        'BREAKPOINT': 'breakpoint',
        'INSTRUCTION': 'instruction',
        'VECTORED': 'vectored',
        'IMPLEMENTED': 'implemented',
    }
    for part in name_parts:
        phrase = name_to_phrase.get(part)
        if phrase:
            keywords.append((phrase, 2))

    return keywords


# ---------------------------------------------------------------------------
# Core matching engine
# ---------------------------------------------------------------------------

def find_spec_locations(param, spec_files):
    """
    Search all spec files for text related to this parameter.

    Returns a list of candidate matches, sorted by relevance score.
    Each match: {file, line_number, line_text, score, reasons, is_normative, in_note}
    """
    search_terms = build_search_terms(param)
    if not search_terms:
        return []

    candidates = defaultdict(lambda: {
        "score": 0, "reasons": [], "is_normative": False, "in_note": False,
    })

    for filename, lines in spec_files.items():
        for line_idx, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith("//"):
                continue

            # Skip table-heavy lines (pipes indicate table cells, not prose)
            if line_stripped.count('|') >= 3:
                continue

            line_key = (filename, line_idx + 1)

            # Track which strategy categories matched to prevent score inflation
            segment_score = 0
            max_segment_score = 3  # cap contribution from name-segment matches
            normative_bonus_applied = False

            for pattern, weight, reason in search_terms:
                if pattern.search(line):
                    entry = candidates[line_key]
                    entry["file"] = filename
                    entry["line_number"] = line_idx + 1
                    entry["line_text"] = line_stripped

                    if "Name segment" in reason:
                        segment_score += weight
                        entry["score"] += min(weight, max_segment_score - (segment_score - weight))
                        if segment_score - weight < max_segment_score:
                            entry["reasons"].append(reason)
                    else:
                        entry["score"] += weight
                        entry["reasons"].append(reason)

                    if not normative_bonus_applied and ("[#norm:" in line or "[[norm:" in line):
                        entry["is_normative"] = True
                        entry["score"] += 2
                        normative_bonus_applied = True

                    if is_note_block(lines, line_idx):
                        entry["in_note"] = True
                        entry["score"] -= 3

    # Convert to list, filter low-score noise, sort by score descending
    results = []
    MAX_SCORE = 50
    for key, entry in candidates.items():
        if entry["score"] >= 3:
            entry["score"] = min(entry["score"], MAX_SCORE)
            entry["reasons"] = list(set(entry["reasons"]))
            results.append(entry)

    results.sort(key=lambda x: (-x["score"], x["file"], x["line_number"]))
    return results[:10]


# ---------------------------------------------------------------------------
# Context extraction: get surrounding lines for each match
# ---------------------------------------------------------------------------

def extract_context(spec_files, filename, line_number, context_lines=2):
    """Get the matched line plus surrounding context lines."""
    lines = spec_files.get(filename, [])
    if not lines:
        return ""

    start = max(0, line_number - 1 - context_lines)
    end = min(len(lines), line_number + context_lines)

    context_parts = []
    for i in range(start, end):
        prefix = ">>>" if i == line_number - 1 else "   "
        context_parts.append(f"{prefix} {i+1:5d}| {lines[i].rstrip()}")

    return "\n".join(context_parts)


# ---------------------------------------------------------------------------
# Main mapping logic
# ---------------------------------------------------------------------------

def main():
    # Load ground truth
    gt_path = DATA_DIR / "ground_truth.json"
    if not gt_path.exists():
        print(f"ERROR: {gt_path} not found. Run export_udb_params.py first.")
        return

    with open(gt_path, encoding="utf-8") as f:
        ground_truth = json.load(f)

    params = ground_truth["parameters"]
    print(f"Loaded {len(params)} parameters from ground truth")

    # Load spec files
    print(f"Loading spec files from {SPEC_DIR}...")
    spec_files = load_spec_files()
    total_lines = sum(len(lines) for lines in spec_files.values())
    print(f"  {len(spec_files)} files, {total_lines} total lines")

    # Map each parameter
    print("Mapping parameters to spec text...")
    mappings = []
    params_with_matches = 0
    params_with_strong_matches = 0

    for i, param in enumerate(params):
        candidates = find_spec_locations(param, spec_files)

        has_match = len(candidates) > 0
        best_score = candidates[0]["score"] if candidates else 0
        has_strong = best_score >= 5

        if has_match:
            params_with_matches += 1
        if has_strong:
            params_with_strong_matches += 1

        # Add context to top candidates
        for cand in candidates[:5]:
            cand["context"] = extract_context(
                spec_files, cand["file"], cand["line_number"]
            )

        entry = {
            "parameter_name": param["name"],
            "classification": param["classification"],
            "value_type": param["value_type"]["type"],
            "num_candidates": len(candidates),
            "best_score": best_score,
            "candidates": candidates[:5],
        }
        mappings.append(entry)

        if (i + 1) % 20 == 0:
            print(f"  Processed {i+1}/{len(params)} parameters...")

    # Output
    output = {
        "metadata": {
            "total_parameters": len(params),
            "params_with_matches": params_with_matches,
            "params_with_strong_matches": params_with_strong_matches,
            "spec_files_searched": len(spec_files),
            "total_spec_lines": total_lines,
        },
        "mappings": mappings,
    }

    out_path = DATA_DIR / "spec_mappings.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nWritten mappings to {out_path}")
    print(f"\n{'='*60}")
    print(f"SPEC MAPPING SUMMARY")
    print(f"{'='*60}")
    print(f"Total parameters:          {len(params)}")
    print(f"With any match (score>=3): {params_with_matches} ({params_with_matches*100//len(params)}%)")
    print(f"With strong match (>=5):   {params_with_strong_matches} ({params_with_strong_matches*100//len(params)}%)")
    print(f"No matches found:          {len(params) - params_with_matches}")

    # Show a few examples of strong matches
    print(f"\n--- Sample strong matches ---")
    shown = 0
    for m in mappings:
        if m["best_score"] >= 7 and shown < 5:
            cand = m["candidates"][0]
            print(f"\n  {m['parameter_name']} (score={cand['score']}, {m['classification']})")
            print(f"  File: {cand['file']}:{cand['line_number']}")
            print(f"  Text: {cand['line_text'][:120]}")
            shown += 1

    # Show parameters with no matches
    no_match = [m["parameter_name"] for m in mappings if m["num_candidates"] == 0]
    if no_match:
        print(f"\n--- Parameters with NO spec matches ({len(no_match)}) ---")
        for nm in no_match[:20]:
            print(f"  {nm}")
        if len(no_match) > 20:
            print(f"  ... and {len(no_match) - 20} more")


if __name__ == "__main__":
    main()
