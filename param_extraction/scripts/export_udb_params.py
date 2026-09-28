#!/usr/bin/env python3
"""
Phase 1, Step 1: Export all UDB parameters to structured JSON.

Reads every spec/std/isa/param/*.yaml file (excluding MOCK_* test fixtures),
extracts metadata, derives value types from JSON Schema structures,
cross-references with CSR definitions to find WARL connections,
and heuristically classifies each parameter.

Output: data/ground_truth.json
"""

import yaml
import json
import re
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PARAM_DIR = REPO_ROOT / "spec" / "std" / "isa" / "param"
CSR_DIR = REPO_ROOT / "spec" / "std" / "isa" / "csr"
SPEC_DIR = REPO_ROOT / "ext" / "riscv-isa-manual" / "src"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Schema analysis: derive the "value type" from JSON Schema structures
# ---------------------------------------------------------------------------

def derive_value_type(schema):
    """
    Analyze a JSON Schema object and return a structured description
    of the parameter's value type.

    Returns a dict with:
      - type: one of "binary", "enum", "range", "set", "bitmask",
              "value", "conditional", "unknown"
      - details: type-specific metadata
    """
    if schema is None:
        return {"type": "unknown", "details": {}}

    # Conditional schema (oneOf with "when" clauses)
    if "oneOf" in schema and isinstance(schema["oneOf"], list):
        branches = schema["oneOf"]
        if branches and isinstance(branches[0], dict) and "when" in branches[0]:
            branch_types = []
            for branch in branches:
                inner = branch.get("schema", {})
                branch_types.append({
                    "condition": _summarize_when(branch.get("when", {})),
                    "inner_type": derive_value_type(inner),
                })
            return {"type": "conditional", "details": {"branches": branch_types}}

    # rv32/rv64 split at top level
    if "rv32" in schema and "rv64" in schema and len(schema) == 2:
        return {
            "type": "conditional",
            "details": {
                "branches": [
                    {"condition": "rv32", "inner_type": derive_value_type(schema["rv32"])},
                    {"condition": "rv64", "inner_type": derive_value_type(schema["rv64"])},
                ]
            },
        }

    schema_type = schema.get("type")

    # Boolean
    if schema_type == "boolean":
        return {"type": "binary", "details": {"choices": [True, False]}}

    # Integer
    if schema_type == "integer":
        if "enum" in schema:
            vals = schema["enum"]
            if len(vals) == 2:
                return {"type": "binary", "details": {"choices": vals}}
            return {"type": "enum", "details": {"values": vals}}
        if "minimum" in schema or "maximum" in schema:
            return {
                "type": "range",
                "details": {
                    "minimum": schema.get("minimum"),
                    "maximum": schema.get("maximum"),
                },
            }
        return {"type": "value", "details": {"base": "integer"}}

    # String
    if schema_type == "string":
        if "enum" in schema:
            vals = schema["enum"]
            if len(vals) == 2:
                return {"type": "binary", "details": {"choices": vals}}
            return {"type": "enum", "details": {"values": vals}}
        return {"type": "value", "details": {"base": "string"}}

    # Array
    if schema_type == "array":
        items = schema.get("items", {})
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")

        # Fixed-length boolean array = bitmask
        if _is_boolean_array(schema):
            return {
                "type": "bitmask",
                "details": {"length": max_items or min_items},
            }

        # Array of enum items = set (subset selection)
        if isinstance(items, dict) and "enum" in items:
            return {
                "type": "set",
                "details": {
                    "universe": items["enum"],
                    "min_items": min_items,
                    "max_items": max_items,
                },
            }
        if isinstance(items, dict) and items.get("type") == "integer" and "enum" in items:
            return {
                "type": "set",
                "details": {
                    "universe": items["enum"],
                    "min_items": min_items,
                    "max_items": max_items,
                },
            }

        return {
            "type": "set",
            "details": {
                "element_type": items.get("type", "mixed"),
                "min_items": min_items,
                "max_items": max_items,
            },
        }

    # Top-level enum without explicit type
    if "enum" in schema:
        vals = schema["enum"]
        if len(vals) == 2:
            return {"type": "binary", "details": {"choices": vals}}
        return {"type": "enum", "details": {"values": vals}}

    # Fallback: schema has allOf, $ref, or other complex structures
    if "$ref" in schema:
        return {"type": "value", "details": {"ref": schema["$ref"]}}

    if "allOf" in schema:
        return {"type": "value", "details": {"complex": "allOf"}}

    return {"type": "unknown", "details": {"raw_keys": list(schema.keys())}}


