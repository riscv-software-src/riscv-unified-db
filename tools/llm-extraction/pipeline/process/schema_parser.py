"""
Purpose:
    Core schema analysis logic for parsing JSON/YAML parameter interfaces.
    Migrated from shared utils to centralize schema introspection across stages.

Pipeline Stage:
    process

Inputs:
    - Raw dict/list structures loaded from UDB YAML/JSON schemas
    - defs_data (injected at init) for resolving JSON $ref chains

Outputs:
    - (None — provides SchemaParser class for schema parsing)

Core Responsibilities:
    - Resolve $ref pointers into concrete schema definitions
    - Extract and compress enum lists
    - Parse numeric constraint ranges (minimum, maximum)

Key Assumptions:
    - $ref targets under '#/$defs/' align with defs_data
    - UDB schema structures adhere to the expected format

Failure Modes:
    - Deep recursion on highly nested schemas
    - Missing '$defs' keys inside defs_data lead to empty resolution

Notes:
    - Recursive algorithms natively unpack anyOf/oneOf/allOf logic.
"""

from typing import Any

class SchemaParser:
    def __init__(self, defs_data: dict):
        self.defs_data = defs_data

    def resolve_ref(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref = obj["$ref"]
                resolved = {}
                if "#/$defs/" in ref:
                    key = ref.split("#/$defs/")[-1]
                    resolved = self.defs_data.get("$defs", {}).get(key, {})
                obj = {**self.resolve_ref(resolved), **obj}
                if "$ref" in obj:
                    del obj["$ref"]
            return {k: self.resolve_ref(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.resolve_ref(i) for i in obj]
        return obj

    def extract_enums(self, obj: Any) -> list:
        enums = []
        if isinstance(obj, dict):
            if "enum" in obj:
                enums.extend(obj["enum"])
            if "$ref" in obj:
                ref = obj["$ref"]
                if "#/$defs/" in ref:
                    key = ref.split("#/$defs/")[-1]
                    enums.extend(self.extract_enums(self.defs_data.get("$defs", {}).get(key, {})))
            for k in ("allOf", "anyOf", "oneOf", "items"):
                if k in obj:
                    node = obj[k]
                    targets = node if isinstance(node, list) else [node]
                    for item in targets:
                        enums.extend(self.extract_enums(item))
        elif isinstance(obj, list):
            for item in obj:
                enums.extend(self.extract_enums(item))
        return enums

    def extract_range(self, obj: Any):
        mins, maxs = [], []
        def _walk(node):
            if isinstance(node, dict):
                if "minimum" in node: mins.append(node["minimum"])
                if "maximum" in node: maxs.append(node["maximum"])
                for v in node.values(): _walk(v)
            elif isinstance(node, list):
                for i in node: _walk(i)
        _walk(obj)
        return (min(mins) if mins else None, max(maxs) if maxs else None)

    def compress_enum(self, enum_list: list):
        if len(enum_list) > 20:
            try:
                return f"{len(enum_list)} values, min={min(enum_list)}, max={max(enum_list)}"
            except Exception:
                return f"{len(enum_list)} values"
        return enum_list

    def extract_field_type(self, obj: Any) -> str:
        """
        Extract the field type from a schema object.

        Tries multiple keys in order of precedence:
        1. "type" (if present)
        2. "schema_type" (from UDB extensions)
        3. "format" (e.g. "uint32", "uint64")
        4. "description" (fallback to parse bit-width)

        Returns
        -------
        A string describing the type, or "unknown" if it cannot be determined.
        """
        if isinstance(obj, dict):
            # 1. Direct "type" key
            if "type" in obj:
                return str(obj["type"])

            # 2. "schema_type" from UDB extensions
            if "schema_type" in obj:
                return str(obj["schema_type"])

            # 3. "format" key (common in UDB schemas)
            if "format" in obj:
                return str(obj["format"])

            # 4. "description" fallback: parse bit-width
            if "description" in obj:
                desc = str(obj["description"]).lower()
                if "uint32" in desc:
                    return "uint32"
                if "uint64" in desc:
                    return "uint64"
                if "uint128" in desc:
                    return "uint128"
                if "xlen-bit" in desc:
                    return "xlen-bit"
                if "xlen bits" in desc:
                    return "xlen-bit"

            # 5. Recurse into anyOf/oneOf/allOf
            for key in ("anyOf", "oneOf", "allOf"):
                if key in obj:
                    node = obj[key]
                    targets = node if isinstance(node, list) else [node]
                    for item in targets:
                        field_type = self.extract_field_type(item)
                        if field_type != "unknown":
                            return field_type

            # 6. Recurse into "items" for arrays
            if "items" in obj:
                return self.extract_field_type(obj["items"])

        elif isinstance(obj, list):
            # For arrays, try to determine the type of the items
            if obj:
                return self.extract_field_type(obj[0])

        return "unknown"