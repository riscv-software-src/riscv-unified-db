# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Behavior contract for the forward-only publication authority."""

from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.publication import (
    PublicationContractError,
    resolve_historical_path,
    validate_publication_manifest,
)


def git(*arguments: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class PublicationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary.name)
        git("init", "-q", cwd=self.repository)
        git("config", "user.email", "test@example.invalid", cwd=self.repository)
        git("config", "user.name", "SpecChoice test", cwd=self.repository)
        self.experiment = self.repository / "experiments/specchoice-v1.3.2"
        self.runtime = self.experiment / "src/example.py"
        self.test = self.experiment / "tests/test_example.py"
        self.runtime.parent.mkdir(parents=True)
        self.test.parent.mkdir(parents=True)
        self.runtime.write_text("VALUE = 1\n", encoding="utf-8")
        self.test.write_text("# validation consumer\n", encoding="utf-8")
        git("add", self.runtime.as_posix(), self.test.as_posix(), cwd=self.repository)
        git("commit", "-q", "-m", "fixture", cwd=self.repository)
        self.upstream_base = git("rev-parse", "HEAD", cwd=self.repository)
        self.manifest_path = self.experiment / "evidence/publication-manifest-v1.json"
        self.manifest = self._valid_manifest()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _entry(self, path: Path, role: str, consumer: str) -> dict[str, object]:
        return {
            "path": path.relative_to(self.repository).as_posix(),
            "sha256": sha256_bytes(path.read_bytes()),
            "role": role,
            "consumers": [consumer],
        }

    def _valid_manifest(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "publication": {
                "upstream_base_commit": self.upstream_base,
                "paths": [
                    self._entry(self.runtime, "runtime", "tests/test_example.py"),
                    self._entry(
                        self.test,
                        "validation",
                        "python3 -m unittest discover -s tests -p test_*.py",
                    ),
                ],
            },
            "historical_evidence": {"commits": [], "mappings": []},
            "policy": {
                "experiment_root": "experiments/specchoice-v1.3.2",
                "prohibited_repository_root_dependencies": [".planning/"],
                "tracked_package_files_must_match_inventory": True,
                "ambient_custom_refs_prohibited": True,
            },
        }

    def _write(self, value: dict[str, object] | None = None) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_bytes(canonical_json_bytes(value or self.manifest))

    def _updated_hash(self, manifest: dict[str, object], path: Path) -> None:
        relative = path.relative_to(self.repository).as_posix()
        publication = manifest["publication"]
        assert isinstance(publication, dict)
        entries = publication["paths"]
        assert isinstance(entries, list)
        for entry in entries:
            if isinstance(entry, dict) and entry.get("path") == relative:
                entry["sha256"] = sha256_bytes(path.read_bytes())
                return
        self.fail(f"missing manifest entry for {relative}")

    def test_unsupported_schema_version_fails_closed(self) -> None:
        self.manifest["schema_version"] = 2
        self._write()

        with self.assertRaisesRegex(
            PublicationContractError, "PUBLICATION_MANIFEST_SCHEMA_UNSUPPORTED"
        ):
            validate_publication_manifest(self.repository, self.manifest_path)

    def test_changed_declared_hash_fails_closed(self) -> None:
        self._write()
        self.runtime.write_text("VALUE = 2\n", encoding="utf-8")

        with self.assertRaisesRegex(
            PublicationContractError, "PUBLICATION_FILE_HASH_MISMATCH"
        ):
            validate_publication_manifest(self.repository, self.manifest_path)

    def test_missing_declared_tracked_file_fails_closed(self) -> None:
        self._write()
        self.runtime.unlink()

        with self.assertRaisesRegex(
            PublicationContractError, "PUBLICATION_FILE_MISSING"
        ):
            validate_publication_manifest(self.repository, self.manifest_path)

    def test_undeclared_tracked_package_file_fails_closed(self) -> None:
        extra = self.experiment / "config/undeclared.json"
        extra.parent.mkdir(parents=True)
        extra.write_text("{}\n", encoding="utf-8")
        git("add", extra.as_posix(), cwd=self.repository)
        git("commit", "-q", "-m", "undeclared", cwd=self.repository)
        self._write()

        with self.assertRaisesRegex(
            PublicationContractError, "PUBLICATION_INVENTORY_MISMATCH"
        ):
            validate_publication_manifest(self.repository, self.manifest_path)

    def test_every_path_requires_a_concrete_consumer(self) -> None:
        publication = self.manifest["publication"]
        assert isinstance(publication, dict)
        paths = publication["paths"]
        assert isinstance(paths, list) and isinstance(paths[0], dict)
        paths[0]["consumers"] = []
        self._write()

        with self.assertRaisesRegex(
            PublicationContractError, "PUBLICATION_CONSUMER_REQUIRED"
        ):
            validate_publication_manifest(self.repository, self.manifest_path)

    def test_runtime_cannot_depend_on_repository_root_planning(self) -> None:
        self.runtime.write_text(
            'PLAN = ".planning/ROADMAP.md"\n', encoding="utf-8"
        )
        self._updated_hash(self.manifest, self.runtime)
        self._write()

        with self.assertRaisesRegex(
            PublicationContractError, "PROHIBITED_REPOSITORY_ROOT_DEPENDENCY"
        ):
            validate_publication_manifest(self.repository, self.manifest_path)

    def test_runtime_cannot_require_an_ambient_custom_ref(self) -> None:
        self.runtime.write_text(
            'REF = "refs/specchoice/pr-2164-head"\n', encoding="utf-8"
        )
        self._updated_hash(self.manifest, self.runtime)
        self._write()

        with self.assertRaisesRegex(
            PublicationContractError, "AMBIENT_CUSTOM_REF_DEPENDENCY"
        ):
            validate_publication_manifest(self.repository, self.manifest_path)

    def test_unavailable_historical_commit_is_reported_not_available(self) -> None:
        historical = self.manifest["historical_evidence"]
        assert isinstance(historical, dict)
        historical["commits"] = [
            {"commit_sha": "f" * 40, "tree_sha": "e" * 40, "role": "old_snapshot"}
        ]
        self._write()

        result = validate_publication_manifest(self.repository, self.manifest_path)

        self.assertEqual(result["status"], "valid")
        self.assertEqual(
            result["historical_provenance"],
            [{"commit_sha": "f" * 40, "status": "not_available"}],
        )

    def test_available_contradictory_historical_commit_fails_closed(self) -> None:
        historical = self.manifest["historical_evidence"]
        assert isinstance(historical, dict)
        historical["commits"] = [
            {
                "commit_sha": self.upstream_base,
                "tree_sha": "0" * 40,
                "role": "old_snapshot",
            }
        ]
        self._write()

        with self.assertRaisesRegex(
            PublicationContractError, "HISTORICAL_PROVENANCE_CONTRADICTORY"
        ):
            validate_publication_manifest(self.repository, self.manifest_path)

    def test_archive_mapping_hash_is_a_blocking_integrity_gate(self) -> None:
        archive = self.experiment / "evidence/archive/repository-root/.planning/ROADMAP.md"
        archive.parent.mkdir(parents=True)
        archive.write_text("# frozen roadmap\n", encoding="utf-8")
        git("add", archive.as_posix(), cwd=self.repository)
        git("commit", "-q", "-m", "archive", cwd=self.repository)
        publication = self.manifest["publication"]
        historical = self.manifest["historical_evidence"]
        assert isinstance(publication, dict) and isinstance(historical, dict)
        paths = publication["paths"]
        assert isinstance(paths, list)
        paths.append(self._entry(archive, "historical_input", "legacy:.planning/ROADMAP.md"))
        historical["mappings"] = [
            {
                "legacy_path": ".planning/ROADMAP.md",
                "archive_path": archive.relative_to(self.repository).as_posix(),
                "sha256": sha256_bytes(b"different\n"),
            }
        ]
        self._write()

        with self.assertRaisesRegex(
            PublicationContractError, "HISTORICAL_ARCHIVE_HASH_MISMATCH"
        ):
            validate_publication_manifest(self.repository, self.manifest_path)

    def test_publication_mapping_cannot_be_shadowed_by_ambient_planning(self) -> None:
        archive = self.experiment / "evidence/archive/repository-root/.planning/ROADMAP.md"
        ambient = self.repository / ".planning/ROADMAP.md"
        archive.parent.mkdir(parents=True)
        ambient.parent.mkdir(parents=True)
        archive.write_text("# frozen roadmap\n", encoding="utf-8")
        ambient.write_text("# ambient roadmap\n", encoding="utf-8")
        git("add", archive.as_posix(), cwd=self.repository)
        git("commit", "-q", "-m", "archive", cwd=self.repository)
        publication = self.manifest["publication"]
        historical = self.manifest["historical_evidence"]
        assert isinstance(publication, dict) and isinstance(historical, dict)
        paths = publication["paths"]
        assert isinstance(paths, list)
        paths.append(self._entry(archive, "historical_input", "legacy:.planning/ROADMAP.md"))
        historical["mappings"] = [
            {
                "legacy_path": ".planning/ROADMAP.md",
                "archive_path": archive.relative_to(self.repository).as_posix(),
                "sha256": sha256_bytes(archive.read_bytes()),
            }
        ]
        self._write()

        resolved = resolve_historical_path(self.repository, ".planning/ROADMAP.md")

        self.assertEqual(
            resolved,
            "experiments/specchoice-v1.3.2/evidence/archive/repository-root/.planning/ROADMAP.md",
        )


if __name__ == "__main__":
    unittest.main()
