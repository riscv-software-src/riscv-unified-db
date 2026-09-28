#!/usr/bin/env python3
# Copyright (c) 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear
"""
LLM extraction pipeline for RISC-V architectural parameters.

Assembles prompts from Phase 2 templates, sends them to LLM APIs,
parses structured JSON responses, and stores results per chunk and model.

Modes:
  pilot   — run extraction on machine.adoc chunks only (for prompt validation)
  run     — run extraction on all chunks
  merge   — merge per-chunk results into a single all_results_{model}.json
  status  — show progress (which chunks have been processed)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
CHUNKS_DIR = PROJECT_DIR / "chunks"
RESULTS_DIR = PROJECT_DIR / "results"
PROMPTS_DIR = PROJECT_DIR / "prompts" / "v1"
DATA_DIR = PROJECT_DIR / "data"

PROMPT_VERSION = os.environ.get("PROMPT_VERSION", "v1")

sys.path.insert(0, str(SCRIPT_DIR))
from run_prompt import (  # noqa: E402
    estimate_tokens,
    format_examples_section,
    format_param_names_section,
    load_examples,
    load_system_prompt,
    load_udb_param_names,
)

logger = logging.getLogger("extract")

# Rate limit: 30K input tokens per minute for this API tier.
# We track token expenditure and sleep as needed.
RATE_LIMIT_TOKENS_PER_MIN = int(os.environ.get("RATE_LIMIT_TPM", "30000"))


class RateLimiter:
    """Token-bucket rate limiter respecting Anthropic's per-minute input token limit.

    Uses 75% of the nominal limit as effective budget to account for token
    estimation inaccuracies and API-side accounting differences.
    """

    SAFETY_FACTOR = 0.75

    def __init__(self, tokens_per_min: int = RATE_LIMIT_TOKENS_PER_MIN) -> None:
        self.tokens_per_min = tokens_per_min
        self.effective_limit = int(tokens_per_min * self.SAFETY_FACTOR)
        self._log: list[tuple[float, int]] = []

    def _prune(self, now: float) -> None:
        cutoff = now - 60.0
        self._log = [(t, n) for t, n in self._log if t > cutoff]

    def wait_if_needed(self, estimated_tokens: int) -> float:
        """Block until we have budget for `estimated_tokens`. Returns seconds waited."""
        total_waited = 0.0
        while True:
            now = time.monotonic()
            self._prune(now)
            used = sum(n for _, n in self._log)
            if used + estimated_tokens <= self.effective_limit:
                break
            if not self._log:
                break
            oldest_ts = self._log[0][0]
            wait = max(oldest_ts + 61.0 - now, 5.0)
            logger.info(
                "  Rate limit: %d/%d tokens used (effective %d), waiting %.0fs",
                used,
                self.tokens_per_min,
                self.effective_limit,
                wait,
            )
            time.sleep(wait)
            total_waited += wait
        return total_waited

    def record(self, tokens: int) -> None:
        self._log.append((time.monotonic(), tokens))


REQUIRED_PARAM_FIELDS = {
    "excerpt",
    "line_number",
    "parameter_name",
    "existing_udb_name",
    "class",
    "value_type",
    "confidence",
    "reasoning",
}

VALID_CLASSES = {
    "NORM_DIRECT",
    "NORM_CSR_WARL",
    "NORM_CSR_RW",
    "SW_RULE",
    "NON_ISA",
    "NON_NORM",
    "DOC_RULE",
    "UNKNOWN",
}

VALID_VALUE_TYPES = {"binary", "enum", "range", "set", "bitmask", "value"}

# Source files with no architectural parameters (boilerplate, non-normative,
# formal proofs, examples, or top-level include wrappers). Skipping these
# saves ~23% of input tokens with zero recall loss.
SKIP_SOURCE_FILES: set[str] = {
    "bibliography.adoc",
    "bitmanip-examples.adoc",
    "calling-convention.adoc",
    "colophon.adoc",
    "index.adoc",
    "mm-alloy.adoc",
    "mm-eplan.adoc",
    "mm-formal.adoc",
    "mm-herd.adoc",
    "priv-history.adoc",
    "priv-insns.adoc",
    "priv-preface.adoc",
    "priv-rationale.adoc",
    "rationale.adoc",
    "riscv-privileged.adoc",
    "riscv-unprivileged.adoc",
    "rv-32-64g.adoc",
    "symbols.adoc",
    "vector-examples.adoc",
}

MODEL_ALIASES: dict[str, dict[str, str]] = {
    "claude": {
        "provider": "anthropic",
        "model_id": "claude-sonnet-4-20250514",
        "display_name": "claude-sonnet-4",
    },
    "gpt4o": {
        "provider": "openai",
        "model_id": "gpt-4o-2024-11-20",
        "display_name": "gpt-4o",
    },
    "gemini": {
        "provider": "google",
        "model_id": "gemini-2.5-pro",
        "display_name": "gemini-2.5-pro",
    },
}


@dataclass
class ExtractionResult:
    chunk_id: str
    source_file: str
    start_line: int
    end_line: int
    content_start_line: int
    model: str
    parameters: list[dict]
    skipped_non_parameters: list[dict]
    raw_response: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    timestamp: str
    error: str | None = None
    retry_count: int = 0

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source_file": self.source_file,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content_start_line": self.content_start_line,
            "model": self.model,
            "parameters": self.parameters,
            "skipped_non_parameters": self.skipped_non_parameters,
            "raw_response": self.raw_response,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
            "error": self.error,
            "retry_count": self.retry_count,
        }


# --- Prompt assembly ---


def build_user_message(chunk_text: str, chunk_meta: dict) -> str:
    """Build the user message from examples + param names + chunk."""
    examples = load_examples()
    param_names = load_udb_param_names()

    parts = [
        format_examples_section(examples),
        format_param_names_section(param_names),
        _format_chunk(chunk_text, chunk_meta),
    ]
    return "\n\n---\n\n".join(parts)


def _format_chunk(chunk_text: str, meta: dict) -> str:
    lines = [
        "## Specification Text to Analyze",
        "",
        f"File: `{meta['source_file']}`",
        f"Lines: {meta['start_line']}-{meta['end_line']}",
        "",
        "Analyze the following specification text and extract all architectural parameters.",
        f"Treat lines before {meta['content_start_line']} as overlap context only; avoid re-extracting a parameter when its defining sentence appears entirely in that overlap region.",
        f"Include line numbers relative to the original file (starting from line {meta['start_line']}).",
        "",
        "```",
        chunk_text,
        "```",
    ]
    return "\n".join(lines)


# --- LLM API callers ---


def call_anthropic(system_prompt: str, user_message: str, model_id: str) -> dict:
    """Call the Anthropic API with 429 backoff. Returns {text, input_tokens, output_tokens}."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("Install anthropic: pip install anthropic")

    client = anthropic.Anthropic(max_retries=0)

    max_429_retries = 5
    for retry_429 in range(max_429_retries + 1):
        try:
            t0 = time.monotonic()
            response = client.messages.create(
                model=model_id,
                max_tokens=int(os.environ.get("MAX_OUTPUT_TOKENS","8192")),
                temperature=0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            latency = int((time.monotonic() - t0) * 1000)

            text = response.content[0].text
            return {
                "text": text,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "latency_ms": latency,
            }
        except anthropic.RateLimitError:
            if retry_429 >= max_429_retries:
                raise
            wait = 30 * (2**retry_429)
            logger.warning(
                "  429 rate limit, backing off %ds (attempt %d/%d)",
                wait,
                retry_429 + 1,
                max_429_retries,
            )
            time.sleep(wait)

    raise RuntimeError("Unreachable")


def call_openai(system_prompt: str, user_message: str, model_id: str) -> dict:
    """Call the OpenAI API. Returns {text, input_tokens, output_tokens}."""
    try:
        import openai
    except ImportError:
        raise RuntimeError("Install openai: pip install openai")

    client = openai.OpenAI()
    t0 = time.monotonic()
    response = client.chat.completions.create(
        model=model_id,
        temperature=0,
        max_tokens=int(os.environ.get("MAX_OUTPUT_TOKENS","8192")),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    latency = int((time.monotonic() - t0) * 1000)

    text = response.choices[0].message.content
    usage = response.usage
    return {
        "text": text,
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "latency_ms": latency,
    }


def call_google(system_prompt: str, user_message: str, model_id: str) -> dict:
    """Call the Google Gemini API. Returns {text, input_tokens, output_tokens}."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("Install google-genai: pip install google-genai")

    client = genai.Client()
    t0 = time.monotonic()
    response = client.models.generate_content(
        model=model_id,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0,
            max_output_tokens=8192,
        ),
    )
    latency = int((time.monotonic() - t0) * 1000)

    text = response.text
    input_tokens = response.usage_metadata.prompt_token_count or 0
    output_tokens = response.usage_metadata.candidates_token_count or 0

    return {
        "text": text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency,
    }


def call_llm(
    provider: str,
    system_prompt: str,
    user_message: str,
    model_id: str,
) -> dict:
    """Dispatch to the appropriate LLM provider."""
    callers = {
        "anthropic": call_anthropic,
        "openai": call_openai,
        "google": call_google,
    }
    caller = callers.get(provider)
    if not caller:
        raise ValueError(f"Unknown provider: {provider}")
    return caller(system_prompt, user_message, model_id)


# --- JSON parsing and validation ---


def extract_json_from_response(text: str) -> dict | None:
    """Extract JSON object from LLM response text, handling markdown fences."""
    text = text.strip()

    fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    return None


def validate_result(data: dict) -> tuple[list[dict], list[dict], list[str]]:
    """
    Validate extracted JSON against expected schema.
    Returns (parameters, skipped, warnings).
    """
    warnings: list[str] = []

    if "parameters" not in data:
        warnings.append("Missing 'parameters' key in response")
        params = []
    else:
        params = data["parameters"]
        if not isinstance(params, list):
            warnings.append("'parameters' is not a list")
            params = []

    skipped = data.get("skipped_non_parameters", [])
    if not isinstance(skipped, list):
        skipped = []

    validated_params: list[dict] = []
    for i, p in enumerate(params):
        if not isinstance(p, dict):
            warnings.append(f"Parameter {i} is not a dict")
            continue

        missing = REQUIRED_PARAM_FIELDS - set(p.keys())
        if missing:
            warnings.append(
                f"Parameter {i} ({p.get('parameter_name', '?')}) missing fields: {missing}"
            )

        cls = p.get("class", "")
        if cls and cls not in VALID_CLASSES:
            warnings.append(f"Parameter {p.get('parameter_name', '?')}: invalid class '{cls}'")

        vt = p.get("value_type", "")
        if vt and vt not in VALID_VALUE_TYPES:
            warnings.append(f"Parameter {p.get('parameter_name', '?')}: invalid value_type '{vt}'")

        validated_params.append(p)

    return validated_params, skipped, warnings


# --- Core extraction ---


def process_chunk(
    chunk_meta: dict,
    chunk_text: str,
    model_alias: str,
    system_prompt: str,
    delay_seconds: float = 1.0,
    max_retries: int = 1,
    rate_limiter: RateLimiter | None = None,
) -> ExtractionResult:
    """Process a single chunk through the LLM pipeline."""
    model_info = MODEL_ALIASES[model_alias]
    provider = model_info["provider"]
    model_id = model_info["model_id"]
    display_name = model_info["display_name"]

    user_message = build_user_message(chunk_text, chunk_meta)
    est_tokens = estimate_tokens(system_prompt + user_message)

    logger.info(
        "Processing %s (%s, lines %d-%d, ~%d tokens)",
        chunk_meta["chunk_id"],
        chunk_meta["source_file"],
        chunk_meta["start_line"],
        chunk_meta["end_line"],
        est_tokens,
    )

    if rate_limiter:
        rate_limiter.wait_if_needed(est_tokens)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                logger.info("  Retry %d/%d for %s", attempt, max_retries, chunk_meta["chunk_id"])
                time.sleep(delay_seconds * 2)

            api_result = call_llm(provider, system_prompt, user_message, model_id)
            if rate_limiter:
                rate_limiter.record(api_result["input_tokens"])
            raw_text = api_result["text"]

            parsed = extract_json_from_response(raw_text)
            if parsed is None:
                if attempt < max_retries:
                    last_error = "JSON parse failed"
                    logger.warning("  JSON parse failed, will retry")
                    continue
                logger.error("  JSON parse failed after all retries")
                return ExtractionResult(
                    chunk_id=chunk_meta["chunk_id"],
                    source_file=chunk_meta["source_file"],
                    start_line=chunk_meta["start_line"],
                    end_line=chunk_meta["end_line"],
                    content_start_line=chunk_meta["content_start_line"],
                    model=display_name,
                    parameters=[],
                    skipped_non_parameters=[],
                    raw_response=raw_text,
                    input_tokens=api_result["input_tokens"],
                    output_tokens=api_result["output_tokens"],
                    latency_ms=api_result["latency_ms"],
                    timestamp=datetime.now(UTC).isoformat(),
                    error="JSON parse failed",
                    retry_count=attempt,
                )

            params, skipped, warnings = validate_result(parsed)
            for w in warnings:
                logger.warning("  Validation: %s", w)

            logger.info(
                "  Found %d parameters, %d skipped (%d input, %d output tokens, %dms)",
                len(params),
                len(skipped),
                api_result["input_tokens"],
                api_result["output_tokens"],
                api_result["latency_ms"],
            )

            return ExtractionResult(
                chunk_id=chunk_meta["chunk_id"],
                source_file=chunk_meta["source_file"],
                start_line=chunk_meta["start_line"],
                end_line=chunk_meta["end_line"],
                content_start_line=chunk_meta["content_start_line"],
                model=display_name,
                parameters=params,
                skipped_non_parameters=skipped,
                raw_response=raw_text,
                input_tokens=api_result["input_tokens"],
                output_tokens=api_result["output_tokens"],
                latency_ms=api_result["latency_ms"],
                timestamp=datetime.now(UTC).isoformat(),
                retry_count=attempt,
            )

        except Exception as exc:
            last_error = str(exc)
            logger.error("  API error: %s", last_error)
            if attempt < max_retries:
                time.sleep(delay_seconds * 2)

    return ExtractionResult(
        chunk_id=chunk_meta["chunk_id"],
        source_file=chunk_meta["source_file"],
        start_line=chunk_meta["start_line"],
        end_line=chunk_meta["end_line"],
        content_start_line=chunk_meta["content_start_line"],
        model=display_name,
        parameters=[],
        skipped_non_parameters=[],
        raw_response="",
        input_tokens=0,
        output_tokens=0,
        latency_ms=0,
        timestamp=datetime.now(UTC).isoformat(),
        error=last_error or "Unknown error",
        retry_count=max_retries,
    )


# --- Orchestration ---


def load_manifest() -> dict:
    manifest_path = CHUNKS_DIR / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}. Run chunker.py first.")
    with open(manifest_path) as f:
        return json.load(f)


def load_chunk_text(chunk_id: str) -> str:
    """Load chunk text from file, stripping the metadata header."""
    chunk_path = CHUNKS_DIR / f"{chunk_id}.txt"
    if not chunk_path.exists():
        raise FileNotFoundError(f"Chunk file not found: {chunk_path}")

    text = chunk_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    content_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "#":
            content_start = i + 1
            break
        if not line.startswith("#"):
            content_start = i
            break

    if content_start < len(lines) and lines[content_start].strip() == "":
        content_start += 1

    return "".join(lines[content_start:])


def get_result_path(model_alias: str, chunk_id: str) -> Path:
    display = MODEL_ALIASES[model_alias]["display_name"]
    if PROMPT_VERSION != "v1":
        model_dir = RESULTS_DIR / PROMPT_VERSION / display
    else:
        model_dir = RESULTS_DIR / display
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir / f"{chunk_id}.json"


def is_chunk_done(model_alias: str, chunk_id: str) -> bool:
    result_path = get_result_path(model_alias, chunk_id)
    if not result_path.exists():
        return False
    try:
        with open(result_path) as f:
            data = json.load(f)
        return data.get("error") is None
    except (json.JSONDecodeError, KeyError):
        return False


def run_extraction(
    model_alias: str,
    chunk_filter: list[str] | None = None,
    source_filter: str | None = None,
    delay: float = 1.0,
    skip_done: bool = True,
    max_retries: int = 1,
    include_skipped_sources: bool = False,
) -> list[ExtractionResult]:
    """Run extraction on selected chunks."""
    manifest = load_manifest()
    system_prompt = load_system_prompt()

    chunks_to_process = manifest["chunks"]

    if not include_skipped_sources:
        before = len(chunks_to_process)
        chunks_to_process = [
            c for c in chunks_to_process if c["source_file"] not in SKIP_SOURCE_FILES
        ]
        n_skipped_sources = before - len(chunks_to_process)
        if n_skipped_sources:
            logger.info(
                "Skipping %d chunks from non-parameter source files",
                n_skipped_sources,
            )

    if source_filter:
        chunks_to_process = [c for c in chunks_to_process if source_filter in c["source_file"]]
    if chunk_filter:
        chunks_to_process = [c for c in chunks_to_process if c["chunk_id"] in chunk_filter]

    limiter = RateLimiter()

    results: list[ExtractionResult] = []
    total = len(chunks_to_process)
    skipped = 0

    for idx, chunk_meta in enumerate(chunks_to_process):
        chunk_id = chunk_meta["chunk_id"]

        if skip_done and is_chunk_done(model_alias, chunk_id):
            logger.info("Skipping %s (already done)", chunk_id)
            skipped += 1
            continue

        chunk_text = load_chunk_text(chunk_id)
        result = process_chunk(
            chunk_meta=chunk_meta,
            chunk_text=chunk_text,
            model_alias=model_alias,
            system_prompt=system_prompt,
            delay_seconds=delay,
            max_retries=max_retries,
            rate_limiter=limiter,
        )

        result_path = get_result_path(model_alias, chunk_id)
        with open(result_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
            f.write("\n")

        results.append(result)

        if delay > 0 and idx < total - 1:
            time.sleep(delay)

    logger.info(
        "Done: %d processed, %d skipped, %d total",
        len(results),
        skipped,
        total,
    )
    return results


def merge_results(model_alias: str) -> Path:
    """Merge per-chunk results into a single file."""
    display = MODEL_ALIASES[model_alias]["display_name"]
    if PROMPT_VERSION != "v1":
        model_dir = RESULTS_DIR / PROMPT_VERSION / display
    else:
        model_dir = RESULTS_DIR / display

    if not model_dir.exists():
        raise FileNotFoundError(f"No results directory: {model_dir}")

    chunk_files = sorted(model_dir.glob("chunk_*.json"))
    if not chunk_files:
        raise FileNotFoundError(f"No chunk results in {model_dir}")

    all_results: list[dict] = []
    total_params = 0
    total_skipped = 0
    total_input_tokens = 0
    total_output_tokens = 0
    errors = 0

    for cf in chunk_files:
        with open(cf) as f:
            data = json.load(f)
        all_results.append(data)
        total_params += len(data.get("parameters", []))
        total_skipped += len(data.get("skipped_non_parameters", []))
        total_input_tokens += data.get("input_tokens", 0)
        total_output_tokens += data.get("output_tokens", 0)
        if data.get("error"):
            errors += 1

    output = {
        "model": display,
        "total_chunks": len(all_results),
        "total_parameters": total_params,
        "total_skipped": total_skipped,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "errors": errors,
        "results": all_results,
    }

    if PROMPT_VERSION != "v1":
        output_path = RESULTS_DIR / PROMPT_VERSION / f"all_results_{display}.json"
    else:
        output_path = RESULTS_DIR / f"all_results_{display}.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")

    logger.info(
        "Merged %d chunks -> %s (%d params, %d skipped, %d errors, %d/%d tokens)",
        len(all_results),
        output_path.name,
        total_params,
        total_skipped,
        errors,
        total_input_tokens,
        total_output_tokens,
    )
    return output_path


# --- CLI ---


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_pilot(args: argparse.Namespace) -> None:
    """Pilot extraction on machine.adoc only."""
    setup_logging(args.verbose)
    logger.info("Pilot run: model=%s, source=machine.adoc", args.model)
    results = run_extraction(
        model_alias=args.model,
        source_filter="machine.adoc",
        delay=args.delay,
        skip_done=not args.force,
        max_retries=args.retries,
    )
    _print_summary(results, args.model)


def cmd_run(args: argparse.Namespace) -> None:
    """Run extraction on all chunks."""
    setup_logging(args.verbose)
    source = args.source if args.source else None
    include_all = getattr(args, "include_all", False)
    logger.info("Full run: model=%s, source=%s", args.model, source or "all")
    results = run_extraction(
        model_alias=args.model,
        source_filter=source,
        delay=args.delay,
        skip_done=not args.force,
        max_retries=args.retries,
        include_skipped_sources=include_all,
    )
    _print_summary(results, args.model)


def cmd_merge(args: argparse.Namespace) -> None:
    """Merge per-chunk results."""
    setup_logging(args.verbose)
    output_path = merge_results(args.model)
    print(f"Merged results written to: {output_path}")


def cmd_status(args: argparse.Namespace) -> None:
    """Show extraction progress."""
    setup_logging(False)
    manifest = load_manifest()
    total_chunks = manifest["total_chunks"]
    processable = [c for c in manifest["chunks"] if c["source_file"] not in SKIP_SOURCE_FILES]
    print(
        f"Total chunks: {total_chunks} ({len(processable)} with parameters, "
        f"{total_chunks - len(processable)} skipped)"
    )

    for _alias, info in MODEL_ALIASES.items():
        display = info["display_name"]
        if PROMPT_VERSION != "v1":
            model_dir = RESULTS_DIR / PROMPT_VERSION / display
        else:
            model_dir = RESULTS_DIR / display
        if not model_dir.exists():
            print(f"  {display}: not started")
            continue

        done_files = list(model_dir.glob("chunk_*.json"))
        done = 0
        errored = 0
        total_params = 0
        total_input = 0
        total_output = 0
        for df in done_files:
            try:
                with open(df) as f:
                    data = json.load(f)
                if data.get("error"):
                    errored += 1
                else:
                    done += 1
                    total_params += len(data.get("parameters", []))
                total_input += data.get("input_tokens", 0)
                total_output += data.get("output_tokens", 0)
            except (json.JSONDecodeError, KeyError):
                errored += 1

        print(
            f"  {display}: {done}/{total_chunks} done, {errored} errors, "
            f"{total_params} params, {total_input:,}+{total_output:,} tokens"
        )


def _print_summary(results: list[ExtractionResult], model_alias: str) -> None:
    if not results:
        print("No chunks processed (all skipped or none matched filter).")
        return

    display = MODEL_ALIASES[model_alias]["display_name"]
    total_params = sum(len(r.parameters) for r in results)
    total_skipped = sum(len(r.skipped_non_parameters) for r in results)
    total_input = sum(r.input_tokens for r in results)
    total_output = sum(r.output_tokens for r in results)
    total_latency = sum(r.latency_ms for r in results)
    error_count = sum(1 for r in results if r.error)

    print(f"\n{'=' * 50}")
    print(f"Extraction Summary: {display}")
    print(f"{'=' * 50}")
    print(f"  Chunks processed: {len(results)}")
    print(f"  Parameters found: {total_params}")
    print(f"  Non-params skipped: {total_skipped}")
    print(f"  Errors: {error_count}")
    print(f"  Input tokens: {total_input:,}")
    print(f"  Output tokens: {total_output:,}")
    print(f"  Total latency: {total_latency / 1000:.1f}s")
    if error_count:
        print("\n  Errors:")
        for r in results:
            if r.error:
                print(f"    {r.chunk_id}: {r.error}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM extraction pipeline for RISC-V parameters",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Shared args
    def add_common_args(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--model",
            required=True,
            choices=list(MODEL_ALIASES.keys()),
            help="Model alias to use",
        )
        p.add_argument(
            "--delay", type=float, default=1.0, help="Delay between API calls in seconds"
        )
        p.add_argument("--retries", type=int, default=1, help="Max retries on parse failure")
        p.add_argument(
            "--force", action="store_true", help="Re-process chunks even if results exist"
        )
        p.add_argument("-v", "--verbose", action="store_true")

    p_pilot = subparsers.add_parser("pilot", help="Pilot on machine.adoc")
    add_common_args(p_pilot)
    p_pilot.set_defaults(func=cmd_pilot)

    p_run = subparsers.add_parser("run", help="Run on all chunks")
    add_common_args(p_run)
    p_run.add_argument("--source", help="Filter to a specific source file")
    p_run.add_argument(
        "--include-all",
        action="store_true",
        help="Include non-parameter source files (normally skipped)",
    )
    p_run.set_defaults(func=cmd_run)

    p_merge = subparsers.add_parser("merge", help="Merge per-chunk results")
    p_merge.add_argument("--model", required=True, choices=list(MODEL_ALIASES.keys()))
    p_merge.add_argument("-v", "--verbose", action="store_true")
    p_merge.set_defaults(func=cmd_merge)

    p_status = subparsers.add_parser("status", help="Show progress")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