def _is_boolean_array(schema):
    """Check if this array schema represents a fixed-length boolean array (bitmask)."""
    items = schema.get("items", {})
    additional = schema.get("additionalItems", {})

    if isinstance(items, dict) and items.get("type") == "boolean":
        return True

    # Tuple-style: items is a list (positional) + additionalItems is boolean
    if isinstance(items, list):
        all_bool_or_const = all(
            i.get("type") == "boolean" or "const" in i
            for i in items
            if isinstance(i, dict)
        )
        additional_bool = isinstance(additional, dict) and additional.get("type") == "boolean"
        if all_bool_or_const and (additional_bool or not additional):
            return True

    return False


def _summarize_when(when):
    """Produce a human-readable summary of a 'when' condition."""
    param = when.get("param", {})
    if param:
        return f"{param.get('name', '?')} == {param.get('equal', '?')}"
    return str(when)


# ---------------------------------------------------------------------------
# definedBy extraction
# ---------------------------------------------------------------------------

def flatten_defined_by(defined_by):
    """
    Convert the definedBy condition tree into a flat, readable structure.

    Returns a dict with:
      - extensions: list of extension names involved
      - params: list of parameter conditions involved
      - raw: the original structure for full fidelity
      - summary: human-readable string
    """
    if defined_by is None:
        return {"extensions": [], "params": [], "raw": None, "summary": "none"}

    extensions = []
    params = []
    _collect_conditions(defined_by, extensions, params)

    summary = _summarize_defined_by(defined_by)

    return {
        "extensions": sorted(set(extensions)),
        "params": params,
        "raw": defined_by,
        "summary": summary,
    }


def _collect_conditions(node, extensions, params):
    """Recursively collect extension names and param conditions."""
    if not isinstance(node, dict):
        return

    if "name" in node and isinstance(node["name"], str):
        ext_name = node["name"]
        if ext_name not in ("allOf", "anyOf", "noneOf"):
            extensions.append(ext_name)

    if "extension" in node:
        ext = node["extension"]
        if isinstance(ext, dict):
            _collect_conditions(ext, extensions, params)
        elif isinstance(ext, str):
            extensions.append(ext)

    if "param" in node:
        p = node["param"]
        if isinstance(p, dict):
            if "name" in p:
                params.append({
                    "name": p["name"],
                    "condition": {k: v for k, v in p.items() if k != "name" and k != "reason"},
                })
            if "allOf" in p:
                for item in p["allOf"]:
                    _collect_conditions({"param": item}, extensions, params)

    for key in ("allOf", "anyOf", "noneOf"):
        if key in node:
            for item in node[key]:
                _collect_conditions(item, extensions, params)


