"""
Purpose:
    Central configuration for the RISC-V UDB LLM-extraction pipeline.
    Defines all path constants, logging setup, and high-level chunking vocabulary.

Pipeline Stage:
    all (imported by every pipeline module)

Inputs:
    - spec/schemas/schema_defs.json  (loaded once for $ref resolution)

Outputs:
    - (none — configuration only)

Core Responsibilities:
    - Resolve TOOL_DIR, DATA_DIR, REPO_ROOT from __file__
    - Declare ISA source paths (PARAM_DIR, CSR_DIR, EXT_DIR, PROSE_DIR)
    - Declare output paths (OUTPUT_DIR, CORPUS_PATH, DB_DIR, etc.)
    - Provide CHUNK_KEYWORDS and DIR_TO_CHUNK_TYPE for broad intent routing
    - Load SCHEMA_DEFS_DATA once at import time

Key Assumptions:
    - This file lives at llm-extraction/configs/config.py
    - REPO_ROOT is always riscv-unified-db/ (4 levels up from this file)
    - All runtime artefacts are written under DATA_DIR, not alongside source

Failure Modes:
    - SCHEMA_DEFS_DATA silently becomes {} if schema_defs.json is missing
    - Wrong REPO_ROOT if directory structure is changed

Notes:
    - Fine-grained filter keyword lists live in schema_rules.yaml, not here
    - Taxonomy enumerations live in taxonomy.yaml, not here
"""

from pathlib import Path
from ruamel.yaml import YAML
import json
import logging

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("udb")

# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------

CONFIGS_DIR  = Path(__file__).parent.resolve()          # llm-extraction/configs/
TOOL_DIR     = CONFIGS_DIR.parent                       # llm-extraction/
REPO_ROOT    = TOOL_DIR.parent.parent.parent            # riscv-unified-db/

DATA_DIR     = TOOL_DIR / "data"

# ---------------------------------------------------------------------------
# ISA source paths (inside the riscv-unified-db repository)
# ---------------------------------------------------------------------------

PARAM_DIR   = REPO_ROOT / "spec" / "std" / "isa" / "param"
CSR_DIR     = REPO_ROOT / "spec" / "std" / "isa" / "csr"
EXT_DIR     = REPO_ROOT / "spec" / "std" / "isa" / "ext"
PROSE_DIR   = REPO_ROOT / "spec" / "std" / "isa" / "prose"
SCHEMA_DEFS = REPO_ROOT / "spec" / "schemas" / "schema_defs.json"

# ---------------------------------------------------------------------------
# ISA manual (external, shallow-cloned into data/)
# ---------------------------------------------------------------------------

ISA_MANUAL_REPO_URL = "https://github.com/riscv/riscv-isa-manual.git"
ISA_MANUAL_DIR      = DATA_DIR / "riscv-isa-manual"

# ---------------------------------------------------------------------------
# Output paths (all under data/output/)
# ---------------------------------------------------------------------------

OUTPUT_DIR            = DATA_DIR / "output"
CORPUS_PATH           = OUTPUT_DIR / "param_corpus.json"
ANALYSIS_CORPUS_PATH  = OUTPUT_DIR / "param_analysis_corpus.json"
REPORT_PATH           = OUTPUT_DIR / "UDB_PARAMETER_DATABASE_REPORT.md"
GRAPH_PATH            = OUTPUT_DIR / "dependency_graph.json"
CHUNKS_PATH           = OUTPUT_DIR / "chunks.json"
CHUNKS_REPO_PATH      = OUTPUT_DIR / "chunks_repo.json"
PARAMETER_DATASET_PATH = OUTPUT_DIR / "parameter_dataset.csv"
FILTER_STATS_PATH     = OUTPUT_DIR / "filter_stats.md"
RAW_CHUNKS_DIR        = OUTPUT_DIR / "raw_chunks"

# ---------------------------------------------------------------------------
# ChromaDB vector index (data/chroma_db/)
# ---------------------------------------------------------------------------

DB_DIR = DATA_DIR / "chroma_db"

# ---------------------------------------------------------------------------
# Misc constants
# ---------------------------------------------------------------------------

MOCK_PREFIX = "MOCK_"

CSR_IDL_KEYS = {
    "sw_write(csr_value)",
    "type()",
    "reset_value()",
    "legal?(csr_value)",
    "sw_read()",
}

# ---------------------------------------------------------------------------
# Chunking vocabulary (high-level; file-type routing and broad keyword groups)
# Fine-grained filter vocabulary lives in configs/schema_rules.yaml.
# ---------------------------------------------------------------------------

# Maps source-file directory extension → chunk type label stored in output JSON.
DIR_TO_CHUNK_TYPE: dict[str, str] = {
    "adoc":  "adoc_prose",      # AsciiDoc ISA manual prose
    "yaml":  "yaml_schema",     # UDB parameter / CSR YAML schemas
    "json":  "json_schema",     # JSON schema definitions
}

# Broad keyword families used by the chunker for quick intent classification.
# Detailed keyword lists (frozensets) are loaded from schema_rules.yaml at
# runtime by spec_chunker.py to allow tuning without code changes.
CHUNK_KEYWORDS: dict[str, list[str]] = {
    "normative_strong":  ["[#norm:"],
    "normative_words":   ["may", "must", "should", "shall"],
    "parameter_flags":   ["warl", "wlrl", "legal", "implementation-defined", "configurable"],
}

# ---------------------------------------------------------------------------
# YAML helper (shared across pipeline modules)
# ---------------------------------------------------------------------------

yaml = YAML()
yaml.preserve_quotes = True

# ---------------------------------------------------------------------------
# Schema definitions (loaded once at import time)
# ---------------------------------------------------------------------------

try:
    with open(SCHEMA_DEFS, "r", encoding="utf-8") as _f:
        SCHEMA_DEFS_DATA = json.load(_f)
except Exception as _e:
    logger.warning(f"Could not load schema_defs.json: {_e}")
    SCHEMA_DEFS_DATA = {}
