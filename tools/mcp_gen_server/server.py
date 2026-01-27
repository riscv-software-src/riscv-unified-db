#!/usr/bin/env python3

# Copyright (c) Synopsys, Inc.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""
MCP server for RISC-V Unified Database

Standalone tool for querying pre-generated YAML-based architecture data in gen/.
Users are responsible for populating gen/ (e.g., ./do gen:resolved_arch).

Provides tools for querying:
- Instructions, CSRs, Extensions
- IDL Functions and their usages

Enhanced features:
- Regex search support
- Fuzzy matching for typo-tolerant searches
- Field-specific searches
- XLEN filtering
- Combined multi-domain queries
"""

import asyncio
import contextlib
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml
from mcp.server.lowlevel.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# ============================================================================
# Constants and Configuration
# ============================================================================

REPO_ROOT = Path(__file__).resolve().parents[2]
GEN_DIR = REPO_ROOT / "gen"


# ============================================================================
# Fuzzy Matching Utilities
# ============================================================================


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _fuzzy_match(query: str, target: str, threshold: float = 0.6) -> bool:
    """
    Check if query fuzzy matches target.

    Args:
        query: search string
        target: string to match against
        threshold: similarity threshold (0-1), default 0.6

    Returns:
        True if similarity >= threshold
    """
    if not query or not target:
        return False

    query_lower = query.lower()
    target_lower = target.lower()

    # Exact substring match always passes
    if query_lower in target_lower:
        return True

    # Calculate similarity
    max_len = max(len(query_lower), len(target_lower))
    if max_len == 0:
        return True

    distance = _levenshtein_distance(query_lower, target_lower)
    similarity = 1.0 - (distance / max_len)

    return similarity >= threshold


def _fuzzy_score(query: str, target: str) -> float:
    """Calculate fuzzy match score (0-1, higher is better)."""
    if not query or not target:
        return 0.0

    query_lower = query.lower()
    target_lower = target.lower()

    # Exact match bonus
    if query_lower == target_lower:
        return 1.0

    # Substring match bonus
    if query_lower in target_lower:
        return 0.9

    max_len = max(len(query_lower), len(target_lower))
    if max_len == 0:
        return 1.0

    distance = _levenshtein_distance(query_lower, target_lower)
    return 1.0 - (distance / max_len)


# ============================================================================
# Utility Functions
# ============================================================================


def _ensure_in_gen(path: Path) -> Path:
    """Validate path is inside gen/ and is a YAML file."""
    p = (REPO_ROOT / path).resolve()
    if not str(p).startswith(str(GEN_DIR.resolve())):
        raise ValueError("Path must be inside 'gen/'")
    if p.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError("Path must end with .yaml or .yml")
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"File not found: {p}")
    return p


def _load_yaml(path: Path) -> dict:
    """Load and parse a YAML file."""
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _extract_defined_by(data: dict) -> list[str]:
    """Extract extension names from definedBy field (handles string, list, dict with anyOf/allOf)."""
    defined = data.get("definedBy")
    if defined is None:
        return []
    if isinstance(defined, str):
        return [defined]
    if isinstance(defined, list):
        return [str(x) for x in defined]
    if isinstance(defined, dict):
        # handle anyOf / allOf patterns
        for k in ("anyOf", "allOf", "oneOf"):
            if k in defined and isinstance(defined[k], list):
                return [str(x) for x in defined[k]]
    return []


def _extension_in_path(rel_parts: list[str]) -> str | None:
    """Find extension name from path (heuristic: segment after 'inst')."""
    for i, part in enumerate(rel_parts):
        if part == "inst" and i + 1 < len(rel_parts):
            return rel_parts[i + 1]
    return None


def _csr_extensions(data: dict) -> set[str]:
    """Extract all extension names from CSR (top-level and field-level definedBy)."""
    exts: set[str] = set()
    top = data.get("definedBy")
    if isinstance(top, str):
        exts.add(top)
    elif isinstance(top, list):
        exts.update(str(x) for x in top)
    fields = data.get("fields")
    if isinstance(fields, dict):
        for fld in fields.values():
            if isinstance(fld, dict) and "definedBy" in fld:
                db = fld.get("definedBy")
                if isinstance(db, str):
                    exts.add(db)
                elif isinstance(db, list):
                    exts.update(str(x) for x in db)
    return exts


def _extract_xlen(data: dict) -> set[int]:
    """
    Extract XLEN values from instruction/CSR data.

    Checks base field and other indicators to determine if instruction
    supports 32-bit, 64-bit, or both.
    """
    xlens: set[int] = set()

    # Check base field (common indicator)
    base = data.get("base")
    if isinstance(base, (int, str)):
        try:
            base_int = int(base)
            if base_int in {32, 64}:
                xlens.add(base_int)
        except (ValueError, TypeError):
            pass

    # Check for RV32/RV64 in definedBy or name
    defined_by = _extract_defined_by(data)
    name = data.get("name", "")

    indicators = defined_by + [name]
    for indicator in indicators:
        s = str(indicator).upper()
        if "RV32" in s or "32" in s:
            xlens.add(32)
        if "RV64" in s or "64" in s:
            xlens.add(64)

    # Check encoding for base-specific patterns
    encoding = data.get("encoding")
    if isinstance(encoding, dict):
        match = encoding.get("match", "")
        if isinstance(match, str):
            # Some encodings have XLEN-specific patterns
            if "32" in match:
                xlens.add(32)
            if "64" in match:
                xlens.add(64)

    # If no specific XLEN found, assume both (most instructions support both)
    if not xlens:
        xlens = {32, 64}

    return xlens


def _matches_field_search(data: dict, field: str, pattern: str, use_regex: bool = False) -> bool:
    """
    Check if a specific field in data matches the pattern.

    Args:
        data: YAML data dict
        field: field name (supports nested with dots, e.g., "encoding.match")
        pattern: search pattern
        use_regex: if True, treat pattern as regex

    Returns:
        True if field exists and matches pattern
    """
    # Handle nested fields
    parts = field.split(".")
    value = data
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return False

    if value is None:
        return False

    # Convert value to string for matching
    value_str = str(value) if not isinstance(value, (list, dict)) else json.dumps(value)

    if use_regex:
        try:
            return bool(re.search(pattern, value_str, re.IGNORECASE))
        except re.error:
            return False
    else:
        return pattern.lower() in value_str.lower()


# ============================================================================
# Path Iterators (domain-specific file discovery)
# ============================================================================


def _iter_instruction_yaml_paths() -> list[Path]:
    """Find all instruction YAML files."""
    paths: list[Path] = []
    if not GEN_DIR.exists():
        return paths
    for root, _dirs, files in os.walk(GEN_DIR):
        root_p = Path(root)
        # Only consider instruction folders
        if "inst" not in root_p.parts:
            continue
        for f in files:
            if f.lower().endswith((".yaml", ".yml")):
                p = root_p / f
                # Must be under spec/*/inst or resolved_spec/*/inst
                if any(part in {"spec", "resolved_spec"} for part in p.relative_to(GEN_DIR).parts):
                    paths.append(p)
    return paths


def _iter_csr_yaml_paths() -> list[Path]:
    """Find all CSR YAML files."""
    paths: list[Path] = []
    if not GEN_DIR.exists():
        return paths
    for root, _dirs, files in os.walk(GEN_DIR):
        root_p = Path(root)
        if "csr" not in root_p.parts:
            continue
        for f in files:
            if f.lower().endswith((".yaml", ".yml")):
                p = root_p / f
                paths.append(p)
    return paths


def _iter_extension_yaml_paths() -> list[Path]:
    """Find all extension YAML files."""
    paths: list[Path] = []
    if not GEN_DIR.exists():
        return paths
    for root, _dirs, files in os.walk(GEN_DIR):
        root_p = Path(root)
        if "ext" not in root_p.parts:
            continue
        for f in files:
            if f.lower().endswith((".yaml", ".yml")):
                p = root_p / f
                paths.append(p)
    return paths


# ============================================================================
# Low-Level YAML Access
# ============================================================================


async def list_gen_yaml():
    """List all YAML files under gen/ as repo-relative paths."""
    if not GEN_DIR.exists():
        return {"files": []}
    paths: list[str] = []
    for root, _dirs, files in os.walk(GEN_DIR):
        for f in files:
            if f.lower().endswith((".yaml", ".yml")):
                full = Path(root) / f
                rel = str(full.relative_to(REPO_ROOT))
                paths.append(rel)
    paths.sort()
    return {"count": len(paths), "files": paths}


async def read_gen_yaml(args: dict[str, Any]):
    """Read and parse a YAML file under gen/."""
    rel = args.get("path")
    if not isinstance(rel, str):
        raise ValueError("'path' arg must be a string")
    p = _ensure_in_gen(Path(rel))
    data = _load_yaml(p)
    return {"path": rel, "data": data}


# ============================================================================
# Instruction Tools
# ============================================================================


async def search_instructions(args: dict[str, Any]):
    """
    Search instruction YAMLs with flexible filtering.

    Args:
        term: substring to match in filename/path (optional)
        keys: list of required top-level YAML keys (optional)
        extensions: list of extension names to filter by (optional)
        xlen: filter by XLEN (32, 64, or list [32, 64]) (optional)
        use_regex: treat term as regex pattern (default False)
        fuzzy: enable fuzzy matching with threshold (0-1, default disabled)
        field: specific field to search in (e.g., "assembly", "encoding.match")
        limit: max results (default 50)
    """
    term = args.get("term")
    keys = args.get("keys") or []
    extensions = args.get("extensions") or []
    xlen_filter = args.get("xlen")
    use_regex = args.get("use_regex", False)
    fuzzy = args.get("fuzzy")
    field = args.get("field")
    limit = int(args.get("limit") or 50)

    if term is not None and not isinstance(term, str):
        raise ValueError("'term' must be a string if provided")
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise ValueError("'keys' must be a list of strings")
    if not isinstance(extensions, list) or not all(isinstance(e, str) for e in extensions):
        raise ValueError("'extensions' must be a list of strings")

    # Parse XLEN filter
    xlen_set: set[int] = set()
    if xlen_filter is not None:
        if isinstance(xlen_filter, int):
            xlen_set = {xlen_filter}
        elif isinstance(xlen_filter, list):
            xlen_set = {
                int(x)
                for x in xlen_filter
                if isinstance(x, int) or (isinstance(x, str) and x.isdigit())
            }
        else:
            with contextlib.suppress(ValueError, TypeError):
                xlen_set = {int(xlen_filter)}

    ext_set = {e for e in extensions}
    results: list[dict[str, Any]] = []
    count = 0

    # Compile regex if needed
    regex_pattern = None
    if use_regex and term:
        try:
            regex_pattern = re.compile(term, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

    for p in _iter_instruction_yaml_paths():
        rel = p.relative_to(REPO_ROOT)
        rel_str = str(rel)

        try:
            data = _load_yaml(p)
        except Exception:
            continue

        # Keys filter: require all specified keys
        if keys and not all(k in data for k in keys):
            continue

        # Field-specific search
        if field:
            if term is None:
                continue
            if not _matches_field_search(data, field, term, use_regex):
                continue
        # General term filter
        elif term:
            namepart = p.stem.lower()
            target_str = rel_str.lower()

            # Also include instruction name and assembly in search
            inst_name = data.get("name", "")
            assembly = data.get("assembly", "")
            long_name = data.get("long_name", "")
            search_text = f"{namepart} {target_str} {inst_name} {assembly} {long_name}".lower()

            matched = False

            if regex_pattern:
                matched = bool(regex_pattern.search(search_text))
            elif fuzzy:
                threshold = float(fuzzy) if isinstance(fuzzy, (int, float)) else 0.6
                matched = (
                    _fuzzy_match(term, inst_name, threshold)
                    or _fuzzy_match(term, assembly, threshold)
                    or _fuzzy_match(term, namepart, threshold)
                )
            else:
                matched = term.lower() in search_text

            if not matched:
                continue

        defined_by = _extract_defined_by(data)
        ext_from_path = _extension_in_path(
            rel.relative_to(GEN_DIR).parts if rel.is_relative_to(GEN_DIR) else rel.parts
        )

        # Extension filter
        if ext_set:
            present = set(defined_by)
            if ext_from_path:
                present.add(ext_from_path)
            if present.isdisjoint(ext_set):
                continue

        # XLEN filter
        if xlen_set:
            inst_xlens = _extract_xlen(data)
            if inst_xlens.isdisjoint(xlen_set):
                continue

        info = {
            "path": rel_str,
            "kind": data.get("kind"),
            "name": data.get("name"),
            "long_name": data.get("long_name"),
            "assembly": data.get("assembly"),
            "encoding": (
                {"match": data.get("encoding", {}).get("match")}
                if isinstance(data.get("encoding"), dict)
                else None
            ),
            "definedBy": defined_by,
            "extensionInPath": ext_from_path,
            "xlen": list(_extract_xlen(data)),
        }

        # Add fuzzy score if fuzzy matching was used
        if fuzzy and term:
            score = max(
                _fuzzy_score(term, data.get("name", "")),
                _fuzzy_score(term, data.get("assembly", "")),
                _fuzzy_score(term, p.stem),
            )
            info["fuzzy_score"] = round(score, 3)

        results.append(info)
        count += 1
        if count >= limit:
            break

    # Sort by fuzzy score if applicable
    if fuzzy and term:
        results.sort(key=lambda x: x.get("fuzzy_score", 0), reverse=True)

    return {
        "count": count,
        "results": results,
        "search_mode": {
            "regex": use_regex,
            "fuzzy": bool(fuzzy),
            "field_specific": bool(field),
            "xlen_filter": list(xlen_set) if xlen_set else None,
        },
    }


# ============================================================================
# CSR Tools
# ============================================================================


async def search_csrs(args: dict[str, Any]):
    """
    Search CSR YAMLs with flexible filtering.

    Args:
        term: substring to match in filename/path (optional)
        keys: list of required top-level YAML keys (optional)
        extensions: list of extension names to filter by (optional)
        xlen: filter by XLEN (32, 64, or list [32, 64]) (optional)
        use_regex: treat term as regex pattern (default False)
        fuzzy: enable fuzzy matching with threshold (0-1, default disabled)
        field: specific field to search in (e.g., "priv_mode", "address")
        limit: max results (default 50)
    """
    term = args.get("term")
    keys = args.get("keys") or []
    extensions = args.get("extensions") or []
    xlen_filter = args.get("xlen")
    use_regex = args.get("use_regex", False)
    fuzzy = args.get("fuzzy")
    field = args.get("field")
    limit = int(args.get("limit") or 50)

    if term is not None and not isinstance(term, str):
        raise ValueError("'term' must be a string if provided")
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise ValueError("'keys' must be a list of strings")
    if not isinstance(extensions, list) or not all(isinstance(e, str) for e in extensions):
        raise ValueError("'extensions' must be a list of strings")

    # Parse XLEN filter
    xlen_set: set[int] = set()
    if xlen_filter is not None:
        if isinstance(xlen_filter, int):
            xlen_set = {xlen_filter}
        elif isinstance(xlen_filter, list):
            xlen_set = {
                int(x)
                for x in xlen_filter
                if isinstance(x, int) or (isinstance(x, str) and x.isdigit())
            }
        else:
            with contextlib.suppress(ValueError, TypeError):
                xlen_set = {int(xlen_filter)}

    ext_set = set(extensions)
    results: list[dict[str, Any]] = []
    count = 0

    # Compile regex if needed
    regex_pattern = None
    if use_regex and term:
        try:
            regex_pattern = re.compile(term, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

    for p in _iter_csr_yaml_paths():
        rel = str(p.relative_to(REPO_ROOT))

        try:
            data = _load_yaml(p)
        except Exception:
            continue

        # Keys filter
        if keys and not all(k in data for k in keys):
            continue

        # Field-specific search
        if field:
            if term is None:
                continue
            if not _matches_field_search(data, field, term, use_regex):
                continue
        # General term filter
        elif term:
            namepart = p.stem.lower()
            csr_name = data.get("name", "")
            long_name = data.get("long_name", "")
            search_text = f"{namepart} {rel.lower()} {csr_name} {long_name}".lower()

            matched = False

            if regex_pattern:
                matched = bool(regex_pattern.search(search_text))
            elif fuzzy:
                threshold = float(fuzzy) if isinstance(fuzzy, (int, float)) else 0.6
                matched = (
                    _fuzzy_match(term, csr_name, threshold)
                    or _fuzzy_match(term, long_name, threshold)
                    or _fuzzy_match(term, namepart, threshold)
                )
            else:
                matched = term.lower() in search_text

            if not matched:
                continue

        csr_exts = _csr_extensions(data)

        # Extension filter
        if ext_set and csr_exts.isdisjoint(ext_set):
            continue

        # XLEN filter
        if xlen_set:
            csr_xlens = _extract_xlen(data)
            if csr_xlens.isdisjoint(xlen_set):
                continue

        info = {
            "path": rel,
            "kind": data.get("kind"),
            "name": data.get("name"),
            "long_name": data.get("long_name"),
            "address": data.get("address"),
            "priv_mode": data.get("priv_mode"),
            "definedBy": list(csr_exts),
            "xlen": list(_extract_xlen(data)),
        }

        # Add fuzzy score if fuzzy matching was used
        if fuzzy and term:
            score = max(
                _fuzzy_score(term, data.get("name", "")),
                _fuzzy_score(term, data.get("long_name", "")),
                _fuzzy_score(term, p.stem),
            )
            info["fuzzy_score"] = round(score, 3)

        results.append(info)
        count += 1
        if count >= limit:
            break

    # Sort by fuzzy score if applicable
    if fuzzy and term:
        results.sort(key=lambda x: x.get("fuzzy_score", 0), reverse=True)

    return {
        "count": count,
        "results": results,
        "search_mode": {
            "regex": use_regex,
            "fuzzy": bool(fuzzy),
            "field_specific": bool(field),
            "xlen_filter": list(xlen_set) if xlen_set else None,
        },
    }


# ============================================================================
# Multi-Domain Search Tool
# ============================================================================


async def search_all(args: dict[str, Any]):
    """
    Search across multiple domains (instructions, CSRs, extensions) simultaneously.

    Args:
        term: search term (required)
        domains: list of domains to search ["instructions", "csrs", "extensions"]
                 (default: all domains)
        use_regex: treat term as regex pattern (default False)
        fuzzy: enable fuzzy matching with threshold (0-1, default disabled)
        extensions: filter by extension names (optional)
        xlen: filter by XLEN (32, 64) (optional)
        limit_per_domain: max results per domain (default 20)

    Returns:
        Combined results from all requested domains with match scores
    """
    term = args.get("term")
    if not term or not isinstance(term, str):
        raise ValueError("'term' is required and must be a string")

    domains = args.get("domains") or ["instructions", "csrs", "extensions"]
    use_regex = args.get("use_regex", False)
    fuzzy = args.get("fuzzy")
    extensions_filter = args.get("extensions") or []
    xlen_filter = args.get("xlen")
    limit_per_domain = int(args.get("limit_per_domain") or 20)

    if not isinstance(domains, list):
        raise ValueError("'domains' must be a list")

    valid_domains = {"instructions", "csrs", "extensions"}
    for d in domains:
        if d not in valid_domains:
            raise ValueError(f"Invalid domain '{d}'. Must be one of: {valid_domains}")

    results = {}

    # Search instructions
    if "instructions" in domains:
        inst_args = {
            "term": term,
            "use_regex": use_regex,
            "fuzzy": fuzzy,
            "extensions": extensions_filter,
            "xlen": xlen_filter,
            "limit": limit_per_domain,
        }
        inst_results = await search_instructions(inst_args)
        results["instructions"] = {
            "count": inst_results["count"],
            "results": inst_results["results"],
        }

    # Search CSRs
    if "csrs" in domains:
        csr_args = {
            "term": term,
            "use_regex": use_regex,
            "fuzzy": fuzzy,
            "extensions": extensions_filter,
            "xlen": xlen_filter,
            "limit": limit_per_domain,
        }
        csr_results = await search_csrs(csr_args)
        results["csrs"] = {
            "count": csr_results["count"],
            "results": csr_results["results"],
        }

    # Search extensions
    if "extensions" in domains:
        # For extensions, do a simpler search
        ext_results = {"count": 0, "results": []}
        regex_pattern = None
        if use_regex:
            with contextlib.suppress(re.error):
                regex_pattern = re.compile(term, re.IGNORECASE)

        for p in _iter_extension_yaml_paths():
            try:
                data = _load_yaml(p)
                if data.get("kind") != "extension":
                    continue

                name = data.get("name", "")
                long_name = data.get("long_name", "")
                search_text = f"{name} {long_name}".lower()

                matched = False
                if regex_pattern:
                    matched = bool(regex_pattern.search(search_text))
                elif fuzzy:
                    threshold = float(fuzzy) if isinstance(fuzzy, (int, float)) else 0.6
                    matched = _fuzzy_match(term, name, threshold) or _fuzzy_match(
                        term, long_name, threshold
                    )
                else:
                    matched = term.lower() in search_text

                if matched:
                    info = {
                        "path": str(p.relative_to(REPO_ROOT)),
                        "name": name,
                        "long_name": long_name,
                    }
                    if fuzzy:
                        score = max(_fuzzy_score(term, name), _fuzzy_score(term, long_name))
                        info["fuzzy_score"] = round(score, 3)

                    ext_results["results"].append(info)
                    ext_results["count"] += 1
                    if ext_results["count"] >= limit_per_domain:
                        break
            except Exception:
                continue

        # Sort by fuzzy score if applicable
        if fuzzy:
            ext_results["results"].sort(key=lambda x: x.get("fuzzy_score", 0), reverse=True)

        results["extensions"] = ext_results

    # Calculate total matches
    total_count = sum(r.get("count", 0) for r in results.values())

    return {
        "total_count": total_count,
        "domains_searched": domains,
        "search_mode": {
            "regex": use_regex,
            "fuzzy": bool(fuzzy),
            "xlen_filter": xlen_filter,
        },
        "results": results,
    }


# ============================================================================
# Extension Tools (Consolidated)
# ============================================================================


async def search_extensions(args: dict[str, Any]):
    """
    Flexible extension search and retrieval.

    Args:
        name: specific extension name (optional, omit to list all)
        include_instructions: include instruction summary (default False)
        include_csrs: include CSR summary (default False)
        limit: max instructions/CSRs per section (default 100)

    Returns:
        If name is None: list of all extensions
        If name provided: detailed extension info with optional instruction/CSR data
    """
    name = args.get("name")
    include_instructions = args.get("include_instructions", False)
    include_csrs = args.get("include_csrs", False)
    limit = int(args.get("limit") or 100)

    # Collect all extensions
    items: list[dict[str, Any]] = []
    for p in _iter_extension_yaml_paths():
        try:
            data = _load_yaml(p)
        except Exception:
            continue
        if data.get("kind") == "extension" and isinstance(data.get("name"), str):
            items.append(
                {
                    "path": str(p.relative_to(REPO_ROOT)),
                    "name": data.get("name"),
                    "long_name": data.get("long_name"),
                    "data": data,  # Keep full data for detail view
                }
            )

    # De-dup by name, favor shortest path
    by_name: dict[str, dict[str, Any]] = {}
    for it in items:
        n = it["name"]
        if n not in by_name or len(it["path"]) < len(by_name[n]["path"]):
            by_name[n] = it

    # List all extensions if no specific name
    if not name:
        extensions = [
            {"path": v["path"], "name": v["name"], "long_name": v["long_name"]}
            for v in sorted(by_name.values(), key=lambda x: x["name"])
        ]
        return {"count": len(extensions), "extensions": extensions}

    # Get specific extension
    if name not in by_name:
        return {"found": False, "name": name}

    ext_info = by_name[name]
    result = {
        "found": True,
        "path": ext_info["path"],
        "extension": ext_info["data"],
    }

    # Optionally include instructions
    if include_instructions:
        insts: list[dict[str, Any]] = []
        for p in _iter_instruction_yaml_paths():
            try:
                data = _load_yaml(p)
            except Exception:
                continue
            defined_by = set(_extract_defined_by(data))
            rel_parts = p.relative_to(GEN_DIR).parts if str(p).startswith(str(GEN_DIR)) else p.parts
            ext_from_path = _extension_in_path(list(rel_parts))
            if name in defined_by or (ext_from_path == name):
                insts.append(
                    {
                        "path": str(p.relative_to(REPO_ROOT)),
                        "name": data.get("name"),
                        "assembly": data.get("assembly"),
                        "encoding": (
                            data.get("encoding", {}).get("match")
                            if isinstance(data.get("encoding"), dict)
                            else None
                        ),
                    }
                )
                if len(insts) >= limit:
                    break
        result["instructions"] = {"count": len(insts), "items": insts}

    # Optionally include CSRs
    if include_csrs:
        csrs: list[dict[str, Any]] = []
        for p in _iter_csr_yaml_paths():
            try:
                data = _load_yaml(p)
            except Exception:
                continue
            csr_exts = _csr_extensions(data)
            if name in csr_exts:
                csrs.append(
                    {
                        "path": str(p.relative_to(REPO_ROOT)),
                        "name": data.get("name"),
                        "address": data.get("address"),
                        "priv_mode": data.get("priv_mode"),
                    }
                )
                if len(csrs) >= limit:
                    break
        result["csrs"] = {"count": len(csrs), "items": csrs}

    return result


# ============================================================================
# Function/IDL Tools
# ============================================================================


def _find_funcs_adoc() -> tuple[Path | None, Path | None]:
    """Locate function documentation files."""
    funcs_doc = None
    all_funcs = None
    cfg_root = GEN_DIR / "cfg_html_doc"
    if not cfg_root.exists():
        return None, None
    for root, _dirs, _files in os.walk(cfg_root):
        root_p = Path(root)
        # prefer antora/modules/funcs/pages/funcs.adoc
        if root_p.name == "pages" and "funcs" in root_p.parts and "modules" in root_p.parts:
            cand = root_p / "funcs.adoc"
            if cand.exists():
                funcs_doc = cand
        if root_p.name == "funcs" and root_p.parent.name == "adoc":
            cand_all = root_p / "all_funcs.adoc"
            if cand_all.exists():
                all_funcs = cand_all
    return funcs_doc, all_funcs


def _parse_all_funcs_names(all_funcs_path: Path) -> list[str]:
    """Extract function names from all_funcs.adoc."""
    names: list[str] = []
    try:
        with open(all_funcs_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("* ") and "`" in line:
                    # format: * `name`
                    back = re.findall(r"`([^`]+)\`?", line)
                    if back:
                        names.append(back[0])
    except Exception:
        pass
    return names


def _parse_funcs_sections(funcs_path: Path) -> dict[str, str]:
    """Parse function documentation sections."""
    sections: dict[str, str] = {}
    try:
        with open(funcs_path, encoding="utf-8") as fh:
            content = fh.read()
        # Split on level 2 headings "== name" (start of line)
        parts = re.split(r"^==\s+", content, flags=re.M)
        # parts[0] is preamble; subsequent parts are "Name\n<body>"
        for part in parts[1:]:
            lines = part.splitlines()
            if not lines:
                continue
            header = lines[0].strip()
            name = header.split()[0]
            body = "\n".join(lines[1:]).strip()
            sections[name] = body
    except Exception:
        pass
    return sections


async def search_functions(args: dict[str, Any]):
    """
    Search function documentation.

    Args:
        term: search term (optional, omit or empty string to list all)
        limit: max results (default 100)

    Returns matching functions with snippets
    """
    term = args.get("term", "")
    limit = int(args.get("limit") or 100)

    funcs_doc, all_funcs = _find_funcs_adoc()
    sections = _parse_funcs_sections(funcs_doc) if funcs_doc else {}

    # If no term, return all function names
    if not term:
        if all_funcs:
            names = _parse_all_funcs_names(all_funcs)
        else:
            names = sorted(sections.keys())
        return {"count": len(names[:limit]), "functions": names[:limit]}

    # Search by term
    out: list[dict[str, str | None]] = []
    for k, v in sections.items():
        if term.lower() in k.lower() or (v and term.lower() in v.lower()):
            out.append({"name": k, "snippet": v[:300] if v else None})
            if len(out) >= limit:
                break

    return {"count": len(out), "results": out}


async def read_function_doc(args: dict[str, Any]):
    """Read complete documentation for a specific function."""
    name = args.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("'name' is required")

    funcs_doc, _ = _find_funcs_adoc()
    sections = _parse_funcs_sections(funcs_doc) if funcs_doc else {}
    body = sections.get(name)

    # Fuzzy match if exact name not found
    if body is None:
        for k, v in sections.items():
            if k.startswith(name):
                body = v
                name = k
                break

    return {
        "name": name,
        "found": body is not None,
        "doc": body,
        "source": str(funcs_doc) if funcs_doc else None,
    }


async def find_function_usages(args: dict[str, Any]):
    """Find instruction YAMLs that use a specific function."""
    name = args.get("name")
    limit = int(args.get("limit") or 50)

    if not isinstance(name, str) or not name:
        raise ValueError("'name' is required")

    hits: list[dict[str, str]] = []
    count = 0

    # Scan instruction YAMLs for function references
    for p in _iter_instruction_yaml_paths():
        try:
            data = _load_yaml(p)
        except Exception:
            continue

        for key in ("operation()", "sail()"):
            val = data.get(key)
            if isinstance(val, str) and (name in val):
                # Extract snippet around first occurrence
                idx = val.find(name)
                snippet = val[max(0, idx - 60) : idx + 120]
                hits.append(
                    {
                        "path": str(p.relative_to(REPO_ROOT)),
                        "key": key,
                        "snippet": snippet,
                    }
                )
                count += 1
                if count >= limit:
                    return {"count": count, "results": hits}

    return {"count": count, "results": hits}


# ============================================================================
# MCP Server Setup
# ============================================================================


async def main() -> None:
    server = Server("riscv-udb-mcp")

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return [
            # ===== Low-Level YAML Access =====
            Tool(
                name="list_gen_yaml",
                description="List all YAML files under gen/ as repo-relative paths",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="read_gen_yaml",
                description="Read and parse a YAML file under gen/; returns JSON",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "repo-relative path under gen/",
                        }
                    },
                    "required": ["path"],
                },
            ),
            # ===== Instruction Tools =====
            Tool(
                name="search_instructions",
                description="Search instruction YAMLs with advanced filtering (regex, fuzzy matching, field-specific, XLEN)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "term": {
                            "type": "string",
                            "description": "substring/regex to match in filename/path/content",
                        },
                        "keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "top-level YAML keys that must exist",
                        },
                        "extensions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "extension names to filter by (definedBy or path)",
                        },
                        "xlen": {
                            "description": "filter by XLEN: 32, 64, or [32, 64]",
                            "oneOf": [
                                {"type": "integer", "enum": [32, 64]},
                                {
                                    "type": "array",
                                    "items": {"type": "integer", "enum": [32, 64]},
                                },
                            ],
                        },
                        "use_regex": {
                            "type": "boolean",
                            "default": False,
                            "description": "treat term as regex pattern",
                        },
                        "fuzzy": {
                            "description": "enable fuzzy matching (true or threshold 0-1)",
                            "oneOf": [
                                {"type": "boolean"},
                                {"type": "number", "minimum": 0, "maximum": 1},
                            ],
                        },
                        "field": {
                            "type": "string",
                            "description": "specific field to search (e.g., 'assembly', 'encoding.match')",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 500,
                            "default": 50,
                        },
                    },
                },
            ),
            # ===== CSR Tools =====
            Tool(
                name="search_csrs",
                description="Search CSR YAMLs with advanced filtering (regex, fuzzy matching, field-specific, XLEN)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "term": {
                            "type": "string",
                            "description": "substring/regex to match in filename/path/content",
                        },
                        "keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "required YAML keys",
                        },
                        "extensions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "extension names",
                        },
                        "xlen": {
                            "description": "filter by XLEN: 32, 64, or [32, 64]",
                            "oneOf": [
                                {"type": "integer", "enum": [32, 64]},
                                {
                                    "type": "array",
                                    "items": {"type": "integer", "enum": [32, 64]},
                                },
                            ],
                        },
                        "use_regex": {
                            "type": "boolean",
                            "default": False,
                            "description": "treat term as regex pattern",
                        },
                        "fuzzy": {
                            "description": "enable fuzzy matching (true or threshold 0-1)",
                            "oneOf": [
                                {"type": "boolean"},
                                {"type": "number", "minimum": 0, "maximum": 1},
                            ],
                        },
                        "field": {
                            "type": "string",
                            "description": "specific field to search (e.g., 'priv_mode', 'address')",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 500,
                            "default": 50,
                        },
                    },
                },
            ),
            # ===== Extension Tools (Consolidated) =====
            Tool(
                name="search_extensions",
                description=(
                    "Flexible extension query: list all extensions (omit name) or get detailed info for "
                    "a specific extension (provide name). Optionally include instructions/CSRs."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "extension name (omit to list all)",
                        },
                        "include_instructions": {
                            "type": "boolean",
                            "default": False,
                            "description": "include instruction summary",
                        },
                        "include_csrs": {
                            "type": "boolean",
                            "default": False,
                            "description": "include CSR summary",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5000,
                            "default": 100,
                            "description": "max items per section",
                        },
                    },
                },
            ),
            # ===== Multi-Domain Search =====
            Tool(
                name="search_all",
                description=(
                    "Search across multiple domains (instructions, CSRs, extensions) simultaneously. "
                    "Supports regex, fuzzy matching, and XLEN filtering."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "term": {
                            "type": "string",
                            "description": "search term (required)",
                        },
                        "domains": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["instructions", "csrs", "extensions"],
                            },
                            "default": ["instructions", "csrs", "extensions"],
                            "description": "domains to search",
                        },
                        "use_regex": {
                            "type": "boolean",
                            "default": False,
                            "description": "treat term as regex",
                        },
                        "fuzzy": {
                            "description": "enable fuzzy matching (true or threshold 0-1)",
                            "oneOf": [
                                {"type": "boolean"},
                                {"type": "number", "minimum": 0, "maximum": 1},
                            ],
                        },
                        "extensions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "filter by extension names",
                        },
                        "xlen": {
                            "description": "filter by XLEN: 32, 64, or [32, 64]",
                            "oneOf": [
                                {"type": "integer", "enum": [32, 64]},
                                {
                                    "type": "array",
                                    "items": {"type": "integer", "enum": [32, 64]},
                                },
                            ],
                        },
                        "limit_per_domain": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 20,
                        },
                    },
                    "required": ["term"],
                },
            ),
            # ===== Function/IDL Tools =====
            Tool(
                name="search_functions",
                description="Search IDL functions by term (omit term to list all functions)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "term": {
                            "type": "string",
                            "description": "search term (omit for full list)",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 500,
                            "default": 100,
                        },
                    },
                },
            ),
            Tool(
                name="read_function_doc",
                description="Read complete documentation for a specific function by name",
                inputSchema={
                    "type": "object",
                    "properties": {"name": {"type": "string", "description": "function name"}},
                    "required": ["name"],
                },
            ),
            Tool(
                name="find_function_usages",
                description="Find instruction YAMLs whose operation()/sail() code reference the function",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "function name"},
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 500,
                            "default": 50,
                        },
                    },
                    "required": ["name"],
                },
            ),
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any] | None):
        args = arguments or {}

        # Route to appropriate handler
        handlers = {
            "list_gen_yaml": list_gen_yaml,
            "read_gen_yaml": read_gen_yaml,
            "search_instructions": search_instructions,
            "search_csrs": search_csrs,
            "search_extensions": search_extensions,
            "search_all": search_all,
            "search_functions": search_functions,
            "read_function_doc": read_function_doc,
            "find_function_usages": find_function_usages,
        }

        handler = handlers.get(name)
        if not handler:
            raise ValueError(f"Unknown tool: {name}")

        # Call handler (pass args only if function expects them)
        if name == "list_gen_yaml":
            result = await handler()
        else:
            result = await handler(args)

        # Return properly formatted MCP response
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Run over stdio transport (for MCP clients)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