def _summarize_defined_by(node):
    """Produce a compact human-readable summary."""
    if not isinstance(node, dict):
        return str(node)

    if "extension" in node:
        ext = node["extension"]
        if isinstance(ext, dict):
            if "name" in ext:
                ver = ext.get("version", "")
                return f"ext:{ext['name']}" + (f"({ver})" if ver else "")
            if "allOf" in ext:
                parts = [_summarize_defined_by({"extension": e}) for e in ext["allOf"]]
                return " AND ".join(parts)
            if "anyOf" in ext:
                parts = [_summarize_defined_by({"extension": e}) for e in ext["anyOf"]]
                return "(" + " OR ".join(parts) + ")"
            if "noneOf" in ext:
                parts = [_summarize_defined_by({"extension": e}) for e in ext["noneOf"]]
                return "NONE(" + ", ".join(parts) + ")"

    if "allOf" in node:
        parts = [_summarize_defined_by(item) for item in node["allOf"]]
        return " AND ".join(parts)

    if "param" in node:
        p = node["param"]
        if isinstance(p, dict) and "name" in p:
            conds = [f"{k}={v}" for k, v in p.items() if k not in ("name", "reason")]
            return f"param:{p['name']}({', '.join(conds)})"

    return str(node)[:80]


# ---------------------------------------------------------------------------
# CSR cross-reference: find params mentioned in CSR IDL code
# ---------------------------------------------------------------------------

def build_csr_param_xref(csr_dir, param_names):
    """
    Scan all CSR YAML files for references to known parameter names
    in IDL code fields (sw_write, type(), reset_value(), legal?).

    Returns:
      - param_to_csrs: {param_name: [{csr, field, context}]}
      - csr_to_params: {csr_name: [param_name]}
    """
    param_to_csrs = defaultdict(list)
    csr_to_params = defaultdict(set)

    idl_field_keys = [
        "sw_write(csr_value)", "type()", "reset_value()",
        "legal?(csr_value)", "sw_read()",
    ]

    # Build a regex that matches any param name as a whole word
    # Sort by length descending so longer names match first
    sorted_names = sorted(param_names, key=len, reverse=True)
    if not sorted_names:
        return dict(param_to_csrs), dict(csr_to_params)

    param_pattern = re.compile(r'\b(' + '|'.join(re.escape(n) for n in sorted_names) + r')\b')

    csr_files = list(csr_dir.rglob("*.yaml"))
    for csr_path in csr_files:
        try:
            data = load_yaml(csr_path)
        except Exception:
            continue

        if not isinstance(data, dict) or data.get("kind") != "csr":
            continue

        csr_name = data.get("name", csr_path.stem)
        fields = data.get("fields", {})

        # Check CSR-level IDL
        for key in idl_field_keys:
            idl_code = data.get(key)
            if isinstance(idl_code, str):
                for match in param_pattern.finditer(idl_code):
                    pname = match.group(1)
                    param_to_csrs[pname].append({
                        "csr": csr_name,
                        "field": "(csr-level)",
                        "idl_key": key,
                    })
                    csr_to_params[csr_name].add(pname)

        # Check field-level IDL
        if isinstance(fields, dict):
            for field_name, field_data in fields.items():
                if not isinstance(field_data, dict):
                    continue
                for key in idl_field_keys:
                    idl_code = field_data.get(key)
                    if isinstance(idl_code, str):
                        for match in param_pattern.finditer(idl_code):
                            pname = match.group(1)
                            param_to_csrs[pname].append({
                                "csr": csr_name,
                                "field": field_name,
                                "idl_key": key,
                            })
                            csr_to_params[csr_name].add(pname)

                # Also check type() which returns CsrFieldType
                type_func = field_data.get("type()")
                if isinstance(type_func, str):
                    for match in param_pattern.finditer(type_func):
                        pname = match.group(1)
                        param_to_csrs[pname].append({
                            "csr": csr_name,
                            "field": field_name,
                            "idl_key": "type()",
                        })
                        csr_to_params[csr_name].add(pname)

    # Deduplicate
    for pname in param_to_csrs:
        seen = set()
        deduped = []
        for ref in param_to_csrs[pname]:
            key = (ref["csr"], ref["field"], ref["idl_key"])
            if key not in seen:
                seen.add(key)
                deduped.append(ref)
        param_to_csrs[pname] = deduped

    return dict(param_to_csrs), {k: sorted(v) for k, v in csr_to_params.items()}


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------

