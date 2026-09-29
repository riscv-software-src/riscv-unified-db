#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Generate the GitHub Pages artifacts landing page from an HTML template."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from urllib.parse import quote

TOKEN_RE = re.compile(r"@@([A-Z0-9_]+)@@")


def schema_url(pages_url: str, schema_name: str, version: str) -> str:
    base_url = pages_url.rstrip("/")
    path = "/".join(quote(part, safe="") for part in ("schemas", schema_name, version, schema_name))
    return f"{base_url}/{path}" if base_url else f"/{path}"


def schema_index_html(deploy_dir: Path, pages_url: str) -> str:
    schema_index_path = deploy_dir / "schemas" / "index.json"
    if not schema_index_path.exists():
        return "          <p><em>No schema versions published yet.</em></p>\n"

    schema_index = json.loads(schema_index_path.read_text(encoding="utf-8"))
    schemas = schema_index.get("schemas", {})
    if not isinstance(schemas, dict) or not schemas:
        return "          <p><em>No schema versions published yet.</em></p>\n"

    html_lines: list[str] = []
    for schema_name, versions in sorted(schemas.items()):
        if not isinstance(versions, list):
            raise TypeError(
                f"{schema_index_path}: expected versions for {schema_name} to be a list"
            )
        if not versions:
            raise ValueError(f"{schema_index_path}: schema {schema_name} has no versions")

        version_names = sorted({str(version) for version in versions}, reverse=True)

        schema_name_html = escape(str(schema_name), quote=True)
        html_lines.append(f"          <h4>{schema_name_html}</h4>")
        html_lines.append("          <ul>")
        for version in version_names:
            version_html = escape(version, quote=True)
            href = escape(schema_url(pages_url, str(schema_name), version), quote=True)
            html_lines.append(f'            <li><a href="{href}">{version_html}</a></li>')
        html_lines.append("          </ul>")

    if not html_lines:
        return "          <p><em>No schema versions published yet.</em></p>\n"

    return "\n".join(html_lines) + "\n"


def render_template(template_path: Path, replacements: dict[str, str]) -> str:
    rendered = template_path.read_text(encoding="utf-8")
    template_tokens = set(TOKEN_RE.findall(rendered))
    missing_tokens = sorted(template_tokens - replacements.keys())
    if missing_tokens:
        tokens = ", ".join(f"@@{token}@@" for token in missing_tokens)
        raise ValueError(f"No replacement provided for template token(s): {tokens}")

    for token in sorted(template_tokens):
        rendered = rendered.replace(f"@@{token}@@", replacements[token])

    return rendered


def render_index(deploy_dir: Path, template_path: Path) -> str:
    pages_url = os.environ.get("PAGES_URL", "").rstrip("/")
    replacements = {
        "GITHUB_REF_NAME": escape(os.environ.get("GITHUB_REF_NAME", ""), quote=True),
        "GITHUB_SHA": escape(os.environ.get("GITHUB_SHA", ""), quote=True),
        "PAGES_URL": escape(pages_url, quote=True),
        "SCHEMA_INDEX_HTML": schema_index_html(deploy_dir, pages_url),
        "TODAY": datetime.now(UTC).date().isoformat(),
    }
    return render_template(template_path, replacements)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deploy-dir",
        type=Path,
        default=Path(os.environ.get("DEPLOY_DIR") or "_site"),
        help="Pages deployment directory; defaults to $DEPLOY_DIR or _site",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=Path(__file__).with_name("pages.html.template"),
        help="HTML template path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output HTML path; defaults to <deploy-dir>/index.html",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = args.output or args.deploy_dir / "index.html"

    args.deploy_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_index(args.deploy_dir, args.template), encoding="utf-8")


if __name__ == "__main__":
    main()
