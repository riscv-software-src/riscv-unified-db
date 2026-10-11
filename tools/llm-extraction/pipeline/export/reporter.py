"""
Purpose:
    Generate three isolated reports for the RISC-V UDB extraction pipeline:
      1. AsciiDoc Chunker Report (from detailed filter stats + raw chunks)
      2. UDB YAML Chunker Report (from the UDB chunks)
      3. Overall Summary Report (combines timing and high-level outcomes)

Pipeline Stage:
    export

Inputs:
    - data/output/adoc_report_data.json
    - data/output/parameter_dataset.csv (via Pandas)
    - data/output/udb_chunks.json       (via Pandas)
    - _TIMINGS

Outputs:
    - data/evaluation/report_adoc_chunker.md
    - data/evaluation/report_udb_chunker.md
    - data/evaluation/report_overall_summary.md
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pandas as pd

import sys
_EXPORT_DIR = Path(__file__).parent.resolve()
_TOOL_DIR   = _EXPORT_DIR.parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from configs.config import OUTPUT_DIR, DATA_DIR, logger  # noqa: E402

EVAL_DIR = DATA_DIR / "evaluation"


# ---------------------------------------------------------------------------
# Data Loading (Pandas)
# ---------------------------------------------------------------------------

def _load_adoc_dataframe() -> pd.DataFrame:
    """Loads the AsciiDoc parameter dataset CSV into Pandas."""
    csv_path = OUTPUT_DIR / "parameter_dataset.csv"
    if not csv_path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(csv_path)
        return df.fillna("")
    except Exception as e:
        logger.warning(f"Error loading {csv_path}: {e}")
        return pd.DataFrame()


def _load_udb_dataframe() -> pd.DataFrame:
    """Loads the UDB JSON chunks into Pandas."""
    json_path = OUTPUT_DIR / "udb_chunks.json"
    if not json_path.exists():
        return pd.DataFrame()
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        return df.fillna("")
    except Exception as e:
        logger.warning(f"Error loading {json_path}: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Render Helpers
# ---------------------------------------------------------------------------

def _render_parameter_list(df: pd.DataFrame, title: str) -> str:
    """Renders a Pandas DataFrame of parameters into a Markdown table (sampled for brevity)."""
    if df.empty:
        return f"\n## {title}\n> No parameters found.\n"

    # Select columns if they exist
    cols = []
    if "section" in df.columns: cols.append("section")
    if "parameter_class" in df.columns: cols.append("parameter_class")
    if "text" in df.columns: cols.append("text")
    if "confidence" in df.columns: cols.append("confidence")

    sub_df = df[cols].copy()
    
    # ── Sample up to 10 items randomly per parameter_class ──
    if "parameter_class" in sub_df.columns:
        sampled_dfs = []
        for p_class, group in sub_df.groupby("parameter_class"):
            sampled_dfs.append(group.sample(n=min(len(group), 10), random_state=42))
        if sampled_dfs:
            sub_df = pd.concat(sampled_dfs, ignore_index=True)
    else:
        sub_df = sub_df.sample(n=min(len(sub_df), 10), random_state=42)
    
    # Text truncation to avoid breaking markdown limits per row
    if "text" in sub_df.columns:
        sub_df["text"] = sub_df["text"].str.replace("\n", " ").str.slice(0, 200) + "..."
    if "section" in sub_df.columns:
        sub_df["section"] = sub_df["section"].str.replace("\n", " ")

    lines = [f"\n## {title}\n"]
    lines.append("> _Showing a randomized sample (up to 10 chunks per parameter class)._\n")
    lines.append("| " + " | ".join(sub_df.columns).title() + " |")
    lines.append("|" + "|".join(["---"] * len(sub_df.columns)) + "|")

    for _, row in sub_df.iterrows():
        row_strs = [str(col_val).replace('|', '\\|') for col_val in row]
        lines.append("| " + " | ".join(row_strs) + " |")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 1. AsciiDoc Chunker Report
# ---------------------------------------------------------------------------

def _write_adoc_report(report_data: dict, df: pd.DataFrame, out_path: Path) -> None:
    if not report_data and df.empty:
        out_path.write_text("> ⚠️ AsciiDoc report data not found.\n")
        return

    lines = ["# AsciiDoc Spec Chunker Full Analysis Report\n"]

    g = report_data.get("global", {})
    lines.append("## Executive Summary")
    lines.append(f"- Total Files: {g.get('total_files', 0)}")
    lines.append(f"- Processed Files: {g.get('processed_files', 0)}")
    lines.append(f"- Skipped Files: {g.get('skipped_files', 0)}")
    lines.append(f"- Total Raw Chunks: {g.get('total_raw_chunks', 0)}")
    lines.append(f"- Final Chunks (in dataset): {len(df) if not df.empty else g.get('total_final_chunks', 0)}")
    lines.append(f"- Reduction: {g.get('reduction_percent', 0)}%\n")

    # Filter rules logic
    filters = report_data.get("filters", {})
    lines.append("\n## Filter Breakdown (Why chunks were dropped)")
    sorted_drops = sorted(filters.get("reasons", {}).items(), key=lambda i: i[1], reverse=True)
    for k, v in sorted_drops:
        lines.append(f"- {k}: {v}")

    # Use Pandas for distribution analysis
    if not df.empty:
        lines.append("\n## Confidence Distribution")
        conf_counts = df["confidence"].value_counts()
        for k, v in conf_counts.items():
            lines.append(f"- {k}: {v} ({(v/len(df)*100):.1f}%)")

        lines.append("\n## Parameter Classification Summary")
        cls_counts = df["parameter_class"].value_counts()
        for k, v in cls_counts.items():
            lines.append(f"- {k}: {v} ({(v/len(df)*100):.1f}%)")

        lines.append("\n## Parameter Type Summary")
        type_counts = df["parameter_type"].value_counts()
        for k, v in type_counts.items():
            lines.append(f"- {k}: {v} ({(v/len(df)*100):.1f}%)")

        lines.append("\n## Per-file Chunk Selection Analysis")
        lines.append("| S.No | File | Raw Candidates | Selected Final Chunks | Dropped |")
        lines.append("|---|---|---|---|---|")
        files_info = report_data.get("files", {})
        sorted_files = sorted(files_info.items(), key=lambda i: i[1].get("dropped", 0), reverse=True)
        for i, (f, d) in enumerate(sorted_files, 1):
            lines.append(f"| {i} | `{f}` | {d.get('raw_chunks', 0)} | {d.get('final_chunks', 0)} | {d.get('dropped', 0)} |")

        lines.append(_render_parameter_list(df, "Complete Extracted Parameters List (AsciiDoc)"))

    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# 2. UDB YAML Chunker Report
# ---------------------------------------------------------------------------

def _write_udb_report(df: pd.DataFrame, out_path: Path) -> dict:
    if df.empty:
        out_path.write_text("> ⚠️ UDB chunks not found.\n")
        return {"total": 0}

    lines = ["# UDB YAML Chunker Analysis Report\n"]
    lines.append("## Executive Summary")
    lines.append(f"- Total UDB Chunks Produced: {len(df)}")
    
    lines.append("\n## Source Breakdown")
    for k, v in df["source"].value_counts().items():
        lines.append(f"- {k}: {v}")

    lines.append("\n## Parameter Class Summary")
    for k, v in df["parameter_class"].value_counts().items():
        lines.append(f"- {k}: {v}")

    lines.append("\n## Parameter Type Summary")
    for k, v in df["parameter_type"].value_counts().items():
        lines.append(f"- {k}: {v}")

    lines.append("\n## Per-file Chunk Generation Analysis")
    lines.append("| S.No | Source File | Chunks Generated |")
    lines.append("|---|---|---|")
    if "source_file" in df.columns:
        file_counts = df["source_file"].value_counts()
        for i, (f, count) in enumerate(file_counts.items(), 1):
            lines.append(f"| {i} | `{f}` | {count} |")
    else:
        lines.append("> _Source file information not found in dataset._\n")

    # Append full list of parameters
    lines.append(_render_parameter_list(df, "Complete Extracted Parameters List (UDB)"))

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return {"total": len(df), "src_dist": df["source"].value_counts().to_dict()}


# ---------------------------------------------------------------------------
# 3. Overall Pipeline Report
# ---------------------------------------------------------------------------

def _write_overall_report(timings: dict[str, float], adoc_data: dict, udb_stats: dict, out_path: Path) -> None:
    lines = ["# Overall Pipeline Summary Report\n"]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines.append(f"> Execution completed at {ts}\n")

    lines.append("## Phase Execution Timings")
    if not timings:
        lines.append("_No timing data available (likely run sequentially by the user)._")
    else:
        lines.append("| Phase | Duration |")
        lines.append("|---|---|")
        total = 0.0
        for phase, secs in timings.items():
            total += secs
            lines.append(f"| `{phase}` | {secs:.1f}s |")
        lines.append(f"| **Total** | **{total:.1f}s** |")

    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def generate_markdown_report(timings: dict[str, float] | None = None) -> list[Path]:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    
    adoc_out    = EVAL_DIR / "report_adoc_chunker.md"
    udb_out     = EVAL_DIR / "report_udb_chunker.md"
    
    # AsciiDoc legacy stats (for drops)
    adoc_json = OUTPUT_DIR / "adoc_report_data.json"
    adoc_data = {}
    if adoc_json.exists():
        try:
             adoc_data = json.loads(adoc_json.read_text(encoding="utf-8"))
        except Exception:
             pass

    # Load data via pandas
    df_adoc = _load_adoc_dataframe()
    df_udb  = _load_udb_dataframe()

    # Generate
    _write_adoc_report(adoc_data, df_adoc, adoc_out)
    udb_stats = _write_udb_report(df_udb, udb_out)

    return [adoc_out, udb_out]