# Patterns in parameter names that indicate CSR-related parameters
CSR_NAME_PATTERNS = [
    (r'^MTVEC_', 'mtvec'),
    (r'^STVEC_', 'stvec'),
    (r'^VSTVEC_', 'vstvec'),
    (r'^MSTATUS_', 'mstatus'),
    (r'^MISA_', 'misa'),
    (r'^MUTABLE_MISA_', 'misa'),
    (r'^SATP_', 'satp'),
    (r'^DCSR_', 'dcsr'),
    (r'^JVT_', 'jvt'),
    (r'^MSTATEEN_', 'mstateen'),
    (r'^HSTATEEN_', 'hstateen'),
    (r'^SSTATEEN_', 'sstateen'),
    (r'^HPM_', 'hpmcounter/hpmevent'),
    (r'^COUNTINHIBIT_', 'mcountinhibit'),
    (r'^MCOUNTENABLE_', 'mcounteren'),
    (r'^SCOUNTENABLE_', 'scounteren'),
    (r'^HCOUNTENABLE_', 'hcounteren'),
]

# Parameters that are clearly about trap/reporting behavior (not CSR fields)
TRAP_REPORT_PATTERNS = [
    r'^TRAP_ON_',
    r'^REPORT_',
    r'^PRECISE_',
]

# Parameters known to be direct architectural choices
DIRECT_ARCH_NAMES = {
    'MXLEN', 'SXLEN', 'UXLEN', 'VSXLEN', 'VUXLEN',
    'PHYS_ADDR_WIDTH', 'NUM_PMP_ENTRIES', 'PMP_GRANULARITY',
    'VLEN', 'ELEN', 'CACHE_BLOCK_SIZE', 'PMA_GRANULARITY',
    'ASID_WIDTH', 'VMID_WIDTH', 'PMLEN',
    'ARCH_ID_VALUE', 'IMP_ID_VALUE', 'VENDOR_ID_BANK', 'VENDOR_ID_OFFSET',
    'CONFIG_PTR_ADDRESS', 'NUM_EXTERNAL_GUEST_INTERRUPTS',
    'MARCHID_IMPLEMENTED', 'MIMPID_IMPLEMENTED',
}


