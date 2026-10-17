# SPDX-License-Identifier: BSD-3-Clause-Clear
from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_treatments.schema import (
    TreatmentContractError,
    _load_frame_advisory_patterns_v1,
    evaluate_frame_advisories_v1,
    parse_treatment_response_v1,
    validate_source_span_v1,
)


class FrameContractTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        experiment = Path(__file__).parents[1]
        self.source_raw = (experiment / "fixtures/treatments/frame-source-v1.txt").read_bytes()
        self.response = json.loads(
            (experiment / "fixtures/treatments/frame-response-b-valid-v1.json").read_text(
                encoding="utf-8"
            )
        )

    def _parse(self, response: object | None = None):
        value = self.response if response is None else response
        return parse_treatment_response_v1(canonical_json_bytes(value), self.source_raw)

    def _error_code(self, response: object | bytes) -> str:
        raw = response if isinstance(response, bytes) else canonical_json_bytes(response)
        with self.assertRaises(TreatmentContractError) as caught:
            parse_treatment_response_v1(raw, self.source_raw)
        return caught.exception.code

    def _span_error_code(self, span: object) -> str:
        with self.assertRaises(TreatmentContractError) as caught:
            validate_source_span_v1(span, self.source_raw)
        return caught.exception.code

    def test_valid_b_response_binds_exact_three_axis_spans(self) -> None:
        parsed = self._parse()

        self.assertTrue(parsed.valid)
        self.assertEqual(parsed.diagnostics, ())
        self.assertEqual(
            tuple(parsed.delegation_frame),
            ("authority", "choice_object", "choice_space_origin"),
        )
        self.assertEqual(len(parsed.adjudication["evidence_spans"]), 1)
        for axis in parsed.delegation_frame.values():
            span = axis["evidence_span"]
            self.assertEqual(
                self.source_raw[span["start_byte"] : span["end_byte"]].decode("utf-8"),
                span["text"],
            )
        self.assertEqual(parsed.canonical_projection, canonical_json_bytes(parsed.as_dict()))

    def test_unknown_and_key_order_are_deterministic(self) -> None:
        response = deepcopy(self.response)
        response["delegation_frame"]["authority"]["value"] = "unknown"
        response["delegation_frame"]["choice_space_origin"]["value"] = "unknown"
        reordered = {
            "adjudication": response["adjudication"],
            "delegation_frame": {
                "choice_space_origin": response["delegation_frame"]["choice_space_origin"],
                "choice_object": response["delegation_frame"]["choice_object"],
                "authority": response["delegation_frame"]["authority"],
            },
            "target_sha256": response["target_sha256"],
            "model_generated": response["model_generated"],
            "origin": response["origin"],
            "system": response["system"],
            "schema_version": response["schema_version"],
        }

        original = self._parse(response)
        reordered_parsed = self._parse(reordered)

        self.assertTrue(original.valid)
        self.assertTrue(reordered_parsed.valid)
        self.assertEqual(original.canonical_projection, reordered_parsed.canonical_projection)
        self.assertEqual(original.diagnostics, reordered_parsed.diagnostics)

    def test_equal_and_adjacent_spans_remain_axis_scoped(self) -> None:
        response = deepcopy(self.response)
        source_sha256 = response["target_sha256"]
        first = response["delegation_frame"]["authority"]["evidence_span"]
        text = self.source_raw.decode("utf-8")
        response["delegation_frame"]["choice_object"]["evidence_span"] = deepcopy(first)
        response["delegation_frame"]["choice_space_origin"]["evidence_span"] = {
            "source_sha256": source_sha256,
            "start_byte": first["end_byte"],
            "end_byte": len(self.source_raw),
            "text": text[first["end_byte"] :],
        }

        parsed = self._parse(response)

        self.assertTrue(parsed.valid)
        axes = parsed.delegation_frame
        self.assertEqual(
            axes["authority"]["evidence_span"],
            axes["choice_object"]["evidence_span"],
        )
        self.assertEqual(
            axes["authority"]["evidence_span"]["end_byte"],
            axes["choice_space_origin"]["evidence_span"]["start_byte"],
        )
        self.assertEqual(len(axes), 3)

    def test_preregistered_frame_combination_is_warning_only(self) -> None:
        frame = deepcopy(self.response["delegation_frame"])
        frame["authority"]["value"] = "software"
        frame["choice_space_origin"]["value"] = "implementation_selected"

        warnings = evaluate_frame_advisories_v1(frame)

        self.assertEqual(
            [(item.code, item.severity, item.field) for item in warnings],
            [
                (
                    "FRAME_COMBINATION_REQUIRES_REVIEW",
                    "warning",
                    "delegation_frame",
                )
            ],
        )

    def test_a_bc_and_axis_boundaries_are_closed(self) -> None:
        system_a = deepcopy(self.response)
        system_a["system"] = "A"
        system_a.pop("delegation_frame")
        self.assertTrue(self._parse(system_a).valid)

        system_a["delegation_frame"] = deepcopy(self.response["delegation_frame"])
        self.assertEqual(self._error_code(system_a), "DELEGATION_FRAME_FORBIDDEN_FOR_A")

        for system in ("B", "C"):
            missing_frame = deepcopy(self.response)
            missing_frame["system"] = system
            missing_frame.pop("delegation_frame")
            self.assertEqual(self._error_code(missing_frame), "DELEGATION_FRAME_REQUIRED")

            valid = deepcopy(self.response)
            valid["system"] = system
            parsed = self._parse(valid)
            self.assertEqual(set(parsed.as_dict()), set(self._parse().as_dict()))
            self.assertEqual(parsed.delegation_frame, self._parse().delegation_frame)

        for mutation in (
            lambda frame: frame.pop("authority"),
            lambda frame: frame.__setitem__("fourth_axis", deepcopy(frame["authority"])),
        ):
            response = deepcopy(self.response)
            mutation(response["delegation_frame"])
            self.assertEqual(self._error_code(response), "DELEGATION_FRAME_AXES_INVALID")

    def test_invalid_axis_enums_and_raw_json_fail_closed(self) -> None:
        response = deepcopy(self.response)
        response["delegation_frame"]["authority"]["value"] = "missing"
        self.assertEqual(self._error_code(response), "DELEGATION_FRAME_ENUM_INVALID")

        self.assertEqual(
            self._error_code(b'{"system":"B","system":"C"}'),
            "TREATMENT_JSON_INVALID",
        )
        self.assertEqual(self._error_code(b""), "TREATMENT_JSON_INVALID")
        self.assertEqual(self._error_code(b"\xff"), "TREATMENT_JSON_INVALID")
        self.assertEqual(self._error_code(b"null"), "TREATMENT_RESPONSE_KEYS_INVALID")

    def test_every_source_span_boundary_has_a_stable_code(self) -> None:
        span = deepcopy(self.response["delegation_frame"]["authority"]["evidence_span"])
        cases = {
            "missing": None,
            "empty_text": {**span, "text": ""},
            "bool_offset": {**span, "start_byte": True},
            "negative_offset": {**span, "start_byte": -1},
            "equal_offsets": {**span, "end_byte": span["start_byte"]},
            "reversed_offsets": {**span, "start_byte": span["end_byte"]},
            "out_of_range": {**span, "end_byte": len(self.source_raw) + 1},
        }
        self.assertEqual(self._span_error_code(cases.pop("missing")), "FRAME_EVIDENCE_SPAN_REQUIRED")
        for case in cases.values():
            self.assertEqual(self._span_error_code(case), "FRAME_EVIDENCE_SPAN_INVALID")
        unicode_raw = "é".encode("utf-8")
        with self.assertRaises(TreatmentContractError) as caught:
            validate_source_span_v1(
                {
                    "source_sha256": sha256_bytes(unicode_raw),
                    "start_byte": 0,
                    "end_byte": 1,
                    "text": "é",
                },
                unicode_raw,
            )
        self.assertEqual(caught.exception.code, "FRAME_EVIDENCE_TEXT_NOT_UTF8")
        self.assertEqual(
            self._span_error_code({**span, "text": "wrong"}),
            "FRAME_EVIDENCE_TEXT_MISMATCH",
        )

    def test_malformed_adjudication_has_no_parsed_response(self) -> None:
        response = deepcopy(self.response)
        response["adjudication"]["surfaced"] = False
        self.assertEqual(self._error_code(response), "ADJUDICATION_INVALID")

    def test_advisories_are_ordered_nonblocking_and_exact(self) -> None:
        response = deepcopy(self.response)
        response["delegation_frame"]["authority"]["value"] = "software"
        response["delegation_frame"]["choice_object"]["value"] = "extension_gate"
        parsed = self._parse(response)

        warnings = evaluate_frame_advisories_v1(parsed.delegation_frame)

        self.assertTrue(parsed.valid)
        self.assertEqual(parsed.diagnostics, ())
        self.assertEqual(parsed.delegation_frame, response["delegation_frame"])
        self.assertEqual(parsed.adjudication, response["adjudication"])
        self.assertEqual(
            [item.finding_id for item in warnings],
            [
                "EXTENSION_GATE_WITH_IMPLEMENTATION_SELECTED_SPACE",
                "SOFTWARE_WITH_IMPLEMENTATION_SELECTED_SPACE",
            ],
        )
        no_match = deepcopy(parsed.delegation_frame)
        no_match["choice_space_origin"]["value"] = "ISA_fixed"
        self.assertEqual(evaluate_frame_advisories_v1(no_match), ())

    def test_advisory_config_is_canonical_and_rejects_unknown_keys(self) -> None:
        experiment = Path(__file__).parents[1]
        raw = (experiment / "config/treatments/frame-advisory-patterns-v1.json").read_bytes()
        self.assertEqual(raw, canonical_json_bytes(json.loads(raw)))

        with TemporaryDirectory() as directory:
            invalid = Path(directory) / "frame-advisory-patterns-invalid.json"
            invalid.write_bytes(canonical_json_bytes({"schema_version": "frame-advisory-patterns-v1", "patterns": [], "extra": True}))
            with patch("specchoice_treatments.schema._ADVISORY_CONFIG_PATH", invalid):
                with self.assertRaisesRegex(RuntimeError, "^FRAME_ADVISORY_CONFIG_INVALID$"):
                    _load_frame_advisory_patterns_v1()

    def test_adversarial_fixture_is_canonical_and_covers_declared_boundaries(self) -> None:
        fixture = Path(__file__).parents[1] / "fixtures/treatments/frame-response-adversarial-v1.json"
        raw = fixture.read_bytes()
        table = json.loads(raw)
        self.assertEqual(raw, canonical_json_bytes(table))
        self.assertEqual(
            {case["id"] for case in table["cases"]},
            {
                "a_with_frame",
                "axis_missing_or_extra",
                "bc_missing_frame",
                "duplicate_json_keys",
                "empty_or_invalid_offset",
                "invalid_enum",
                "malformed_adjudication",
                "missing_span",
                "split_utf8_code_point",
                "text_mismatch",
            },
        )


if __name__ == "__main__":
    unittest.main()
