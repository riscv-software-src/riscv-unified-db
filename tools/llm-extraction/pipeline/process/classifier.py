"""
Purpose:
    Parametric classification of rules extracted from the ISA manual.
    Determines parameter class, type, and extraction confidence based on
    signals and taxonomy definitions.

Pipeline Stage:
    process

Inputs:
    - configs/taxonomy.yaml     (class/type definitions)
    - configs/schema_rules.yaml (vocabulary signals)

Outputs:
    - (None — provides functions for the pipeline)

Core Responsibilities:
    - Load signal vocabularies and taxonomy labels
    - Provide signal detection helpers (_has_strong_modal, etc.)
    - Classify extraction confidence (low/medium/high/very_high)
    - Classify parameter class and type using taxonomy definitions
    - Gate chunk inclusion logic (should_keep)

Key Assumptions:
    - Parameter classes and types align with configs/taxonomy.yaml
    - Signal detection strips AsciiDoc inline markup before matching
    - Numeric forms ("read-only 0") are treated equivalently to word forms

Failure Modes:
    - Misclassification if taxonomy.yaml categories change without updating logic

Notes:
    - All public helpers accept raw (not yet lowercased) text; lowercasing
      is done internally so callers do not need to pre-process.
    - strip_markup() is applied at the start of every public helper so that
      backtick-quoted CSR names (`misa`) and bold WARL markers (*WARL*)
      are recognised correctly.
    - Section context is used as a secondary CSR signal in both confidence
      scoring and class classification (fixes "TVM is read-only 0" cases).
"""

import re
from pathlib import Path
from typing import Optional

import yaml

import sys
_PROCESS_DIR = Path(__file__).parent.resolve()
_TOOL_DIR = _PROCESS_DIR.parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from configs.config import CONFIGS_DIR


# ---------------------------------------------------------------------------
# Config Loaders
# ---------------------------------------------------------------------------

_SCHEMA_RULES_PATH = CONFIGS_DIR / "schema_rules.yaml"
_TAXONOMY_PATH     = CONFIGS_DIR / "taxonomy.yaml"

