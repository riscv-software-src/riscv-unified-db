"""
Purpose:
    Ingests UDB parameter, CSR, and extension YAML schemas and converts them
    into structured chunk records matching the AsciiDocChunker output schema,
    enabling a unified downstream embedding and retrieval pipeline.

Pipeline Stage:
    ingest

Inputs:
    - spec/std/isa/param/*.yaml   (one YAML file = one parameter)
    - spec/std/isa/csr/*.yaml     (one YAML file = one CSR, with field definitions)
    - spec/std/isa/ext/*.yaml     (extension metadata and descriptions)

Outputs:
    - data/output/udb_chunks.json  (chunk records; schema matches chunks_repo.json)

Core Responsibilities:
    - Discover and parse parameter / CSR / extension YAML files
    - Normalize schema format (wrapper-style vs schema-as-root)
    - Build human-readable summary sentence per parameter / CSR field
    - Classify parameter_class and parameter_type using taxonomy.yaml labels
    - Write chunk records compatible with AsciiDocChunker output

Key Assumptions:
    - One YAML file = one parameter or one CSR
    - Schema may be at root level or nested under a "schema" key
    - $id field is a valid fallback when "name" is absent

Failure Modes:
    - Empty udb_chunks.json if YAML structure changes and normalization fails
    - Missing name/description fields reduce classification quality
    - NotImplementedError raised on run() until TODO methods are implemented

Notes:
    - Uses rule-based classification (not ML) — consistent with chunker_adoc.py
    - Output chunk schema must stay in sync with AsciiDocChunker chunk dict keys
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ── sys.path bootstrap ──────────────────────────────────────────────────────

_INGEST_DIR  = Path(__file__).parent.resolve()   # pipeline/ingest/
_TOOL_DIR    = _INGEST_DIR.parent.parent          # llm-extraction/

if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))



from configs.config import (        # noqa: E402
    PARAM_DIR,
    CSR_DIR,
    EXT_DIR,
    OUTPUT_DIR,
    logger,
)
from pipeline.utils import chunk_id, flatten_text   # noqa: E402

# Output path for UDB-sourced chunks.
UDB_CHUNKS_PATH = OUTPUT_DIR / "udb_chunks.json"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _extract_defined_by(node) -> str:
    """
    Normalise the ``definedBy`` field from a UDB YAML into a plain string.

    UDB supports two forms:
      - ``{extension: {name: S}}``           → ``"S"``
      - ``{anyOf: [{extension: {name: A}}, …]}`` → ``"A, B"``
    """
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        ext = node.get("extension") or {}
        if isinstance(ext, dict):
            return str(ext.get("name", ""))
        any_of = node.get("anyOf") or []
        names  = []
        for item in any_of:
            if isinstance(item, dict):
                e = item.get("extension") or {}
                if isinstance(e, dict):
                    names.append(str(e.get("name", "")))
        return ", ".join(n for n in names if n)
    return ""


def _schema_summary(schema: dict) -> str:
    """
    Build a short human-readable constraint summary from a UDB ``schema`` node.

    Examples:
      integer [0, 16]              → type=integer, minimum=0, maximum=16
      string enum [A, B, C]        → type=string, enum: A, B, C
    """
    if not schema:
        return ""
    parts: list[str] = []
    typ = schema.get("type", "")
    if typ:
        parts.append(f"type={typ}")
    minimum = schema.get("minimum")
    maximum = schema.get("maximum")
    if minimum is not None or maximum is not None:
        parts.append(f"range=[{minimum}, {maximum}]")
    enum = schema.get("enum") or schema.get("const")
    if enum:
        if isinstance(enum, list):
            parts.append(f"enum: {', '.join(str(v) for v in enum[:8])}")
        else:
            parts.append(f"const: {enum}")
    return ", ".join(parts)


# Maps JSON Schema primitive types → taxonomy.yaml parameter_type labels.
_SCHEMA_TYPE_MAP: dict[str, str] = {
    "integer": "range",
    "number":  "range",
    "boolean": "binary",
    "string":  "enum",    # most string params are mode/encoding selectors
    "array":   "range",
    "object":  "unknown",
}


def _map_schema_type(schema: dict) -> str:
    """
    Map a UDB ``schema`` node to a taxonomy.yaml ``parameter_type`` label.

    Rules (in priority order):
      1. If the schema has an ``enum`` or ``const`` key → ``"enum"``
      2. If it has ``minimum`` or ``maximum`` → ``"range"``
      3. Map the ``type`` string via ``_SCHEMA_TYPE_MAP``
      4. Fall back to ``"unknown"``
    """
    if not schema:
        return "unknown"
    if schema.get("enum") or schema.get("const"):
        return "enum"
    if schema.get("minimum") is not None or schema.get("maximum") is not None:
        return "range"
    raw_type = schema.get("type", "")
    return _SCHEMA_TYPE_MAP.get(str(raw_type).lower(), "unknown")


def _first_line(value) -> str:
    """
    Return the first non-empty line of a (possibly multiline) IDL string.

    IDL ``type()`` and ``reset_value()`` functions are multi-line;
    only the first line is useful in a chunk summary.
    """
    text = str(value).strip() if value else ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


class UDBChunker:
    """Produce chunk dicts from UDB YAML schemas compatible with AsciiDocChunker output."""

    def __init__(
        self,
        param_dir: Path = PARAM_DIR,
        csr_dir:   Path = CSR_DIR,
        ext_dir:   Path = EXT_DIR,
    ) -> None:
        self.param_dir = param_dir
        self.csr_dir   = csr_dir
        self.ext_dir   = ext_dir
        self.chunks:   list[dict] = []

    def _ingest_params(self) -> None:
        """
        Walk param_dir, parse each YAML file, and append a chunk dict per parameter.

        Each chunk captures the parameter name, description, type/range/enum
        constraints from the nested ``schema`` key, and the ``definedBy`` extension.
        Confidence is set to ``"high"`` because UDB parameters are normative.
        """
        from configs.config import yaml  # ruamel.yaml instance

        files = sorted(self.param_dir.glob("*.yaml"))
        logger.info(f"_ingest_params: {len(files)} parameter files found in {self.param_dir}")

        for idx, path in enumerate(files):
            try:
                with open(path, encoding="utf-8") as fh:
                    data = yaml.load(fh)
            except Exception as exc:
                logger.warning(f"Skipping {path.name}: {exc}")
                continue

            name        = str(data.get("name") or path.stem)
            description = flatten_text(data.get("description") or "")
            schema_node = data.get("schema") or {}
            defined_by  = _extract_defined_by(data.get("definedBy"))

            # Build a concise, human-readable summary sentence.
            constraints = _schema_summary(schema_node)
            text_parts  = [f"Parameter {name}"]
            if description:
                text_parts.append(description)
            if constraints:
                text_parts.append(f"Schema: {constraints}.")
            if defined_by:
                text_parts.append(f"Defined by: {defined_by}.")
            text = " ".join(text_parts)

            self.chunks.append({
                "chunk_id":        chunk_id("udb_param", str(path), idx),
                "source":          "udb_param",
                "source_file":     str(path.relative_to(self.param_dir.parent.parent.parent)),
                "section":         name,
                "text":            text,
                "parameter_class": "non_CSR_parameter",
                "parameter_type":  _map_schema_type(schema_node),
                "confidence":      "high",
                "defined_by":      defined_by,
            })

    def _ingest_csrs(self) -> None:
        """
        Walk csr_dir recursively (CSRs are grouped in sub-dirs by extension),
        parse each YAML file, and emit one chunk per CSR plus one chunk per field.

        Field chunks capture: name, location, description, type() IDL, reset_value() IDL.
        """
        from configs.config import yaml

        files = sorted(self.csr_dir.rglob("*.yaml"))
        logger.info(f"_ingest_csrs: {len(files)} CSR files found under {self.csr_dir}")

        for idx, path in enumerate(files):
            try:
                with open(path, encoding="utf-8") as fh:
                    data = yaml.load(fh)
            except Exception as exc:
                logger.warning(f"Skipping {path.name}: {exc}")
                continue

            if data.get("kind") != "csr":
                continue

            csr_name    = str(data.get("name") or path.stem)
            csr_desc    = flatten_text(data.get("description") or "")
            address     = data.get("address", "")
            priv_mode   = data.get("priv_mode", "")

            # ── Top-level CSR chunk ──────────────────────────────────────────
            csr_text = f"CSR {csr_name} (address={address}, priv={priv_mode})"
            if csr_desc:
                csr_text += f": {csr_desc[:300]}"

            self.chunks.append({
                "chunk_id":        chunk_id("udb_csr", str(path), idx),
                "source":          "udb_csr",
                "source_file":     str(path),
                "section":         csr_name,
                "text":            csr_text,
                "parameter_class": "CSR_controlled",
                "parameter_type":  "csr_register",
                "confidence":      "high",
                "defined_by":      _extract_defined_by(data.get("definedBy")),
            })

            # ── Per-field chunks ─────────────────────────────────────────────
            for field_name, field in (data.get("fields") or {}).items():
                if not isinstance(field, dict):
                    continue
                f_desc  = flatten_text(field.get("description") or "")
                # type() is an IDL function string — take only the first line for readability.
                f_type  = _first_line(field.get("type()") or field.get("type") or "")
                f_reset = _first_line(field.get("reset_value()") or field.get("reset_value") or "")
                # location may be split by RV32/RV64 — prefer unified, fall back to both.
                loc = (
                    field.get("location")
                    or f"rv32={field.get('location_rv32', '?')} rv64={field.get('location_rv64', '?')}"
                )

                parts = [
                    f"CSR {csr_name} field {field_name} (bits={loc})",
                    f_desc[:300] if f_desc else "",
                    f"type: {f_type}" if f_type else "",
                    f"reset: {f_reset[:80]}" if f_reset else "",
                ]
                field_text = " ".join(p for p in parts if p)

                self.chunks.append({
                    "chunk_id":        chunk_id("udb_csr_field", f"{path}::{field_name}", idx),
                    "source":          "udb_csr_field",
                    "source_file":     str(path),
                    "section":         f"{csr_name}.{field_name}",
                    "text":            field_text,
                    "parameter_class": "CSR_controlled",
                    "parameter_type":  "csr_field",
                    "confidence":      "high",
                    "defined_by":      "",
                })

    def _ingest_extensions(self) -> None:
        """
        Walk ext_dir, extract each extension's long_name, description, and
        ratification status as a lightweight chunk.
        """
        from configs.config import yaml

        files = sorted(self.ext_dir.glob("*.yaml"))
        logger.info(f"_ingest_extensions: {len(files)} extension files found in {self.ext_dir}")

        for idx, path in enumerate(files):
            try:
                with open(path, encoding="utf-8") as fh:
                    data = yaml.load(fh)
            except Exception as exc:
                logger.warning(f"Skipping {path.name}: {exc}")
                continue

            if data.get("kind") != "extension":
                continue

            name      = str(data.get("name") or path.stem)
            long_name = str(data.get("long_name") or "")
            desc      = flatten_text(data.get("description") or "")
            versions  = data.get("versions") or []
            state     = versions[0].get("state", "") if versions else ""

            parts = [f"Extension {name}"]
            if long_name:
                parts.append(f"({long_name})")  
            if state:
                parts.append(f"[{state}]")
            if desc:
                parts.append(desc[:400])
            text = " ".join(parts)

            self.chunks.append({
                "chunk_id":        chunk_id("udb_ext", str(path), idx),
                "source":          "udb_ext",
                "source_file":     str(path),
                "section":         name,
                "text":            text,
                "parameter_class": "non_CSR_parameter",
                "parameter_type":  "extension",
                "confidence":      "high",
                "defined_by":      name,
            })

    def _write_outputs(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(UDB_CHUNKS_PATH, "w", encoding="utf-8") as fh:
            json.dump(self.chunks, fh, indent=2, ensure_ascii=False)
        logger.info(f"UDB chunks written → {UDB_CHUNKS_PATH} ({len(self.chunks)} chunks)")

    def run(self) -> bool:
        """Run full ingestion. Raises NotImplementedError until TODOs are filled."""
        logger.info("UDBChunker.run() — ingesting parameter / CSR YAML schemas …")
        self._ingest_params()
        self._ingest_csrs()
        self._ingest_extensions()
        self._write_outputs()
        logger.info(f"UDBChunker complete: {len(self.chunks)} chunks produced.")
        return True




def main() -> None:
    chunker = UDBChunker()
    chunker.run()


if __name__ == "__main__":
    main()
