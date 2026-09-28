#!/usr/bin/env python3
"""
Prompt assembler for RISC-V architectural parameter extraction.

Combines system prompt + few-shot examples + UDB parameter names + spec chunk
into a complete prompt suitable for LLM analysis.

Three operational modes:
  assemble  — build and print a complete prompt for a given spec chunk
  chunk     — split a spec file into overlapping chunks suitable for LLM context
  estimate  — report token estimates for each prompt layer
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TypedDict

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
PROMPT_DIR = PROJECT_DIR / "prompts" / "v1"
DATA_DIR = PROJECT_DIR / "data"

CHARS_PER_TOKEN = 3.8

CONTEXT_LIMITS: dict[str, int] = {
    "gpt-4o": 128_000,
    "gpt-4-turbo": 128_000,
    "claude-3-5-sonnet": 200_000,
    "claude-3-opus": 200_000,
    "gemini-1.5-pro": 1_000_000,
    "llama-3-70b": 8_192,
    "default": 128_000,
}

RESERVED_OUTPUT_TOKENS = 4_096
SYSTEM_OVERHEAD_TOKENS = 200

class ChunkMeta(TypedDict):
    file: str
    start_line: int
    end_line: int
    total_lines: int
    chunk_index: int
    total_chunks: int


def estimate_tokens(text: str) -> int:
    """Rough token estimate using chars/token ratio."""
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def load_system_prompt() -> str:
    path = PROMPT_DIR / "system_prompt.txt"
    if not path.exists():
        raise FileNotFoundError(f"System prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_examples() -> dict:
    path = PROMPT_DIR / "examples.json"
    if not path.exists():
        raise FileNotFoundError(f"Examples not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_udb_param_names() -> list[str]:
    path = DATA_DIR / "udb_param_names.txt"
    if not path.exists():
        raise FileNotFoundError(f"UDB param names not found: {path}")
    names = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return sorted(set(names))


def format_examples_section(examples: dict) -> str:
    """Format few-shot examples into a clear prompt section."""
    lines = ["## Few-Shot Examples", ""]
    lines.append("### Positive Examples (extract these)")
    lines.append("")

    for i, ex in enumerate(examples.get("positive_examples", []), 1):
        lines.append(f"**Example {i}** — `{ex['input_file']}`, line {ex['input_line']}")
        lines.append("")
        lines.append("Input text:")
        lines.append(f"> {ex['input_excerpt']}")
        lines.append("")
        lines.append("Expected output:")
        lines.append("```json")
        lines.append(json.dumps(ex["expected_output"], indent=2))
        lines.append("```")
        lines.append("")

    lines.append("### Negative Examples (do NOT extract these)")
    lines.append("")

    for i, ex in enumerate(examples.get("negative_examples", []), 1):
        lines.append(f"**Non-parameter {i}** — `{ex['input_file']}`, line {ex['input_line']}")
        lines.append("")
        lines.append("Input text:")
        lines.append(f"> {ex['input_excerpt']}")
        lines.append("")
        lines.append(f"Why not a parameter: {ex['reason_for_rejection']}")
        lines.append("")

    return "\n".join(lines)


def format_param_names_section(names: list[str]) -> str:
    """Format UDB parameter names as a reference list."""
    lines = [
        "## Known UDB Parameter Names",
        "",
        "When a parameter you find matches one of these known names, use the exact name.",
        "For new parameters not in this list, suggest a descriptive UPPER_SNAKE_CASE name.",
        "",
    ]
    lines.append(", ".join(names))
    return "\n".join(lines)


def format_chunk_section(
    chunk_text: str, meta: ChunkMeta
) -> str:
    """Format the spec chunk with metadata for the LLM."""
    lines = [
        "## Specification Text to Analyze",
        "",
        f"File: `{meta['file']}`",
        f"Lines: {meta['start_line']}-{meta['end_line']} "
        f"(chunk {meta['chunk_index']}/{meta['total_chunks']})",
        "",
        "Analyze the following specification text and extract all architectural parameters.",
        "Include line numbers relative to the original file (starting from "
        f"line {meta['start_line']}).",
        "",
        "```",
        chunk_text,
        "```",
    ]
    return "\n".join(lines)


def assemble_prompt(
    chunk_text: str,
    meta: ChunkMeta,
    model: str = "default",
    include_examples: bool = True,
    include_param_names: bool = True,
) -> dict[str, str]:
    """
    Assemble the complete prompt from all layers.

    Returns a dict with 'system' and 'user' keys suitable for chat API calls.
    """
    system_prompt = load_system_prompt()

    user_parts: list[str] = []

    if include_examples:
        examples = load_examples()
        user_parts.append(format_examples_section(examples))

    if include_param_names:
        names = load_udb_param_names()
        user_parts.append(format_param_names_section(names))

    user_parts.append(format_chunk_section(chunk_text, meta))

    user_message = "\n\n---\n\n".join(user_parts)

    total_tokens = (
        estimate_tokens(system_prompt)
        + estimate_tokens(user_message)
        + SYSTEM_OVERHEAD_TOKENS
        + RESERVED_OUTPUT_TOKENS
    )

    limit = CONTEXT_LIMITS.get(model, CONTEXT_LIMITS["default"])
    if total_tokens > limit:
        raise ValueError(
            f"Assembled prompt ({total_tokens:,} est. tokens) exceeds "
            f"{model} context limit ({limit:,} tokens). "
            f"Reduce chunk size or disable examples/param names."
        )

    return {
        "system": system_prompt,
        "user": user_message,
        "estimated_tokens": total_tokens,
        "model": model,
    }


# --- Chunking logic ---


def detect_section_boundaries(lines: list[str]) -> list[int]:
    """
    Find AsciiDoc section headers (lines starting with == or more).
    Returns a list of 0-based line indices that are section starts.
    """
    boundaries = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("== ") or stripped.startswith("=== ") or \
           stripped.startswith("==== ") or stripped.startswith("===== "):
            boundaries.append(i)
    return boundaries


def chunk_spec_file(
    filepath: Path,
    max_chunk_tokens: int = 40_000,
    overlap_lines: int = 20,
) -> list[tuple[str, ChunkMeta]]:
    """
    Split a spec file into chunks that respect section boundaries.

    Strategy:
    1. Find all section headers in the file.
    2. Greedily accumulate sections until the chunk would exceed max_chunk_tokens.
    3. Emit the chunk and start a new one with `overlap_lines` of overlap.
    """
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    total_lines = len(lines)

    if total_lines == 0:
        return []

    boundaries = detect_section_boundaries(lines)

    if not boundaries:
        boundaries = [0]
    if boundaries[0] != 0:
        boundaries.insert(0, 0)

    chunks: list[tuple[str, ChunkMeta]] = []
    current_start = 0
    chunk_index = 0

    while current_start < total_lines:
        candidate_sections = [b for b in boundaries if b >= current_start]
        if not candidate_sections:
            candidate_sections = [current_start]

        chunk_end = current_start
        for i, sec_start in enumerate(candidate_sections):
            next_boundary = (
                candidate_sections[i + 1] if i + 1 < len(candidate_sections) else total_lines
            )
            candidate_text = "".join(lines[current_start:next_boundary])
            if estimate_tokens(candidate_text) > max_chunk_tokens and chunk_end > current_start:
                break
            chunk_end = next_boundary

        if chunk_end <= current_start:
            chunk_end = min(current_start + int(max_chunk_tokens * CHARS_PER_TOKEN / 80), total_lines)

        chunk_text = "".join(lines[current_start:chunk_end])
        chunk_index += 1
        meta: ChunkMeta = {
            "file": filepath.name,
            "start_line": current_start + 1,
            "end_line": chunk_end,
            "total_lines": total_lines,
            "chunk_index": chunk_index,
            "total_chunks": 0,
        }
        chunks.append((chunk_text, meta))

        if chunk_end >= total_lines:
            break

        current_start = max(current_start + 1, chunk_end - overlap_lines)

    for _, meta in chunks:
        meta["total_chunks"] = len(chunks)

    return chunks


# --- CLI ---


def cmd_assemble(args: argparse.Namespace) -> None:
    """Assemble and print a complete prompt for a spec chunk."""
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    total_lines = len(lines)

    start = max(1, args.start_line) if args.start_line else 1
    end = min(args.end_line, total_lines) if args.end_line else total_lines

    chunk_text = "".join(lines[start - 1 : end])
    meta: ChunkMeta = {
        "file": filepath.name,
        "start_line": start,
        "end_line": end,
        "total_lines": total_lines,
        "chunk_index": 1,
        "total_chunks": 1,
    }

    prompt = assemble_prompt(
        chunk_text,
        meta,
        model=args.model,
        include_examples=not args.no_examples,
        include_param_names=not args.no_param_names,
    )

    if args.output_json:
        json.dump(prompt, sys.stdout, indent=2)
        print()
    else:
        print("=" * 70)
        print("SYSTEM PROMPT")
        print("=" * 70)
        print(prompt["system"])
        print()
        print("=" * 70)
        print("USER MESSAGE")
        print("=" * 70)
        print(prompt["user"])
        print()
        print("=" * 70)
        print(f"Estimated tokens: {prompt['estimated_tokens']:,}")
        print(f"Model: {prompt['model']}")
        print("=" * 70)


def cmd_chunk(args: argparse.Namespace) -> None:
    """Split a spec file into chunks and show their boundaries."""
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    chunks = chunk_spec_file(
        filepath,
        max_chunk_tokens=args.max_tokens,
        overlap_lines=args.overlap,
    )

    if args.output_json:
        output = []
        for chunk_text, meta in chunks:
            output.append({
                "meta": meta,
                "text": chunk_text if args.include_text else None,
                "estimated_tokens": estimate_tokens(chunk_text),
            })
        json.dump(output, sys.stdout, indent=2)
        print()
    else:
        print(f"File: {filepath.name}")
        print(f"Total lines: {chunks[0][1]['total_lines'] if chunks else 0}")
        print(f"Chunks: {len(chunks)}")
        print()
        for chunk_text, meta in chunks:
            tokens = estimate_tokens(chunk_text)
            print(
                f"  Chunk {meta['chunk_index']}/{meta['total_chunks']}: "
                f"lines {meta['start_line']}-{meta['end_line']} "
                f"({meta['end_line'] - meta['start_line'] + 1} lines, "
                f"~{tokens:,} tokens)"
            )


def cmd_estimate(args: argparse.Namespace) -> None:
    """Report token estimates for each prompt layer."""
    system_prompt = load_system_prompt()
    examples = load_examples()
    param_names = load_udb_param_names()

    system_tokens = estimate_tokens(system_prompt)
    examples_text = format_examples_section(examples)
    examples_tokens = estimate_tokens(examples_text)
    names_text = format_param_names_section(param_names)
    names_tokens = estimate_tokens(names_text)

    fixed_total = system_tokens + examples_tokens + names_tokens + SYSTEM_OVERHEAD_TOKENS

    print("Prompt Layer Token Estimates")
    print("=" * 50)
    print(f"  System prompt:        {system_tokens:>6,} tokens")
    print(f"  Few-shot examples:    {examples_tokens:>6,} tokens")
    print(f"  UDB param names:      {names_tokens:>6,} tokens")
    print(f"  System overhead:      {SYSTEM_OVERHEAD_TOKENS:>6,} tokens")
    print(f"  Reserved for output:  {RESERVED_OUTPUT_TOKENS:>6,} tokens")
    print(f"  {'─' * 36}")
    print(f"  Fixed overhead:       {fixed_total:>6,} tokens")
    print()

    print("Available for spec chunk per model:")
    for model, limit in sorted(CONTEXT_LIMITS.items()):
        available = limit - fixed_total - RESERVED_OUTPUT_TOKENS
        print(f"  {model:<25s} {available:>8,} tokens (~{int(available * CHARS_PER_TOKEN):,} chars)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prompt assembler for RISC-V parameter extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- assemble ---
    p_asm = subparsers.add_parser("assemble", help="Build a complete prompt for a spec chunk")
    p_asm.add_argument("file", help="Path to the .adoc spec file")
    p_asm.add_argument("--start-line", type=int, default=None, help="Start line (1-based)")
    p_asm.add_argument("--end-line", type=int, default=None, help="End line (1-based)")
    p_asm.add_argument("--model", default="default", help="Target model for context limit check")
    p_asm.add_argument("--no-examples", action="store_true", help="Omit few-shot examples")
    p_asm.add_argument("--no-param-names", action="store_true", help="Omit UDB param name list")
    p_asm.add_argument("--output-json", action="store_true", help="Output as JSON")
    p_asm.set_defaults(func=cmd_assemble)

    # --- chunk ---
    p_chunk = subparsers.add_parser("chunk", help="Split a spec file into chunks")
    p_chunk.add_argument("file", help="Path to the .adoc spec file")
    p_chunk.add_argument("--max-tokens", type=int, default=40_000, help="Max tokens per chunk")
    p_chunk.add_argument("--overlap", type=int, default=20, help="Overlap lines between chunks")
    p_chunk.add_argument("--output-json", action="store_true", help="Output as JSON")
    p_chunk.add_argument("--include-text", action="store_true", help="Include chunk text in JSON")
    p_chunk.set_defaults(func=cmd_chunk)

    # --- estimate ---
    p_est = subparsers.add_parser("estimate", help="Report token estimates for prompt layers")
    p_est.set_defaults(func=cmd_estimate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
