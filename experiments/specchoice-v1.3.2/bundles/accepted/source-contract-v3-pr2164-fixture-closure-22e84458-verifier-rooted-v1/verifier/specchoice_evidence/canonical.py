# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Canonical JSON and byte-validation primitives.

Raw upstream files are deliberately handled as bytes by :func:`sha256_bytes`; text
normalisation is only for explicitly derived canonical text views.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CanonicalValueError(ValueError):
    """A stable validation failure for a canonical value."""


def normalize_canonical_text(value: str) -> str:
    """Return the explicit NFC/LF canonical view of text, never raw source bytes."""
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def normalize_canonical_value(value: Any) -> Any:
    """Recursively normalise strings used in a canonical JSON view."""
    if isinstance(value, str):
        return normalize_canonical_text(value)
    if isinstance(value, list):
        return [normalize_canonical_value(item) for item in value]
    if isinstance(value, dict):
        return {normalize_canonical_text(str(key)): normalize_canonical_value(item) for key, item in value.items()}
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Encode a deterministic UTF-8 JSON document with one trailing LF."""
    normalized = normalize_canonical_value(value)
    return (
        json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    """Hash authoritative bytes without decoding, normalising, or reparsing them."""
    return hashlib.sha256(data).hexdigest()


def require_byte_length(value: object) -> int:
    """Require an exact non-negative JSON integer (booleans are not integers here)."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CanonicalValueError("INVALID_BYTE_LENGTH")
    return value


def require_sha256(value: object) -> str:
    """Require a lowercase SHA-256 digest in its canonical text representation."""
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise CanonicalValueError("INVALID_SHA256")
    return value
