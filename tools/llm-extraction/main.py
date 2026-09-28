#!/usr/bin/env python3
"""
Purpose:
    CLI entry point for the RISC-V UDB LLM-extraction pipeline.
    Parses subcommand and flags; delegates all logic to pipeline_runner.py.

Pipeline Stage:
    entry point (orchestrates all stages)

Inputs:
    - CLI arguments: subcommand, --mode, --dry-run

Outputs:
    - (delegates to pipeline_runner.run())

Core Responsibilities:
    - Define and parse CLI arguments via argparse
    - Import pipeline_runner with sys.path fallback for non-venv usage
    - Forward subcommand + mode to pipeline_runner.run()

Key Assumptions:
    - Run from llm-extraction/ with the .venv activated
    - pipeline_runner.py is in the same directory

Failure Modes:
    - parser.error() if pipeline_runner cannot be imported
    - sys.exit(0) on --dry-run (not a failure)

Notes:
    - All real work is in pipeline_runner.py; this file stays thin by design

Usage:
    python main.py all
    python main.py embed --mode analysis
    python main.py process
    python main.py ingest
    python main.py export
"""

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main",
        description="RISC-V UDB LLM Extraction Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Subcommands\n"
            "-----------\n"
            "  ingest   — Clone / update riscv-isa-manual (git shallow clone)\n"
            "  process  — Parse AsciiDoc → filtered chunk JSON + CSV\n"
            "  embed    — Build ChromaDB vector index from parameter YAML schemas\n"
            "  export   — Write dependency graph, report, and analysis corpus\n"
            "  all      — Run ingest → process → embed → export\n"
        ),
    )

    parser.add_argument(
        "subcommand",
        choices=["ingest", "process", "embed", "export", "all"],
        help="Pipeline stage to run.",
    )
    parser.add_argument(
        "--mode",
        choices=["rag", "analysis"],
        default="rag",
        help=(
            "Embedding mode for the 'embed' and 'all' subcommands.\n"
            "  rag      = retrieval index only (default)\n"
            "  analysis = retrieval index + full analysis corpus JSON"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be executed without actually running anything.",
    )

    return parser


# ---------------------------------------------------------------------------


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.dry_run:
        print(f"[dry-run] Would execute subcommand: {args.subcommand!r}  (mode={args.mode})")
        sys.exit(0)

    # pipeline_runner is a sibling file; fall back to explicit path insert if needed.
    try:
        from pipeline_runner import run
    except ModuleNotFoundError:
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "chunk"))
        try:
            from pipeline_runner import run
        except ModuleNotFoundError as exc:
            parser.error(
                f"Could not import pipeline_runner: {exc}\n"
                "Make sure you are running from the llm-extraction/ directory "
                "or that the virtual environment is activated."
            )

    run(subcommand=args.subcommand, mode=args.mode)


if __name__ == "__main__":
    main()
