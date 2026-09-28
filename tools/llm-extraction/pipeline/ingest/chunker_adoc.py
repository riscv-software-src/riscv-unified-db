"""
Purpose:
    Parses RISC-V ISA manual AsciiDoc source files and extracts normative
    parameter-defining sentences as structured chunk records for downstream
    classification and embedding.

Pipeline Stage:
    ingest

Inputs:
    - data/riscv-isa-manual/src/**/*.adoc  (shallow-cloned ISA manual)
    - configs/schema_rules.yaml            (filter keyword lists, loaded at import)
    - configs/taxonomy.yaml                (file-classification rules, loaded at import)

Outputs:
    - data/output/raw_chunks/<file>.json   (pre-filter sentences, one JSON per .adoc)
    - data/output/chunks_repo.json         (post-filter combined chunks)
    - data/output/parameter_dataset.csv    (flat CSV for downstream annotation)
    - data/output/filter_stats.md          (per-file + global filter-statistics report)

Core Responsibilities:
    - Load keyword vocabulary from schema_rules.yaml (not hardcoded frozensets)
    - Load file-classification rules from taxonomy.yaml
    - Clean AsciiDoc markup and split text into atomic normative sentences
    - Filter noise, narrative, computation descriptions, and soft rationale
    - Score confidence and classify parameter class + type per chunk
    - Persist raw (pre-filter) and final (post-filter) chunk outputs

Key Assumptions:
    - ISA manual is at ISA_MANUAL_DIR or will be cloned by _ensure_repo()
    - All .adoc source files live under src/ inside the manual repository
    - All keyword strings in schema_rules.yaml are already lowercased

Failure Modes:
    - Empty chunks_repo.json if ISA manual is missing or src/ layout changes
    - KeyError / silent under-extraction if schema_rules.yaml keys are renamed
    - Over-extraction if noise_patterns list in schema_rules.yaml is too short

Notes:
    - Filtering is ordered cheapest-first: structural validity → semantic checks
    - flush_paragraphs() is a proper instance method (not a closure) for testability
    - split_conditions() is public so conditional-splitting logic can be tested alone
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from tqdm import tqdm

# ── sys.path bootstrap ──────────────────────────────────────────────────────
# Ensure llm-extraction/ and llm-extraction/chunk/ are importable when this
# module is used standalone (e.g. during testing or direct execution).

_INGEST_DIR = Path(__file__).parent.resolve()          # pipeline/ingest/
_PIPELINE_DIR = _INGEST_DIR.parent                     # pipeline/
_TOOL_DIR = _PIPELINE_DIR.parent                       # llm-extraction/
_CHUNK_DIR = _TOOL_DIR / "chunk"

for _p in (str(_TOOL_DIR), str(_CHUNK_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_CONFIGS_DIR        = _TOOL_DIR / "configs"
_SCHEMA_RULES_PATH  = _CONFIGS_DIR / "schema_rules.yaml"
_TAXONOMY_PATH      = _CONFIGS_DIR / "taxonomy.yaml"

from configs.config import (           # noqa: E402
    ISA_MANUAL_DIR,
    ISA_MANUAL_REPO_URL,
    OUTPUT_DIR,
    CHUNKS_REPO_PATH,
    FILTER_STATS_PATH,
    PARAMETER_DATASET_PATH,
    RAW_CHUNKS_DIR,
    logger,
)
from pipeline.utils import chunk_id, normalize_text      # noqa: E402

from pipeline.process.classifier import (
    _RULES,
    classify_confidence,
    classify_parameter_class,
    classify_parameter_type,
    contains_any,
    has_access_vocab,
    has_any_modal,
    has_condition_vocab,
    has_csr_vocab,
    has_explicit_bit_rule,
    has_field_vocab,
    has_numeric_constraint,
    has_strong_modal,
    is_narrative,
    is_pure_description,
    should_keep,
)





def _load_taxonomy() -> dict:
    """
    Read configs/taxonomy.yaml and return the file-classification look-ups
    needed by classify_file().
    """
    import yaml as _yaml

    with open(_TAXONOMY_PATH, "r", encoding="utf-8") as fh:
        data = _yaml.safe_load(fh)

    cats = data.get("ignore_file_categories", {})
    return {
        "ignored_exact":  frozenset(cats.get("ignored_exact", [])),
        "formal_files":   tuple(cats.get("formal_files", [])),
        "profile_prefix": cats.get("profile_prefix", "profiles/"),
        "doc_files":      tuple(cats.get("doc_files", [])),
    }


_TAXONOMY = _load_taxonomy()

_IGNORED_FILES_EXACT: frozenset[str] = _TAXONOMY["ignored_exact"]
_FORMAL_FILES:        tuple[str, ...] = _TAXONOMY["formal_files"]
_PROFILE_PREFIX:      str             = _TAXONOMY["profile_prefix"]
_DOC_FILES:           tuple[str, ...] = _TAXONOMY["doc_files"]


# Regexes stay in Python for safety; patterns are documented in schema_rules.yaml.

_RE_NOTE_BLOCK    = re.compile(r'\[NOTE\]\s*\n====.*?====\s*\n', re.DOTALL)
_RE_EQUAL_RUNS    = re.compile(r'={2,}')
_RE_ANCHOR        = re.compile(r'\[\[.*?\]\]')
_RE_NORM_ATTR     = re.compile(r'\[#?norm:[^\]]+\]#?')
_RE_INDEX_TERM    = re.compile(r'\(\(\(.*?\)\)\)')
_RE_XREF          = re.compile(r'<<[^>]+>>')
_RE_TABLE         = re.compile(r'\|===.*?\|===', re.DOTALL)
_RE_PERCENT_ATTR  = re.compile(r'\[%.*?\]')
_RE_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)
_RE_LIST_BULLET   = re.compile(r'^[\*\-]\s+', re.MULTILINE)
_RE_WHITESPACE    = re.compile(r'\s+')
_RE_SECTION_HDR   = re.compile(r'^(=+)\s+(.+)$')

# Capital+lowercase lookahead prevents splitting on abbreviations like "e.g. Foo".
_RE_SPLIT_SENT = re.compile(r'(?<=[.;])\s+(?=[A-Z][a-z])')

# 'The' and 'All' excluded: they inflated raw-chunk counts 2× in earlier runs.
_RE_SPLIT_COND = re.compile(r'(?=\b(?:If|When|Unless|Otherwise)\b)')

_RE_TAG_PAIR = re.compile(r'<[^>]{1,80}>')




def classify_file(file_path: str) -> tuple[str, Optional[str]]:
    """
    Determine how a source .adoc file should be processed.

    Returns
    -------
    (mode, category) where *mode* is one of:
      "ignore"          — skip entirely
      "process"         — full normative extraction (main corpus)
      "process_formal"  — memory-model / formal sections (light mode)
      "process_profile" — profile requirement sections
      "process_docs"    — naming / intro / preface sections

    *category* is the ignored-bucket key used in the filter report, or None
    when the file is actively processed into the main corpus.
    """
    for name in _IGNORED_FILES_EXACT:
        if file_path.endswith(name):
            return "ignore", "docs"

    if any(name in file_path for name in _FORMAL_FILES):
        return "process_formal", "formal"
    if _PROFILE_PREFIX in file_path:
        return "process_profile", "profiles"
    if any(name in file_path for name in _DOC_FILES):
        return "process_docs", "docs"

    return "process", None


def _raw_chunk_filename(file_path: str) -> str:
    """
    Convert a relative adoc path like ``src/priv/machine.adoc`` into a flat
    filename ``src__priv__machine.json`` safe for any filesystem.
    """
    return file_path.replace("/", "__").replace(".adoc", ".json")


def _split_on_conjunctions(text: str) -> list[str]:
    """
    Split a compound constraint sentence on 'and' / 'or'.

    Only fires when *both* parts look like complete constraints (≥ 8 words,
    ending with a period).  Otherwise the original sentence is returned intact
    so no content is silently discarded.
    """
    parts = re.split(r'\b(?:and|or)\b', text)
    candidates = [
        p.strip() for p in parts
        if len(p.strip().split()) >= 8 and p.strip().endswith(".")
    ]
    return candidates if len(candidates) >= 2 else [text]




class AsciiDocChunker:
    """
    Two-stage AsciiDoc chunker.

    Stage 1 — raw_chunks/ : per-file pre-filter sentences (for debugging/diffing).
    Stage 2 — chunks_repo.json / parameter_dataset.csv : final filtered output.
    """

    # -----------------------------------------------------------------------
    # Initialisation
    # -----------------------------------------------------------------------

    def __init__(self, repo_dir: Path) -> None:
        self.repo_dir = repo_dir
        self.repo_results: list[dict] = []
        self._global_counter: int = 0

        self.report: dict = {
            "global": {},
            "files": {},
            "filters": {"reasons": {}, "rules": []},
            "file_classification": {
                "processed": [],
                "ignored": {"formal": [], "docs": [], "profiles": []},
            },
            "confidence_distribution": {
                "very_high": 0,
                "high":      0,
                "medium":    0,
                "low":       0,
            },
            "classification": {
                "class":           {},
                "type":            {},
                "unknown_samples": [],
            },
        }

    # -----------------------------------------------------------------------
    # Repository management
    # -----------------------------------------------------------------------

    def _ensure_repo(self) -> None:
        if not self.repo_dir.exists():
            logger.info(f"Cloning ISA manual into {self.repo_dir} …")
            subprocess.run(
                ["git", "clone", "--depth=1", ISA_MANUAL_REPO_URL, str(self.repo_dir)],
                check=True,
            )

    def _repo_commit(self) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    # -----------------------------------------------------------------------
    # Report helpers
    # -----------------------------------------------------------------------

    def _log_rule(self, name: str) -> None:
        if name not in self.report["filters"]["rules"]:
            self.report["filters"]["rules"].append(name)

    def _drop(self, reason: str) -> None:
        self.report["filters"]["reasons"][reason] = (
            self.report["filters"]["reasons"].get(reason, 0) + 1
        )

    def _record_drop(self, reason: str, file_path: str) -> None:
        """Convenience: increment both the global and per-file drop counters."""
        self._drop(reason)
        self.report["files"][file_path]["dropped"] += 1

    # -----------------------------------------------------------------------
    # Text cleaning
    # -----------------------------------------------------------------------

    def _preprocess(self, raw_text: str) -> str:
        """Remove AsciiDoc [NOTE] delimited blocks before line processing."""
        self._log_rule("clean_note_blocks: Remove AsciiDoc [NOTE] delimited blocks")
        return _RE_NOTE_BLOCK.sub("", raw_text)

    def _clean_text(self, text: str) -> str:
        """
        Strip AsciiDoc structural markup, leaving only prose content.
        Block-level constructs are removed before inline markup.
        """
        self._log_rule("clean_formatting: Strip AsciiDoc structural markup")
        text = _RE_EQUAL_RUNS.sub("", text)
        text = _RE_ANCHOR.sub("", text)
        text = _RE_NORM_ATTR.sub("", text)
        text = _RE_INDEX_TERM.sub("", text)
        text = _RE_XREF.sub("", text)
        text = _RE_TABLE.sub("", text)
        text = _RE_PERCENT_ATTR.sub("", text)
        text = _RE_BLOCK_COMMENT.sub("", text)

        self._log_rule("clean_artifacts: Strip list bullets and inline symbols")
        text = _RE_LIST_BULLET.sub("", text)
        text = text.replace("as defined in .", "")
        text = text.replace("≠", "!=")
        text = text.replace("#", "").replace("_", "")

        return _RE_WHITESPACE.sub(" ", text).strip()

    # -----------------------------------------------------------------------
    # Sentence splitting
    # -----------------------------------------------------------------------

    def split_conditions(self, text: str) -> list[str]:
        """
        Sub-split a sentence on genuine logical openers (If / When / Unless /
        Otherwise).

        'The' and 'All' are deliberately absent — splitting on them caused
        raw-chunk counts to jump from ~5 k to ~11 k in earlier runs.
        """
        self._log_rule("split_logical: Sub-split on conditional openers")
        return _RE_SPLIT_COND.split(text)

    def _split_into_atomic_rules(self, text: str) -> list[str]:
        """
        Split a cleaned paragraph into atomic normative sentences.

        Strategy
        --------
        1. Split on sentence-ending punctuation (period or semicolon)
           followed by whitespace and a Capital+lowercase pair.  This
           conservatively avoids splitting on abbreviations.
        2. Sub-split each part on genuine logical openers via
           ``split_conditions()``.
        3. Attempt conjunction splitting (and/or) only on long sentences
           where both halves look like complete constraints.
        """
        self._log_rule("split_sentences: Split on sentence boundaries")
        parts = _RE_SPLIT_SENT.split(text)

        refined: list[str] = []
        for part in parts:
            sub_parts = self.split_conditions(part)
            for sp in sub_parts:
                sp = sp.strip()
                if len(sp) > 25:
                    self._log_rule(
                        "split_conjunctions: Decouple and/or compound constraints"
                    )
                    refined.extend(_split_on_conjunctions(sp))

        return [s for s in refined if len(s.strip()) > 25]

    # -----------------------------------------------------------------------
    # Structural validity
    # -----------------------------------------------------------------------

    def _is_valid_chunk(self, text: str) -> tuple[bool, Optional[str]]:
        """
        Hard structural checks — applied first, before any semantic work.
        Returns ``(valid, drop_reason)``.
        """
        t = text.strip()

        self._log_rule("validate_complete: Reject very short non-terminal fragments")
        if not t.endswith(".") and len(t.split()) < 7:
            return False, "truncated"

        self._log_rule("validate_bullets: Reject AsciiDoc list elements")
        if t.startswith(".") or t.startswith("*"):
            return False, "bullet"
        if re.match(r'^\d+\.\s', t):
            return False, "bullet"

        self._log_rule("validate_refs: Reject broken cross-reference artefacts")
        if _RE_TAG_PAIR.search(t):
            return False, "formal_reference_tag"

        tl = t.lower()
        if tl.startswith("note"):
            return False, "note"
        if any(p in tl for p in ("see .", "as defined in .", "(see )")):
            return False, "broken_reference"
        if tl.startswith("synopsis::"):
            return False, "synopsis_header"

        return True, None

    # -----------------------------------------------------------------------
    # Semantic filters
    # -----------------------------------------------------------------------

    def _is_diagram_noise(self, text: str) -> bool:
        """Reject WaveDrom, table dumps, and design-rationale fragments."""
        t = text.lower()
        if contains_any(t, _RULES["noise_patterns"]):
            return True
        if "+" in text and "register" in t and not has_any_modal(t):
            return True
        if "[" in text and "]" in text and "bits" in t and not has_any_modal(t):
            return True
        return False

    def _is_non_normative(self, text: str) -> bool:
        """Reject clearly narrative / non-normative sentences."""
        t = text.lower()
        if is_narrative(t) and not has_strong_modal(t):
            return True
        if is_pure_description(t):
            return True
        return False

    def _is_computation_description(self, text: str) -> bool:
        """Reject computation-step descriptions when no modal is present."""
        t = text.lower()
        return contains_any(t, _RULES["computation_patterns"]) and not has_any_modal(t)

    def _is_soft_rationale(self, text: str) -> bool:
        """Reject design-rationale sentences when no strong modal is present."""
        t = text.lower()
        return contains_any(t, _RULES["soft_rationale_patterns"]) and not has_strong_modal(t)

    # -----------------------------------------------------------------------
    # Intent checkers (mode-specific)
    # -----------------------------------------------------------------------

    def _has_normative_intent(self, text: str) -> bool:
        """General intent check for the main 'process' mode."""
        t = text.lower()
        return (
            has_any_modal(t)
            or has_condition_vocab(t)
            or has_csr_vocab(t)
            or has_field_vocab(t)
            or has_access_vocab(t)
            or has_explicit_bit_rule(t)
            or has_numeric_constraint(text)
            or contains_any(t, _RULES["normative_intent_vocab"])
        )

    def _has_formal_intent(self, text: str) -> bool:
        """Memory-model / formal section intent."""
        return contains_any(text.lower(), _RULES["formal_intent"])

    def _has_profile_intent(self, text: str) -> bool:
        """Profile section intent."""
        return contains_any(text.lower(), _RULES["profile_intent"])

    def _has_doc_intent(self, text: str) -> bool:
        """Naming / intro / preface section intent."""
        return contains_any(text.lower(), _RULES["docs_intent"])

    def _compute_intent(self, mode: str, text: str) -> bool:
        dispatch = {
            "process_formal":  self._has_formal_intent,
            "process_profile": self._has_profile_intent,
            "process_docs":    self._has_doc_intent,
        }
        return dispatch.get(mode, self._has_normative_intent)(text)

    # -----------------------------------------------------------------------
    # Mode-specific secondary filter
    # -----------------------------------------------------------------------

    def _passes_mode_filter(
        self, mode: str, text: str
    ) -> tuple[bool, Optional[str]]:
        """
        Applied *after* the keep gate.  Drops content that passed confidence
        scoring but does not belong in the mode's output corpus.
        """
        if mode == "process_formal":
            if not (self._has_formal_intent(text) or has_any_modal(text.lower())):
                return False, "formal_filtered"

        elif mode == "process_profile":
            if not self._has_profile_intent(text):
                return False, "profile_filtered"

        elif mode == "process_docs":
            if not self._has_doc_intent(text):
                return False, "doc_filtered"

        return True, None



    # -----------------------------------------------------------------------
    # Raw chunk persistence
    # -----------------------------------------------------------------------

    def _save_raw_chunks(self, file_path: str, raw_sentences: list[dict]) -> None:
        """
        Write all cleaned sentences for one .adoc file to
        ``data/output/raw_chunks/<safe_name>.json`` *before* any semantic
        filter runs.  Used for debugging, diffing, and offline analysis.
        """
        out_path = RAW_CHUNKS_DIR / _raw_chunk_filename(file_path)
        payload = {
            "source_file": file_path,
            "total":       len(raw_sentences),
            "sentences":   raw_sentences,
        }
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)

    # -----------------------------------------------------------------------
    # Paragraph flushing  (promoted from nested closure in original code)
    # -----------------------------------------------------------------------

    def flush_paragraphs(
        self,
        paragraphs_buf: list[str],
        section_hierarchy: list[str],
        start_line: int,
        mode: str,
        file_path: str,
        file_chunks: list[dict],
        raw_sentences: list[dict],
    ) -> None:
        """
        Process all paragraphs accumulated since the last section header.

        Parameters
        ----------
        paragraphs_buf    : lines collected between the previous header and now
        section_hierarchy : current breadcrumb stack, e.g. ["Intro", "CSRs"]
        start_line        : 1-based line number where this paragraph block starts
        mode              : processing mode string ("process", "process_formal", …)
        file_path         : relative path of the source .adoc file (for logging)
        file_chunks       : accumulator for accepted chunk dicts (mutated in-place)
        raw_sentences     : accumulator for pre-filter sentence dicts (mutated)
        """
        text_block = "\n".join(paragraphs_buf).strip()
        if not text_block:
            return

        paragraphs   = re.split(r"\n\s*\n", text_block)
        line_offset  = start_line
        section_path = " > ".join(section_hierarchy)

        self._log_rule("warl_detection")
        self._log_rule("csr_context_boost")
        self._log_rule("confidence_classification")

        for para in paragraphs:
            p_norm        = normalize_text(para)
            p_lines_count = para.count("\n") + 1

            if (
                not p_norm
                or p_norm.startswith("//")
                or p_norm.startswith("include::")
            ):
                line_offset += p_lines_count + 1
                continue

            cleaned   = self._clean_text(p_norm)
            sentences = self._split_into_atomic_rules(cleaned)

            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                # ── Stage 1: collect raw sentence ──────────────────────────
                self.report["files"][file_path]["raw_chunks"] += 1
                raw_sentences.append({
                    "text":       sentence,
                    "section":    section_path,
                    "line_range": [line_offset, line_offset + p_lines_count - 1],
                })

                # ── Stage 2: filtering pipeline ────────────────────────────

                # 1. Hard structural validation
                valid, drop_reason = self._is_valid_chunk(sentence)
                if not valid:
                    self._record_drop(drop_reason, file_path)
                    continue

                tl = sentence.lower()

                # 2. Instruction-description header
                if tl.startswith("description"):
                    self._record_drop("instruction_description", file_path)
                    continue

                # 3. Diagram / formatting noise
                if self._is_diagram_noise(sentence):
                    self._record_drop("noise", file_path)
                    continue

                # 4. Non-normative narrative
                if self._is_non_normative(sentence):
                    self._record_drop("non_normative", file_path)
                    continue

                # 5. Computation description
                if self._is_computation_description(sentence):
                    self._record_drop("computation_description", file_path)
                    continue

                # 6. Soft rationale / design intent
                if self._is_soft_rationale(sentence):
                    self._record_drop("soft_rationale", file_path)
                    continue

                # 7. Confidence + intent gate
                intent = self._compute_intent(mode, sentence)
                keep, confidence = should_keep(sentence, section_path, intent)
                self.report["confidence_distribution"][confidence] += 1

                if not keep:
                    self._record_drop("low_signal", file_path)
                    continue

                # 8. Mode-specific secondary filter
                passes, drop_reason = self._passes_mode_filter(mode, sentence)
                if not passes:
                    self._record_drop(drop_reason, file_path)
                    continue

                # ── Accept ──────────────────────────────────────────────────
                self._global_counter += 1
                self.report["files"][file_path]["final_chunks"] += 1

                param_class = classify_parameter_class(sentence)
                param_type  = classify_parameter_type(sentence)

                cls = self.report["classification"]["class"]
                cls[param_class] = cls.get(param_class, 0) + 1

                typ = self.report["classification"]["type"]
                typ[param_type] = typ.get(param_type, 0) + 1

                if (
                    param_class == "unknown"
                    and len(self.report["classification"]["unknown_samples"]) < 10
                ):
                    self.report["classification"]["unknown_samples"].append(sentence)

                file_chunks.append({
                    "chunk_id":        chunk_id(file_path, section_path, self._global_counter),
                    "text":            sentence,
                    "source_file":     file_path,
                    "section":         section_path,
                    "confidence":      confidence,
                    "parameter_class": param_class,
                    "parameter_type":  param_type,
                    "line_range":      [line_offset, line_offset + p_lines_count - 1],
                })

            line_offset += p_lines_count + 1

    # -----------------------------------------------------------------------
    # Per-file processing
    # -----------------------------------------------------------------------

    def process_file(self, file_path: str) -> None:
        """Parse one .adoc file and append accepted chunks to repo_results."""
        status, ignored_cat = classify_file(file_path)

        if status == "ignore":
            self.report["file_classification"]["ignored"][ignored_cat].append(file_path)
            return

        mode = status
        self.report["file_classification"]["processed"].append(file_path)

        abs_path = self.repo_dir / file_path
        if not abs_path.exists():
            logger.warning(f"File not found in repo: {file_path}")
            return

        raw_text   = abs_path.read_text(encoding="utf-8")
        clean_text = self._preprocess(raw_text)
        lines      = clean_text.split("\n")

        current_hierarchy: list[str]  = ["Preamble"]
        paragraphs_buf:    list[str]  = []
        start_line:        int        = 1
        file_chunks:       list[dict] = []
        raw_sentences:     list[dict] = []

        self.report["files"][file_path] = {
            "raw_chunks":   0,
            "final_chunks": 0,
            "dropped":      0,
        }

        for _i, line in enumerate(lines, 1):
            header_match = _RE_SECTION_HDR.match(line)
            if header_match:
                self.flush_paragraphs(
                    paragraphs_buf, current_hierarchy, start_line,
                    mode, file_path, file_chunks, raw_sentences,
                )

                level = len(header_match.group(1))
                title = header_match.group(2).strip()

                if level == 1 or not current_hierarchy:
                    current_hierarchy = [title]
                else:
                    depth_idx = level - 1
                    if depth_idx < len(current_hierarchy):
                        current_hierarchy = current_hierarchy[:depth_idx] + [title]
                    else:
                        current_hierarchy.append(title)

                paragraphs_buf = []
                start_line     = _i + 1
            else:
                paragraphs_buf.append(line)

        # Flush the final paragraph block.
        self.flush_paragraphs(
            paragraphs_buf, current_hierarchy, start_line,
            mode, file_path, file_chunks, raw_sentences,
        )

        # Persist raw sentences (pre-filter) for offline inspection.
        self._save_raw_chunks(file_path, raw_sentences)

        if file_chunks:
            self.repo_results.append({"file": file_path, "chunks": file_chunks})

    # -----------------------------------------------------------------------
    # Output writing
    # -----------------------------------------------------------------------

    def _write_outputs(self) -> None:
        """Write chunks_repo.json, parameter_dataset.csv, and dump report data."""
        with open(CHUNKS_REPO_PATH, "w", encoding="utf-8") as fh:
            json.dump(self.repo_results, fh, indent=2)

        # ── Dump report dict for pipeline/export/reporter.py ──
        report_data_path = OUTPUT_DIR / "adoc_report_data.json"
        with open(report_data_path, "w", encoding="utf-8") as fh:
            json.dump(self.report, fh, indent=2)

        with open(PARAMETER_DATASET_PATH, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "chunk_id", "file", "line",
                "section", "text",
                "parameter_class", "parameter_type",
                "confidence", "reviewed", "notes",
            ])
            for file_data in self.repo_results:
                for c in file_data["chunks"]:
                    writer.writerow([
                        c["chunk_id"],
                        c["source_file"],
                        c["line_range"][0],
                        c["section"],
                        c["text"],
                        c["parameter_class"],
                        c["parameter_type"],
                        c["confidence"],
                        False,
                        "",
                    ])

    # -----------------------------------------------------------------------
    # Orchestration
    # -----------------------------------------------------------------------

    def run(self) -> bool:
        """
        Full pipeline run:
          1. Ensure the ISA manual repository is present (clone if needed).
          2. Discover all .adoc sources.
          3. Process each file through the filtering pipeline.
          4. Write all output artefacts.

        Returns ``True`` on success.
        """
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        RAW_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

        self._ensure_repo()

        src_dir   = self.repo_dir / "src"
        rel_files = sorted(
            str(f.relative_to(self.repo_dir))
            for f in src_dir.rglob("*.adoc")
        )

        logger.info(f"Processing {len(rel_files)} AsciiDoc files …")

        for f in tqdm(rel_files, desc="Parsing"):
            self.process_file(f)

        r_total = sum(d["raw_chunks"]   for d in self.report["files"].values())
        k_total = sum(d["final_chunks"] for d in self.report["files"].values())

        self.report["global"] = {
            "total_files":        len(rel_files),
            "processed_files":    len(self.report["file_classification"]["processed"]),
            "skipped_files":      sum(
                len(v) for v in self.report["file_classification"]["ignored"].values()
            ),
            "total_raw_chunks":   r_total,
            "total_final_chunks": k_total,
            "reduction_percent":  round(100 - (k_total / max(1, r_total) * 100), 2),
            "isa_manual_commit":  self._repo_commit(),
        }
        # Report generation is suspended pending pipeline/export completion.
        # self._write_report()

        self._write_outputs()
        logger.info(f"Analysis exported  → {FILTER_STATS_PATH}")
        logger.info(f"Raw chunks saved   → {RAW_CHUNKS_DIR}/ ({len(rel_files)} files)")
        return True


# ---------------------------------------------------------------------------
# CLI entry point (for direct invocation / testing)
# ---------------------------------------------------------------------------

def main() -> None:
    chunker = AsciiDocChunker(ISA_MANUAL_DIR)
    chunker.run()


if __name__ == "__main__":
    main()
