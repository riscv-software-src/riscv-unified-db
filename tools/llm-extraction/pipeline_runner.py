"""
Purpose:
    Orchestration logic for the RISC-V UDB extraction pipeline.
    Receives a subcommand from main.py and dispatches to the correct stage.

Pipeline Stage:
    all (orchestrates ingest → process → embed → export)

Inputs:
    - (delegates to per-stage modules; see each _run_* function)

Outputs:
    - (delegates to per-stage modules; see each _run_* function)

Core Responsibilities:
    - Set up sys.path so pipeline/ and configs/ are importable from any cwd
    - Implement _run_ingest, _run_process, _run_embed, _run_export
    - Collect per-phase wall-clock timings and pass to reporter
    - Dispatch run(subcommand, mode) → correct stage(s)

Key Assumptions:
    - Called by main.py; never run directly
    - Modules are imported lazily inside each _run_* to avoid circular deps

Failure Modes:
    - sys.exit(1) on AsciiDocChunker failure or unknown subcommand
    - ModuleNotFoundError if .venv is not activated before running

Notes:
    - Lazy imports (inside _run_*) keep startup time fast for --dry-run
    - Phase timings (seconds) are accumulated in _TIMINGS and passed to
      reporter.generate_markdown_report() during _run_export.
"""

import subprocess
import sys
import time
from pathlib import Path

# sys.path setup: pipeline/ and configs/ must be importable from any cwd.
_TOOL_DIR = Path(__file__).parent.resolve()   # llm-extraction/

if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from configs.config import (          # noqa: E402  (after sys.path setup)
    logger,
    ISA_MANUAL_DIR,
    ISA_MANUAL_REPO_URL,
    OUTPUT_DIR,
    DATA_DIR,
    CHUNKS_PATH,
)

# Accumulates wall-clock seconds per phase; passed to the reporter.
_TIMINGS: dict[str, float] = {}


# ---------------------------------------------------------------------------
# Internal timing helper
# ---------------------------------------------------------------------------

