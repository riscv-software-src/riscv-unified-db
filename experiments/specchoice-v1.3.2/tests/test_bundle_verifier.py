# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Byte-custody and non-accepted candidate bundle tests."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from specchoice_evidence.bundle import (
    BundleError,
    accept_local_candidate,
    construct_candidate,
    construct_verifier_rooted_candidate,
    publish_accepted,
    verify_candidate,
)
from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.source_contract import (
    SourceContractProposalError,
    require_accepted_publication_authorization,
    require_local_accepted_generation_authorization,
    validate_local_accepted_generation_decision,
    validate_source_publication_decision,
)
from specchoice_evidence.verify import (
    BundleVerificationError,
    create_synthetic_accepted_bundle,
    verify_accepted_bundle,
)


def git(*arguments: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def proposal_for(raw: bytes, commit: str, tree: str) -> dict[str, object]:
    return {
        "schema_version": "1",
        "status": "pending_reviewer_approval",
        "proposed_contract_version": "2",
        "requested_generation_label": "candidate-v2",
        "base_frozen_contract": {"path": "config/source_snapshots.json", "sha256": "a" * 64},
        "historical_rejected_receipt": {"path": "bundles/rejected/receipt.json", "sha256": "b" * 64},
        "snapshots": [{
            "snapshot_id": "fixture",
            "repository": "example/repository",
            "pull_request": 7,
            "pinned_commit_sha": commit,
            "pinned_tree_sha": tree,
            "canonical_pr_head_sha": commit,
            "reachability": "equal_head",
            "change_control": "versioned_correction",
        }],
        "consumed_files": [{
            "snapshot_id": "fixture",
            "upstream_path": "fixture.txt",
            "local_bundle_path": "raw/fixture.txt",
            "experimental_role": "test fixture",
            "why_consumed": "Proves byte custody.",
            "raw_authoritative": True,
            "raw_byte_length": len(raw),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "declared_transforms": [],
        }],
    }


def candidate_decision_for(proposal: dict[str, object]) -> dict[str, object]:
    return {
        "approval_scope": "candidate_construction_only",
        "approved_contract": {
            "base_frozen_contract": proposal["base_frozen_contract"],
            "consumed_files": proposal["consumed_files"],
            "historical_rejected_receipt": proposal["historical_rejected_receipt"],
            "proposed_contract_version": proposal["proposed_contract_version"],
            "requested_generation_label": proposal["requested_generation_label"],
            "snapshots": proposal["snapshots"],
        },
        "authorization": {
            "accepted_publication_authorized": False,
            "candidate_construction_authorized": True,
            "source_extraction_authorized": True,
        },
        "proposal": {
            "path": "receipts/source-contract-correction-proposal-v2.json",
            "sha256": sha256_bytes(canonical_json_bytes(proposal)),
        },
        "reviewer": {"approval_token": "authorize-candidate-construction-only"},
        "schema_version": "1",
        "state": "candidate_construction_authorized",
    }


class BundleVerifierTests(unittest.TestCase):
    """Public verifier regressions for descriptor-bound source consumption."""

    def _accepted_copy(self, root: Path) -> Path:
        experiment = Path(__file__).resolve().parents[1]
        source = experiment / (
            "bundles/accepted/"
            "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
        )
        copied = root / "accepted"
        shutil.copytree(source, copied)
        return copied

    def test_public_source_verifier_rejects_rebound_root_intermediate_and_fifo_leafs(self) -> None:
        for mutation in ("root", "intermediate", "fifo"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                copied = self._accepted_copy(Path(directory))
                if mutation == "root":
                    sibling = copied.with_name("replacement")
                    shutil.copytree(copied, sibling)
                    (sibling / "content-manifest-core.json").write_bytes(b"{}\n")
                    os.rename(copied, copied.with_name("old"))
                    os.rename(sibling, copied)
                elif mutation == "intermediate":
                    raw = copied / "raw"
                    sibling = copied / "replacement-raw"
                    shutil.copytree(raw, sibling)
                    next(sibling.rglob("*.txt")).write_bytes(b"replacement raw bytes")
                    shutil.rmtree(raw)
                    os.rename(sibling, raw)
                else:
                    leaf = copied / "fixture-registry-pr2164-v1.json"
                    leaf.unlink()
                    os.mkfifo(leaf)
                with self.assertRaises(BundleVerificationError):
                    verify_accepted_bundle(copied)

    def test_descriptor_tree_closure_rejects_rebind_without_pathname_walk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = self._accepted_copy(Path(directory))
            (copied / "unexpected.txt").write_bytes(b"must block closed inventory")
            with self.assertRaisesRegex(BundleVerificationError, "BUNDLE_EXTRA_FILE"):
                verify_accepted_bundle(copied)


class CandidateBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.audit = self.root / "audit.git"
        git("init", "-q", self.source.as_posix())
        git("config", "user.email", "test@example.invalid", cwd=self.source)
        git("config", "user.name", "SpecChoice test", cwd=self.source)
        self.raw = "decomposed-e\u0301\r\n".encode("utf-8")
        (self.source / "fixture.txt").write_bytes(self.raw)
        git("add", "fixture.txt", cwd=self.source)
        git("commit", "-qm", "fixture", cwd=self.source)
        self.commit = git("rev-parse", "HEAD", cwd=self.source)
        self.tree = git("rev-parse", "HEAD^{tree}", cwd=self.source)
        git("clone", "--bare", "-q", self.source.as_posix(), self.audit.as_posix())
        git("--git-dir", self.audit.as_posix(), "update-ref", "refs/specchoice/pr/7", self.commit)
        self.proposal = proposal_for(self.raw, self.commit, self.tree)
        self.decision = candidate_decision_for(self.proposal)
        self.candidates = self.root / "bundles" / "candidates"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_candidate_copies_exact_git_blob_and_has_deterministic_noncyclic_binding(self) -> None:
        result = construct_candidate(self.decision, self.proposal, self.audit, self.candidates)
        candidate = self.candidates / "candidate-v2"
        self.assertEqual(result["status"], "candidate")
        self.assertEqual((candidate / "raw/fixture.txt").read_bytes(), self.raw)
        self.assertEqual(verify_candidate(candidate)["root_sha256"], result["root_sha256"])
        self.assertFalse((self.root / "bundles" / "accepted").exists())
        with self.assertRaisesRegex(BundleError, "CANDIDATE_TARGET_EXISTS"):
            construct_candidate(self.decision, self.proposal, self.audit, self.candidates)

    def test_tampered_final_bindings_and_raw_bytes_fail_closed(self) -> None:
        construct_candidate(self.decision, self.proposal, self.audit, self.candidates)
        candidate = self.candidates / "candidate-v2"
        manifest_path = candidate / "snapshot-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["snapshots"][0]["root_sha256"] = "0" * 64
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with self.assertRaisesRegex(BundleError, "SNAPSHOT_MANIFEST_SELF_DIGEST_MISMATCH"):
            verify_candidate(candidate)

    def test_recomputed_top_level_and_per_snapshot_binding_tampering_rejects(self) -> None:
        construct_candidate(self.decision, self.proposal, self.audit, self.candidates)
        candidate = self.candidates / "candidate-v2"
        manifest_path = candidate / "snapshot-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["generation"] = "other"
        without_self = dict(manifest)
        without_self.pop("snapshot_manifest_sha256")
        manifest["snapshot_manifest_sha256"] = sha256_bytes(canonical_json_bytes(without_self))
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with self.assertRaisesRegex(BundleError, "SNAPSHOT_BINDING_MISMATCH"):
            verify_candidate(candidate)

        construct_candidate(self.decision, self.proposal, self.audit, self.candidates / "third")
        candidate = self.candidates / "third" / "candidate-v2"
        manifest_path = candidate / "snapshot-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["manifest_sha256"] = "0" * 64
        without_self = dict(manifest)
        without_self.pop("snapshot_manifest_sha256")
        manifest["snapshot_manifest_sha256"] = sha256_bytes(canonical_json_bytes(without_self))
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with self.assertRaisesRegex(BundleError, "MANIFEST_SHA256_MISMATCH"):
            verify_candidate(candidate)

        construct_candidate(self.decision, self.proposal, self.audit, self.candidates / "fourth")
        candidate = self.candidates / "fourth" / "candidate-v2"
        manifest_path = candidate / "snapshot-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["snapshots"][0]["repository"] = "tampered/repository"
        without_self = dict(manifest)
        without_self.pop("snapshot_manifest_sha256")
        manifest["snapshot_manifest_sha256"] = sha256_bytes(canonical_json_bytes(without_self))
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with self.assertRaisesRegex(BundleError, "SNAPSHOT_CORE_PROJECTION_MISMATCH"):
            verify_candidate(candidate)

        construct_candidate(self.decision, self.proposal, self.audit, self.candidates / "fifth")
        candidate = self.candidates / "fifth" / "candidate-v2"
        manifest_path = candidate / "snapshot-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["snapshot_manifest_sha256"] = "0" * 64
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with self.assertRaisesRegex(BundleError, "SNAPSHOT_MANIFEST_SELF_DIGEST_MISMATCH"):
            verify_candidate(candidate)

        construct_candidate(self.decision, self.proposal, self.audit, self.candidates / "second")
        candidate = self.candidates / "second" / "candidate-v2"
        manifest_path = candidate / "snapshot-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["snapshots"][0]["manifest_sha256"] = "0" * 64
        without_self = dict(manifest)
        without_self.pop("snapshot_manifest_sha256")
        manifest["snapshot_manifest_sha256"] = sha256_bytes(canonical_json_bytes(without_self))
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with self.assertRaisesRegex(BundleError, "SNAPSHOT_BINDING_MISMATCH"):
            verify_candidate(candidate)

    def test_interruption_alias_special_file_and_accepted_publication_all_fail_closed(self) -> None:
        invalid = copy.deepcopy(self.proposal)
        invalid["consumed_files"][0]["raw_sha256"] = "0" * 64
        with self.assertRaisesRegex(BundleError, "RAW_SHA256_MISMATCH"):
            construct_candidate(candidate_decision_for(invalid), invalid, self.audit, self.candidates)
        self.assertEqual(list(self.candidates.glob(".candidate-v2.staging-*")), [])
        self.assertFalse((self.root / "bundles" / "accepted").exists())

        construct_candidate(self.decision, self.proposal, self.audit, self.candidates)
        raw_path = self.candidates / "candidate-v2" / "raw" / "fixture.txt"
        raw_path.unlink()
        raw_path.symlink_to("missing-target")
        with self.assertRaisesRegex(BundleError, "SYMLINK_REJECTED"):
            verify_candidate(self.candidates / "candidate-v2")
        with self.assertRaisesRegex(BundleError, "ACCEPTED_PUBLICATION_NOT_AUTHORIZED"):
            publish_accepted(self.decision)

    def test_inventory_collision_and_accepted_scope_escalation_reject(self) -> None:
        invalid = copy.deepcopy(self.proposal)
        duplicate = copy.deepcopy(invalid["consumed_files"][0])
        duplicate["upstream_path"] = "nested.txt"
        duplicate["local_bundle_path"] = "raw/fixture.txt/child.txt"
        invalid["consumed_files"].append(duplicate)
        with self.assertRaisesRegex(BundleError, "LOCAL_PATH_COLLISION"):
            construct_candidate(candidate_decision_for(invalid), invalid, self.audit, self.candidates)

        decision = candidate_decision_for(self.proposal)
        decision["authorization"]["accepted_publication_authorized"] = True
        with self.assertRaisesRegex(SourceContractProposalError, "AUTHORIZATION_INVALID"):
            validate_source_publication_decision(
                decision,
                self.proposal,
                proposal_path="receipts/source-contract-correction-proposal-v2.json",
                proposal_sha256=sha256_bytes(canonical_json_bytes(self.proposal)),
            )
        with self.assertRaisesRegex(SourceContractProposalError, "ACCEPTED_PUBLICATION_NOT_AUTHORIZED"):
            require_accepted_publication_authorization(self.decision)

    def test_copied_accepted_bundle_replays_without_git_network_or_repository_modules(self) -> None:
        construct_candidate(self.decision, self.proposal, self.audit, self.candidates)
        candidate = self.candidates / "candidate-v2"
        accepted = self.root / "accepted" / "fixture-accepted"
        identity = create_synthetic_accepted_bundle(candidate, accepted, "fixture-accepted")
        self.assertEqual(verify_accepted_bundle(accepted)["root_sha256"], identity["root_sha256"])

        copied = self.root / "copied-away"
        shutil.copytree(accepted, copied)
        shim = self.root / "no-git"
        shim.mkdir()
        (shim / "git").write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
        (shim / "sitecustomize.py").write_text(
            "import socket\n"
            "def blocked(*args, **kwargs):\n    raise RuntimeError('network blocked')\n"
            "socket.socket = blocked\n",
            encoding="utf-8",
        )
        os.chmod(shim / "git", 0o755)
        environment = {
            "PATH": f"{shim}{os.pathsep}{os.environ.get('PATH', '')}",
            "PYTHONPATH": shim.as_posix(),
        }
        completed = subprocess.run(
            [sys.executable, "verify_bundle.py"],
            cwd=copied,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        verifier = copied / "verifier/specchoice_evidence/verify.py"
        verifier.write_text(verifier.read_text(encoding="utf-8") + "# tampered\n", encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, "verify_bundle.py"], cwd=copied, env=environment, check=False
        )
        self.assertNotEqual(completed.returncode, 0)


class VerifierRootedCandidateTests(unittest.TestCase):
    def test_real_candidate_is_re_rooted_and_replays_away_from_repository(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        source = experiment / "bundles/candidates/source-contract-v2-pr2192-86a0021b"
        source_identity = verify_candidate(source)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidates = root / "bundles/candidates"
            generation = "source-contract-v2-pr2192-86a0021b-verifier-rooted"
            identity = construct_verifier_rooted_candidate(source, candidates, generation)
            candidate = candidates / generation
            self.assertEqual(identity["status"], "candidate")
            self.assertNotEqual(identity["root_sha256"], source_identity["root_sha256"])
            self.assertTrue((candidate / "verify_bundle.py").is_file())
            self.assertEqual(verify_candidate(candidate)["root_sha256"], identity["root_sha256"])
            self.assertFalse((root / "bundles/accepted").exists())

            copied = root / "copied-away"
            shutil.copytree(candidate, copied)
            shim = root / "no-git"
            shim.mkdir()
            (shim / "git").write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
            (shim / "sitecustomize.py").write_text(
                "import socket\n"
                "def blocked(*args, **kwargs):\n    raise RuntimeError('network blocked')\n"
                "socket.socket = blocked\n",
                encoding="utf-8",
            )
            os.chmod(shim / "git", 0o755)
            environment = {
                "PATH": f"{shim}{os.pathsep}{os.environ.get('PATH', '')}",
                "PYTHONPATH": shim.as_posix(),
            }
            completed = subprocess.run(
                [sys.executable, "verify_bundle.py"], cwd=copied, env=environment,
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            for path in (
                "raw/parameter_emitter/param_emitter.py",
                "content-manifest-core.json",
                "snapshot-manifest.json",
                "verifier/specchoice_evidence/verify.py",
            ):
                target = copied / path
                target.write_bytes(target.read_bytes() + b"# tampered\n")
                completed = subprocess.run(
                    [sys.executable, "verify_bundle.py"], cwd=copied, env=environment,
                    check=False, capture_output=True, text=True,
                )
                self.assertNotEqual(completed.returncode, 0, path)
                shutil.rmtree(copied)
                shutil.copytree(candidate, copied)


class LocalAcceptanceTests(unittest.TestCase):
    def test_local_acceptance_is_exactly_bound_immutable_and_not_external_publication(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        candidate = experiment / "bundles/candidates/source-contract-v2-pr2192-86a0021b-verifier-rooted-v1"
        core = candidate / "content-manifest-core.json"
        snapshot = candidate / "snapshot-manifest.json"
        identity = verify_candidate(candidate)
        decision = {
            "approval_scope": "local_accepted_generation_only",
            "approved_generation": {
                "candidate_relative_path": "bundles/candidates/source-contract-v2-pr2192-86a0021b-verifier-rooted-v1",
                "core_sha256": sha256_bytes(core.read_bytes()),
                "generation": identity["generation"],
                "root_sha256": identity["root_sha256"],
                "snapshot_manifest_sha256": json.loads(snapshot.read_text(encoding="utf-8"))["snapshot_manifest_sha256"],
            },
            "authorization": {
                "external_publication_authorized": False,
                "local_accepted_generation_authorized": True,
            },
            "reviewed_receipt_basis_sha256": "f" * 64,
            "reviewer": {"disposition": "approved_local_only"},
            "schema_version": "2",
            "state": "local_accepted_generation_authorized",
        }
        validated = validate_local_accepted_generation_decision(decision, allow_historical=True)
        require_local_accepted_generation_authorization(
            validated,
            identity,
            json.loads(snapshot.read_text(encoding="utf-8"))["snapshot_manifest_sha256"],
            allow_historical=True,
        )
        with self.assertRaisesRegex(SourceContractProposalError, "EXTERNAL_PUBLICATION_NOT_AUTHORIZED"):
            require_accepted_publication_authorization(validated)

        with tempfile.TemporaryDirectory() as directory:
            accepted_root = Path(directory) / "bundles/accepted"
            accepted = accept_local_candidate(validated, candidate, accepted_root, allow_historical=True)
            accepted_path = accepted_root / identity["generation"]
            self.assertEqual(accepted, identity)
            self.assertEqual((accepted_path / "content-manifest-core.json").read_bytes(), core.read_bytes())
            self.assertEqual((accepted_path / "snapshot-manifest.json").read_bytes(), snapshot.read_bytes())
            self.assertEqual(verify_candidate(accepted_path), identity)
            self.assertFalse((accepted_path / ".git").exists())
            copied = Path(directory) / "copied-away"
            shutil.copytree(accepted_path, copied)
            shim = Path(directory) / "no-git"
            shim.mkdir()
            (shim / "git").write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
            (shim / "sitecustomize.py").write_text(
                "import socket\n"
                "def blocked(*args, **kwargs):\n    raise RuntimeError('network blocked')\n"
                "socket.socket = blocked\n",
                encoding="utf-8",
            )
            os.chmod(shim / "git", 0o755)
            replay = subprocess.run(
                [sys.executable, "verify_bundle.py"],
                cwd=copied,
                env={"PATH": f"{shim}{os.pathsep}{os.environ.get('PATH', '')}", "PYTHONPATH": shim.as_posix()},
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            for relative in ("raw/parameter_emitter/param_emitter.py", "content-manifest-core.json", "snapshot-manifest.json", "verifier/specchoice_evidence/verify.py"):
                target = copied / relative
                target.write_bytes(target.read_bytes() + b"# tampered\n")
                replay = subprocess.run(
                    [sys.executable, "verify_bundle.py"], cwd=copied,
                    env={"PATH": f"{shim}{os.pathsep}{os.environ.get('PATH', '')}", "PYTHONPATH": shim.as_posix()},
                    check=False, capture_output=True, text=True,
                )
                self.assertNotEqual(replay.returncode, 0, relative)
                shutil.rmtree(copied)
                shutil.copytree(accepted_path, copied)
            with self.assertRaisesRegex(BundleError, "LOCAL_ACCEPTED_TARGET_EXISTS"):
                accept_local_candidate(validated, candidate, accepted_root, allow_historical=True)


if __name__ == "__main__":
    unittest.main()