def classify_parameter(param_data, csr_refs, value_type_info):
    """
    Heuristically assign a classification to a parameter.

    Classification hierarchy:
      NORM_DIRECT     - Normative, directly configurable (not CSR-controlled)
      NORM_CSR_WARL   - Normative, parameter is legal values of a WARL CSR field
      NORM_CSR_RW     - Normative, whether a CSR/field is RO vs RW
      SW_RULE         - Software-deterministic (impl-defined but determinate with correct SW)
      NON_ISA         - Platform-level, not ISA architectural
      NON_NORM        - Non-normative / informational
      UNKNOWN         - Cannot confidently classify
    """
    name = param_data.get("name", "")
    desc = param_data.get("description", "").lower()
    long_name = param_data.get("long_name", "").lower()

    has_csr_refs = len(csr_refs) > 0
    has_sw_write_ref = any(r["idl_key"] == "sw_write(csr_value)" for r in csr_refs)
    has_type_ref = any(r["idl_key"] == "type()" for r in csr_refs)

    classification = "UNKNOWN"
    confidence = "low"
    reasoning = ""

    # --- Check for HW_ prefix first (hardware update behavior, SW-deterministic) ---
    # Must come before CSR checks because HW_ params are referenced in CSR type()
    # but are conceptually SW rules, not CSR-controlled parameters
    if name.startswith("HW_"):
        classification = "SW_RULE"
        confidence = "medium"
        reasoning = "Hardware update behavior (HW_ prefix) — software-deterministic with correct fencing"
        return classification, confidence, reasoning

    # --- Check for existence/availability parameters ---
    # Params with _IMPLEMENTED or _AVAILABLE suffix control whether a CSR/feature
    # exists at all. They may be referenced in CSR IDL (because the CSR behavior
    # depends on whether it exists), but the parameter itself is a direct
    # architectural choice, not a WARL/RW control.
    if name.endswith("_IMPLEMENTED") or name.endswith("_AVAILABLE"):
        classification = "NORM_DIRECT"
        confidence = "high"
        reasoning = f"Feature/CSR existence parameter ('{name.split('_')[-1]}' suffix)"
        return classification, confidence, reasoning

    # --- Check for direct architectural parameters ---
    if name in DIRECT_ARCH_NAMES:
        classification = "NORM_DIRECT"
        confidence = "high"
        reasoning = f"Well-known architectural parameter '{name}'"
        return classification, confidence, reasoning

    # --- Check for trap/report behavior (normative, not CSR-controlled) ---
    for pattern in TRAP_REPORT_PATTERNS:
        if re.match(pattern, name):
            classification = "NORM_DIRECT"
            confidence = "high"
            reasoning = f"Trap/report behavior parameter (matches {pattern})"
            return classification, confidence, reasoning

    # --- Check for CSR WARL field parameters ---
    # If the parameter is referenced in sw_write() of a CSR field,
    # it controls the legal write values — classic WARL parameter
    if has_sw_write_ref:
        csr_fields = [(r["csr"], r["field"]) for r in csr_refs if r["idl_key"] == "sw_write(csr_value)"]
        classification = "NORM_CSR_WARL"
        confidence = "high"
        reasoning = f"Referenced in sw_write() of {csr_fields[0][0]}.{csr_fields[0][1]}"
        return classification, confidence, reasoning

    # If referenced in type() of a CSR field, it controls read-write behavior
    if has_type_ref:
        csr_fields = [(r["csr"], r["field"]) for r in csr_refs if r["idl_key"] == "type()"]
        classification = "NORM_CSR_RW"
        confidence = "high"
        reasoning = f"Controls type (RO/RW) of {csr_fields[0][0]}.{csr_fields[0][1]}"
        return classification, confidence, reasoning

    # --- Check name patterns that suggest CSR association ---
    for pattern, csr in CSR_NAME_PATTERNS:
        if re.match(pattern, name):
            # _TYPE suffix with rw/read-only values = controls field RO/RW behavior
            if name.endswith("_TYPE"):
                classification = "NORM_CSR_RW"
                confidence = "medium" if has_csr_refs else "low"
                reasoning = f"CSR field type control parameter for '{csr}' (determines RO/RW behavior)"
                return classification, confidence, reasoning

            if has_csr_refs:
                classification = "NORM_CSR_WARL"
                confidence = "medium"
                reasoning = f"Name pattern suggests CSR '{csr}' association, confirmed by IDL references"
            else:
                classification = "NORM_CSR_WARL"
                confidence = "low"
                reasoning = f"Name pattern suggests CSR '{csr}' association, but no IDL cross-reference found"
            return classification, confidence, reasoning

    # --- Check for SW-rule parameters ---
    sw_rule_keywords = [
        "implementation-defined whether",
        "implementation may choose",
        "implementation defined",
        "imprecise",
        "unpredictable",
    ]
    for kw in sw_rule_keywords:
        if kw in desc:
            if "dirty" in desc or "fence" in desc or "cache" in desc:
                classification = "SW_RULE"
                confidence = "medium"
                reasoning = f"Description contains '{kw}' with dirty/fence/cache context"
                return classification, confidence, reasoning

    # --- Check for endianness parameters ---
    if "ENDIANNESS" in name:
        if has_csr_refs:
            classification = "NORM_CSR_WARL"
            confidence = "high"
            reasoning = "Endianness parameter controlled via mstatus/mstatush WARL bits"
        else:
            classification = "NORM_DIRECT"
            confidence = "medium"
            reasoning = "Endianness parameter"
        return classification, confidence, reasoning

    # --- Check for translation mode parameters ---
    if "TRANSLATION" in name or "MODE" in name:
        if has_csr_refs:
            classification = "NORM_CSR_WARL"
            confidence = "medium"
            reasoning = "Translation/mode parameter with CSR references"
        else:
            classification = "NORM_DIRECT"
            confidence = "medium"
            reasoning = "Translation/mode parameter"
        return classification, confidence, reasoning

    # --- Check for TINST/TVAL parameters ---
    if name.startswith("TINST_") or "TVAL" in name:
        classification = "NORM_DIRECT"
        confidence = "medium"
        reasoning = "Trap value reporting parameter"
        return classification, confidence, reasoning

    # --- Check for FOLLOW/FORCE/IGNORE parameters (behavioral choices) ---
    if name.startswith("FOLLOW_") or name.startswith("FORCE_") or name.startswith("IGNORE_"):
        classification = "NORM_DIRECT"
        confidence = "medium"
        reasoning = "Implementation behavioral choice parameter"
        return classification, confidence, reasoning

    # --- Check for LRSC parameters ---
    if "LRSC" in name:
        classification = "NORM_DIRECT"
        confidence = "medium"
        reasoning = "Load-reserved/store-conditional behavior parameter"
        return classification, confidence, reasoning

    # --- Check for MISALIGNED parameters ---
    if "MISALIGNED" in name:
        classification = "NORM_DIRECT"
        confidence = "medium"
        reasoning = "Misaligned access behavior parameter"
        return classification, confidence, reasoning

    # --- Check for HW_ prefix (hardware update behavior) ---
    if name.startswith("HW_"):
        classification = "SW_RULE"
        confidence = "medium"
        reasoning = "Hardware update behavior — may be software-deterministic"
        return classification, confidence, reasoning

    # --- Fallback: if it has CSR refs, lean toward CSR-related ---
    if has_csr_refs:
        # Distinguish: sw_write/type refs → CSR-controlled; sw_read/reset refs → incidental
        has_write_or_type = any(
            r["idl_key"] in ("sw_write(csr_value)", "type()", "legal?(csr_value)")
            for r in csr_refs
        )
        if has_write_or_type:
            classification = "NORM_CSR_WARL"
            confidence = "low"
            reasoning = "Has CSR write/type IDL references but no strong name/description signal"
        else:
            classification = "NORM_DIRECT"
            confidence = "low"
            reasoning = "Has CSR read/reset IDL references only (incidental, not controlling WARL behavior)"
        return classification, confidence, reasoning

    # --- Default ---
    classification = "NORM_DIRECT"
    confidence = "low"
    reasoning = "No strong signals; defaulting to direct normative parameter"
    return classification, confidence, reasoning


