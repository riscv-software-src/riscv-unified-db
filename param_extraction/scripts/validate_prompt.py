#!/usr/bin/env python3
"""
Validation script for Phase 2 deliverables.

Checks:
1. taxonomy.md completeness and consistency
2. examples.json structure, coverage, and spec text accuracy
3. system_prompt.txt output schema and taxonomy coverage
4. run_prompt.py assembly correctness and token budgets
5. Chunk boundary integrity
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
PROMPT_DIR = PROJECT_DIR / "prompts" / "v1"
DATA_DIR = PROJECT_DIR / "data"
SPEC_DIR = PROJECT_DIR.parent / "ext" / "riscv-isa-manual" / "src"

EXPECTED_CLASSES = {
    "NORM_DIRECT", "NORM_CSR_WARL", "NORM_CSR_RW", "SW_RULE",
    "NON_ISA", "NON_NORM", "DOC_RULE", "UNKNOWN",
}

EXPECTED_VALUE_TYPES = {"binary", "enum", "range", "set", "bitmask", "value"}

REQUIRED_OUTPUT_FIELDS = {
    "excerpt", "line_number", "parameter_name", "existing_udb_name",
    "class", "value_type", "confidence", "reasoning",
}

errors: list[str] = []
warnings: list[str] = []
checks_passed = 0


def check(condition: bool, message: str, *, warn_only: bool = False) -> None:
    global checks_passed
    if condition:
        checks_passed += 1
    elif warn_only:
        warnings.append(f"  WARNING: {message}")
    else:
        errors.append(f"  FAIL: {message}")


def validate_taxonomy() -> None:
    print("\n1. Validating taxonomy.md")
    print("-" * 40)

    path = PROMPT_DIR.parent.parent / "taxonomy.md"
    check(path.exists(), "taxonomy.md exists")
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")

    for cls in EXPECTED_CLASSES:
        check(
            f"`{cls}`" in text or f"### `{cls}`" in text,
            f"taxonomy.md defines class {cls}",
        )

    for vt in EXPECTED_VALUE_TYPES:
        check(f"`{vt}`" in text, f"taxonomy.md defines value type {vt}")

    check("Decision Tree" in text, "taxonomy.md has a decision tree section")
    check("Disambiguation" in text, "taxonomy.md has disambiguation guidance")

    lines = text.splitlines()
    check(len(lines) >= 50, f"taxonomy.md has sufficient content ({len(lines)} lines)")


def validate_examples() -> None:
    print("\n2. Validating examples.json")
    print("-" * 40)

    path = PROMPT_DIR / "examples.json"
    check(path.exists(), "examples.json exists")
    if not path.exists():
        return

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    check(isinstance(data, dict), "examples.json top-level is an object")
    if not isinstance(data, dict):
        return

    pos = data.get("positive_examples", [])
    neg = data.get("negative_examples", [])

    check(len(pos) >= 5, f"At least 5 positive examples (got {len(pos)})")
    check(len(neg) >= 3, f"At least 3 negative examples (got {len(neg)})")

    classes_covered = set()
    for ex in pos:
        check("input_excerpt" in ex, f"Positive example has input_excerpt")
        check("input_file" in ex, f"Positive example has input_file")
        check("expected_output" in ex, f"Positive example has expected_output")

        out = ex.get("expected_output", {})
        for field in REQUIRED_OUTPUT_FIELDS:
            check(
                field in out,
                f"Positive example {out.get('parameter_name', '?')} has field '{field}'",
            )

        cls = out.get("class")
        if cls:
            classes_covered.add(cls)
            check(
                cls in EXPECTED_CLASSES,
                f"Example class '{cls}' is a valid class",
            )

        vt = out.get("value_type")
        if vt:
            check(
                vt in EXPECTED_VALUE_TYPES,
                f"Example value_type '{vt}' is valid",
            )

    normative_classes = {"NORM_DIRECT", "NORM_CSR_WARL", "NORM_CSR_RW", "SW_RULE"}
    for cls in normative_classes:
        check(
            cls in classes_covered,
            f"Positive examples cover class {cls}",
        )

    for ex in neg:
        check("input_excerpt" in ex, "Negative example has input_excerpt")
        check("reason_for_rejection" in ex, "Negative example has reason_for_rejection")
        check(
            ex.get("expected_output") is None,
            "Negative example has null expected_output",
        )

    udb_names = set()
    names_path = DATA_DIR / "udb_param_names.txt"
    if names_path.exists():
        udb_names = {
            line.strip()
            for line in names_path.read_text().splitlines()
            if line.strip()
        }

    for ex in pos:
        out = ex.get("expected_output", {})
        udb_name = out.get("existing_udb_name")
        if udb_name and udb_names:
            check(
                udb_name in udb_names,
                f"Example UDB name '{udb_name}' exists in udb_param_names.txt",
            )

    for ex in pos:
        spec_file = ex.get("input_file", "")
        spec_path = SPEC_DIR / spec_file
        if spec_path.exists():
            spec_text = spec_path.read_text(encoding="utf-8")
            excerpt = ex["input_excerpt"]
            first_sentence = excerpt.split("\n")[0][:80]
            check(
                first_sentence in spec_text or first_sentence.replace(">=", "{ge}") in spec_text,
                f"Excerpt for {ex.get('expected_output', {}).get('parameter_name', '?')} found in {spec_file}",
                warn_only=True,
            )


def validate_system_prompt() -> None:
    print("\n3. Validating system_prompt.txt")
    print("-" * 40)

    path = PROMPT_DIR / "system_prompt.txt"
    check(path.exists(), "system_prompt.txt exists")
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")

    for cls in EXPECTED_CLASSES:
        check(
            cls in text or f"**{cls}**" in text,
            f"System prompt mentions class {cls}",
        )

    for vt in EXPECTED_VALUE_TYPES:
        check(f"**{vt}**" in text or f"- **{vt}**" in text, f"System prompt mentions value type {vt}")

    check('"parameters"' in text, "System prompt defines output schema with 'parameters' key")
    check('"excerpt"' in text, "System prompt output schema has 'excerpt' field")
    check('"reasoning"' in text, "System prompt output schema has 'reasoning' field")
    check('"line_number"' in text, "System prompt output schema has 'line_number' field")

    check("JSON" in text, "System prompt mentions JSON output format")

    check("NOTE" in text, "System prompt warns about NOTE blocks")
    check('"may"' in text or "'may'" in text, "System prompt discusses 'may' disambiguation")

    from run_prompt import estimate_tokens
    tokens = estimate_tokens(text)
    check(tokens <= 1200, f"System prompt is ≤1200 tokens ({tokens} estimated)", warn_only=True)


def validate_assembler() -> None:
    print("\n4. Validating run_prompt.py assembly")
    print("-" * 40)

    from run_prompt import (
        assemble_prompt,
        chunk_spec_file,
        estimate_tokens,
        load_system_prompt,
        load_examples,
        load_udb_param_names,
    )

    system = load_system_prompt()
    check(len(system) > 100, "System prompt loads successfully")

    examples = load_examples()
    check(len(examples.get("positive_examples", [])) >= 5, "Examples load successfully")

    names = load_udb_param_names()
    check(len(names) >= 100, f"UDB param names load successfully ({len(names)} names)")

    test_file = SPEC_DIR / "machine.adoc"
    if not test_file.exists():
        print("  SKIP: machine.adoc not available for assembly test")
        return

    text = test_file.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    chunk_text = "".join(lines[3334:3400])
    meta = {
        "file": "machine.adoc",
        "start_line": 3335,
        "end_line": 3400,
        "total_lines": len(lines),
        "chunk_index": 1,
        "total_chunks": 1,
    }

    prompt = assemble_prompt(chunk_text, meta, model="gpt-4o")
    check("system" in prompt, "Assembled prompt has 'system' key")
    check("user" in prompt, "Assembled prompt has 'user' key")
    check("estimated_tokens" in prompt, "Assembled prompt has 'estimated_tokens'")

    total = prompt["estimated_tokens"]
    check(total < 128_000, f"Assembled prompt fits in gpt-4o context ({total:,} tokens)")

    check(
        "NUM_PMP_ENTRIES" in prompt["user"],
        "UDB param names appear in user message",
    )
    check(
        "Few-Shot Examples" in prompt["user"],
        "Few-shot examples appear in user message",
    )
    check(
        "Specification Text" in prompt["user"],
        "Spec chunk header appears in user message",
    )

    try:
        assemble_prompt(chunk_text, meta, model="llama-3-70b")
        errors.append("  FAIL: Should have raised ValueError for llama-3-70b context overflow")
    except ValueError:
        check(True, "Context overflow correctly raises ValueError for small models")

    prompt_no_extras = assemble_prompt(
        chunk_text, meta,
        model="default",
        include_examples=False,
        include_param_names=False,
    )
    check(
        "Few-Shot Examples" not in prompt_no_extras["user"],
        "Examples correctly omitted when disabled",
    )
    check(
        prompt_no_extras["estimated_tokens"] < prompt["estimated_tokens"],
        "Token count is lower without examples/names",
    )


def validate_chunking() -> None:
    print("\n5. Validating chunking logic")
    print("-" * 40)

    from run_prompt import chunk_spec_file

    test_file = SPEC_DIR / "machine.adoc"
    if not test_file.exists():
        print("  SKIP: machine.adoc not available for chunking test")
        return

    chunks = chunk_spec_file(test_file, max_chunk_tokens=40_000)
    check(len(chunks) >= 1, f"Chunking produces at least 1 chunk ({len(chunks)} chunks)")

    all_text = test_file.read_text(encoding="utf-8")
    total_lines = len(all_text.splitlines())

    check(
        chunks[0][1]["start_line"] == 1,
        "First chunk starts at line 1",
    )
    check(
        chunks[-1][1]["end_line"] == total_lines,
        f"Last chunk ends at last line ({chunks[-1][1]['end_line']} == {total_lines})",
    )

    for chunk_text, meta in chunks:
        check(
            meta["total_chunks"] == len(chunks),
            f"Chunk {meta['chunk_index']} total_chunks is correct",
        )

    if len(chunks) > 1:
        for i in range(1, len(chunks)):
            prev_end = chunks[i - 1][1]["end_line"]
            curr_start = chunks[i][1]["start_line"]
            check(
                curr_start <= prev_end,
                f"Chunks {i} and {i+1} overlap (prev_end={prev_end}, curr_start={curr_start})",
            )

    small_chunks = chunk_spec_file(test_file, max_chunk_tokens=5_000)
    check(
        len(small_chunks) > len(chunks),
        f"Smaller max_tokens produces more chunks ({len(small_chunks)} > {len(chunks)})",
    )

    for _, meta in small_chunks:
        from run_prompt import estimate_tokens
        chunk_text = _
        tokens = estimate_tokens(chunk_text)
        check(
            tokens < 8_000,
            f"Chunk {meta['chunk_index']} with 5K limit is under 8K tokens ({tokens:,})",
            warn_only=True,
        )


def main() -> None:
    global checks_passed

    print("=" * 60)
    print("Phase 2 Deliverable Validation")
    print("=" * 60)

    validate_taxonomy()
    validate_examples()
    validate_system_prompt()
    validate_assembler()
    validate_chunking()

    print()
    print("=" * 60)
    print(f"Results: {checks_passed} passed, {len(errors)} failed, {len(warnings)} warnings")
    print("=" * 60)

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(w)

    if errors:
        print("\nErrors:")
        for e in errors:
            print(e)
        sys.exit(1)
    else:
        print("\nAll checks passed!")


if __name__ == "__main__":
    main()
