#!/usr/bin/env python3
"""
Phase 1, Final: Generate a comprehensive human-readable report and CSV
from the ground truth and spec mapping data.

Produces:
  - data/phase1_report.txt    (human-readable summary)
  - data/parameters_catalog.csv  (spreadsheet-ready catalog)
  - data/udb_param_names.txt  (flat list for LLM prompt inclusion)

Reads:
  - data/ground_truth.json
  - data/spec_mappings.json
"""

import json
import csv
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def main():
    # Load data
    with open(DATA_DIR / "ground_truth.json", encoding="utf-8") as f:
        gt = json.load(f)
    with open(DATA_DIR / "spec_mappings.json", encoding="utf-8") as f:
        sm = json.load(f)

    params = gt["parameters"]
    mappings = {m["parameter_name"]: m for m in sm["mappings"]}

    # Generate flat name list (for LLM prompts)
    names = sorted(p["name"] for p in params)
    names_path = DATA_DIR / "udb_param_names.txt"
    with open(names_path, "w", encoding="utf-8") as f:
        for name in names:
            f.write(name + "\n")
    print(f"Written {len(names)} parameter names to {names_path}")

    # Generate CSV catalog
    csv_path = DATA_DIR / "parameters_catalog.csv"
    generate_csv(params, mappings, csv_path)
    print(f"Written CSV catalog to {csv_path}")

    # Generate human-readable report
    report_path = DATA_DIR / "phase1_report.txt"
    generate_report(params, mappings, gt["statistics"], sm["metadata"], report_path)
    print(f"Written report to {report_path}")


def generate_csv(params, mappings, out_path):
    """Generate a CSV file suitable for review or import into a spreadsheet."""
    rows = []
    for p in params:
        m = mappings.get(p["name"], {})
        candidates = m.get("candidates", [])
        best = candidates[0] if candidates else {}

        rows.append({
            "parameter_name": p["name"],
            "long_name": p["long_name"],
            "classification": p["classification"],
            "classification_confidence": p["classification_confidence"],
            "classification_reasoning": p["classification_reasoning"],
            "value_type": p["value_type"]["type"],
            "value_details": _format_value_details(p["value_type"]),
            "defined_by_extensions": ", ".join(p["defined_by"]["extensions"]),
            "defined_by_summary": p["defined_by"]["summary"],
            "has_requirements": p["has_requirements"],
            "num_csr_references": len(p["csr_references"]),
            "csr_names": ", ".join(sorted(set(
                r["csr"] for r in p["csr_references"]
            ))),
            "spec_file": best.get("file", ""),
            "spec_line": best.get("line_number", ""),
            "spec_score": best.get("score", 0),
            "spec_is_normative": best.get("is_normative", ""),
            "spec_in_note": best.get("in_note", ""),
            "spec_text": best.get("line_text", "")[:200],
            "description": p["description"][:300],
        })

    if not rows:
        return

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _format_value_details(value_type):
    """Format value type details into a compact string."""
    vt = value_type["type"]
    details = value_type.get("details", {})

    if vt == "binary":
        choices = details.get("choices", [])
        return f"choices: {choices}"
    elif vt == "enum":
        vals = details.get("values", [])
        if len(vals) <= 5:
            return f"values: {vals}"
        return f"{len(vals)} values"
    elif vt == "range":
        return f"[{details.get('minimum', '?')}..{details.get('maximum', '?')}]"
    elif vt == "set":
        universe = details.get("universe", [])
        if universe:
            return f"subset of {universe}"
        return f"set of {details.get('element_type', '?')}"
    elif vt == "bitmask":
        return f"{details.get('length', '?')}-bit mask"
    elif vt == "conditional":
        branches = details.get("branches", [])
        return f"{len(branches)} conditional branches"
    return str(details)[:80]