# ---------------------------------------------------------------------------
# Main export logic
# ---------------------------------------------------------------------------

def export_single_param(yaml_path, param_csr_refs):
    """Read one param YAML and produce a structured dict."""
    data = load_yaml(yaml_path)
    if not isinstance(data, dict):
        return None

    name = data.get("name", yaml_path.stem)
    schema = data.get("schema", {})
    defined_by = data.get("definedBy")
    requirements = data.get("requirements")
    description = data.get("description", "")
    long_name = data.get("long_name", "")

    value_type_info = derive_value_type(schema)
    defined_by_info = flatten_defined_by(defined_by)
    csr_refs = param_csr_refs.get(name, [])

    classification, confidence, reasoning = classify_parameter(
        data, csr_refs, value_type_info
    )

    has_requirements = requirements is not None
    req_summary = None
    if has_requirements:
        if isinstance(requirements, dict):
            req_summary = requirements.get("reason", requirements.get("idl()", "")[:200])
        elif isinstance(requirements, str):
            req_summary = requirements[:200]

    result = {
        "name": name,
        "long_name": long_name.strip() if isinstance(long_name, str) else str(long_name),
        "description": description.strip() if isinstance(description, str) else str(description),
        "defined_by": defined_by_info,
        "value_type": value_type_info,
        "has_requirements": has_requirements,
        "requirements_summary": req_summary,
        "csr_references": csr_refs,
        "classification": classification,
        "classification_confidence": confidence,
        "classification_reasoning": reasoning,
        "source_file": str(yaml_path.relative_to(REPO_ROOT)),
    }

    return result


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Collect all non-MOCK parameter names
    param_files = sorted(PARAM_DIR.glob("*.yaml"))
    real_params = [f for f in param_files if not f.stem.startswith("MOCK_")]
    print(f"Found {len(real_params)} real parameter files (excluded {len(param_files) - len(real_params)} MOCK files)")

    param_names = [f.stem for f in real_params]

    # Step 2: Build CSR cross-reference
    print("Building CSR cross-reference...")
    param_to_csrs, csr_to_params = build_csr_param_xref(CSR_DIR, param_names)
    params_with_csr_refs = sum(1 for v in param_to_csrs.values() if v)
    print(f"  {params_with_csr_refs} parameters referenced in CSR IDL code")

    # Step 3: Export each parameter
    print("Exporting parameters...")
    results = []
    for pf in real_params:
        entry = export_single_param(pf, param_to_csrs)
        if entry:
            results.append(entry)

    # Step 4: Compute statistics
    stats = compute_statistics(results)

    output = {
        "metadata": {
            "total_parameters": len(results),
            "source": str(PARAM_DIR.relative_to(REPO_ROOT)),
            "csr_source": str(CSR_DIR.relative_to(REPO_ROOT)),
        },
        "statistics": stats,
        "parameters": results,
    }

    out_path = OUTPUT_DIR / "ground_truth.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nWritten {len(results)} parameters to {out_path}")
    print_summary(stats)


