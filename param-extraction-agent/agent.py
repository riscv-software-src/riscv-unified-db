#!/usr/bin/env python3
"""
agent.py — ParameterExtractorAgent

LFX Fall 2026 PoC: extract RISC-V architectural parameters from ISA
manual text and emit strict UDB-style YAML.

Usage:
    export OPENAI_API_KEY=sk-...          # or ANTHROPIC_API_KEY=...
    python agent.py --input spec_chapter_1.txt --output params.yaml
    python agent.py --input spec_chapter_1.txt --output params.yaml \
        --provider anthropic --model claude-sonnet-4-6 --chunk-size 3000

Design notes (put these in your PR description):
  - Context management: chunk_text() splits large spec files into
    paragraph-aligned windows under `chunk_size` characters so we never
    blow the model's context window, and so each chunk stays a coherent
    "subsection" (proposal point 3).
  - Reproducibility: every run is a single deterministic CLI command
    with explicit --input/--output/--model flags. No hidden state.
  - Validation: raw LLM output is parsed as YAML then validated against
    the Pydantic ParameterFile schema (schema.py). If validation fails,
    the agent sends the error back to the model and asks it to fix its
    own output (self-correction loop, bounded retries) before falling
    back to skipping that chunk with a logged warning.
"""

from __future__ import annotations
import argparse
import os
import sys
import textwrap
from pathlib import Path

import yaml
from pydantic import ValidationError

from schema import ParameterFile
from prompts import build_messages

MAX_FIX_RETRIES = 2


