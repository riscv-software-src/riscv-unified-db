# SPDX-License-Identifier: BSD-3-Clause-Clear
"""End-to-end tracer tests for the closed test-only lexical retriever."""

from __future__ import annotations

import ast
import io
import json
import socket
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
import specchoice_treatments.cli as treatments_cli
import specchoice_treatments.retrieval as treatments_retrieval
from specchoice_treatments.cli import build_parser, main
from specchoice_treatments.retrieval import (
    RetrievalContractError,
    build_retrieval_report_v1,
    load_retrieval_contract_v1,
    rank_complete_pairs_v1,
    validate_test_only_target_v1,
)


class RetrievalContractTests(unittest.TestCase):
    """The tracer proves one target through the sole offline CLI."""

    root = Path(__file__).parents[1]
    target_path = "fixtures/treatments/synthetic-target-v1.json"
    corpus_path = "fixtures/treatments/synthetic-complete-pairs-v1.json"
    config_path = "config/treatments/lexical-retrieval-contract-v1.json"
    prompt_manifest_path = "prompts/treatments/prompt-bundle-manifest-v1.json"

    def setUp(self) -> None:
        self.target = json.loads((self.root / self.target_path).read_bytes())
        self.corpus = json.loads((self.root / self.corpus_path).read_bytes())
        self.config = load_retrieval_contract_v1(self.root, self.config_path)
        self.prompt_manifest = json.loads((self.root / self.prompt_manifest_path).read_bytes())

    def _run_cli(self) -> tuple[int, bytes]:
        output = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with redirect_stdout(output):
            exit_code = main([
                "verify-retrieval-contract",
                "--target", self.target_path,
                "--corpus", self.corpus_path,
                "--config", self.config_path,
                "--prompt-manifest", self.prompt_manifest_path,
            ])
        output.flush()
        return exit_code, output.buffer.getvalue()

    @staticmethod
    def _seal_target(target: dict[str, object]) -> None:
        source_text = target["source_text"]
        assert isinstance(source_text, str)
        target["source_sha256"] = sha256_bytes(source_text.encode("utf-8"))
        target["record_sha256"] = sha256_bytes(canonical_json_bytes({
            key: value for key, value in target.items() if key != "record_sha256"
        }))

    @staticmethod
    def _seal_corpus(corpus: dict[str, object]) -> None:
        corpus["corpus_sha256"] = sha256_bytes(canonical_json_bytes({
            key: value for key, value in corpus.items() if key != "corpus_sha256"
        }))

    def test_cli_tracer_returns_exact_two_complete_pairs(self) -> None:
        exit_code, stdout = self._run_cli()
        report = build_retrieval_report_v1(
            target=self.target,
            corpus=self.corpus,
            config=self.config,
            prompt_manifest=self.prompt_manifest,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout, canonical_json_bytes(report))
        self.assertEqual(
            stdout,
            (self.root / "reports/h3/test-only-retrieval-contract-v1.json").read_bytes(),
        )
        self.assertEqual([item["pair_id"] for item in report["results"]], [
            "SYNTH_PAIR_ALPHA", "SYNTH_PAIR_GAMMA",
        ])
        self.assertEqual(len(report["results"]), 2)
        self.assertEqual(
            [{key: item[key] for key in ("pair_id", "positive_source_text", "contrast_source_text", "cosine_score")}
             for item in report["results"]],
            [{
                "pair_id": "SYNTH_PAIR_ALPHA",
                "positive_source_text": "Alpha positive: implementation chooses label.\n",
                "contrast_source_text": "Alpha contrast: ISA fixes label.\n",
                "cosine_score": "0.60058743602146969",
            }, {
                "pair_id": "SYNTH_PAIR_GAMMA",
                "positive_source_text": "Gamma positive: implementation chooses flag.\n",
                "contrast_source_text": "Gamma contrast: ISA fixes flag.\n",
                "cosine_score": "0.24681266140992938",
            }],
        )

    def test_target_text_changes_rank(self) -> None:
        changed_target = deepcopy(self.target)
        changed_target["source_text"] = "Beta platform software access.\n"
        self._seal_target(changed_target)
        changed = rank_complete_pairs_v1(
            target=changed_target,
            corpus=self.corpus,
            config=self.config,
        )
        baseline = rank_complete_pairs_v1(
            target=self.target,
            corpus=self.corpus,
            config=self.config,
        )

        self.assertNotEqual(
            [item.pair_id for item in baseline],
            [item.pair_id for item in changed],
        )
        self.assertEqual([item.pair_id for item in changed], ["SYNTH_PAIR_BETA", "SYNTH_PAIR_ALPHA"])

    def test_null_pair_frame_is_incomplete_even_after_corpus_rehash(self) -> None:
        corpus = deepcopy(self.corpus)
        corpus["pairs"][0]["positive"]["frame"] = None
        self._seal_corpus(corpus)

        with self.assertRaisesRegex(RetrievalContractError, "^RETRIEVAL_PAIR_INCOMPLETE$"):
            rank_complete_pairs_v1(target=self.target, corpus=corpus, config=self.config)

    def test_empty_pair_evidence_is_incomplete_even_after_corpus_rehash(self) -> None:
        corpus = deepcopy(self.corpus)
        corpus["pairs"][0]["positive"]["evidence_spans"] = []
        self._seal_corpus(corpus)

        with self.assertRaisesRegex(RetrievalContractError, "^RETRIEVAL_PAIR_INCOMPLETE$"):
            rank_complete_pairs_v1(target=self.target, corpus=corpus, config=self.config)

    def test_axis_span_mismatch_is_incomplete_even_after_corpus_rehash(self) -> None:
        corpus = deepcopy(self.corpus)
        corpus["pairs"][0]["positive"]["frame"]["authority"]["evidence_span"]["start_byte"] = 1
        self._seal_corpus(corpus)

        with self.assertRaisesRegex(RetrievalContractError, "^RETRIEVAL_PAIR_INCOMPLETE$"):
            rank_complete_pairs_v1(target=self.target, corpus=corpus, config=self.config)

    def test_report_binds_explicit_prompt_manifest_and_distinct_identities(self) -> None:
        parser = build_parser()
        subparsers = next(action for action in parser._actions if action.dest == "command")
        self.assertEqual(set(subparsers.choices), {"verify-retrieval-contract"})
        command = subparsers.choices["verify-retrieval-contract"]
        self.assertEqual(
            {action.dest for action in command._actions if action.required},
            {"target", "corpus", "config", "prompt_manifest"},
        )

        report = build_retrieval_report_v1(
            target=self.target,
            corpus=self.corpus,
            config=self.config,
            prompt_manifest=self.prompt_manifest,
        )
        self.assertEqual(
            [item["pair_id"] for item in report["results"]],
            self.prompt_manifest["pair_selection"]["C"],
        )
        self.assertTrue(report["prompt_c_pair_ids_match"])
        self.assertEqual(
            report["config_file_sha256"],
            sha256_bytes((self.root / self.config_path).read_bytes()),
        )
        self.assertEqual(report["config_contract_sha256"], self.config["contract_sha256"])
        self.assertEqual(
            report["target_file_sha256"],
            sha256_bytes((self.root / self.target_path).read_bytes()),
        )
        self.assertEqual(report["target_record_sha256"], self.target["record_sha256"])
        self.assertEqual(report["target_source_sha256"], self.target["source_sha256"])
        self.assertEqual(
            report["corpus_file_sha256"],
            sha256_bytes((self.root / self.corpus_path).read_bytes()),
        )
        self.assertEqual(report["corpus_content_sha256"], self.corpus["corpus_sha256"])
        self.assertEqual(
            report["prompt_manifest_file_sha256"],
            sha256_bytes((self.root / self.prompt_manifest_path).read_bytes()),
        )
        self.assertNotEqual(report["config_file_sha256"], report["config_contract_sha256"])
        self.assertNotEqual(report["target_file_sha256"], report["target_record_sha256"])
        self.assertNotEqual(report["target_record_sha256"], report["target_source_sha256"])
        self.assertNotEqual(report["corpus_file_sha256"], report["corpus_content_sha256"])
        self.assertNotIn("target_sha256", report)
        self.assertNotIn("corpus_sha256", report)
        self.assertEqual(
            report["report_sha256"],
            sha256_bytes(canonical_json_bytes({
                key: value for key, value in report.items() if key != "report_sha256"
            })),
        )

    def test_prompt_manifest_is_required_and_no_ambient_default_path_is_read(self) -> None:
        with redirect_stderr(io.StringIO()) as stderr:
            exit_code = main([
                "verify-retrieval-contract",
                "--target", self.target_path,
                "--corpus", self.corpus_path,
                "--config", self.config_path,
            ])
        self.assertEqual(exit_code, 2)
        self.assertIn("--prompt-manifest", stderr.getvalue())

        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            for relative_path in (
                self.target_path,
                self.corpus_path,
                self.config_path,
            ):
                source = self.root / relative_path
                destination = sandbox / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            explicit_manifest_path = "inputs/selected-prompt-manifest-v1.json"
            explicit_manifest = sandbox / explicit_manifest_path
            explicit_manifest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.root / self.prompt_manifest_path, explicit_manifest)
            ambient_manifest = sandbox / "prompts/treatments/prompt-bundle-manifest-v1.json"
            ambient_manifest.parent.mkdir(parents=True, exist_ok=True)
            ambient_manifest.write_bytes(b'{"not":"an approved manifest"}\n')
            output = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
            with patch("specchoice_treatments.cli._EXPERIMENT_ROOT", sandbox), redirect_stdout(output):
                exit_code = main([
                    "verify-retrieval-contract",
                    "--target", self.target_path,
                    "--corpus", self.corpus_path,
                    "--config", self.config_path,
                    "--prompt-manifest", explicit_manifest_path,
                ])
            self.assertEqual(exit_code, 0)

    def test_malformed_or_unapproved_prompt_manifest_fails_closed(self) -> None:
        malformed = deepcopy(self.prompt_manifest)
        malformed["pair_selection"] = {"C": ["SYNTH_PAIR_ALPHA"]}
        malformed["manifest_sha256"] = sha256_bytes(canonical_json_bytes({
            key: value for key, value in malformed.items() if key != "manifest_sha256"
        }))
        with self.assertRaisesRegex(RetrievalContractError, "RETRIEVAL_PROMPT_SELECTION_MISMATCH"):
            build_retrieval_report_v1(
                target=self.target,
                corpus=self.corpus,
                config=self.config,
                prompt_manifest=malformed,
            )

        mismatch = deepcopy(self.prompt_manifest)
        mismatch["pair_selection"]["C"] = ["SYNTH_PAIR_ALPHA", "SYNTH_PAIR_BETA"]
        mismatch["manifest_sha256"] = sha256_bytes(canonical_json_bytes({
            key: value for key, value in mismatch.items() if key != "manifest_sha256"
        }))
        with self.assertRaisesRegex(RetrievalContractError, "RETRIEVAL_PROMPT_SELECTION_MISMATCH"):
            build_retrieval_report_v1(
                target=self.target,
                corpus=self.corpus,
                config=self.config,
                prompt_manifest=mismatch,
            )

        unapproved = deepcopy(self.prompt_manifest)
        unapproved["manifest_sha256"] = "0" * 64
        with self.assertRaisesRegex(RetrievalContractError, "RETRIEVAL_PROMPT_SELECTION_MISMATCH"):
            build_retrieval_report_v1(
                target=self.target,
                corpus=self.corpus,
                config=self.config,
                prompt_manifest=unapproved,
            )

    def test_noncanonical_prompt_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            for relative_path in (self.target_path, self.corpus_path, self.config_path):
                source = self.root / relative_path
                destination = sandbox / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            malformed_manifest_path = "inputs/noncanonical-manifest.json"
            destination = sandbox / malformed_manifest_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((self.root / self.prompt_manifest_path).read_bytes().rstrip(b"\n") + b" \n")
            with patch("specchoice_treatments.cli._EXPERIMENT_ROOT", sandbox), redirect_stderr(io.StringIO()):
                exit_code = main([
                    "verify-retrieval-contract",
                    "--target", self.target_path,
                    "--corpus", self.corpus_path,
                    "--config", self.config_path,
                    "--prompt-manifest", malformed_manifest_path,
                ])
            self.assertEqual(exit_code, 2)

    def test_zero_scores_and_exact_ties_return_two_by_pair_id_independent_of_input_order(self) -> None:
        zero_target = deepcopy(self.target)
        zero_target["source_text"] = "unshared lexical material only\n"
        self._seal_target(zero_target)
        reversed_corpus = deepcopy(self.corpus)
        reversed_corpus["pairs"].reverse()
        self._seal_corpus(reversed_corpus)

        baseline = rank_complete_pairs_v1(target=zero_target, corpus=self.corpus, config=self.config)
        reversed_results = rank_complete_pairs_v1(
            target=zero_target, corpus=reversed_corpus, config=self.config,
        )

        self.assertEqual([item.pair_id for item in baseline], ["SYNTH_PAIR_ALPHA", "SYNTH_PAIR_BETA"])
        self.assertEqual([item.cosine_score for item in baseline], [0.0, 0.0])
        self.assertEqual(reversed_results, baseline)

    def test_insufficient_duplicate_and_incomplete_corpora_fail_without_partial_ranking(self) -> None:
        for pair_count in (0, 1):
            with self.subTest(pair_count=pair_count):
                corpus = deepcopy(self.corpus)
                corpus["pairs"] = corpus["pairs"][:pair_count]
                self._seal_corpus(corpus)
                with self.assertRaisesRegex(RetrievalContractError, "^INSUFFICIENT_RETRIEVAL_PAIRS$"):
                    rank_complete_pairs_v1(target=self.target, corpus=corpus, config=self.config)

        duplicate = deepcopy(self.corpus)
        duplicate["pairs"][1]["pair_id"] = duplicate["pairs"][0]["pair_id"]
        self._seal_corpus(duplicate)
        with self.assertRaisesRegex(RetrievalContractError, "^RETRIEVAL_PAIR_ID_DUPLICATE$"):
            rank_complete_pairs_v1(target=self.target, corpus=duplicate, config=self.config)

        incomplete = deepcopy(self.corpus)
        incomplete["pairs"][0]["contrast"] = None
        self._seal_corpus(incomplete)
        with self.assertRaisesRegex(RetrievalContractError, "^RETRIEVAL_PAIR_INCOMPLETE$"):
            rank_complete_pairs_v1(target=self.target, corpus=incomplete, config=self.config)

    def test_empty_and_recursive_forbidden_target_fields_fail_before_tokenization(self) -> None:
        for source_text in ("", None):
            with self.subTest(source_text=source_text):
                empty = deepcopy(self.target)
                empty["source_text"] = source_text
                if isinstance(source_text, str):
                    self._seal_target(empty)
                with self.assertRaisesRegex(RetrievalContractError, "^RETRIEVAL_TARGET_INVALID$"):
                    validate_test_only_target_v1(empty)

        forbidden_fields = (
            "case_id", "fixture_id", "gold", "gold_label", "delegation_frame", "frame",
            "primary_family", "decisive_axes", "relevance", "relevant_pair_ids", "final_disposition",
            "final_status", "parameter_status", "rank", "score", "similarity", "top_k",
            "case_identity", "family", "authority",
        )
        for field in forbidden_fields:
            with self.subTest(field=field):
                target = deepcopy(self.target)
                target["unrelated"] = {"nested": {field: "forbidden"}}
                self._seal_target(target)
                with self.assertRaisesRegex(RetrievalContractError, "^RETRIEVAL_QUERY_FIELD_FORBIDDEN$"):
                    validate_test_only_target_v1(target)

    def test_isolation_and_phase_three_paths_fail_closed_before_ranking(self) -> None:
        for root_name, value in (("target", self.target), ("corpus", self.corpus)):
            for isolation_field, invalid_value in (("test_only", False), ("count_eligible", True)):
                with self.subTest(root=root_name, field=isolation_field):
                    isolated = deepcopy(value)
                    isolated[isolation_field] = invalid_value
                    if root_name == "target":
                        self._seal_target(isolated)
                        with self.assertRaisesRegex(RetrievalContractError, "^RETRIEVAL_TEST_ONLY_REQUIRED$"):
                            rank_complete_pairs_v1(target=isolated, corpus=self.corpus, config=self.config)
                    else:
                        self._seal_corpus(isolated)
                        with self.assertRaisesRegex(RetrievalContractError, "^RETRIEVAL_TEST_ONLY_REQUIRED$"):
                            rank_complete_pairs_v1(target=self.target, corpus=isolated, config=self.config)

        for isolation_field, invalid_value in (("test_only", False), ("count_eligible", True)):
            with self.subTest(pair_field=isolation_field):
                isolated = deepcopy(self.corpus)
                isolated["pairs"][0][isolation_field] = invalid_value
                self._seal_corpus(isolated)
                with self.assertRaisesRegex(RetrievalContractError, "^RETRIEVAL_TEST_ONLY_REQUIRED$"):
                    rank_complete_pairs_v1(target=self.target, corpus=isolated, config=self.config)

        for forbidden_path, expected in (
            ("phase3/data-authority-v1.json", "RETRIEVAL_TARGET_INVALID"),
            ("data/preregistration/candidates-v1/candidate-inventory.json", "RETRIEVAL_TARGET_INVALID"),
            ("/tmp/input.json", "RETRIEVAL_CLI_INPUT_INVALID"),
            ("../fixtures/treatments/synthetic-target-v1.json", "RETRIEVAL_CLI_INPUT_INVALID"),
        ):
            with self.subTest(path=forbidden_path), redirect_stderr(io.StringIO()) as stderr:
                exit_code = main([
                    "verify-retrieval-contract", "--target", forbidden_path,
                    "--corpus", self.corpus_path, "--config", self.config_path,
                    "--prompt-manifest", self.prompt_manifest_path,
                ])
            self.assertEqual(exit_code, 2)
            self.assertEqual(stderr.getvalue(), f"{expected}\n")

        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            for relative_path in (self.corpus_path, self.config_path, self.prompt_manifest_path):
                destination = sandbox / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.root / relative_path, destination)
            target_link = sandbox / "inputs/target-link.json"
            target_link.parent.mkdir(parents=True, exist_ok=True)
            target_link.symlink_to(self.root / self.target_path)
            with patch("specchoice_treatments.cli._EXPERIMENT_ROOT", sandbox), redirect_stderr(io.StringIO()) as stderr:
                exit_code = main([
                    "verify-retrieval-contract", "--target", "inputs/target-link.json",
                    "--corpus", self.corpus_path, "--config", self.config_path,
                    "--prompt-manifest", self.prompt_manifest_path,
                ])
            self.assertEqual(exit_code, 2)
            self.assertEqual(stderr.getvalue(), "RETRIEVAL_CLI_INPUT_INVALID\n")

    def test_cli_has_no_production_or_network_reachability(self) -> None:
        parser = build_parser()
        subparsers = next(action for action in parser._actions if action.dest == "command")
        self.assertEqual(set(subparsers.choices), {"verify-retrieval-contract"})

        observed: list[object] = []
        def blocked(*args: object, **kwargs: object) -> object:
            observed.append((args, kwargs))
            raise AssertionError("network must not be reached")

        with patch.object(socket, "create_connection", side_effect=blocked), patch.object(
            socket.socket, "connect", side_effect=blocked,
        ), redirect_stderr(io.StringIO()):
            self.assertEqual(self._run_cli()[0], 0)
            self.assertEqual(main(["model-run"]), 2)
        self.assertEqual(observed, [])

        imports: set[str] = set()
        for module in (treatments_cli, treatments_retrieval):
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module.split(".", 1)[0])
        self.assertFalse(imports & {
            "socket", "http", "urllib", "requests", "openai", "anthropic", "boto3", "keyring",
        })


if __name__ == "__main__":
    unittest.main()
