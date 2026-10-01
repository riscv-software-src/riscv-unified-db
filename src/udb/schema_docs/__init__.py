# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Offline, independently versioned JSON Schema MDX generation."""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ..authoring import AuthoringPlan, GeneratedFile
from ..schema import SchemaStore
from ..serialization import dumps_json
from ._input import (
    ProjectionNotice,
    SchemaDocsProjectionWarning,
    snapshot,
    validate_projection,
)
from ._render import PageRenderer, render_index
from ._types import SchemaDocsError
from ._usage import ProjectionUsage

__all__ = [
    "ProjectionNotice",
    "SchemaDocsError",
    "SchemaDocsProjectionWarning",
    "SchemaDocumentation",
    "SchemaDocumentationPlan",
    "generate_schema_docs",
]


def _warn(notices: tuple[ProjectionNotice, ...]) -> None:
    if notices:
        keys = ", ".join(sorted({notice.keyword for notice in notices}))
        warnings.warn(
            f"schema documentation uses the legacy presentation for {len(notices)} "
            f"located features ({keys}); inspect .notices for precise locations and limits",
            SchemaDocsProjectionWarning,
            stacklevel=3,
        )


@dataclass(frozen=True)
class SchemaDocumentationPlan:
    """Validated outputs plus disclosed legacy presentation limits."""

    authoring: AuthoringPlan
    notices: tuple[ProjectionNotice, ...]
    current_pages: tuple[PurePosixPath, ...] = ()
    history_pages: frozenset[PurePosixPath] | None = None

    @property
    def outputs(self) -> tuple[GeneratedFile, ...]:
        return self.authoring.outputs

    def apply(
        self,
        output: str | Path,
        *,
        check: bool = False,
        replace_current: bool = False,
    ) -> tuple[PurePosixPath, ...]:
        """Publish atomically or return drift, protecting existing versioned pages."""
        root = Path(output)
        if root.is_symlink():
            raise SchemaDocsError(f"schema documentation output contains a symlink: {root}")
        includes_index = any(item.path == PurePosixPath("index.mdx") for item in self.outputs)
        if self.history_pages is not None or includes_index:
            current = set(self.current_pages)
            actual_history = {
                PurePosixPath(version, name + ".mdx")
                for version, names in _historical_pages(root).items()
                for name in names
            }
            if self.history_pages is None and actual_history - current:
                raise SchemaDocsError(
                    "an index plan created without an output root cannot retain existing history; "
                    "re-plan with the destination root"
                )
            if (
                self.history_pages is not None
                and actual_history - current != self.history_pages - current
            ):
                raise SchemaDocsError("schema history changed after planning; create a new plan")
        drift = self.authoring.apply(root, check=True)
        if check:
            return drift
        conflicts = [
            path
            for path in drift
            if (
                path.suffix in (".md", ".mdx")
                and path != PurePosixPath("index.mdx")
                and (root / path).exists()
                and (not replace_current or path not in self.current_pages)
            )
        ]
        if conflicts:
            raise SchemaDocsError(
                "existing versioned schema pages are immutable; differing paths: "
                + ", ".join(path.as_posix() for path in conflicts)
            )
        return self.authoring.apply(root)