def generate_report(params, mappings, stats, mapping_meta, out_path):
    """Generate a comprehensive human-readable report."""
    lines = []
    w = lines.append

    w("=" * 72)
    w("PHASE 1 REPORT: UDB Parameter Ground Truth")
    w("RISC-V Architectural Parameter Extraction Project")
    w("=" * 72)
    w("")

    # --- Overview ---
    w("1. OVERVIEW")
    w("-" * 40)
    w(f"  Total real parameters in UDB:    {len(params)}")
    w(f"  Spec files searched:             {mapping_meta['spec_files_searched']}")
    w(f"  Total spec lines:                {mapping_meta['total_spec_lines']}")
    w(f"  Parameters with spec matches:    {mapping_meta['params_with_matches']} ({mapping_meta['params_with_matches']*100//len(params)}%)")
    w(f"  Parameters with strong matches:  {mapping_meta['params_with_strong_matches']} ({mapping_meta['params_with_strong_matches']*100//len(params)}%)")
    w("")

    # --- Classification breakdown ---
    w("2. CLASSIFICATION BREAKDOWN")
    w("-" * 40)
    for cls, count in sorted(stats["by_classification"].items()):
        pct = count * 100 // len(params)
        w(f"  {cls:20s}  {count:4d}  ({pct:2d}%)")
    w("")
    w("  Classification descriptions:")
    w("    NORM_DIRECT    = Normative, directly configurable (not CSR-controlled)")
    w("    NORM_CSR_WARL  = Normative, legal values of a WARL CSR field")
    w("    NORM_CSR_RW    = Normative, controls whether CSR field is RO/RW")
    w("    SW_RULE        = Software-deterministic (impl-defined but deterministic w/ correct SW)")
    w("")

    # --- Value type breakdown ---
    w("3. VALUE TYPE BREAKDOWN")
    w("-" * 40)
    for vt, count in sorted(stats["by_value_type"].items()):
        pct = count * 100 // len(params)
        w(f"  {vt:20s}  {count:4d}  ({pct:2d}%)")
    w("")
    w("  Value type descriptions:")
    w("    binary       = Exactly 2 choices (boolean or 2-value enum)")
    w("    enum         = Finite set of 3+ discrete values")
    w("    range        = Continuous integer range with min/max bounds")
    w("    set          = Subset selection from a fixed universe of values")
    w("    bitmask      = Fixed-length boolean array (one bit per feature)")
    w("    conditional  = Schema varies based on another parameter (e.g., MXLEN)")
    w("    value        = Single unconstrained value")
    w("")

    # --- Confidence breakdown ---
    w("4. CLASSIFICATION CONFIDENCE")
    w("-" * 40)
    for conf, count in sorted(stats["by_confidence"].items()):
        pct = count * 100 // len(params)
        w(f"  {conf:20s}  {count:4d}  ({pct:2d}%)")
    w("")

    # --- Extension breakdown ---
    w("5. DEFINING EXTENSIONS (Top 15)")
    w("-" * 40)
    for ext, count in list(stats["top_defining_extensions"].items())[:15]:
        w(f"  {ext:20s}  {count:4d}")
    w("")

    # --- Detailed parameter listing by classification ---
    w("6. PARAMETER LISTING BY CLASSIFICATION")
    w("-" * 40)

    by_class = defaultdict(list)
    for p in params:
        by_class[p["classification"]].append(p)

    for cls in ["NORM_DIRECT", "NORM_CSR_WARL", "NORM_CSR_RW", "SW_RULE", "UNKNOWN"]:
        class_params = by_class.get(cls, [])
        if not class_params:
            continue

        w(f"\n  --- {cls} ({len(class_params)} parameters) ---")
        for p in sorted(class_params, key=lambda x: x["name"]):
            m = mappings.get(p["name"], {})
            candidates = m.get("candidates", [])
            best = candidates[0] if candidates else {}

            vt = p["value_type"]
            vt_str = vt["type"]
            if vt["type"] == "binary":
                choices = vt.get("details", {}).get("choices", [])
                vt_str = f"binary({choices})"
            elif vt["type"] == "enum":
                vals = vt.get("details", {}).get("values", [])
                vt_str = f"enum({len(vals)} vals)"

            spec_loc = ""
            if best:
                spec_loc = f" -> {best.get('file', '?')}:{best.get('line_number', '?')}"
                if best.get("is_normative"):
                    spec_loc += " [NORM]"

            csr_str = ""
            if p["csr_references"]:
                csrs = sorted(set(r["csr"] for r in p["csr_references"]))[:3]
                csr_str = f"  CSRs: {', '.join(csrs)}"

            w(f"    {p['name']}")
            w(f"      Type: {vt_str}  |  Exts: {p['defined_by']['summary']}{csr_str}")
            if spec_loc:
                w(f"      Spec:{spec_loc}")
            w(f"      Conf: {p['classification_confidence']}  |  {p['classification_reasoning'][:90]}")

    w("")
    w("=" * 72)
    w("END OF REPORT")
    w("=" * 72)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