def _load_schema_rules() -> dict[str, frozenset[str]]:
    with open(_SCHEMA_RULES_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    signals = data.get("signals", {})
    noise   = data.get("noise",   {})
    intent  = data.get("intent",  {})

    def _fs(section: dict, key: str) -> frozenset[str]:
        return frozenset(section.get(key, []))

    return {
        "strong_modals":          _fs(signals, "strong_modals"),
        "weak_modals":            _fs(signals, "weak_modals"),
        "csr_vocab":              _fs(signals, "csr_vocab"),
        "register_context_vocab": _fs(signals, "register_context_vocab"),
        "field_vocab":            _fs(signals, "field_vocab"),
        "bit_constraint_vocab":   _fs(signals, "bit_constraint_vocab"),
        "range_vocab":            _fs(signals, "range_vocab"),
        "condition_vocab":        _fs(signals, "condition_vocab"),
        "binary_state_vocab":     _fs(signals, "binary_state_vocab"),
        "access_vocab":           _fs(signals, "access_vocab"),
        "normative_intent_vocab": _fs(signals, "normative_intent_vocab"),

        "narrative_patterns":      _fs(noise, "narrative_patterns"),
        "computation_patterns":    _fs(noise, "computation_patterns"),
        "noise_patterns":          _fs(noise, "noise_patterns"),
        "soft_rationale_patterns": _fs(noise, "soft_rationale_patterns"),

        "formal_intent":  _fs(intent, "formal"),
        "profile_intent": _fs(intent, "profile"),
        "docs_intent":    _fs(intent, "docs"),
    }

def _load_taxonomy_classes() -> tuple[frozenset[str], frozenset[str]]:
    with open(_TAXONOMY_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    classes = frozenset(c["name"] for c in data.get("parameter_classes", []))
    types   = frozenset(t["name"] for t in data.get("parameter_types",   []))

    if not classes:
        classes = frozenset({"CSR_controlled", "SW_rule", "non_CSR_parameter", "unknown"})
    if not types:
        types   = frozenset({"binary", "range", "enum", "unknown"})

    return classes, types

_RULES = _load_schema_rules()
_VALID_CLASSES, _VALID_TYPES = _load_taxonomy_classes()

_STRONG_MODALS:          frozenset[str] = _RULES["strong_modals"]
_WEAK_MODALS:            frozenset[str] = _RULES["weak_modals"]
_ALL_MODALS:             frozenset[str] = _STRONG_MODALS | _WEAK_MODALS
_CSR_VOCAB:              frozenset[str] = _RULES["csr_vocab"]
_REGISTER_CONTEXT_VOCAB: frozenset[str] = _RULES["register_context_vocab"]
_FIELD_VOCAB:            frozenset[str] = _RULES["field_vocab"]
_BIT_CONSTRAINT_VOCAB:   frozenset[str] = _RULES["bit_constraint_vocab"]
_RANGE_VOCAB:            frozenset[str] = _RULES["range_vocab"]
_CONDITION_VOCAB:        frozenset[str] = _RULES["condition_vocab"]
_BINARY_STATE_VOCAB:     frozenset[str] = _RULES["binary_state_vocab"]
_ACCESS_VOCAB:           frozenset[str] = _RULES["access_vocab"]
_NORMATIVE_INTENT_VOCAB: frozenset[str] = _RULES["normative_intent_vocab"]

# Numeric forms of binary-state phrases not covered by word-form vocab.
# "read-only 0", "set to 0", "set to 1", "cleared to 0", "hardwired to 0/1"
_RE_BINARY_NUMERIC = re.compile(
    r'\b(?:read-only|hardwired to|set to|cleared to)\s+[01]\b',
    re.IGNORECASE,
)

_RE_NUMERIC_CONSTRAINT = re.compile(
    r'\b\d+\s*(?:bits?|bytes?|words?|xlen|mxlen|ilen|vlen)\b'
    r'|\b(?:at least|at most|no (?:greater|less) than)\s+\d'
    r'|\b\d+(?:-bit|-byte)\b',
    re.IGNORECASE,
)

# Strips AsciiDoc inline markup that the text cleaner does not always remove:
#   `backtick-quoted names`   →  the bare name
#   *bold text*               →  the bare text
#   _italic text_             →  the bare text
_RE_BACKTICK  = re.compile(r'`([^`]+)`')
_RE_BOLD      = re.compile(r'\*([^*]+)\*')
_RE_ITALIC    = re.compile(r'_([^_]+)_')


# ---------------------------------------------------------------------------
# Markup stripping
# ---------------------------------------------------------------------------

def strip_markup(text: str) -> str:
    """
    Remove residual AsciiDoc inline markup so that keyword matching works
    on CSR names that survive the chunker's cleaning step.

    Examples
    --------
    ``The `misa` CSR is a *WARL* register.``
    → ``The misa CSR is a WARL register.``
    """
    text = _RE_BACKTICK.sub(r'\1', text)
    text = _RE_BOLD.sub(r'\1', text)
    text = _RE_ITALIC.sub(r'\1', text)
    return text


# ---------------------------------------------------------------------------
# Signal Core
# ---------------------------------------------------------------------------

_COMPILED_VOCABS: dict[frozenset[str], re.Pattern] = {}

def contains_any(t: str, vocab: frozenset[str]) -> bool:
    """
    Return True if *t* contains any keyword from *vocab* using word boundaries.

    The input *t* must already be lowercased by the caller.
    Markup is NOT stripped here — call strip_markup() first when needed.
    """
    if not vocab:
        return False
    if vocab not in _COMPILED_VOCABS:
        sorted_kw = sorted([str(kw).lower() for kw in vocab], key=len, reverse=True)
        pattern_str = r'\b(?:' + '|'.join(re.escape(kw) for kw in sorted_kw) + r')\b'
        _COMPILED_VOCABS[vocab] = re.compile(pattern_str)
    return bool(_COMPILED_VOCABS[vocab].search(t))


def _clean(text: str) -> str:
    """Strip markup and lowercase — the standard pre-processing for all helpers."""
    return strip_markup(text).lower()


def has_strong_modal(t: str) -> bool:
    return contains_any(_clean(t), _STRONG_MODALS)

def has_any_modal(t: str) -> bool:
    return contains_any(_clean(t), _ALL_MODALS)

def has_csr_vocab(t: str) -> bool:
    return contains_any(_clean(t), _CSR_VOCAB)

def has_field_vocab(t: str) -> bool:
    return contains_any(_clean(t), _FIELD_VOCAB)

def has_condition_vocab(t: str) -> bool:
    return contains_any(_clean(t), _CONDITION_VOCAB)

def has_access_vocab(t: str) -> bool:
    return contains_any(_clean(t), _ACCESS_VOCAB)

def has_binary_state(t: str) -> bool:
    tc = _clean(t)
    return contains_any(tc, _BINARY_STATE_VOCAB) or bool(_RE_BINARY_NUMERIC.search(tc))

def has_range_vocab(t: str) -> bool:
    return contains_any(_clean(t), _RANGE_VOCAB)

def has_numeric_constraint(text: str) -> bool:
    return bool(_RE_NUMERIC_CONSTRAINT.search(strip_markup(text)))

def has_explicit_bit_rule(t: str) -> bool:
    tc = _clean(t)
    if not contains_any(tc, _BIT_CONSTRAINT_VOCAB):
        return False
    return (
        has_any_modal(tc)
        or has_condition_vocab(tc)
        or has_access_vocab(tc)
        or contains_any(tc, frozenset({"field", "encoded", "zero", "sign"}))
    )

def is_narrative(t: str) -> bool:
    return contains_any(_clean(t), _RULES["narrative_patterns"])

def is_pure_description(t: str) -> bool:
    tc = _clean(t)
    if has_any_modal(tc) or has_condition_vocab(tc):
        return False
    if has_csr_vocab(tc) and has_access_vocab(tc):
        return False
    return contains_any(tc, _RULES["computation_patterns"])


# ---------------------------------------------------------------------------
# Section-context helpers
# ---------------------------------------------------------------------------

# CSR register names that appear in section headings but not sentence bodies.
# Extracted from the ISA manual heading patterns ("in `mstatus` register" etc.)
_RE_SECTION_CSR = re.compile(
    r'\b(?:' +
    '|'.join(re.escape(name) for name in sorted(_RULES["csr_vocab"], key=len, reverse=True)) +
    r')\b',
    re.IGNORECASE,
)

def section_has_csr(section: str) -> bool:
    """
    Return True when the section breadcrumb names a known CSR register.

    This catches cases like:
      text  = "TVM is read-only 0 when S-mode is not supported."
      section = "Virtualization Support in `mstatus` Register"
    where the text alone has no CSR keyword.
    """
    return bool(_RE_SECTION_CSR.search(strip_markup(section)))


# ---------------------------------------------------------------------------
# Classification Logic
# ---------------------------------------------------------------------------

def classify_confidence(text: str, section: str) -> str:
    """
    Score extraction confidence for a single chunk.

    Changes vs. original
    --------------------
    - strip_markup() applied before matching so `misa` / *WARL* are found.
    - section_has_csr() promotes section-only CSR contexts to "high"
      (was silently scored "low", causing real constraints to be dropped).
    - has_binary_state() now covers numeric forms ("read-only 0").
    """
    t   = _clean(text)
    sec = strip_markup(section).lower()

    # Tier 1 — very_high
    if contains_any(t, frozenset({"warl", "wpri", "wlrl"})):
        return "very_high"
    if has_strong_modal(t):
        return "very_high"

    # Tier 2 — high
    if has_csr_vocab(t):
        return "high"
    if has_field_vocab(t) or has_access_vocab(t):
        return "high"
    if has_explicit_bit_rule(t):
        return "high"
    if has_condition_vocab(t):
        return "high"
    # Section-context boost: sentence lives inside a named CSR section
    if section_has_csr(section):
        return "high"
    if any(k in sec for k in _REGISTER_CONTEXT_VOCAB):
        return "high"

    # Tier 3 — medium
    if has_any_modal(t):
        return "medium"
    if has_numeric_constraint(text):
        return "medium"
    if has_binary_state(t):          # e.g. "read-only 0" without explicit CSR
        return "medium"
    if any(k in sec for k in ("memory", "ordering", "model")):
        return "medium"

    return "low"


def should_keep(text: str, section: str, intent: bool) -> tuple[bool, str]:
    confidence = classify_confidence(text, section)
    t = _clean(text)

    if confidence in ("very_high", "high"):
        return True, confidence

    if confidence == "medium" and intent:
        return True, confidence

    if has_numeric_constraint(text) and has_condition_vocab(t):
        return True, "medium"

    return False, confidence


def classify_parameter_class(text: str, section: str = "") -> str:
    """
    Classify the parameter class of a chunk.

    Changes vs. original
    --------------------
    - strip_markup() applied before matching so `misa` / *WARL* are found.
    - section parameter: when the text has no CSR keyword but the section names
      a CSR register, the chunk is classified CSR_controlled.
    - Condition-only sentences ("If aq bit is set, … is treated as …") without
      a modal are now classified non_CSR_parameter when they describe normative
      architectural behaviour rather than narrative prose.
    - Reserved-encoding sentences are classified non_CSR_parameter.
    - Normative-outcome vocabulary ("raises", "results in", "is sign-extended"
      etc.) routes to non_CSR_parameter even without an explicit modal.
    - VLEN / XLEN numeric constraints are matched (vlen added to numeric regex).

    Priority order (first match wins)
    ----------------------------------
    1. WARL / WPRI / WLRL keywords           → CSR_controlled
    2. Named CSR in sentence body             → CSR_controlled
    3. Field + access vocab                   → CSR_controlled
    4. Explicit bit rule + access vocab       → CSR_controlled
    5. Section names a CSR + any signal       → CSR_controlled
    6. Software / ABI / fence vocab           → SW_rule
    7. Strong modal (must / shall)            → non_CSR_parameter
    8. Condition + normative outcome / bound  → non_CSR_parameter
    9. Condition alone (long, non-narrative)  → non_CSR_parameter
    10. Reserved encoding                     → non_CSR_parameter
    11. Numeric constraint                    → non_CSR_parameter
    12. Normative-outcome vocab               → non_CSR_parameter
    13. Any modal                             → non_CSR_parameter
    14. fallback                              → unknown
    """
    t = _clean(text)

    # ── CSR-controlled ──────────────────────────────────────────────────────
    if contains_any(t, frozenset({"warl", "wpri", "wlrl"})):
        return "CSR_controlled" if "CSR_controlled" in _VALID_CLASSES else "unknown"

    if has_csr_vocab(t):
        return "CSR_controlled" if "CSR_controlled" in _VALID_CLASSES else "unknown"

    if has_field_vocab(t) and has_access_vocab(t):
        return "CSR_controlled" if "CSR_controlled" in _VALID_CLASSES else "unknown"

    if has_explicit_bit_rule(t) and has_access_vocab(t):
        return "CSR_controlled" if "CSR_controlled" in _VALID_CLASSES else "unknown"

    if section and section_has_csr(section):
        if has_access_vocab(t) or has_binary_state(t) or has_condition_vocab(t) or has_any_modal(t):
            return "CSR_controlled" if "CSR_controlled" in _VALID_CLASSES else "unknown"

    # ── SW_rule ─────────────────────────────────────────────────────────────
    _SW_VOCAB = frozenset({
        "software", "fence", "execution environment",
        "abi", "calling convention",
        "supervisor software", "machine-mode software",
        "hypervisor", "user-mode software",
        "operating system",
    })
    if contains_any(t, _SW_VOCAB):
        return "SW_rule" if "SW_rule" in _VALID_CLASSES else "unknown"

    # ── non_CSR_parameter ───────────────────────────────────────────────────
    if has_strong_modal(t):
        return "non_CSR_parameter" if "non_CSR_parameter" in _VALID_CLASSES else "unknown"

    # Condition + normative outcome or concrete bound (no modal required).
    # Covers: "If aq bit is set, the operation is treated as an acquire."
    # Covers: "If the value is zero, the result is sign-extended."
    _NORMATIVE_OUTCOME = frozenset({
        "raise", "raises", "not permitted", "illegal instruction",
        "results in", "is sign-extended", "is zero-extended",
        "is treated as", "is placed", "is written", "is read",
        "is undefined", "unpredictable", "implementation-defined",
        "may vary", "implementation-specific", "unspecified",
        "depends on", "determined by", "controls", "enforces",
    })
    if has_condition_vocab(t) and (
        contains_any(t, _NORMATIVE_OUTCOME)
        or has_numeric_constraint(text)
        or has_binary_state(t)
        or has_access_vocab(t)
    ):
        return "non_CSR_parameter" if "non_CSR_parameter" in _VALID_CLASSES else "unknown"

    # Condition alone — long, non-narrative sentences that define
    # architectural behaviour without an explicit modal.
    # Threshold: ≥ 12 words to avoid short fragments.
    if (
        has_condition_vocab(t)
        and not is_narrative(t)
        and len(text.split()) >= 12
    ):
        return "non_CSR_parameter" if "non_CSR_parameter" in _VALID_CLASSES else "unknown"

    # Reserved encodings
    if (
        contains_any(t, frozenset({"reserved", "reserved encoding", "encodings are reserved"}))
        and not is_narrative(t)
    ):
        return "non_CSR_parameter" if "non_CSR_parameter" in _VALID_CLASSES else "unknown"

    if has_numeric_constraint(text) and not is_narrative(t):
        return "non_CSR_parameter" if "non_CSR_parameter" in _VALID_CLASSES else "unknown"

    if contains_any(t, _NORMATIVE_OUTCOME) and not is_narrative(t):
        return "non_CSR_parameter" if "non_CSR_parameter" in _VALID_CLASSES else "unknown"

    if has_any_modal(t):
        return "non_CSR_parameter" if "non_CSR_parameter" in _VALID_CLASSES else "unknown"

    return "unknown"


def classify_parameter_type(text: str, section: str = "") -> str:
    """
    Classify the parameter type of a chunk.

    Changes vs. original
    --------------------
    - strip_markup() applied before matching.
    - Numeric binary-state patterns ("read-only 0", "hardwired to 1") handled
      by has_binary_state() which now includes _RE_BINARY_NUMERIC.
    - enum detection extended with UDB access-mode labels (RO, RW, RW-R …).
    """
    t = _clean(text)

    # binary: explicit boolean-state patterns (word or numeric)
    if has_binary_state(t):
        return "binary" if "binary" in _VALID_TYPES else "unknown"

    # range: explicit numeric or bit-width bounds
    if has_numeric_constraint(text) or has_range_vocab(t):
        return "range" if "range" in _VALID_TYPES else "unknown"

    # enum: mode / encoding selection
    enum_vocab = frozenset({
        "one of", "either", "select", "encoding",
        "privilege level", "privilege mode",
        "access mode", "addressing mode",
        # UDB CSR field type labels
        "ro", "rw", "rw-r", "ro-h", "rw-h", "rw-rh",
    })
    if contains_any(t, enum_vocab):
        return "enum" if "enum" in _VALID_TYPES else "unknown"

    # CSR / field → likely an enum (register mode or encoding)
    if has_csr_vocab(t) or has_field_vocab(t):
        return "enum" if "enum" in _VALID_TYPES else "unknown"

    # Section-context CSR + condition → typically binary or enum
    if section and section_has_csr(section):
        if has_condition_vocab(t) and has_strong_modal(t):
            return "binary" if "binary" in _VALID_TYPES else "unknown"
        if has_any_modal(t):
            return "enum" if "enum" in _VALID_TYPES else "unknown"

    if has_condition_vocab(t) and has_strong_modal(t):
        return "binary" if "binary" in _VALID_TYPES else "unknown"

    if has_any_modal(t):
        return "enum" if "enum" in _VALID_TYPES else "unknown"

    return "unknown"