class SchemaDocumentation:
    """An instance-scoped, validated SchemaStore documentation snapshot."""

    def __init__(self, schemas: SchemaStore | None = None) -> None:
        self._schemas = snapshot(schemas)
        notices = list(validate_projection(self._schemas))
        usage = ProjectionUsage(self._schemas)
        try:
            self._rendered = {
                name: PageRenderer(name, self._schemas, usage).generate() for name in self._schemas
            }
        except SchemaDocsError:
            _warn(tuple(notices))
            raise
        recorded = {(notice.schema, notice.pointer, notice.keyword) for notice in notices}
        for omission in usage.omissions():
            if omission[:3] not in recorded:
                notices.append(ProjectionNotice(*omission))
        self.notices = tuple(notices)
        _warn(self.notices)

    @property
    def schema_names(self) -> tuple[str, ...]:
        return tuple(self._schemas)

    def render(self, schema: str) -> str:
        """Return one MDX page, preserving legacy provenance and formatting."""
        if schema not in self._schemas:
            raise SchemaDocsError(f"unknown documentation schema {schema!r}")
        return self._rendered[schema]

    def plan(
        self,
        output: str | Path | None = None,
        *,
        schema: str | None = None,
        output_file: str | PurePosixPath | None = None,
        generate_index: bool = True,
    ) -> SchemaDocumentationPlan:
        """Plan all pages/categories/index or one page with an optional file override."""
        if output_file is not None and schema is None:
            raise SchemaDocsError("output_file requires a single schema")
        if output_file is not None:
            override = PurePosixPath(output_file)
            if override.suffix not in (".md", ".mdx"):
                raise SchemaDocsError("output_file must be a .md or .mdx page")
            if override == PurePosixPath("index.mdx"):
                raise SchemaDocsError("output_file cannot replace the schema index")
            if any(re.fullmatch(r"v\d+(\.\d+)*", part) for part in override.parts[:-1]):
                if re.fullmatch(r"v\d+(\.\d+)*", override.parts[0]) is None:
                    raise SchemaDocsError(
                        "output_file inside a version directory must be this schema's canonical page"
                    )
                if schema not in self._schemas or override.parts[0] != self._schemas[schema]["$id"]:
                    raise SchemaDocsError("output_file cannot target a historical schema version")
                canonical = PurePosixPath(
                    self._schemas[schema]["$id"],
                    schema.removesuffix(".json") + ".mdx",
                )
                if override != canonical:
                    raise SchemaDocsError(
                        "output_file inside a version directory must be this schema's canonical page"
                    )
        names = self.schema_names if schema is None else (schema,)
        dependencies = tuple(PurePosixPath("schemas", name) for name in self.schema_names) or (
            PurePosixPath("schemas"),
        )
        outputs = []
        pages = _historical_pages(Path(output)) if output is not None else {}
        history_pages = (
            frozenset(
                PurePosixPath(version, name + ".mdx")
                for version, historical_names in pages.items()
                for name in historical_names
            )
            if output is not None and schema is None and generate_index
            else None
        )
        current_pages = []
        versions = set()
        for name in names:
            text = self.render(name)
            version = self._schemas[name]["$id"]
            current_pages.append(PurePosixPath(version, name.removesuffix(".json") + ".mdx"))
            path = (
                PurePosixPath(output_file)
                if output_file is not None
                else (PurePosixPath(version, name.removesuffix(".json") + ".mdx"))
            )
            outputs.append(
                GeneratedFile(path, text.encode("utf-8"), "schema-docs", dependencies, 0o644)
            )
            versions.add(version)
            pages.setdefault(version, set()).add(name.removesuffix(".json"))
        if schema is None:
            for position, version in enumerate(sorted(versions, reverse=True), 1):
                content = dumps_json(
                    {
                        "label": version,
                        "position": position,
                        "collapsible": True,
                        "collapsed": False,
                    },
                    sort_keys=False,
                )
                outputs.append(
                    GeneratedFile(
                        PurePosixPath(version, "_category_.json"),
                        content.encode("utf-8"),
                        "schema-docs",
                        dependencies,
                        0o644,
                    )
                )
            if generate_index:
                outputs.append(
                    GeneratedFile(
                        PurePosixPath("index.mdx"),
                        render_index(pages).encode("utf-8"),
                        "schema-docs",
                        dependencies,
                        0o644,
                    )
                )
        return SchemaDocumentationPlan(
            AuthoringPlan(tuple(outputs)),
            self.notices,
            tuple(current_pages),
            history_pages,
        )


def _historical_pages(root: Path) -> dict[str, set[str]]:
    if root.is_symlink():
        raise SchemaDocsError(f"schema documentation output contains a symlink: {root}")
    if not root.exists():
        return {}
    if not root.is_dir():
        raise SchemaDocsError(f"schema documentation output must be a real directory: {root}")
    pages = {}
    for version in sorted(root.iterdir()):
        if re.fullmatch(r"v\d+(\.\d+)*", version.name) is None:
            continue
        if version.is_symlink():
            raise SchemaDocsError(f"schema history contains a symlink: {version}")
        if not version.is_dir():
            continue
        names = set()
        for page in sorted(version.glob("*.mdx")):
            if page.name.startswith("."):
                continue
            if page.is_symlink() or not page.is_file():
                raise SchemaDocsError(f"schema history contains an unsafe page: {page}")
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", page.stem) is None:
                raise SchemaDocsError(f"unsupported historical schema page name: {page}")
            names.add(page.stem)
        pages[version.name] = names
    return pages


def generate_schema_docs(
    output: str | Path,
    *,
    schemas: SchemaStore | None = None,
    schema: str | None = None,
    output_file: str | PurePosixPath | None = None,
    check: bool = False,
    replace_current: bool = False,
    generate_index: bool = True,
) -> tuple[PurePosixPath, ...]:
    """Generate/check versioned MDX using bundled schemas unless supplied."""
    docs = SchemaDocumentation(schemas)
    plan = docs.plan(
        output,
        schema=schema,
        output_file=output_file,
        generate_index=generate_index,
    )
    return plan.apply(output, check=check, replace_current=replace_current)