class ParameterExtractorAgent:
    DEFAULT_MODELS = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-sonnet-4-6",
        "groq": "llama-3.3-70b-versatile",   # free tier, OpenAI-SDK compatible
        "gemini": "gemini-2.0-flash",        # free tier
    }

    def __init__(self, provider: str = "groq", model: str = None, chunk_size: int = 3500):
        self.provider = provider
        self.chunk_size = chunk_size
        self.model = model or self.DEFAULT_MODELS.get(provider, "gpt-4o-mini")
        self._client = self._init_client()

    # ------------------------------------------------------------------
    # Client setup
    # ------------------------------------------------------------------
    def _init_client(self):
        if self.provider == "openai":
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                sys.exit("ERROR: set OPENAI_API_KEY environment variable")
            return OpenAI(api_key=api_key)

        elif self.provider == "anthropic":
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                sys.exit("ERROR: set ANTHROPIC_API_KEY environment variable")
            return anthropic.Anthropic(api_key=api_key)

        elif self.provider == "groq":
            # Groq exposes an OpenAI-compatible endpoint, free tier,
            # no card required: https://console.groq.com
            from openai import OpenAI
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                sys.exit("ERROR: set GROQ_API_KEY environment variable "
                         "(get a free key at https://console.groq.com)")
            return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

        elif self.provider == "gemini":
            # Gemini also exposes an OpenAI-compatible endpoint, free
            # tier: https://aistudio.google.com/apikey
            from openai import OpenAI
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                sys.exit("ERROR: set GEMINI_API_KEY environment variable "
                         "(get a free key at https://aistudio.google.com/apikey)")
            return OpenAI(
                api_key=api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )

        else:
            sys.exit(f"ERROR: unknown provider '{self.provider}'")

    # ------------------------------------------------------------------
    # Context management: chunk the spec text into safe, coherent pieces
    # ------------------------------------------------------------------
    def chunk_text(self, text: str) -> list[str]:
        """
        Split on paragraph boundaries (blank lines) and pack paragraphs
        into chunks up to self.chunk_size characters, never splitting a
        paragraph mid-sentence. Keeps each chunk a coherent "subsection"
        rather than an arbitrary character slice.
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks, current = [], ""

        for para in paragraphs:
            candidate = f"{current}\n\n{para}" if current else para
            if len(candidate) > self.chunk_size and current:
                chunks.append(current)
                current = para
            else:
                current = candidate

        if current:
            chunks.append(current)
        return chunks

    # ------------------------------------------------------------------
    # LLM call (provider-agnostic wrapper)
    # ------------------------------------------------------------------
    def _call_llm(self, messages: list[dict]) -> str:
        if self.provider in ("openai", "groq", "gemini"):
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
            )
            return resp.choices[0].message.content

        elif self.provider == "anthropic":
            system = messages[0]["content"]
            convo = messages[1:]
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system,
                messages=convo,
            )
            return resp.content[0].text

    # ------------------------------------------------------------------
    # Extraction + validation/self-fix loop for a single chunk
    # ------------------------------------------------------------------
    def extract_chunk(self, chunk: str, chapter_hint: str) -> ParameterFile | None:
        messages = build_messages(chunk, chapter_hint)
        raw_output = self._call_llm(messages)

        for attempt in range(MAX_FIX_RETRIES + 1):
            cleaned = self._strip_markdown_fence(raw_output)
            try:
                parsed = yaml.safe_load(cleaned)
                return ParameterFile.model_validate(parsed)
            except (yaml.YAMLError, ValidationError) as e:
                if attempt == MAX_FIX_RETRIES:
                    print(
                        f"  [warn] chunk failed validation after "
                        f"{MAX_FIX_RETRIES} fix attempts, skipping. Error: {e}",
                        file=sys.stderr,
                    )
                    return None
                # Ask the model to fix its own output — this is the
                # "clean up messy output" step from proposal point 4.
                fix_prompt = (
                    "Your previous YAML output failed schema validation "
                    f"with this error:\n{e}\n\n"
                    "Return ONLY corrected, valid YAML matching the same "
                    "schema. No prose, no code fences."
                )
                messages.append({"role": "assistant", "content": raw_output})
                messages.append({"role": "user", "content": fix_prompt})
                raw_output = self._call_llm(messages)

    @staticmethod
    def _strip_markdown_fence(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = lines[1:] if lines[0].startswith("```") else lines
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)
        return text

    # ------------------------------------------------------------------
    # Full run: input file -> chunks -> extraction -> merged YAML file
    # ------------------------------------------------------------------
    def run(self, input_path: str, output_path: str, chapter_hint: str = "unknown"):
        text = Path(input_path).read_text(encoding="utf-8")
        chunks = self.chunk_text(text)
        print(f"Split input into {len(chunks)} chunk(s) "
              f"(chunk_size={self.chunk_size} chars)")

        all_params = []
        for i, chunk in enumerate(chunks, start=1):
            print(f"[{i}/{len(chunks)}] extracting...")
            result = self.extract_chunk(chunk, chapter_hint)
            if result:
                all_params.extend(result.parameters)

        merged = {
            "chapter": chapter_hint,
            "source_document": Path(input_path).name,
            "parameters": [p.model_dump(by_alias=True, exclude_none=True) for p in all_params],
        }

        Path(output_path).write_text(
            yaml.dump(merged, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(f"Wrote {len(all_params)} parameter(s) to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract RISC-V architectural parameters into UDB-style YAML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(__doc__ or ""),
    )
    parser.add_argument("--input", required=True, help="Path to input spec text file")
    parser.add_argument("--output", required=True, help="Path to write output YAML")
    parser.add_argument("--provider", default="groq",
                         choices=["openai", "anthropic", "groq", "gemini"])
    parser.add_argument("--model", default=None, help="Override default model name")
    parser.add_argument("--chunk-size", type=int, default=3500,
                         help="Max characters per chunk sent to the LLM")
    parser.add_argument("--chapter-hint", default="unknown",
                         help="Chapter/section label for this input file")
    args = parser.parse_args()

    agent = ParameterExtractorAgent(
        provider=args.provider, model=args.model, chunk_size=args.chunk_size
    )
    agent.run(args.input, args.output, chapter_hint=args.chapter_hint)


if __name__ == "__main__":
    main()