#!/usr/bin/env python3
# Copyright (c) 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear
"""
AsciiDoc-aware chunker for the RISC-V specification.

Splits spec .adoc files into semantically coherent chunks that preserve
CSR section integrity and respect LLM context window limits.

Chunking rules:
  1. Never split within a ==== section (CSR sections are atomic)
  2. Split at === or ==== boundaries
  3. Target chunk size: 2500-3500 lines (~35K-45K tokens)
  4. Include overlap at boundaries (heading + first paragraph of previous)
  5. Files under 2000 lines are a single chunk

Output:
  chunks/ directory with numbered chunk files and a manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
SPEC_DIR = PROJECT_DIR.parent / "ext" / "riscv-isa-manual" / "src"
CHUNKS_DIR = PROJECT_DIR / "chunks"

TARGET_MIN_LINES = 2500
TARGET_MAX_LINES = 3500
SMALL_FILE_THRESHOLD = 2000
OVERLAP_LINES = 30


@dataclass
class Section:
    """A section of an AsciiDoc file."""

    line_start: int  # 0-based
    line_end: int  # 0-based, exclusive
    level: int  # number of '=' chars (2-5)
    title: str
    children: list[Section] = field(default_factory=list)

    @property
    def size(self) -> int:
        return self.line_end - self.line_start


@dataclass
class ChunkInfo:
    """Metadata for a single chunk."""

    chunk_id: str
    source_file: str
    start_line: int  # 1-based, inclusive (includes overlap)
    end_line: int  # 1-based, inclusive
    content_start_line: int  # 1-based, where new content starts (after overlap)
    total_source_lines: int
    section_headings: list[str]
    overlap_from_line: int | None  # 1-based start of overlap region, or None
    line_count: int

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source_file": self.source_file,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content_start_line": self.content_start_line,
            "total_source_lines": self.total_source_lines,
            "section_headings": self.section_headings,
            "overlap_from_line": self.overlap_from_line,
            "line_count": self.line_count,
        }


def parse_sections(lines: list[str]) -> list[Section]:
    """
    Parse AsciiDoc section headers and build a flat list of sections.
    Each section spans from its header to the next header of the same or
    higher level (or end of file).
    """
    headers: list[tuple[int, int, str]] = []  # (line_idx, level, title)
    for i, line in enumerate(lines):
        m = re.match(r"^(={2,6})\s+(.+)", line.strip())
        if m:
            headers.append((i, len(m.group(1)), m.group(2).strip()))

    if not headers:
        return [
            Section(
                line_start=0,
                line_end=len(lines),
                level=1,
                title="(no sections)",
            )
        ]

    sections: list[Section] = []
    total = len(lines)

    for idx, (start, level, title) in enumerate(headers):
        end = total
        for next_start, next_level, _ in headers[idx + 1 :]:
            if next_level <= level:
                end = next_start
                break
        sections.append(
            Section(
                line_start=start,
                line_end=end,
                level=level,
                title=title,
            )
        )

    return sections


def build_atomic_blocks(sections: list[Section], total_lines: int) -> list[Section]:
    """
    Build atomic blocks that cannot be split.

    An atomic block is:
    - A ==== section including all its ===== children
    - A === section's preamble (text before its first ==== child)
    - Any == level section's preamble

    The key invariant: no chunk boundary falls inside a ==== section.
    """
    blocks: list[Section] = []

    level4_sections = [s for s in sections if s.level == 4]
    level3_sections = [s for s in sections if s.level == 3]
    level2_sections = [s for s in sections if s.level == 2]

    if level4_sections:
        covered = set()
        for s in level4_sections:
            for line_idx in range(s.line_start, s.line_end):
                covered.add(line_idx)
            blocks.append(s)

        for s in level3_sections + level2_sections:
            preamble_end = s.line_end
            for child in level4_sections:
                if s.line_start < child.line_start <= s.line_end:
                    preamble_end = min(preamble_end, child.line_start)
                    break

            if preamble_end > s.line_start + 1:
                preamble_lines = set(range(s.line_start, preamble_end))
                uncovered = preamble_lines - covered
                if uncovered:
                    blocks.append(
                        Section(
                            line_start=min(uncovered),
                            line_end=max(uncovered) + 1,
                            level=s.level,
                            title=s.title + " (preamble)",
                        )
                    )

        all_line_idxs = set(range(total_lines))
        block_covered = set()
        for b in blocks:
            for i in range(b.line_start, b.line_end):
                block_covered.add(i)

        gaps = sorted(all_line_idxs - block_covered)
        if gaps:
            gap_start = gaps[0]
            for i in range(1, len(gaps)):
                if gaps[i] != gaps[i - 1] + 1:
                    blocks.append(
                        Section(
                            line_start=gap_start,
                            line_end=gaps[i - 1] + 1,
                            level=0,
                            title="(gap)",
                        )
                    )
                    gap_start = gaps[i]
            blocks.append(
                Section(
                    line_start=gap_start,
                    line_end=gaps[-1] + 1,
                    level=0,
                    title="(gap)",
                )
            )

    elif level3_sections:
        blocks = list(level3_sections)
        if level3_sections[0].line_start > 0:
            blocks.insert(
                0,
                Section(
                    line_start=0,
                    line_end=level3_sections[0].line_start,
                    level=1,
                    title="(preamble)",
                ),
            )
    else:
        blocks = [
            Section(
                line_start=0,
                line_end=total_lines,
                level=1,
                title="(entire file)",
            )
        ]

    blocks.sort(key=lambda b: b.line_start)
    return blocks


def merge_tiny_blocks(blocks: list[Section], min_size: int = 5) -> list[Section]:
    """Merge very small blocks into their neighbors."""
    if len(blocks) <= 1:
        return blocks

    merged: list[Section] = []
    for block in blocks:
        if not merged:
            merged.append(block)
            continue

        if merged[-1].size < min_size:
            prev = merged.pop()
            merged.append(
                Section(
                    line_start=prev.line_start,
                    line_end=block.line_end,
                    level=prev.level,
                    title=prev.title,
                )
            )
        elif block.size < min_size:
            merged[-1] = Section(
                line_start=merged[-1].line_start,
                line_end=block.line_end,
                level=merged[-1].level,
                title=merged[-1].title,
            )
        else:
            merged.append(block)
    return merged


def pack_chunks(
    blocks: list[Section],
    total_lines: int,
    target_min: int = TARGET_MIN_LINES,
    target_max: int = TARGET_MAX_LINES,
) -> list[list[Section]]:
    """
    Greedily pack atomic blocks into chunks.

    Each chunk accumulates blocks until adding the next block would exceed
    target_max. If the current chunk hasn't reached target_min, keep adding.
    """
    if not blocks:
        return []

    chunks: list[list[Section]] = []
    current: list[Section] = []
    current_size = 0

    for block in blocks:
        if current and current_size + block.size > target_max and current_size >= target_min:
            chunks.append(current)
            current = [block]
            current_size = block.size
        else:
            current.append(block)
            current_size += block.size

    if current:
        chunks.append(current)

    return chunks


def get_overlap_text(
    lines: list[str],
    prev_chunk_blocks: list[Section],
    max_lines: int = OVERLAP_LINES,
) -> tuple[int, list[str]]:
    """
    Extract overlap context from the end of the previous chunk.
    Returns (start_line_0based, overlap_lines).
    """
    if not prev_chunk_blocks:
        return (0, [])

    last_block = prev_chunk_blocks[-1]
    overlap_start = max(last_block.line_start, last_block.line_end - max_lines)

    overlap = lines[overlap_start : last_block.line_end]
    return (overlap_start, overlap)


def get_section_headings(
    blocks: list[Section],
    all_sections: list[Section],
) -> list[str]:
    """Get a list of section headings covered by these blocks."""
    block_range_start = blocks[0].line_start
    block_range_end = blocks[-1].line_end
    headings = []
    for s in all_sections:
        if s.line_start >= block_range_start and s.line_start < block_range_end:
            prefix = "=" * s.level
            headings.append(f"{prefix} {s.title}")
    return headings


def chunk_file(
    filepath: Path,
    target_min: int = TARGET_MIN_LINES,
    target_max: int = TARGET_MAX_LINES,
    small_threshold: int = SMALL_FILE_THRESHOLD,
) -> list[tuple[str, ChunkInfo]]:
    """
    Chunk a single spec file. Returns list of (chunk_text, metadata).
    """
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    total_lines = len(lines)

    if total_lines == 0:
        return []

    all_sections = parse_sections([line.rstrip("\n") for line in lines])

    if total_lines < small_threshold:
        chunk_text = text
        heading_list = [f"{'=' * s.level} {s.title}" for s in all_sections if s.level >= 2]
        meta = ChunkInfo(
            chunk_id="",
            source_file=filepath.name,
            start_line=1,
            end_line=total_lines,
            content_start_line=1,
            total_source_lines=total_lines,
            section_headings=heading_list[:10],
            overlap_from_line=None,
            line_count=total_lines,
        )
        return [(chunk_text, meta)]

    blocks = build_atomic_blocks(all_sections, total_lines)
    blocks = merge_tiny_blocks(blocks)
    packed = pack_chunks(blocks, total_lines, target_min, target_max)

    results: list[tuple[str, ChunkInfo]] = []
    for chunk_idx, block_group in enumerate(packed):
        block_start = block_group[0].line_start
        block_end = block_group[-1].line_end

        overlap_start = None
        overlap_text_lines: list[str] = []
        if chunk_idx > 0:
            prev_blocks = packed[chunk_idx - 1]
            ov_start_0, ov_lines = get_overlap_text(lines, prev_blocks)
            if ov_lines:
                overlap_start = ov_start_0
                overlap_text_lines = ov_lines

        if overlap_text_lines and overlap_start is not None:
            actual_start = overlap_start
            chunk_lines = lines[actual_start:block_end]
        else:
            actual_start = block_start
            chunk_lines = lines[block_start:block_end]

        chunk_text = "".join(chunk_lines)
        headings = get_section_headings(block_group, all_sections)

        meta = ChunkInfo(
            chunk_id="",
            source_file=filepath.name,
            start_line=actual_start + 1,
            end_line=block_end,
            content_start_line=block_start + 1,
            total_source_lines=total_lines,
            section_headings=headings[:20],
            overlap_from_line=(overlap_start + 1)
            if overlap_start is not None and chunk_idx > 0
            else None,
            line_count=block_end - actual_start,
        )
        results.append((chunk_text, meta))

    return results


def chunk_all_files(
    spec_dir: Path = SPEC_DIR,
    target_min: int = TARGET_MIN_LINES,
    target_max: int = TARGET_MAX_LINES,
) -> list[tuple[str, ChunkInfo]]:
    """Chunk all .adoc files in the spec directory."""
    all_chunks: list[tuple[str, ChunkInfo]] = []

    adoc_files = sorted(spec_dir.glob("*.adoc"))
    if not adoc_files:
        print(f"No .adoc files found in {spec_dir}", file=sys.stderr)
        return []

    global_idx = 0
    for filepath in adoc_files:
        file_chunks = chunk_file(filepath, target_min, target_max)
        for chunk_text, meta in file_chunks:
            global_idx += 1
            meta.chunk_id = f"chunk_{global_idx:03d}"
            all_chunks.append((chunk_text, meta))

    return all_chunks


def write_chunks(
    chunks: list[tuple[str, ChunkInfo]],
    output_dir: Path = CHUNKS_DIR,
) -> Path:
    """Write chunk files and manifest to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for existing in output_dir.glob("chunk_*.txt"):
        existing.unlink()
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest_path.unlink()

    manifest_entries: list[dict] = []

    for chunk_text, meta in chunks:
        header_lines = [
            f"# Chunk: {meta.chunk_id}",
            f"# Source: {meta.source_file}",
            f"# Lines: {meta.start_line}-{meta.end_line} (of {meta.total_source_lines})",
            f"# Content starts: line {meta.content_start_line}",
            f"# Line count: {meta.line_count}",
        ]
        if meta.overlap_from_line:
            header_lines.append(f"# Overlap from line: {meta.overlap_from_line}")
        header_lines.append(f"# Sections: {len(meta.section_headings)}")
        for h in meta.section_headings:
            header_lines.append(f"#   {h}")
        header_lines.append("#")
        header_lines.append("")

        file_content = "\n".join(header_lines) + chunk_text

        chunk_path = output_dir / f"{meta.chunk_id}.txt"
        chunk_path.write_text(file_content, encoding="utf-8")

        manifest_entries.append(meta.to_dict())

    manifest = {
        "total_chunks": len(chunks),
        "total_files": len(set(m.source_file for _, m in chunks)),
        "total_lines": sum(m.line_count for _, m in chunks),
        "chunks": manifest_entries,
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    return output_dir


# --- CLI ---


def cmd_run(args: argparse.Namespace) -> None:
    """Chunk all spec files and write output."""
    spec_dir = Path(args.spec_dir)
    if not spec_dir.exists():
        print(f"Error: spec directory not found: {spec_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)

    print(f"Spec directory: {spec_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Target chunk size: {args.min_lines}-{args.max_lines} lines")
    print()

    chunks = chunk_all_files(
        spec_dir=spec_dir,
        target_min=args.min_lines,
        target_max=args.max_lines,
    )

    write_chunks(chunks, output_dir)

    files_seen = set()
    for _, meta in chunks:
        files_seen.add(meta.source_file)

    print(f"Files processed: {len(files_seen)}")
    print(f"Total chunks: {len(chunks)}")
    print()

    by_file: dict[str, list[ChunkInfo]] = {}
    for _, meta in chunks:
        by_file.setdefault(meta.source_file, []).append(meta)

    for fname in sorted(by_file):
        file_chunks = by_file[fname]
        if len(file_chunks) == 1:
            c = file_chunks[0]
            print(f"  {fname}: 1 chunk ({c.line_count} lines)")
        else:
            parts = ", ".join(f"{c.line_count}" for c in file_chunks)
            print(f"  {fname}: {len(file_chunks)} chunks ({parts} lines)")


def cmd_info(args: argparse.Namespace) -> None:
    """Show information about a specific file's chunking."""
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    file_chunks = chunk_file(
        filepath,
        target_min=args.min_lines,
        target_max=args.max_lines,
    )

    lines = filepath.read_text().splitlines()
    total = len(lines)

    print(f"File: {filepath.name}")
    print(f"Total lines: {total}")
    print(f"Chunks: {len(file_chunks)}")
    print()

    for idx, (_chunk_text, meta) in enumerate(file_chunks):
        print(f"  Chunk {idx + 1}/{len(file_chunks)}:")
        print(f"    Lines: {meta.start_line}-{meta.end_line}")
        print(f"    Content starts: line {meta.content_start_line}")
        print(f"    Line count: {meta.line_count}")
        if meta.overlap_from_line:
            print(f"    Overlap from: line {meta.overlap_from_line}")
        print(f"    Sections ({len(meta.section_headings)}):")
        for h in meta.section_headings[:10]:
            print(f"      {h}")
        if len(meta.section_headings) > 10:
            print(f"      ... and {len(meta.section_headings) - 10} more")
        print()


def cmd_verify(args: argparse.Namespace) -> None:
    """Run verification checks on chunking output."""
    spec_dir = Path(args.spec_dir)
    chunks = chunk_all_files(spec_dir=spec_dir)

    errors: list[str] = []
    warnings: list[str] = []

    # 1. All 74 files covered
    all_adocs = sorted(spec_dir.glob("*.adoc"))
    files_chunked = set(m.source_file for _, m in chunks)
    for adoc in all_adocs:
        if adoc.name not in files_chunked:
            errors.append(f"File not chunked: {adoc.name}")
    print(f"1. File coverage: {len(files_chunked)}/{len(all_adocs)} files")

    # 2. No CSR section splits
    # A split occurs if a ==== section's content range (start..end) is
    # cut by a chunk's CONTENT boundary (content_start_line), meaning
    # part of the section's new content is in one chunk and part in
    # another. Overlap regions don't count as splits.
    print("2. CSR section integrity:")
    csr_split_count = 0
    for adoc in all_adocs:
        lines_raw = adoc.read_text().splitlines()
        sections = parse_sections(lines_raw)
        level4 = [s for s in sections if s.level == 4]

        file_chunks = [(t, m) for t, m in chunks if m.source_file == adoc.name]
        if len(file_chunks) <= 1:
            continue

        content_boundaries = []
        for _, meta in file_chunks:
            content_boundaries.append(meta.content_start_line)

        for s4 in level4:
            s4_start = s4.line_start + 1  # 1-based
            s4_end = s4.line_end  # 1-based, exclusive
            for boundary in content_boundaries:
                if s4_start < boundary < s4_end:
                    errors.append(
                        f"CSR section split in {adoc.name}: "
                        f"'{s4.title}' ({s4_start}-{s4_end}) "
                        f"split by content boundary at line {boundary}"
                    )
                    csr_split_count += 1

    if csr_split_count == 0:
        print("   No CSR section splits ✓")
    else:
        print(f"   {csr_split_count} CSR section splits found!")

    # 3. Chunk sizes
    print("3. Chunk size analysis:")
    target_min = TARGET_MIN_LINES
    target_max = TARGET_MAX_LINES
    tolerance = 0.20
    abs_min = int(target_min * (1 - tolerance))
    abs_max = int(target_max * (1 + tolerance))

    multi_chunk_files = {}
    for _, meta in chunks:
        multi_chunk_files.setdefault(meta.source_file, []).append(meta)

    oversized = 0
    for fname, file_chunks in multi_chunk_files.items():
        if len(file_chunks) == 1:
            continue
        for meta in file_chunks:
            if meta.line_count > abs_max:
                warnings.append(
                    f"Oversized chunk: {meta.chunk_id} in {fname} "
                    f"({meta.line_count} lines > {abs_max})"
                )
                oversized += 1
            elif meta.line_count < abs_min and meta.line_count < meta.total_source_lines:
                lc = meta.line_count
                if meta.overlap_from_line:
                    lc = meta.end_line - meta.start_line + 1
                if lc < abs_min:
                    pass

    size_dist = [m.line_count for _, m in chunks]
    print(
        f"   Min: {min(size_dist)}, Max: {max(size_dist)}, "
        f"Mean: {sum(size_dist) / len(size_dist):.0f}"
    )

    # 4. Overlap
    print("4. Overlap integrity:")
    overlap_count = sum(1 for _, m in chunks if m.overlap_from_line is not None)
    multi_chunk_count = sum(len(v) - 1 for v in multi_chunk_files.values() if len(v) > 1)
    print(f"   Overlaps: {overlap_count}, Expected (multi-chunk non-first): {multi_chunk_count}")

    # 5. Metadata completeness
    print("5. Metadata completeness:")
    missing_meta = 0
    no_headings = []
    for _, meta in chunks:
        if not meta.chunk_id:
            missing_meta += 1
        if not meta.source_file:
            missing_meta += 1
        if meta.start_line < 1 or meta.end_line < 1:
            missing_meta += 1
        if not meta.section_headings and meta.line_count > 50:
            no_headings.append(meta.source_file)
    if missing_meta == 0 and not no_headings:
        print("   All metadata fields populated ✓")
    else:
        if missing_meta:
            errors.append(f"{missing_meta} chunks with incomplete metadata")
        if no_headings:
            warnings.append(
                f"{len(no_headings)} chunks with no section headings: {', '.join(no_headings)}"
            )

    # 6. Full coverage: content boundaries should be contiguous
    print("6. Line coverage per file:")
    gap_count = 0
    for fname, file_chunks in multi_chunk_files.items():
        if len(file_chunks) <= 1:
            continue
        sorted_chunks = sorted(file_chunks, key=lambda m: m.content_start_line)
        for i in range(1, len(sorted_chunks)):
            prev_end = sorted_chunks[i - 1].end_line
            curr_content_start = sorted_chunks[i].content_start_line
            if curr_content_start > prev_end + 1:
                errors.append(
                    f"Gap in {fname}: lines {prev_end + 1}-{curr_content_start - 1} not covered"
                )
                gap_count += 1
    if gap_count == 0:
        print("   No gaps in coverage ✓")

    # Summary
    print()
    print(f"{'=' * 50}")
    print(f"Results: {len(errors)} errors, {len(warnings)} warnings")
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  {w}")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("\nAll verification checks passed!")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AsciiDoc-aware chunker for RISC-V spec files",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_run = subparsers.add_parser("run", help="Chunk all spec files and write output")
    p_run.add_argument("--spec-dir", default=str(SPEC_DIR), help="Path to spec .adoc files")
    p_run.add_argument("--output-dir", default=str(CHUNKS_DIR), help="Output directory for chunks")
    p_run.add_argument(
        "--min-lines", type=int, default=TARGET_MIN_LINES, help="Minimum chunk size in lines"
    )
    p_run.add_argument(
        "--max-lines", type=int, default=TARGET_MAX_LINES, help="Maximum chunk size in lines"
    )
    p_run.set_defaults(func=cmd_run)

    p_info = subparsers.add_parser("info", help="Show chunking for a specific file")
    p_info.add_argument("file", help="Path to a .adoc file")
    p_info.add_argument("--min-lines", type=int, default=TARGET_MIN_LINES)
    p_info.add_argument("--max-lines", type=int, default=TARGET_MAX_LINES)
    p_info.set_defaults(func=cmd_info)

    p_verify = subparsers.add_parser("verify", help="Verify chunking output")
    p_verify.add_argument("--spec-dir", default=str(SPEC_DIR))
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
