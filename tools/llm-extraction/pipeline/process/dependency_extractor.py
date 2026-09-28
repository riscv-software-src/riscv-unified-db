"""
Purpose:
    Extracts cross-parameter dependencies and ownership contexts from UDB schemas
    and AsciiDoc sentence text.
    Used for building the global parameter dependency graph.

Pipeline Stage:
    process

Inputs:
    - Raw dict/list structures loaded from UDB YAML/JSON schemas
    - AsciiDoc sentence text strings (from chunker output)
    - AST paths to infer type contexts

Outputs:
    - (None — provides DependencyExtractor class for graph building)

Core Responsibilities:
    - Extract dependencies (which parameters this object relies on)
    - Extract definitions (which extensions/parameters own this object)
    - Infer chunk types from file paths using injected Mapping
    - Extract extension/instruction cross-references from AsciiDoc inline macros

Key Assumptions:
    - YAML-sourced extensions describe their name via
      {"extension": {"name": ...}} or a plain string
    - YAML-sourced parameters describe dependencies via {"param": {"name": ...}}
    - AsciiDoc-sourced text uses macro syntax: ext:NAME[], extlink:NAME[],
      insn:NAME[], param:NAME[] to reference other ISA entities

Failure Modes:
    - Silently misses dependencies if schema structure diverges
    - AsciiDoc macro extraction only covers known macro prefixes; new prefixes
      introduced by the toolchain require adding to _ADOC_MACRO_PREFIXES

Notes:
    - Extracted sets are used downstream to build edges in dependency_graph.json
    - extract_adoc_refs() is the new entry point for text-sourced chunks;
      extract_defined_by() and extract_param_deps() handle YAML-sourced chunks
"""

import re
from typing import Any
from pathlib import Path

# ---------------------------------------------------------------------------
# AsciiDoc inline macro extraction
# ---------------------------------------------------------------------------

# Matches AsciiDoc cross-reference macros of the form  prefix:TARGET[]
# where TARGET is the dependency name (extension, instruction, parameter).
#
# Known macro prefixes in the RISC-V ISA manual:
#   ext:      — standard extension (e.g. ext:a[], ext:zicsr[])
#   extlink:  — extension with hyperlink (e.g. extlink:zalrsc[])
#   insn:     — instruction mnemonic (e.g. insn:fence[], insn:lr.w[])
#   param:    — architectural parameter (e.g. param:XLEN[])
#   csr:      — CSR register name (e.g. csr:mstatus[])
#
_ADOC_MACRO_RE = re.compile(
    r'\b(ext|extlink|insn|param|csr):([A-Za-z0-9_.\-]+)\[\]',
    re.IGNORECASE,
)

# Maps macro prefix → dependency kind label used in the graph
_PREFIX_TO_KIND: dict[str, str] = {
    "ext":     "extension",
    "extlink": "extension",
    "insn":    "instruction",
    "param":   "parameter",
    "csr":     "csr",
}


def extract_adoc_refs(text: str) -> list[dict[str, str]]:
    """
    Extract all AsciiDoc inline macro cross-references from a sentence.

    Returns a list of dicts, each with:
      "name"  — the referenced entity name (e.g. "zalrsc", "fence", "XLEN")
      "kind"  — entity type: "extension", "instruction", "parameter", or "csr"

    Examples
    --------
    >>> extract_adoc_refs("The ext:a[] extension comprises extlink:zalrsc[] and extlink:zaamo[].")
    [{"name": "a", "kind": "extension"},
     {"name": "zalrsc", "kind": "extension"},
     {"name": "zaamo", "kind": "extension"}]

    >>> extract_adoc_refs("The insn:fence[] instruction should be used to order across both domains.")
    [{"name": "fence", "kind": "instruction"}]
    """
    refs = []
    seen: set[tuple[str, str]] = set()
    for match in _ADOC_MACRO_RE.finditer(text):
        prefix = match.group(1).lower()
        name   = match.group(2)
        kind   = _PREFIX_TO_KIND.get(prefix, "unknown")
        key    = (name, kind)
        if key not in seen:
            seen.add(key)
            refs.append({"name": name, "kind": kind})
    return refs


def extract_adoc_extension_names(text: str) -> set[str]:
    """
    Convenience wrapper: return only the set of extension names referenced
    by ext: or extlink: macros in *text*.
    """
    return {
        r["name"]
        for r in extract_adoc_refs(text)
        if r["kind"] == "extension"
    }


def extract_adoc_instruction_names(text: str) -> set[str]:
    """
    Convenience wrapper: return only the set of instruction names referenced
    by insn: macros in *text*.
    """
    return {
        r["name"]
        for r in extract_adoc_refs(text)
        if r["kind"] == "instruction"
    }


# ---------------------------------------------------------------------------
# DependencyExtractor class
# ---------------------------------------------------------------------------

class DependencyExtractor:
    """
    Extracts cross-parameter dependencies and ownership contexts from both
    UDB YAML/JSON schema structures and AsciiDoc sentence text.

    Parameters
    ----------
    dir_to_chunk_type:
        Mapping from directory name to chunk type label, used by
        infer_chunk_type() to annotate graph nodes.
    """

    def __init__(self, dir_to_chunk_type: dict[str, str]):
        self.dir_mapping = dir_to_chunk_type

    # ------------------------------------------------------------------ YAML

    def extract_defined_by(self, obj: Any) -> tuple[set, set]:
        """
        Recursively extract which extensions and parameters *define* (own)
        the schema object *obj*.

        Returns
        -------
        (extensions, params) — both are sets of name strings.
        """
        exts, params = set(), set()
        if isinstance(obj, dict):
            if "extension" in obj:
                ext = obj["extension"]
                if isinstance(ext, str):
                    exts.add(ext)
                elif isinstance(ext, dict) and "name" in ext:
                    exts.add(ext["name"])
            if "param" in obj and isinstance(obj["param"], dict):
                name = obj["param"].get("name")
                if name:
                    params.add(name)
            for v in obj.values():
                e, p = self.extract_defined_by(v)
                exts |= e
                params |= p
        elif isinstance(obj, list):
            for item in obj:
                e, p = self.extract_defined_by(item)
                exts |= e
                params |= p
        return exts, params

    def extract_param_deps(self, obj: Any) -> set:
        """
        Recursively extract parameter names that *obj* depends on.

        Returns
        -------
        A set of parameter name strings.
        """
        deps = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "param" and isinstance(v, dict) and v.get("name"):
                    deps.add(v["name"])
                else:
                    deps |= self.extract_param_deps(v)
        elif isinstance(obj, list):
            for item in obj:
                deps |= self.extract_param_deps(item)
        return deps

    # ----------------------------------------------------------------- Text

    def extract_text_refs(self, text: str) -> list[dict[str, str]]:
        """
        Extract AsciiDoc inline macro cross-references from a sentence string.

        Delegates to the module-level extract_adoc_refs() function so callers
        do not need to import it separately.

        Returns
        -------
        List of {"name": str, "kind": str} dicts.
        """
        return extract_adoc_refs(text)

    def extract_text_extension_deps(self, text: str) -> set[str]:
        """Return the set of extension names referenced in *text*."""
        return extract_adoc_extension_names(text)

    def extract_text_instruction_deps(self, text: str) -> set[str]:
        """Return the set of instruction names referenced in *text*."""
        return extract_adoc_instruction_names(text)

    # --------------------------------------------------------------- Utility

    def infer_chunk_type(self, source_path: "str | Path", yaml_key_path: str = "") -> str:
        """Infer chunk type from the parent directory name of *source_path*."""
        return self.dir_mapping.get(Path(source_path).parent.name, "unknown")
