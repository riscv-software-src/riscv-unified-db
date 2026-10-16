# SPDX-License-Identifier: BSD-3-Clause-Clear
from __future__ import annotations

import unittest

from specchoice_evidence.canonical import (
    CanonicalValueError,
    canonical_json_bytes,
    normalize_canonical_text,
    require_byte_length,
    require_sha256,
    sha256_bytes,
)


class CanonicalTests(unittest.TestCase):
    def test_canonical_json_sorts_and_normalizes_text(self) -> None:
        self.assertEqual(canonical_json_bytes({"b": "e\u0301\r\n", "a": 1}), b'{"a":1,"b":"\xc3\xa9\\n"}\n')

    def test_raw_hash_preserves_bytes(self) -> None:
        self.assertNotEqual(sha256_bytes(b"a\r\n"), sha256_bytes(normalize_canonical_text("a\r\n").encode()))

    def test_byte_length_requires_nonnegative_json_integer(self) -> None:
        self.assertEqual(require_byte_length(0), 0)
        for invalid in (-1, True, 1.5, "1"):
            with self.assertRaisesRegex(CanonicalValueError, "INVALID_BYTE_LENGTH"):
                require_byte_length(invalid)

    def test_digest_requires_lowercase_hex(self) -> None:
        self.assertEqual(require_sha256("a" * 64), "a" * 64)
        for invalid in ("A" * 64, "a" * 63, 3):
            with self.assertRaisesRegex(CanonicalValueError, "INVALID_SHA256"):
                require_sha256(invalid)