def _timed(phase: str):
    """Context manager that records wall-clock duration into _TIMINGS."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        t0 = time.perf_counter()
        try:
            yield
        finally:
            _TIMINGS[phase] = time.perf_counter() - t0
    return _ctx()


# ---------------------------------------------------------------------------
# Stage: ingest
# ---------------------------------------------------------------------------

def _run_ingest() -> None:
    """Clone riscv-isa-manual on first run; fetch + reset to HEAD on subsequent runs."""
    logger.info("=== ingest: riscv-isa-manual ===")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with _timed("ingest"):
        if not ISA_MANUAL_DIR.exists():
            logger.info(f"Cloning ISA manual into {ISA_MANUAL_DIR} …")
            subprocess.run(
                ["git", "clone", "--depth=1", ISA_MANUAL_REPO_URL, str(ISA_MANUAL_DIR)],
                check=True,
            )
        else:
            logger.info(f"ISA manual already present at {ISA_MANUAL_DIR}; pulling latest …")
            subprocess.run(
                ["git", "-C", str(ISA_MANUAL_DIR), "fetch", "--depth=1", "origin", "main"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(ISA_MANUAL_DIR), "reset", "--hard", "origin/main"],
                check=True,
            )

    logger.info("ingest: complete.")


# ---------------------------------------------------------------------------
# Stage: process
# ---------------------------------------------------------------------------

def _run_process() -> None:
    """
    Run both ingest chunkers:
      1. AsciiDocChunker  — chunks the ISA manual prose, then removes the clone.
      2. UDBChunker       — chunks param/csr/ext YAML schemas from the repo.
    """
    logger.info("=== process: spec chunking ===")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. AsciiDoc chunker ──────────────────────────────────────────────────
    from pipeline.ingest.chunker_adoc import AsciiDocChunker  # noqa: PLC0415

    with _timed("process_adoc"):
        chunker = AsciiDocChunker(ISA_MANUAL_DIR)
        success = chunker.run()

    if not success:
        logger.error("process: AsciiDocChunker reported a failure.")
        sys.exit(1)

    import shutil
    if ISA_MANUAL_DIR.exists():
        shutil.rmtree(ISA_MANUAL_DIR)
        logger.info(f"Cleaned up {ISA_MANUAL_DIR}")

    # ── 2. UDB YAML chunker ──────────────────────────────────────────────────
    logger.info("=== process: UDB YAML chunking ===")
    from pipeline.ingest.chunker_udb import UDBChunker  # noqa: PLC0415

    with _timed("process_udb"):
        udb_chunker = UDBChunker()
        udb_chunker.run()

    logger.info("process: complete.")


# ---------------------------------------------------------------------------
# Stage: embed
# ---------------------------------------------------------------------------

def _run_embed(mode: str = "rag") -> None:
    """
    Build ChromaDB vector index from combined AsciiDoc + UDB chunks.
    Loads pre-computed chunks from data/output/udb_chunks.json and
    data/output/chunks_repo.json via the storage modules.
    """
    logger.info(f"=== embed: vector database (mode={mode}) ===")

    import json
    from pipeline.storage.embedder    import embed_texts     # noqa: PLC0415
    from pipeline.storage.chroma_store import upsert_chunks, reset_collection  # noqa: PLC0415

    with _timed("embed"):
        all_chunks: list[dict] = []

        # 1. Load AsciiDoc chunks
        if CHUNKS_REPO_PATH.exists():
            with open(CHUNKS_REPO_PATH, encoding="utf-8") as fh:
                repo = json.load(fh)
            adoc_chunks = [c for entry in repo for c in entry.get("chunks", [])]
            all_chunks.extend(adoc_chunks)
            logger.info(f"embed: {len(adoc_chunks)} AsciiDoc chunks loaded.")
        else:
            logger.warning(f"Chunks file not found: {CHUNKS_REPO_PATH}. Run 'process' first.")

        # 2. Load UDB chunks
        udb_chunks_path = OUTPUT_DIR / "udb_chunks.json"
        if udb_chunks_path.exists():
            udb_chunks = json.loads(udb_chunks_path.read_text(encoding="utf-8"))
            all_chunks.extend(udb_chunks)
            logger.info(f"embed: {len(udb_chunks)} UDB chunks loaded.")
        else:
            logger.warning(f"UDB chunks not found: {udb_chunks_path}. Run 'process' first.")

        if not all_chunks:
            logger.warning("No chunks to embed. Skipping.")
            return

        texts = [c.get("text", "") for c in all_chunks]
        logger.info(f"embed: generating embeddings for {len(all_chunks)} total chunks …")
        embeddings = embed_texts(texts)

        # Full re-index on 'analysis' mode; incremental upsert on 'rag'.
        if mode == "analysis":
            reset_collection()

        upsert = upsert_chunks(all_chunks, embeddings)
        logger.info(f"embed: {upsert} chunks upserted into ChromaDB.")

    logger.info("embed: complete.")


# ---------------------------------------------------------------------------
# Stage: export
# ---------------------------------------------------------------------------

def _run_export(mode: str = "rag") -> None:
    """
    Generate a full evaluation Markdown report:
      - per-phase timing stats
      - confidence histograms (AsciiDoc + UDB)
      - parameter class / type distribution tables
      - unknown-class sample table for manual review
    Output → data/evaluation/pipeline_report_<timestamp>.md
    """
    logger.info(f"=== export (mode={mode}) ===")

    from pipeline.export.reporter import generate_markdown_report  # noqa: PLC0415

    report_path = generate_markdown_report(timings=_TIMINGS)
    logger.info(f"export: report written → {report_path}")
    logger.info("export: complete.")


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def run(subcommand: str, mode: str = "rag") -> None:
    """Dispatch subcommand to the correct pipeline stage(s)."""
    dispatch = {
        "ingest":  lambda: _run_ingest(),
        "process": lambda: _run_process(),
        "embed":   lambda: _run_embed(mode=mode),
        "export":  lambda: _run_export(mode=mode),
        "all": lambda: (
            _run_ingest(),
            _run_process(),
            _run_embed(mode=mode),
            _run_export(mode=mode),
        ),
    }

    handler = dispatch.get(subcommand)
    if handler is None:
        logger.error(f"Unknown subcommand: {subcommand!r}")
        sys.exit(1)

    handler()
    logger.info(f"Pipeline '{subcommand}' finished successfully.")