"""
Purpose:
    Shared text-handling and utility functions for the extraction pipeline.
"""

import hashlib
from typing import Any

def flatten_text(value: Any) -> str:
    """Flatten a nested JSON/YAML list or dict into a single string."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            parts.append(str(item["text"]) if isinstance(item, dict) and "text" in item else str(item))
        return " ".join(p for p in parts if p).strip()
    return str(value) if value is not None else ""


def normalize_text(text: str) -> str:
    """Collapse excess whitespace and newlines."""
    return " ".join(text.split()).strip()


def chunk_id(source: str, path: str, index: int) -> str:
    """Generate a deterministic short hash for chunk IDs."""
    return "chunk_" + hashlib.md5(f"{source}::{path}::{index}".encode()).hexdigest()[:8]
