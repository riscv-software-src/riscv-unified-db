# SPDX-License-Identifier: BSD-3-Clause-Clear
from __future__ import annotations

import json
import re
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_treatments.schema import TreatmentContractError, parse_treatment_response_v1
from specchoice_treatments.prompts import (
    build_prompt_bundle_manifest_v1,
    count_prompt_bytes_v1,
    offline_lexical_token_count_v1,
    PromptBundleError,
    PROMPT_SECTION_ORDER,
    render_prompt_sections_v1,
    render_treatment_prompt_v1,
    validate_contract_response_origin_v1,
    validate_treatment_diffs_v1,
    write_offline_prompt_bundle_v1,
)


class PromptBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        experiment = Path(__file__).parents[1]
        self.config_path = experiment / "config/treatments/prompt-contract-v1.json"
        self.target_path = experiment / "fixtures/treatments/synthetic-target-v1.json"
        self.corpus_path = experiment / "fixtures/treatments/synthetic-complete-pairs-v1.json"
        self.receipt_path = experiment / "fixtures/treatments/synthetic-retrieval-receipt-v1.json"
        self.response_paths = {
            system: experiment / f"fixtures/treatments/contract-response-{system.lower()}-v1.json"
            for system in ("A", "B", "C")
        }
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.target = json.loads(self.target_path.read_text(encoding="utf-8"))
        self.corpus = json.loads(self.corpus_path.read_text(encoding="utf-8"))
        self.receipt = json.loads(self.receipt_path.read_text(encoding="utf-8"))

    def test_named_section_tracer_renders_three_systems(self) -> None:
        rendered = render_treatment_prompt_v1(self.config, self.target)

        self.assertEqual(tuple(rendered), ("A", "B", "C"))
        for system, raw in rendered.items():
            self.assertIsInstance(raw, bytes)
            self.assertNotIn(b"\r", raw)
            self.assertTrue(raw.endswith(b"\n"))
            self.assertFalse(raw.endswith(b"\n\n"))
            self.assertEqual(
                tuple(render_prompt_sections_v1(self.config, self.target, system)),
                PROMPT_SECTION_ORDER,
            )
            self.assertEqual(raw, b"".join(render_prompt_sections_v1(self.config, self.target, system).values()))
        self.assertEqual(
            self.target["source_sha256"],
            "326b6a1274252ca7a69ceff68685f6b3f4e5067eacd83411b9fcfceff77da2c4",
        )
        self.assertEqual(self.target["source_sha256"], sha256_bytes(self.target["source_text"].encode("utf-8")))
        self.assertEqual(
            self.target["record_sha256"],
            sha256_bytes(canonical_json_bytes({key: value for key, value in self.target.items() if key != "record_sha256"})),
        )
        self.assertNotIn("target_sha256", self.target)

    def test_frame_and_shared_sections_are_exact(self) -> None:
        sections = {
            system: render_prompt_sections_v1(self.config, self.target, system)
            for system in ("A", "B", "C")
        }

        self.assertEqual(self.config["demonstration_count"], 2)
        self.assertEqual(
            self.config["fixed_pair_selection"]["corpus_sha256"],
            self.corpus["corpus_sha256"],
        )
        self.assertEqual(
            self.receipt["ranking"],
            [
                {"cosine_score": 0.125, "pair_id": "SYNTH_PAIR_ALPHA", "rank": 1},
                {"cosine_score": 0.0, "pair_id": "SYNTH_PAIR_GAMMA", "rank": 2},
            ],
        )
        self.assertNotIn("ordered_pair_ids", self.receipt)
        self.assertEqual(self.receipt["ordering_rule"], "score_desc_pair_id_asc")
        self.assertEqual(self.receipt["query_rule"], "source_text_only")
        self.assertEqual(
            self.receipt["lexical_rule"], "python_re_findall_unicode_word_boundaries_v1"
        )
        for system in sections:
            self.assertEqual(sections[system]["demonstrations"].count(b"Demonstration "), 2)
        self.assertEqual(sections["A"]["frame_instructions"], b"")
        self.assertEqual(sections["B"]["frame_instructions"], sections["C"]["frame_instructions"])
        self.assertNotIn(b"For each DelegationFrame axis", sections["A"]["frame_instructions"])
        self.assertIn(b"For each DelegationFrame axis", sections["B"]["frame_instructions"])
        for section in ("adjudication_instructions", "output_schema", "evidence_rules"):
            self.assertEqual(sections["B"][section], sections["C"][section])
            self.assertTrue(sections["B"][section])
        self.assertEqual(sections["A"]["evidence_rules"], sections["B"]["evidence_rules"])
        self.assertEqual(
            sections["A"]["evidence_rules"],
            b"For every surfaced finding, quote one or more verbatim source spans in adjudication.evidence_spans.\n",
        )
        self.assertIn(b'exactly one top-level key: "adjudication"', sections["A"]["output_schema"])
        self.assertIn(b'exactly two top-level keys: "delegation_frame" and "adjudication"', sections["B"]["output_schema"])
        for system in ("A", "B", "C"):
            self.assertIn(b'"positive"', sections[system]["demonstrations"])
            self.assertIn(b'"contrast"', sections[system]["demonstrations"])
            self.assertIn(b'"shared_structure"', sections[system]["demonstrations"])
            self.assertIn(b'"discriminating_axes"', sections[system]["demonstrations"])
            self.assertIn(b'"final_status":"accept"', sections[system]["demonstrations"])
            self.assertIn(b'"final_status":"classify_out"', sections[system]["demonstrations"])
            self.assertIn(b"Encode not_surfaced only as:", sections[system]["adjudication_instructions"])
            self.assertIn(b"- parameter_status: null", sections[system]["adjudication_instructions"])
            self.assertIn(
                b"Do not use not_surfaced as a parameter_status value.",
                sections[system]["adjudication_instructions"],
            )
        self.assertIn(b"SYNTH_PAIR_BETA", sections["B"]["demonstrations"])
        self.assertNotIn(b"SYNTH_PAIR_BETA", sections["C"]["demonstrations"])
        self.assertIn(b"SYNTH_PAIR_GAMMA", sections["C"]["demonstrations"])
        self.assertNotIn(b"fixed synthetic pair", sections["C"]["demonstrations"])
        for section in ("shared_guidance", "target"):
            self.assertEqual(sections["A"][section], sections["B"][section])
            self.assertEqual(sections["B"][section], sections["C"][section])

    def test_target_and_raw_text_boundaries_fail_closed(self) -> None:
        invalid_target = deepcopy(self.target)
        invalid_target["source_text"] = ""
        missing_final_lf = deepcopy(self.target)
        missing_final_lf["source_text"] = "synthetic target without its final LF"
        for invalid_config, target in (
            (self.config, invalid_target),
            (self.config, missing_final_lf),
            (self.config, {**self.target, "source_text": None}),
            ({**self.config, "extra": True}, self.target),
            ({**self.config, "shared_guidance": "line\r\n"}, self.target),
        ):
            with self.assertRaisesRegex(PromptBundleError, "^PROMPT_(CONTRACT|TARGET|RAW_BYTES)_INVALID$"):
                render_treatment_prompt_v1(invalid_config, target)

        noncanonical = json.loads(canonical_json_bytes(self.config))
        noncanonical["shared_guidance"] = noncanonical["shared_guidance"].replace("\n", "\r\n")
        with self.assertRaisesRegex(PromptBundleError, "^PROMPT_CONTRACT_INVALID$"):
            render_treatment_prompt_v1(noncanonical, self.target)

        with TemporaryDirectory() as directory:
            root = Path(directory)

            def render_with_target(value: object) -> None:
                path = root / "target.json"
                path.write_bytes(canonical_json_bytes(value))
                with patch("specchoice_treatments.prompts._SYNTHETIC_TARGET_PATH", path):
                    render_treatment_prompt_v1(self.config, value)

            source_as_record = deepcopy(self.target)
            source_as_record["source_sha256"] = self.target["record_sha256"]
            with self.assertRaisesRegex(PromptBundleError, "^PROMPT_TARGET_INVALID$"):
                render_with_target(source_as_record)
            record_as_source = deepcopy(self.target)
            record_as_source["record_sha256"] = self.target["source_sha256"]
            with self.assertRaisesRegex(PromptBundleError, "^PROMPT_TARGET_INVALID$"):
                render_with_target(record_as_source)

            def seal_corpus(value: dict[str, object]) -> None:
                value["corpus_sha256"] = sha256_bytes(canonical_json_bytes({key: item for key, item in value.items() if key != "corpus_sha256"}))

            for mutate in (
                lambda corpus: corpus["pairs"][0].pop("positive"),
                lambda corpus: corpus["pairs"].__setitem__(1, deepcopy(corpus["pairs"][0])),
                lambda corpus: corpus["pairs"][0].__setitem__("test_only", False),
                lambda corpus: corpus["pairs"][0].__setitem__("count_eligible", True),
                lambda corpus: corpus["pairs"][0]["positive"].pop("final_status"),
                lambda corpus: corpus["pairs"][0]["contrast"].__setitem__("final_status", "accept"),
            ):
                invalid_corpus = deepcopy(self.corpus)
                mutate(invalid_corpus)
                seal_corpus(invalid_corpus)
                corpus_path = root / "corpus.json"
                corpus_path.write_bytes(canonical_json_bytes(invalid_corpus))
                with patch("specchoice_treatments.prompts._SYNTHETIC_PAIR_CORPUS_PATH", corpus_path):
                    with self.assertRaisesRegex(PromptBundleError, "^PROMPT_PAIR_(CORPUS_INVALID|ID_DUPLICATE)$"):
                        render_treatment_prompt_v1(self.config, self.target)

            drifted_corpus = deepcopy(self.corpus)
            drifted_corpus["pairs"][0]["shared_structure"].append("changed fixture body")
            seal_corpus(drifted_corpus)
            corpus_path = root / "corpus-drift.json"
            corpus_path.write_bytes(canonical_json_bytes(drifted_corpus))
            with patch("specchoice_treatments.prompts._SYNTHETIC_PAIR_CORPUS_PATH", corpus_path):
                with self.assertRaisesRegex(PromptBundleError, "^PROMPT_CONTRACT_INVALID$"):
                    render_treatment_prompt_v1(self.config, self.target)

            def seal_receipt(value: dict[str, object]) -> None:
                value["receipt_sha256"] = sha256_bytes(canonical_json_bytes({key: item for key, item in value.items() if key != "receipt_sha256"}))

            def render_with_receipt(value: dict[str, object]) -> None:
                seal_receipt(value)
                contract = deepcopy(self.config)
                contract["retrieval_receipt_sha256"] = value["receipt_sha256"]
                contract_path = root / "contract.json"
                receipt_path = root / "receipt.json"
                contract_path.write_bytes(canonical_json_bytes(contract))
                receipt_path.write_bytes(canonical_json_bytes(value))
                with patch("specchoice_treatments.prompts._PROMPT_CONTRACT_PATH", contract_path):
                    with patch("specchoice_treatments.prompts._SYNTHETIC_RETRIEVAL_RECEIPT_PATH", receipt_path):
                        render_prompt_sections_v1(contract, self.target, "C")

            for mutate in (
                lambda receipt: receipt.__setitem__("target_source_sha256", self.target["record_sha256"]),
                lambda receipt: receipt.__setitem__("corpus_sha256", "0" * 64),
                lambda receipt: receipt.__setitem__("ranking", receipt["ranking"][:1]),
                lambda receipt: receipt["ranking"][0].__setitem__("rank", 2),
                lambda receipt: receipt["ranking"][0].__setitem__("cosine_score", -1.0),
                lambda receipt: receipt["ranking"][0].__setitem__("cosine_score", 0.0)
                or receipt["ranking"][1].__setitem__("cosine_score", 0.125),
                lambda receipt: receipt["ranking"].__setitem__(
                    0,
                    {"rank": 1, "pair_id": "SYNTH_PAIR_GAMMA", "cosine_score": 0.0},
                ) or receipt["ranking"].__setitem__(
                    1,
                    {"rank": 2, "pair_id": "SYNTH_PAIR_ALPHA", "cosine_score": 0.0},
                ),
                lambda receipt: receipt.__setitem__("ordered_pair_ids", ["SYNTH_PAIR_ALPHA", "SYNTH_PAIR_GAMMA"]),
                lambda receipt: receipt.__setitem__("ordering_rule", "score_asc_pair_id_asc"),
                lambda receipt: receipt.pop("query_rule"),
            ):
                invalid_receipt = deepcopy(self.receipt)
                mutate(invalid_receipt)
                with self.assertRaisesRegex(PromptBundleError, "^PROMPT_PAIR_CORPUS_INVALID$"):
                    render_with_receipt(invalid_receipt)

            canonical_unsurfaced = {
                "schema_version": "delegation-frame-response-v1",
                "system": "A",
                "origin": "contract_fixture",
                "model_generated": False,
                "target_sha256": self.target["source_sha256"],
                "adjudication": {
                    "surfaced": False,
                    "parameter_status": None,
                    "proposed_name": None,
                    "evidence_spans": [],
                    "rationale": "No candidate finding is present.",
                },
            }
            self.assertFalse(
                parse_treatment_response_v1(
                    canonical_json_bytes(canonical_unsurfaced),
                    self.target["source_text"].encode("utf-8"),
                ).adjudication["surfaced"]
            )
            invalid_unsurfaced = deepcopy(canonical_unsurfaced)
            invalid_unsurfaced["adjudication"]["parameter_status"] = "not_surfaced"
            with self.assertRaisesRegex(TreatmentContractError, "^ADJUDICATION_INVALID$"):
                parse_treatment_response_v1(
                    canonical_json_bytes(invalid_unsurfaced),
                    self.target["source_text"].encode("utf-8"),
                )
            surfaced_without_evidence = deepcopy(canonical_unsurfaced)
            surfaced_without_evidence["adjudication"]["surfaced"] = True
            surfaced_without_evidence["adjudication"]["parameter_status"] = "accept"
            with self.assertRaisesRegex(TreatmentContractError, "^ADJUDICATION_INVALID$"):
                parse_treatment_response_v1(
                    canonical_json_bytes(surfaced_without_evidence),
                    self.target["source_text"].encode("utf-8"),
                )

    def test_three_complete_pairs_and_two_pair_selections(self) -> None:
        rendered = {
            system: render_prompt_sections_v1(self.config, self.target, system)
            for system in ("A", "B", "C")
        }
        pair_ids = [pair["pair_id"] for pair in self.corpus["pairs"]]

        self.assertGreaterEqual(len(pair_ids), 3)
        self.assertEqual(pair_ids, sorted(pair_ids))
        self.assertEqual(len(pair_ids), len(set(pair_ids)))
        self.assertTrue(self.corpus["test_only"])
        self.assertFalse(self.corpus["count_eligible"])
        for pair in self.corpus["pairs"]:
            self.assertTrue(pair["test_only"])
            self.assertFalse(pair["count_eligible"])
            self.assertEqual(set(pair), {
                "pair_id", "shared_structure", "positive", "contrast",
                "discriminating_axes", "test_only", "count_eligible",
            })
            self.assertEqual(pair["positive"]["final_status"], "accept")
            self.assertEqual(pair["contrast"]["final_status"], "classify_out")
        fixed = self.config["fixed_pair_selection"]["ordered_pair_ids"]
        retrieved = [item["pair_id"] for item in self.receipt["ranking"]]
        self.assertEqual(len(fixed), len(set(fixed)))
        self.assertEqual(len(retrieved), len(set(retrieved)))
        self.assertEqual(fixed, ["SYNTH_PAIR_ALPHA", "SYNTH_PAIR_BETA"])
        self.assertEqual(retrieved, ["SYNTH_PAIR_ALPHA", "SYNTH_PAIR_GAMMA"])
        self.assertIn(b"SYNTH_PAIR_BETA", rendered["A"]["demonstrations"])
        self.assertIn(b"SYNTH_PAIR_GAMMA", rendered["C"]["demonstrations"])

    def test_contract_responses_parse_and_remain_human_authored(self) -> None:
        target_raw = self.target["source_text"].encode("utf-8")

        for system, path in self.response_paths.items():
            raw = path.read_bytes()
            envelope = json.loads(raw)
            self.assertEqual(canonical_json_bytes(envelope), raw)
            self.assertEqual(envelope["system"], system)
            self.assertEqual(envelope["origin"], "contract_fixture")
            self.assertIs(envelope["model_generated"], False)
            self.assertIs(envelope["test_only"], True)
            self.assertIs(envelope["count_eligible"], False)
            parsed = validate_contract_response_origin_v1(raw, target_raw)
            self.assertEqual(parsed.system, system)
            self.assertEqual(parsed.origin, "contract_fixture")
            self.assertFalse(parsed.model_generated)
            self.assertNotIn("test_only", parsed.as_dict())
            self.assertNotIn("count_eligible", parsed.as_dict())
        self.assertIsNone(
            validate_contract_response_origin_v1(
                self.response_paths["A"].read_bytes(), target_raw
            ).delegation_frame
        )

    def test_fixture_or_response_authority_escalation_is_rejected(self) -> None:
        target_raw = self.target["source_text"].encode("utf-8")
        valid_raw = self.response_paths["B"].read_bytes()
        valid = json.loads(valid_raw)

        for field, value in (
            ("origin", "raw_model_output"),
            ("model_generated", True),
            ("test_only", False),
            ("count_eligible", True),
        ):
            mutated = deepcopy(valid)
            mutated[field] = value
            with self.assertRaisesRegex(PromptBundleError, "^PROMPT_RESPONSE_INVALID$"):
                validate_contract_response_origin_v1(canonical_json_bytes(mutated), target_raw)
        for evidence_kind in ("raw_model_output", "model_run", "h1", "h2"):
            with self.assertRaisesRegex(PromptBundleError, "^CONTRACT_FIXTURE_EVIDENCE_FORBIDDEN$"):
                validate_contract_response_origin_v1(valid_raw, target_raw, evidence_kind=evidence_kind)
        invalid_corpus = deepcopy(self.corpus)
        invalid_corpus["pairs"][0]["pair_id"] = "warl-implementation-selected-vs-isa-fixed"
        invalid_corpus["corpus_sha256"] = sha256_bytes(
            canonical_json_bytes({key: value for key, value in invalid_corpus.items() if key != "corpus_sha256"})
        )
        with TemporaryDirectory() as directory:
            corpus_path = Path(directory) / "corpus.json"
            corpus_path.write_bytes(canonical_json_bytes(invalid_corpus))
            with patch("specchoice_treatments.prompts._SYNTHETIC_PAIR_CORPUS_PATH", corpus_path):
                with self.assertRaisesRegex(PromptBundleError, "^PROMPT_PAIR_CORPUS_INVALID$"):
                    render_treatment_prompt_v1(self.config, self.target)

    def test_prompt_publication_exactly_resumes_raw_bytes(self) -> None:
        rendered = render_treatment_prompt_v1(self.config, self.target)
        with TemporaryDirectory() as directory:
            output_root = Path(directory)
            manifest = write_offline_prompt_bundle_v1(output_root, self.config, self.target)
            resumed = write_offline_prompt_bundle_v1(output_root, self.config, self.target)

            self.assertEqual(manifest, resumed)
            prompt_root = output_root / "prompts/treatments"
            self.assertEqual(canonical_json_bytes(manifest), (prompt_root / "prompt-bundle-manifest-v1.json").read_bytes())
            for system, raw in rendered.items():
                stored = (prompt_root / f"system-{system.lower()}-v1.txt").read_bytes()
                self.assertEqual(stored, raw)
                record = manifest["prompt_records"][system]
                self.assertEqual(record["sha256"], sha256_bytes(raw))
                self.assertEqual(record["counts"], count_prompt_bytes_v1(raw))
                self.assertEqual(record["counts"]["offline_lexical_token_count"], len(re.findall(r"(?u)\b\w+\b", raw.decode("utf-8"))))
                self.assertEqual(offline_lexical_token_count_v1(raw), record["counts"]["offline_lexical_token_count"])

    def test_treatment_diff_allowlist_rejects_padding_and_reordering(self) -> None:
        sections = {
            system: render_prompt_sections_v1(self.config, self.target, system)
            for system in ("A", "B", "C")
        }
        comparison = validate_treatment_diffs_v1(sections)

        self.assertEqual(comparison["A_B"]["allowed_differences"], ["frame_instructions", "output_schema"])
        self.assertEqual(comparison["A_B"]["observed_differences"], ["frame_instructions", "output_schema"])
        self.assertEqual(comparison["B_C"]["allowed_differences"], ["demonstrations"])
        self.assertEqual(comparison["B_C"]["observed_differences"], ["demonstrations"])
        for system in ("A", "B", "C"):
            self.assertEqual(sections[system]["demonstrations"].count(b"Demonstration "), 2)

        padded = deepcopy(sections)
        padded["B"]["shared_guidance"] += b"neutral padding\n"
        with self.assertRaisesRegex(PromptBundleError, "^TREATMENT_DIFF_NOT_ALLOWLISTED$"):
            validate_treatment_diffs_v1(padded)
        reordered = deepcopy(sections)
        reordered["C"]["demonstrations"] = (
            reordered["C"]["demonstrations"].split(b"Demonstration 2:")[1]
            + b"Demonstration 2:"
            + reordered["C"]["demonstrations"].split(b"Demonstration 2:")[0]
        )
        with self.assertRaisesRegex(PromptBundleError, "^TREATMENT_DIFF_NOT_ALLOWLISTED$"):
            validate_treatment_diffs_v1(reordered)

    def test_manifest_accounting_and_preflight_fail_closed(self) -> None:
        manifest = build_prompt_bundle_manifest_v1(self.config, self.target)

        self.assertEqual(manifest["manifest_sha256"], sha256_bytes(canonical_json_bytes({
            key: value for key, value in manifest.items() if key != "manifest_sha256"
        })))
        for field in ("provider_input_tokens", "provider_output_tokens", "maximum_output_tokens"):
            self.assertEqual(manifest[field], "not_applicable_red")
        self.assertEqual(set(manifest["pair_selection"]), {"A", "B", "C"})
        self.assertEqual(manifest["pair_selection"]["A"], manifest["pair_selection"]["B"])
        self.assertNotEqual(manifest["pair_selection"]["B"], manifest["pair_selection"]["C"])
        self.assertEqual(set(manifest["response_records"]), {"A", "B", "C"})

        with TemporaryDirectory() as directory:
            output_root = Path(directory)
            prompt_root = output_root / "prompts/treatments"
            prompt_root.mkdir(parents=True)
            (prompt_root / "system-a-v1.txt").write_bytes(b"divergent\n")
            with self.assertRaisesRegex(PromptBundleError, "^PROMPT_BUNDLE_WRITE_INVALID$"):
                write_offline_prompt_bundle_v1(output_root, self.config, self.target)
            self.assertFalse((prompt_root / "system-b-v1.txt").exists())
            self.assertFalse((prompt_root / "system-c-v1.txt").exists())
            self.assertFalse((prompt_root / "prompt-bundle-manifest-v1.json").exists())


if __name__ == "__main__":
    unittest.main()