def compute_statistics(results):
    """Compute summary statistics over the exported parameters."""
    class_counts = defaultdict(int)
    type_counts = defaultdict(int)
    confidence_counts = defaultdict(int)
    ext_counts = defaultdict(int)

    params_with_csr_refs = 0
    params_with_requirements = 0

    for r in results:
        class_counts[r["classification"]] += 1
        type_counts[r["value_type"]["type"]] += 1
        confidence_counts[r["classification_confidence"]] += 1

        if r["csr_references"]:
            params_with_csr_refs += 1
        if r["has_requirements"]:
            params_with_requirements += 1

        for ext in r["defined_by"]["extensions"]:
            ext_counts[ext] += 1

    return {
        "by_classification": dict(sorted(class_counts.items())),
        "by_value_type": dict(sorted(type_counts.items())),
        "by_confidence": dict(sorted(confidence_counts.items())),
        "params_with_csr_references": params_with_csr_refs,
        "params_with_requirements": params_with_requirements,
        "top_defining_extensions": dict(
            sorted(ext_counts.items(), key=lambda x: -x[1])[:15]
        ),
    }


def print_summary(stats):
    """Print a human-readable summary to stdout."""
    print("\n" + "=" * 60)
    print("PARAMETER EXPORT SUMMARY")
    print("=" * 60)

    print("\nBy Classification:")
    for cls, count in sorted(stats["by_classification"].items()):
        print(f"  {cls:20s}  {count:4d}")

    print("\nBy Value Type:")
    for vt, count in sorted(stats["by_value_type"].items()):
        print(f"  {vt:20s}  {count:4d}")

    print("\nBy Confidence:")
    for conf, count in sorted(stats["by_confidence"].items()):
        print(f"  {conf:20s}  {count:4d}")

    print(f"\nWith CSR references:    {stats['params_with_csr_references']}")
    print(f"With requirements IDL:  {stats['params_with_requirements']}")

    print("\nTop Defining Extensions:")
    for ext, count in list(stats["top_defining_extensions"].items())[:10]:
        print(f"  {ext:20s}  {count:4d}")


if __name__ == "__main__":
    main()
