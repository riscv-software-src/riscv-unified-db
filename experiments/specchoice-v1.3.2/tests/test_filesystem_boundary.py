# SPDX-License-Identifier: BSD-3-Clause-Clear
from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import specchoice_evidence.filesystem as filesystem_module
from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.baseline import (
    BaselineError,
    capture_baseline,
    capture_committed_history,
    check_boundary,
    check_current_boundary,
    check_live_boundary,
    committed_boundary_projection,
    committed_boundary_projection_sha256,
    create_restart_baseline,
    load_baseline,
    path_is_allowed,
    validate_restart_lineage,
)
from specchoice_evidence.filesystem import (
    create_descriptor_directories,
    FilesystemPolicyError,
    inspect_authoritative_path,
    read_closed_authoritative_tree,
    read_authoritative_file,
    read_authoritative_files,
    reject_hardlink_dependency,
    require_relative_posix_path,
    replace_descriptor_file,
    write_new_descriptor_file,
)
from specchoice_evidence.cli import build_parser


class FilesystemBoundaryTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(["git", "-C", os.fspath(root), *args], check=True, stdout=subprocess.PIPE)

    def _commit(self, root: Path, message: str) -> str:
        self._git(
            root,
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "user.name=SpecChoice Test",
            "commit",
            "-m",
            message,
        )
        return subprocess.run(
            ["git", "-C", os.fspath(root), "rev-parse", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()

    def test_committed_out_of_allowlist_path_is_blocking(self) -> None:
        """A clean live worktree must not hide a post-baseline committed violation."""
        payload = {
            "allowlist": {"exact_files": [], "roots": ["experiments/specchoice-v1.3.2/"]},
            "file_kind_policy": {"allowed": ["directory", "regular_file"], "rejected": []},
            "index": {"staged_paths": []},
            "repository": {"head_commit": "", "path_basis": "repository_relative_posix"},
            "schema_version": "1",
            "worktree": {"ignored_paths_in_scope": [], "tracked_changes": [], "untracked_files": []},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args: str) -> None:
                subprocess.run(["git", "-C", os.fspath(root), *args], check=True, stdout=subprocess.PIPE)
            git("init")
            (root / "inside.txt").write_text("baseline", encoding="utf-8")
            git("add", "inside.txt")
            git("-c", "user.email=test@example.invalid", "-c", "user.name=SpecChoice Test", "commit", "-m", "baseline")
            payload["repository"]["head_commit"] = subprocess.run(
                ["git", "-C", os.fspath(root), "rev-parse", "HEAD"], check=True, stdout=subprocess.PIPE, text=True
            ).stdout.strip()
            baseline = root / "baseline.json"
            capture_baseline(baseline, payload)
            (root / "outside.txt").write_text("committed violation", encoding="utf-8")
            git("add", "outside.txt")
            git("-c", "user.email=test@example.invalid", "-c", "user.name=SpecChoice Test", "commit", "-m", "outside")
            result = check_boundary(root, baseline)
        self.assertEqual(result.blocking_violations, 1)
        self.assertEqual(result.classifications[0]["path"], "outside.txt")

    def test_committed_history_collects_all_change_kinds_and_rejects_raw_record_damage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init")
            for name in ("modified.txt", "deleted.txt", "type-change.txt"):
                (root / name).write_text("baseline", encoding="utf-8")
            self._git(root, "add", ".")
            baseline_commit = self._commit(root, "baseline")
            (root / "added.txt").write_text("added", encoding="utf-8")
            (root / "modified.txt").write_text("modified", encoding="utf-8")
            self._git(root, "rm", "deleted.txt")
            (root / "type-change.txt").unlink()
            os.symlink("modified.txt", root / "type-change.txt")
            self._git(root, "add", "-A")
            reviewed_commit = self._commit(root, "all changes")
            changes = capture_committed_history(root, baseline_commit, reviewed_commit)

        self.assertEqual(
            {(change.path, change.change_kind) for change in changes},
            {
                ("added.txt", "added"),
                ("modified.txt", "modified"),
                ("deleted.txt", "deleted"),
                ("type-change.txt", "type_changed"),
            },
        )

        def malformed_git(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
            command = _args[0]
            assert isinstance(command, list)
            if "merge-base" in command:
                return subprocess.CompletedProcess(command, 0)
            if "rev-list" in command and "--parents" in command:
                return subprocess.CompletedProcess(command, 0, stdout=(b"a" * 40) + b" " + (b"b" * 40) + b"\n")
            if "rev-list" in command:
                return subprocess.CompletedProcess(command, 0, stdout=(b"a" * 40) + b"\n")
            if "diff" in command:
                return subprocess.CompletedProcess(command, 0, stdout=b":100644 100644 a b M\0")
            return subprocess.CompletedProcess(command, 0, stdout=(b"a" * 40) + b"\n")

        with patch("specchoice_evidence.baseline.subprocess.run", side_effect=malformed_git):
            with self.assertRaisesRegex(BaselineError, "BOUNDARY_HISTORY_PARSE_ERROR"):
                capture_committed_history(Path("fixture"), "start", "reviewed")

    def test_reviewed_revision_must_exist_and_descend_from_the_baseline_commit(self) -> None:
        payload = {
            "allowlist": {"exact_files": [], "roots": []},
            "repository": {"head_commit": "", "path_basis": "repository_relative_posix"},
            "schema_version": "1",
            "worktree": {"ignored_paths_in_scope": [], "tracked_changes": [], "untracked_files": []},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init")
            (root / "shared.txt").write_text("initial", encoding="utf-8")
            self._git(root, "add", "shared.txt")
            initial = self._commit(root, "initial")
            (root / "main.txt").write_text("main", encoding="utf-8")
            self._git(root, "add", "main.txt")
            baseline_commit = self._commit(root, "baseline")
            payload["repository"]["head_commit"] = baseline_commit
            baseline = root / "baseline.json"
            capture_baseline(baseline, payload)
            self._git(root, "checkout", "-b", "other", initial)
            (root / "other.txt").write_text("other", encoding="utf-8")
            self._git(root, "add", "other.txt")
            other = self._commit(root, "other")
            with self.assertRaisesRegex(BaselineError, "BOUNDARY_HISTORY_REVISION_INVALID"):
                check_boundary(root, baseline, reviewed_revision="missing")
            with self.assertRaisesRegex(BaselineError, "BOUNDARY_HISTORY_NOT_DESCENDANT"):
                check_boundary(root, baseline, reviewed_revision=other)

    def test_committed_history_preserves_add_then_delete_and_blocks_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init")
            (root / "initial.txt").write_text("baseline", encoding="utf-8")
            self._git(root, "add", "initial.txt")
            baseline_commit = self._commit(root, "baseline")
            baseline = root / "baseline.json"
            capture_baseline(
                baseline,
                {
                    "allowlist": {"exact_files": [], "roots": []},
                    "repository": {"head_commit": baseline_commit, "path_basis": "repository_relative_posix"},
                    "schema_version": "1",
                    "worktree": {"ignored_paths_in_scope": [], "tracked_changes": [], "untracked_files": []},
                },
            )
            transient = root / "outside-transient.txt"
            transient.write_text("must remain attributable", encoding="utf-8")
            self._git(root, "add", transient.name)
            self._commit(root, "add outside path")
            self._git(root, "rm", transient.name)
            reviewed = self._commit(root, "delete outside path")

            events = [event for event in capture_committed_history(root, baseline_commit, reviewed) if event.path == transient.name]
            frozen = committed_boundary_projection(root, baseline, reviewed_revision=reviewed)
            current = check_current_boundary(root, baseline)

        self.assertEqual([event.change_kind for event in events], ["added", "deleted"])
        self.assertEqual(len({event.commit for event in events}), 2)
        by_path = {item["path"]: item for item in frozen["boundary_classifications"]}
        self.assertEqual(
            [event["change_kind"] for event in by_path["outside-transient.txt"]["committed_changes"]],
            ["added", "deleted"],
        )
        self.assertTrue(by_path["outside-transient.txt"]["blocking"])
        self.assertTrue({item["path"]: item for item in current.classifications}["outside-transient.txt"]["blocking"])

    def test_committed_projection_is_frozen_at_revision_and_live_gate_is_separate(self) -> None:
        """Later decision/receipt commits and live dirt cannot alter an already reviewed basis."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init")
            (root / "initial.txt").write_text("baseline", encoding="utf-8")
            self._git(root, "add", "initial.txt")
            baseline_commit = self._commit(root, "baseline")
            baseline = root / "baseline.json"
            capture_baseline(
                baseline,
                {
                    "allowlist": {"exact_files": [], "roots": ["experiments/"]},
                    "repository": {"head_commit": baseline_commit, "path_basis": "repository_relative_posix"},
                    "schema_version": "1",
                    "worktree": {"ignored_paths_in_scope": [], "tracked_changes": [], "untracked_files": []},
                },
            )
            (root / "experiments").mkdir()
            (root / "experiments" / "implementation.txt").write_text("reviewed", encoding="utf-8")
            self._git(root, "add", "experiments/implementation.txt")
            reviewed = self._commit(root, "reviewed implementation")
            frozen = committed_boundary_projection(root, baseline, reviewed_revision=reviewed)
            frozen_digest = committed_boundary_projection_sha256(frozen)
            (root / "experiments" / "decision.json").write_text("later", encoding="utf-8")
            (root / "experiments" / "receipt.json").write_text("later", encoding="utf-8")
            self._git(root, "add", "experiments")
            self._commit(root, "later reviewer files")
            self.assertEqual(committed_boundary_projection(root, baseline, reviewed_revision=reviewed), frozen)
            self.assertEqual(committed_boundary_projection_sha256(frozen), frozen_digest)
            self.assertEqual(check_current_boundary(root, baseline).blocking_violations, 0)
            (root / "outside-committed.txt").write_text("block", encoding="utf-8")
            self._git(root, "add", "outside-committed.txt")
            self._commit(root, "post-review out of boundary")
            # The frozen proposal stays exactly at R, while the current issuance/finalize
            # gate sees the clean-worktree committed violation.
            self.assertEqual(committed_boundary_projection(root, baseline, reviewed_revision=reviewed), frozen)
            current = check_current_boundary(root, baseline)
            self.assertEqual(current.blocking_violations, 1)
            self.assertTrue({item["path"]: item for item in current.classifications}["outside-committed.txt"]["blocking"])
            with self.assertRaisesRegex(BaselineError, "BOUNDARY_REVIEWED_REVISION_NOT_FULL"):
                committed_boundary_projection(root, baseline, reviewed_revision="HEAD")
            (root / "outside-live.txt").write_text("block", encoding="utf-8")
            (root / ".DS_Store").write_text("visible", encoding="utf-8")
            live = check_live_boundary(root, baseline)
            self.assertEqual(live.blocking_violations, 1)
            by_path = {item["path"]: item for item in live.classifications}
            self.assertTrue(by_path["outside-live.txt"]["blocking"])
            self.assertFalse(by_path[".DS_Store"]["blocking"])
            self.assertEqual(by_path[".DS_Store"]["diagnostic"], "DS_STORE_IGNORED_OS_METADATA")

    def test_preexisting_inventory_path_preserves_committed_and_live_provenance_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init")
            path = root / "preexisting.txt"
            path.write_text("baseline", encoding="utf-8")
            self._git(root, "add", "preexisting.txt")
            baseline_commit = self._commit(root, "baseline")
            baseline = root / "baseline.json"
            capture_baseline(
                baseline,
                {
                    "allowlist": {"exact_files": [], "roots": []},
                    "repository": {"head_commit": baseline_commit, "path_basis": "repository_relative_posix"},
                    "schema_version": "1",
                    "worktree": {
                        "ignored_paths_in_scope": [],
                        "tracked_changes": [
                            {
                                "path": "preexisting.txt",
                                "file_kind": "regular_file",
                                "byte_length": len(b"baseline"),
                                "sha256": sha256_bytes(b"baseline"),
                            }
                        ],
                        "untracked_files": [],
                    },
                },
            )
            path.write_text("committed", encoding="utf-8")
            self._git(root, "add", "preexisting.txt")
            self._commit(root, "committed change")
            path.write_text("staged", encoding="utf-8")
            self._git(root, "add", "preexisting.txt")
            path.write_text("worktree", encoding="utf-8")
            result = check_boundary(root, baseline)

        self.assertEqual(len(result.classifications), 1)
        record = result.classifications[0]
        self.assertEqual(record["path"], "preexisting.txt")
        self.assertEqual(record["change_sources"], ["committed_history", "staged", "worktree"])
        self.assertEqual(record["committed_change"]["change_kind"], "modified")
        self.assertEqual(record["live_changes"], [{"source": "staged"}, {"source": "worktree"}])

    def test_control_decision_binds_active_artifacts_and_requires_approval(self) -> None:
        experiment_root = Path(__file__).resolve().parents[1]
        baseline = experiment_root / "baselines/phase-start-v2.json"
        allowlist = experiment_root / "config/boundary_allowlist.json"
        policy = experiment_root / "baselines/ds-store-policy-override-v1.json"
        payload = {
            "allowlist": {"path": "config/boundary_allowlist.json", "sha256": sha256_bytes(allowlist.read_bytes())},
            "baseline": {"path": "baselines/phase-start-v2.json", "sha256": sha256_bytes(baseline.read_bytes())},
            "boundary_policy": {
                "path": "baselines/ds-store-policy-override-v1.json",
                "schema_version": "1",
                "sha256": sha256_bytes(policy.read_bytes()),
            },
            "disputes": [],
            "reviewer": {"disposition": "approved", "signal": "approved"},
            "schema_version": "1",
        }
        with tempfile.TemporaryDirectory() as directory:
            decision = Path(directory) / "control-decision.json"
            decision.write_bytes(canonical_json_bytes(payload))
            parser = build_parser()
            arguments = [
                "validate-control-decision",
                str(decision),
                "--baseline",
                "baselines/phase-start-v2.json",
                "--allowlist",
                "config/boundary_allowlist.json",
                "--policy-override",
                "baselines/ds-store-policy-override-v1.json",
            ]
            self.assertEqual(parser.parse_args(arguments).handler(parser.parse_args(arguments)), 0)
            payload["reviewer"]["disposition"] = "disputed"
            decision.write_bytes(canonical_json_bytes(payload))
            with self.assertRaisesRegex(BaselineError, "CONTROL_DECISION_NOT_APPROVED"):
                parser.parse_args(arguments).handler(parser.parse_args(arguments))

    def test_allowlist_is_exact_not_prefix(self) -> None:
        allowlist = {"roots": ["experiments/specchoice-v1.3.2/"], "exact_files": [".planning/STATE.md"]}
        self.assertTrue(path_is_allowed("experiments/specchoice-v1.3.2/a.txt", allowlist))
        self.assertFalse(path_is_allowed("experiments/specchoice-v1.3.2-escape/a.txt", allowlist))
        self.assertTrue(path_is_allowed(".planning/STATE.md", allowlist))

    def test_escape_and_symlink_fail_before_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "safe.txt").write_text("safe", encoding="utf-8")
            os.symlink("safe.txt", root / "link.txt")
            for invalid in ("../safe.txt", "/safe.txt", "safe\\x.txt"):
                with self.assertRaisesRegex(FilesystemPolicyError, "PATH_ESCAPE_DETECTED"):
                    require_relative_posix_path(invalid)
            with self.assertRaisesRegex(FilesystemPolicyError, "SYMLINK_REJECTED"):
                inspect_authoritative_path(root, "link.txt")

    def test_relative_posix_path_rejects_normalized_escape_syntax(self) -> None:
        for invalid in ("safe/.", "safe//child", "./safe", "safe/../outside"):
            with self.assertRaisesRegex(FilesystemPolicyError, "PATH_ESCAPE_DETECTED"):
                require_relative_posix_path(invalid)

    def test_regular_file_is_independent_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.txt").write_bytes(b"raw\r\nbytes")
            evidence = inspect_authoritative_path(root, "sample.txt")
            self.assertEqual(evidence.file_kind, "regular_file")
            self.assertEqual(evidence.byte_length, 10)
            self.assertEqual(evidence.hardlink_count, 1)

        with self.subTest("held root survives directory substitution"), tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            authority = parent / "authority"
            replacement = parent / "replacement"
            authority.mkdir()
            replacement.mkdir()
            for location, prefix in ((authority, "old"), (replacement, "new")):
                (location / "first.txt").write_text(f"{prefix}-first", encoding="utf-8")
                (location / "second.txt").write_text(f"{prefix}-second", encoding="utf-8")
            original = filesystem_module._read_held_regular_file
            swapped = False

            def read_then_swap(*args: object, **kwargs: object) -> bytes:
                nonlocal swapped
                value = original(*args, **kwargs)
                if not swapped:
                    swapped = True
                    os.rename(authority, parent / "retired")
                    os.rename(replacement, authority)
                return value

            with patch.object(filesystem_module, "_read_held_regular_file", side_effect=read_then_swap):
                try:
                    held = read_authoritative_files(authority, ["first.txt", "second.txt"])
                except FilesystemPolicyError as error:
                    self.assertEqual(str(error), "AUTHORITATIVE_ROOT_CHANGED")
                else:
                    self.assertEqual(held["first.txt"][1], b"old-first")
                    self.assertEqual(held["second.txt"][1], b"old-second")

        with self.subTest("held nested fixture survives directory substitution"), tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            authority = parent / "authority"
            fixture = authority / "raw/evaluation_fixtures/FIXTURE"
            replacement = parent / "replacement"
            fixture.mkdir(parents=True)
            replacement.mkdir()
            for location, prefix in ((fixture, "old"), (replacement, "new")):
                (location / "first.txt").write_text(f"{prefix}-first", encoding="utf-8")
                (location / "second.txt").write_text(f"{prefix}-second", encoding="utf-8")
            original = filesystem_module._read_held_regular_file
            swapped = False

            def read_then_swap_nested(*args: object, **kwargs: object) -> bytes:
                nonlocal swapped
                value = original(*args, **kwargs)
                if not swapped:
                    swapped = True
                    os.rename(fixture, authority / "raw/evaluation_fixtures/retired")
                    os.rename(replacement, fixture)
                return value

            with patch.object(filesystem_module, "_read_held_regular_file", side_effect=read_then_swap_nested):
                held = read_authoritative_files(
                    authority,
                    ["raw/evaluation_fixtures/FIXTURE/first.txt", "raw/evaluation_fixtures/FIXTURE/second.txt"],
                )
            self.assertEqual(held["raw/evaluation_fixtures/FIXTURE/first.txt"][1], b"old-first")
            self.assertEqual(held["raw/evaluation_fixtures/FIXTURE/second.txt"][1], b"old-second")

        with self.subTest("closed tree resists root substitution"), tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            authority = parent / "authority"
            replacement = parent / "replacement"
            authority.mkdir()
            replacement.mkdir()
            for location, prefix in ((authority, "old"), (replacement, "new")):
                (location / "first.txt").write_text(f"{prefix}-first", encoding="utf-8")
                (location / "second.txt").write_text(f"{prefix}-second", encoding="utf-8")
            original = filesystem_module._read_held_regular_file_evidence
            swapped = False

            def read_then_swap_tree(*args: object, **kwargs: object) -> tuple[os.stat_result, bytes]:
                nonlocal swapped
                value = original(*args, **kwargs)
                if not swapped:
                    swapped = True
                    os.rename(authority, parent / "retired")
                    os.rename(replacement, authority)
                return value

            with patch.object(filesystem_module, "_read_held_regular_file_evidence", side_effect=read_then_swap_tree):
                try:
                    held = read_closed_authoritative_tree(authority)
                except FilesystemPolicyError as error:
                    self.assertEqual(str(error), "AUTHORITATIVE_ROOT_CHANGED")
                else:
                    self.assertEqual(held["first.txt"][1], b"old-first")
                    self.assertEqual(held["second.txt"][1], b"old-second")

    def test_descriptor_backed_read_requires_no_follow_support(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.txt").write_bytes(b"raw\r\nbytes")
            evidence, content = read_authoritative_file(root, "sample.txt")
            self.assertEqual(evidence.sha256, sha256_bytes(content))
            self.assertEqual(content, b"raw\r\nbytes")
            with patch("specchoice_evidence.filesystem.os.O_NOFOLLOW", 0):
                with self.assertRaisesRegex(FilesystemPolicyError, "NOFOLLOW_UNAVAILABLE"):
                    read_authoritative_file(root, "sample.txt")

    def test_dirfd_reader_rejects_root_and_intermediate_rebind_without_escape(self) -> None:
        """A held authority directory must outlive lexical root/child replacement."""
        with self.subTest(operation="batch-bounded-read-rejects-static-oversize"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "large.yaml").write_bytes(b"x" * 65)
            read_calls = 0
            original_read = os.read

            def count_reads(descriptor: int, size: int) -> bytes:
                nonlocal read_calls
                if stat.S_ISREG(os.fstat(descriptor).st_mode):
                    read_calls += 1
                return original_read(descriptor, size)

            with patch("specchoice_evidence.filesystem.os.read", side_effect=count_reads), self.assertRaisesRegex(
                FilesystemPolicyError, "AUTHORITATIVE_FILE_TOO_LARGE"
            ):
                read_authoritative_files(root, ["large.yaml"], max_bytes=64)
            self.assertEqual(read_calls, 0)

        with self.subTest(operation="batch-bounded-read-stops-at-max-plus-one"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            limit = 64
            leaf = root / "growing.yaml"
            leaf.write_bytes(b"a" * limit)
            inode = leaf.stat().st_ino
            delivered = 0
            grew = False
            original_read = os.read

            def grow_during_read(descriptor: int, size: int) -> bytes:
                nonlocal delivered, grew
                if stat.S_ISREG(os.fstat(descriptor).st_mode) and os.fstat(descriptor).st_ino == inode:
                    if not grew:
                        grew = True
                        with leaf.open("ab") as stream:
                            stream.write(b"b" * 1024)
                    chunk = original_read(descriptor, size)
                    delivered += len(chunk)
                    return chunk
                return original_read(descriptor, size)

            with patch("specchoice_evidence.filesystem.os.read", side_effect=grow_during_read), self.assertRaisesRegex(
                FilesystemPolicyError, "AUTHORITATIVE_(FILE_CHANGED|FILE_TOO_LARGE)"
            ):
                read_authoritative_files(root, ["growing.yaml"], max_bytes=limit)
            self.assertTrue(grew)
            self.assertLessEqual(delivered, limit + 1)

        original_open = os.open
        for replaced_part in ("root", "nested"):
            with self.subTest(replaced_part=replaced_part), tempfile.TemporaryDirectory() as directory:
                parent = Path(directory)
                root = parent / "root"
                leaf = root / "nested" / "leaf.txt"
                leaf.parent.mkdir(parents=True)
                leaf.write_bytes(b"held-bytes")
                replacement = parent / "replacement"
                (replacement / "nested").mkdir(parents=True)
                (replacement / "nested" / "leaf.txt").write_bytes(b"replacement-bytes")
                triggered = False

                def rebind(path: object, flags: int, *args: object, **kwargs: object) -> int:
                    nonlocal triggered
                    # The hardened implementation opens the final component relative
                    # to a held parent; the old implementation opens the full path.
                    if not triggered and os.fspath(path) in {os.fspath(leaf), "leaf.txt"}:
                        triggered = True
                        if replaced_part == "root":
                            os.rename(root, parent / "old-root")
                            os.rename(replacement, root)
                        else:
                            os.rename(root / "nested", root / "old-nested")
                            os.rename(replacement / "nested", root / "nested")
                    return original_open(path, flags, *args, **kwargs)

                with patch("specchoice_evidence.filesystem.os.open", side_effect=rebind):
                    evidence, content = read_authoritative_file(root, "nested/leaf.txt")
                self.assertTrue(triggered)
                self.assertEqual(content, b"held-bytes")
                self.assertEqual(evidence.sha256, sha256_bytes(b"held-bytes"))

        # The two cutover writers must remain pinned to the original held parent
        # even if a concurrent pathname rebind happens between write and replace.
        for operation in ("create", "replace"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                parent = Path(directory)
                root = parent / "root"
                root.mkdir()
                leaf = root / "authority.json"
                if operation == "replace":
                    leaf.write_bytes(b"v2")
                replacement = parent / "replacement"
                replacement.mkdir()
                triggered = False
                original_open = os.open

                def rebind(path: object, flags: int, *args: object, **kwargs: object) -> int:
                    nonlocal triggered
                    if not triggered and os.fspath(path) in {"authority.json", ".authority.json.cutover"}:
                        triggered = True
                        os.rename(root, parent / "old-root")
                        os.rename(replacement, root)
                    return original_open(path, flags, *args, **kwargs)

                with patch("specchoice_evidence.filesystem.os.open", side_effect=rebind):
                    if operation == "create":
                        write_new_descriptor_file(root, "authority.json", b"v3")
                    else:
                        replace_descriptor_file(root, "authority.json", b"v3", b"v2")
                self.assertTrue(triggered)
                self.assertEqual((parent / "old-root" / "authority.json").read_bytes(), b"v3")
                self.assertFalse((root / "authority.json").exists())

        with self.subTest(operation="recoverable-directory-create"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_descriptor_directories(root, ("config/fixture-repairs/v3", "receipts"))
            create_descriptor_directories(root, ("config/fixture-repairs/v3", "receipts"))
            write_new_descriptor_file(root, "config/fixture-repairs/v3/gold.yaml", b"gold")
            self.assertEqual((root / "config/fixture-repairs/v3/gold.yaml").read_bytes(), b"gold")

        with self.subTest(operation="directory-create-held-root"), tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "root"
            replacement = parent / "replacement"
            root.mkdir()
            replacement.mkdir()
            original_mkdir = os.mkdir
            triggered = False

            def rebind_mkdir(path: object, *args: object, **kwargs: object) -> None:
                nonlocal triggered
                if not triggered and os.fspath(path) == "config":
                    triggered = True
                    os.rename(root, parent / "old-root")
                    os.rename(replacement, root)
                original_mkdir(path, *args, **kwargs)

            with patch("specchoice_evidence.filesystem.os.mkdir", side_effect=rebind_mkdir):
                create_descriptor_directories(root, ("config/nested",))
            self.assertTrue(triggered)
            self.assertTrue((parent / "old-root/config/nested").is_dir())
            self.assertFalse((root / "config").exists())

        with self.subTest(operation="directory-create-rejects-symlink"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "outside").mkdir()
            (root / "config").symlink_to(root / "outside", target_is_directory=True)
            with self.assertRaisesRegex(FilesystemPolicyError, "SYMLINK_REJECTED"):
                create_descriptor_directories(root, ("config/nested",))

        payloads = {"config/first.json": b"first", "receipts/second.json": b"second"}
        with self.subTest(operation="batch-opens-authority-root-once"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(
                filesystem_module, "_directory_components", wraps=filesystem_module._directory_components,
            ) as open_root:
                filesystem_module.write_exact_descriptor_files(root, payloads)
            self.assertEqual(open_root.call_count, 1)

        with self.subTest(operation="batch-preflight-to-mkdir-root-rebind"), tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "root"
            replacement = parent / "replacement"
            root.mkdir()
            replacement.mkdir()
            original_mkdir = os.mkdir
            triggered = False

            def rebind_batch_mkdir(path: object, *args: object, **kwargs: object) -> None:
                nonlocal triggered
                if not triggered and os.fspath(path) in {"config", "receipts"}:
                    triggered = True
                    os.rename(root, parent / "old-root")
                    os.rename(replacement, root)
                original_mkdir(path, *args, **kwargs)

            with patch("specchoice_evidence.filesystem.os.mkdir", side_effect=rebind_batch_mkdir):
                try:
                    filesystem_module.write_exact_descriptor_files(root, payloads)
                except FilesystemPolicyError:
                    pass
            self.assertTrue(triggered)
            self.assertFalse(any((root / relative).exists() for relative in payloads))

        with self.subTest(operation="batch-write-to-postflight-root-rebind"), tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "root"
            replacement = parent / "replacement"
            root.mkdir()
            replacement.mkdir()
            original_read = os.read
            triggered = False

            def rebind_on_postflight(descriptor: int, size: int) -> bytes:
                nonlocal triggered
                if not triggered and stat.S_ISREG(os.fstat(descriptor).st_mode):
                    triggered = True
                    os.rename(root, parent / "old-root")
                    os.rename(replacement, root)
                return original_read(descriptor, size)

            with patch("specchoice_evidence.filesystem.os.read", side_effect=rebind_on_postflight):
                try:
                    filesystem_module.write_exact_descriptor_files(root, payloads)
                except FilesystemPolicyError:
                    pass
            self.assertTrue(triggered)
            self.assertFalse(any((root / relative).exists() for relative in payloads))

        with self.subTest(operation="batch-cross-leaf-postflight-mutation"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "config/first.json"
            second = root / "receipts/second.json"
            original_read = os.read
            first_read = False
            triggered = False

            def mutate_prior_leaf(descriptor: int, size: int) -> bytes:
                nonlocal first_read, triggered
                details = os.fstat(descriptor)
                if first.exists() and details.st_ino == first.stat().st_ino:
                    chunk = original_read(descriptor, size)
                    first_read = first_read or bool(chunk)
                    return chunk
                if second.exists() and details.st_ino == second.stat().st_ino and first_read and not triggered:
                    triggered = True
                    first.write_bytes(b"other")
                return original_read(descriptor, size)

            with patch("specchoice_evidence.filesystem.os.read", side_effect=mutate_prior_leaf), self.assertRaisesRegex(
                FilesystemPolicyError, "AUTHORITATIVE_(POSTWRITE_MISMATCH|FILE_CHANGED)"
            ):
                filesystem_module.write_exact_descriptor_files(root, payloads)
            self.assertTrue(triggered)

        with self.subTest(operation="batch-cross-leaf-verification-mutation"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "config/first.json"
            original_stat = os.stat
            first_verified = False
            triggered = False

            def mutate_after_first_verification(path: object, *args: object, **kwargs: object) -> os.stat_result:
                nonlocal first_verified, triggered
                result = original_stat(path, *args, **kwargs)
                if os.fspath(path) == "first.json" and stat.S_ISREG(result.st_mode):
                    first_verified = True
                elif os.fspath(path) == "second.json" and first_verified and not triggered:
                    triggered = True
                    first.write_bytes(b"other")
                return result

            with patch("specchoice_evidence.filesystem.os.stat", side_effect=mutate_after_first_verification), self.assertRaisesRegex(
                FilesystemPolicyError, "AUTHORITATIVE_POSTWRITE_MISMATCH"
            ):
                filesystem_module.write_exact_descriptor_files(root, payloads)
            self.assertTrue(triggered)

        with self.subTest(operation="batch-fsync-failure-removes-unproven-leaf"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_fsync = os.fsync

            def fail_regular_fsync(descriptor: int) -> None:
                if stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise OSError("fsync failed")
                original_fsync(descriptor)

            with patch("specchoice_evidence.filesystem.os.fsync", side_effect=fail_regular_fsync), self.assertRaisesRegex(
                FilesystemPolicyError, "AUTHORITATIVE_WRITE_INVALID"
            ):
                filesystem_module.write_exact_descriptor_files(root, {"config/only.json": b"payload"})
            self.assertFalse((root / "config/only.json").exists())

        with self.subTest(operation="batch-short-write-removes-partial-leaf"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def partial_then_fail(descriptor: int, content: bytes) -> None:
                os.write(descriptor, content[:1])
                raise OSError("short write")

            with patch.object(filesystem_module, "_write_all", side_effect=partial_then_fail), self.assertRaisesRegex(
                FilesystemPolicyError, "AUTHORITATIVE_WRITE_INVALID"
            ):
                filesystem_module.write_exact_descriptor_files(root, {"config/only.json": b"payload"})
            self.assertFalse((root / "config/only.json").exists())

        with self.subTest(operation="batch-existing-resume-is-durable"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative, raw in payloads.items():
                leaf = root / relative
                leaf.parent.mkdir(parents=True, exist_ok=True)
                leaf.write_bytes(raw)
            synced_modes: list[int] = []
            original_fsync = os.fsync

            def record_fsync(descriptor: int) -> None:
                synced_modes.append(stat.S_IFMT(os.fstat(descriptor).st_mode))
                original_fsync(descriptor)

            with patch("specchoice_evidence.filesystem.os.fsync", side_effect=record_fsync):
                filesystem_module.write_exact_descriptor_files(root, payloads)
            self.assertIn(stat.S_IFREG, synced_modes)
            self.assertIn(stat.S_IFDIR, synced_modes)

    def test_dirfd_reader_rejects_regular_to_fifo_immediate_open_without_blocking(self) -> None:
        """The final no-follow open must be nonblocking before a FIFO can be consumed."""
        original_open = os.open
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaf = root / "leaf.txt"
            leaf.write_bytes(b"regular")
            triggered = False

            def replace_with_fifo(path: object, flags: int, *args: object, **kwargs: object) -> int:
                nonlocal triggered
                if not triggered and os.fspath(path) in {os.fspath(leaf), "leaf.txt"}:
                    triggered = True
                    self.assertNotEqual(flags & os.O_NONBLOCK, 0, "final open must be nonblocking")
                    leaf.unlink()
                    os.mkfifo(leaf)
                return original_open(path, flags, *args, **kwargs)

            with patch("specchoice_evidence.filesystem.os.open", side_effect=replace_with_fifo):
                with self.assertRaisesRegex(FilesystemPolicyError, "SPECIAL_FILE_KIND_REJECTED"):
                    read_authoritative_file(root, "leaf.txt")
            self.assertTrue(triggered)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "leaf.txt"
            existing.write_bytes(b"existing")
            with self.assertRaisesRegex(FilesystemPolicyError, "AUTHORITATIVE_DESTINATION_EXISTS"):
                write_new_descriptor_file(root, "leaf.txt", b"new")
            self.assertEqual(existing.read_bytes(), b"existing")
            os.unlink(existing)
            os.symlink("elsewhere", existing)
            with self.assertRaisesRegex(FilesystemPolicyError, "SYMLINK_REJECTED"):
                replace_descriptor_file(root, "leaf.txt", b"new", b"existing")
            os.unlink(existing)
            os.mkfifo(existing)
            with self.assertRaisesRegex(FilesystemPolicyError, "SPECIAL_FILE_KIND_REJECTED"):
                replace_descriptor_file(root, "leaf.txt", b"new", b"existing")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("specchoice_evidence.filesystem.os.fsync", side_effect=OSError("fsync")):
                with self.assertRaisesRegex(FilesystemPolicyError, "AUTHORITATIVE_WRITE_INVALID"):
                    write_new_descriptor_file(root, "leaf.txt", b"new")
            (root / "leaf.txt").unlink()
            (root / "leaf.txt").write_bytes(b"old")
            with patch("specchoice_evidence.filesystem.os.replace", side_effect=OSError("replace")):
                with self.assertRaisesRegex(FilesystemPolicyError, "AUTHORITATIVE_WRITE_INVALID"):
                    replace_descriptor_file(root, "leaf.txt", b"new", b"old")
            self.assertEqual((root / "leaf.txt").read_bytes(), b"old")

            # A crash may leave the already-fsynced exact temporary payload. It is
            # reusable, but every other temporary form is an immutable failure.
            temporary = root / ".leaf.txt.cutover"
            temporary.write_bytes(b"new")
            replace_descriptor_file(root, "leaf.txt", b"new", b"old")
            self.assertEqual((root / "leaf.txt").read_bytes(), b"new")

        for maker, code in (
            (lambda path: path.write_bytes(b"wrong"), "AUTHORITATIVE_TEMPORARY_MISMATCH"),
            (lambda path: os.symlink("leaf.txt", path), "SYMLINK_REJECTED"),
            (lambda path: os.mkfifo(path), "SPECIAL_FILE_KIND_REJECTED"),
        ):
            with self.subTest(crash_temporary=code), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                leaf = root / "leaf.txt"
                temporary = root / ".leaf.txt.cutover"
                leaf.write_bytes(b"old")
                maker(temporary)
                with self.assertRaisesRegex(FilesystemPolicyError, code):
                    replace_descriptor_file(root, "leaf.txt", b"new", b"old")
                self.assertTrue(temporary.exists() or temporary.is_symlink())
                self.assertEqual(leaf.read_bytes(), b"old")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaf = root / "leaf.txt"
            leaf.write_bytes(b"old")
            with self.assertRaisesRegex(FilesystemPolicyError, "AUTHORITATIVE_TARGET_MISMATCH"):
                replace_descriptor_file(root, "leaf.txt", b"new", b"different")
            self.assertEqual(leaf.read_bytes(), b"old")
            with patch("specchoice_evidence.filesystem.os.write", return_value=0):
                with self.assertRaisesRegex(FilesystemPolicyError, "AUTHORITATIVE_WRITE_INVALID"):
                    replace_descriptor_file(root, "leaf.txt", b"new", b"old")
            self.assertTrue((root / ".leaf.txt.cutover").exists())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaf = root / "leaf.txt"
            temporary = root / ".leaf.txt.cutover"
            leaf.write_bytes(b"old")
            temporary.write_bytes(b"new")

            def change_target(*_args: object, **_kwargs: object) -> None:
                leaf.write_bytes(b"changed")

            with patch("specchoice_evidence.filesystem._fsync_held_regular_file", side_effect=change_target):
                with self.assertRaisesRegex(FilesystemPolicyError, "AUTHORITATIVE_TARGET_MISMATCH"):
                    replace_descriptor_file(root, "leaf.txt", b"new", b"old")
            self.assertEqual(leaf.read_bytes(), b"changed")
            self.assertEqual(temporary.read_bytes(), b"new")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaf = root / "leaf.txt"
            temporary = root / ".leaf.txt.cutover"
            leaf.write_bytes(b"old")
            temporary.write_bytes(b"new")

            def change_temporary(*_args: object, **_kwargs: object) -> None:
                temporary.write_bytes(b"changed")

            with patch("specchoice_evidence.filesystem._fsync_held_regular_file", side_effect=change_temporary):
                with self.assertRaisesRegex(FilesystemPolicyError, "AUTHORITATIVE_TEMPORARY_MISMATCH"):
                    replace_descriptor_file(root, "leaf.txt", b"new", b"old")
            self.assertEqual(leaf.read_bytes(), b"old")
            self.assertEqual(temporary.read_bytes(), b"changed")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaf = root / "leaf.txt"
            temporary_source = root / "temporary-source"
            temporary = root / ".leaf.txt.cutover"
            leaf.write_bytes(b"old")
            temporary_source.write_bytes(b"new")
            os.link(temporary_source, temporary)
            with self.assertRaisesRegex(FilesystemPolicyError, "HARDLINK_DEPENDENCY_REJECTED"):
                replace_descriptor_file(root, "leaf.txt", b"new", b"old")
            self.assertEqual(leaf.read_bytes(), b"old")
            self.assertEqual(temporary.read_bytes(), b"new")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaf = root / "leaf.txt"
            temporary = root / ".leaf.txt.cutover"
            leaf.write_bytes(b"old")
            temporary.write_bytes(b"new")
            original_read = filesystem_module._read_held_regular_file
            target_reads = 0

            def change_temp_during_final_target_check(
                parent: int, name: str, accepted_device: int, **kwargs: object,
            ) -> bytes:
                nonlocal target_reads
                result = original_read(parent, name, accepted_device, **kwargs)
                if name == "leaf.txt":
                    target_reads += 1
                    if target_reads == 2:
                        temporary.write_bytes(b"changed")
                return result

            with patch(
                "specchoice_evidence.filesystem._read_held_regular_file",
                side_effect=change_temp_during_final_target_check,
            ):
                with self.assertRaisesRegex(FilesystemPolicyError, "AUTHORITATIVE_TEMPORARY_MISMATCH"):
                    replace_descriptor_file(root, "leaf.txt", b"new", b"old")
            self.assertEqual(target_reads, 2)
            self.assertEqual(leaf.read_bytes(), b"old")
            self.assertEqual(temporary.read_bytes(), b"changed")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaf = root / "leaf.txt"
            leaf.write_bytes(b"old")
            with patch("specchoice_evidence.filesystem.os.fsync", side_effect=OSError("fsync")):
                with self.assertRaisesRegex(FilesystemPolicyError, "AUTHORITATIVE_WRITE_INVALID"):
                    replace_descriptor_file(root, "leaf.txt", b"new", b"old")
            self.assertEqual(leaf.read_bytes(), b"old")
            self.assertEqual((root / ".leaf.txt.cutover").read_bytes(), b"new")

    def test_hardlink_dependency_is_rejected_without_rejecting_independent_bytes(self) -> None:
        with self.assertRaisesRegex(FilesystemPolicyError, "HARDLINK_DEPENDENCY_REJECTED"):
            reject_hardlink_dependency(True)
        reject_hardlink_dependency(False)

    def test_regular_hardlink_remains_independently_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.bin"
            source.write_bytes(b"independent content")
            os.link(source, root / "linked.bin")
            evidence = inspect_authoritative_path(root, "linked.bin")
        self.assertEqual(evidence.file_kind, "regular_file")
        self.assertEqual(evidence.hardlink_count, 2)
        self.assertEqual(evidence.byte_length, len(b"independent content"))

    def test_fifo_and_unproven_mount_boundary_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            os.mkfifo(root / "evidence.fifo")
            with self.assertRaisesRegex(FilesystemPolicyError, "SPECIAL_FILE_KIND_REJECTED"):
                inspect_authoritative_path(root, "evidence.fifo")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            root.mkdir()
            (root / "mounted").mkdir()
            with patch(
                "specchoice_evidence.filesystem._open_directory",
                side_effect=FilesystemPolicyError("MOUNT_BOUNDARY_UNPROVEN"),
            ):
                with self.assertRaisesRegex(FilesystemPolicyError, "MOUNT_BOUNDARY_UNPROVEN"):
                    inspect_authoritative_path(root, "mounted")

    def test_baseline_refuses_overwrite_and_requires_canonical_bytes(self) -> None:
        payload = {
            "schema_version": "1",
            "allowlist": {"roots": ["experiments/specchoice-v1.3.2/"], "exact_files": []},
            "worktree": {"tracked_changes": [], "untracked_files": [], "ignored_paths_in_scope": []},
        }
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / "baseline.json"
            capture_baseline(baseline, payload)
            load_baseline(baseline)
            with self.assertRaisesRegex(BaselineError, "BASELINE_ALREADY_EXISTS"):
                capture_baseline(baseline, payload)
            baseline.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(BaselineError, "BASELINE_NOT_CANONICAL"):
                load_baseline(baseline)

    def test_baseline_entries_require_stable_path_ordering(self) -> None:
        payload = {
            "schema_version": "1",
            "allowlist": {"roots": ["experiments/specchoice-v1.3.2/"], "exact_files": []},
            "worktree": {
                "tracked_changes": [],
                "untracked_files": [
                    {"path": "z.txt", "file_kind": "regular_file", "byte_length": 1, "sha256": "a" * 64},
                    {"path": "a.txt", "file_kind": "regular_file", "byte_length": 1, "sha256": "a" * 64},
                ],
                "ignored_paths_in_scope": [],
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / "baseline.json"
            baseline.write_bytes(canonical_json_bytes(payload))
            with self.assertRaisesRegex(BaselineError, "BASELINE_PATHS_NOT_SORTED"):
                load_baseline(baseline)

    def test_new_outside_allowlist_is_blocking(self) -> None:
        payload = {
            "schema_version": "1",
            "allowlist": {"roots": ["experiments/specchoice-v1.3.2/"], "exact_files": []},
            "worktree": {"tracked_changes": [], "untracked_files": [], "ignored_paths_in_scope": []},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline.json"
            capture_baseline(baseline, payload)
            (root / "outside.txt").write_text("outside", encoding="utf-8")
            with patch("specchoice_evidence.baseline.capture_current_paths", return_value={"outside.txt"}):
                result = check_boundary(root, baseline)
        self.assertEqual(result.blocking_violations, 1)
        self.assertEqual(result.classifications[0]["status"], "new_out_of_boundary")

    def test_restart_retains_original_inventory_without_reclassification(self) -> None:
        payload = {
            "schema_version": "1",
            "allowlist": {"roots": ["experiments/specchoice-v1.3.2/"], "exact_files": []},
            "file_kind_policy": {"allowed": ["directory", "regular_file"], "rejected": []},
            "index": {"staged_paths": []},
            "repository": {"head_commit": "a" * 40, "path_basis": "repository_relative_posix"},
            "worktree": {
                "tracked_changes": [],
                "untracked_files": [{"path": ".DS_Store", "file_kind": "regular_file", "byte_length": 1, "sha256": "b" * 64}],
                "ignored_paths_in_scope": [],
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            v1 = root / "phase-start-v1.json"
            v2 = root / "phase-start-v2.json"
            parent_hash = capture_baseline(v1, payload)
            restart_hash, returned_parent = create_restart_baseline(
                v1,
                v2,
                previous_reference="phase-start-v1.json",
                reason_code="D15_RESTART_NEW_OUT_OF_BOUNDARY",
                remediation={"removed_path": "experiments/.DS_Store"},
            )
            self.assertEqual(returned_parent, parent_hash)
            self.assertNotEqual(restart_hash, parent_hash)
            self.assertEqual(validate_restart_lineage(v2, v1), (restart_hash, parent_hash))
            self.assertEqual(v1.read_bytes(), canonical_json_bytes(payload))
            successor = json.loads(v2.read_text(encoding="utf-8"))
            successor["worktree"]["untracked_files"] = []
            v2.write_bytes(canonical_json_bytes(successor))
            with self.assertRaisesRegex(BaselineError, "RESTART_RECLASSIFICATION_DETECTED"):
                validate_restart_lineage(v2, v1)

    def test_modified_preexisting_path_outside_allowlist_blocks(self) -> None:
        payload = {
            "schema_version": "1",
            "allowlist": {"roots": ["experiments/specchoice-v1.3.2/"], "exact_files": []},
            "worktree": {
                "tracked_changes": [],
                "untracked_files": [
                    {
                        "path": "outside.txt",
                        "file_kind": "regular_file",
                        "byte_length": 3,
                        "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                    }
                ],
                "ignored_paths_in_scope": [],
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline.json"
            capture_baseline(baseline, payload)
            (root / "outside.txt").write_text("changed", encoding="utf-8")
            with patch("specchoice_evidence.baseline.capture_current_paths", return_value={"outside.txt"}):
                result = check_boundary(root, baseline)
        self.assertEqual(result.blocking_violations, 1)
        self.assertEqual(result.classifications[0]["status"], "modified_out_of_boundary")

    def test_ds_store_churn_is_visible_but_nonblocking(self) -> None:
        payload = {
            "schema_version": "1",
            "allowlist": {"roots": ["experiments/specchoice-v1.3.2/"], "exact_files": []},
            "worktree": {
                "tracked_changes": [],
                "untracked_files": [
                    {"path": ".DS_Store", "file_kind": "regular_file", "byte_length": 3, "sha256": "b" * 64},
                    {"path": "outside.txt", "file_kind": "regular_file", "byte_length": 3, "sha256": "b" * 64},
                ],
                "ignored_paths_in_scope": [],
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline.json"
            capture_baseline(baseline, payload)
            (root / ".DS_Store").write_bytes(b"changed")
            (root / "outside.txt").write_bytes(b"changed")
            with patch(
                "specchoice_evidence.baseline.capture_current_paths",
                return_value={".DS_Store", "outside.txt"},
            ):
                result = check_boundary(root, baseline)
        by_path = {item["path"]: item for item in result.classifications}
        self.assertEqual(by_path[".DS_Store"]["status"], "modified_out_of_boundary")
        self.assertFalse(by_path[".DS_Store"]["blocking"])
        self.assertFalse(by_path[".DS_Store"]["attributed_to_phase"])
        self.assertEqual(by_path[".DS_Store"]["diagnostic"], "DS_STORE_IGNORED_OS_METADATA")
        self.assertTrue(by_path["outside.txt"]["blocking"])
        self.assertEqual(result.blocking_violations, 1)

    def test_new_and_deleted_ds_store_are_visible_but_nonblocking(self) -> None:
        payload = {
            "schema_version": "1",
            "allowlist": {"roots": ["experiments/specchoice-v1.3.2/"], "exact_files": []},
            "worktree": {
                "tracked_changes": [],
                "untracked_files": [
                    {"path": "removed/.DS_Store", "file_kind": "regular_file", "byte_length": 3, "sha256": "b" * 64}
                ],
                "ignored_paths_in_scope": [],
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline.json"
            capture_baseline(baseline, payload)
            (root / "new").mkdir()
            (root / "new" / ".DS_Store").write_bytes(b"new")
            with patch(
                "specchoice_evidence.baseline.capture_current_paths",
                return_value={"new/.DS_Store"},
            ):
                result = check_boundary(root, baseline)
        by_path = {item["path"]: item for item in result.classifications}
        self.assertEqual(by_path["removed/.DS_Store"]["status"], "deleted_out_of_boundary")
        self.assertEqual(by_path["new/.DS_Store"]["status"], "new_out_of_boundary")
        self.assertTrue(all(not item["blocking"] for item in by_path.values()))
