# RISC-V Parameter Extraction Agent — LFX Fall 2026 PoC

A proof-of-concept AI agent that extracts architectural parameters from
RISC-V ISA manual text and emits validated UDB-style YAML.

## Why this design

| Proposal ask | What this PoC does |
|---|---|
| Use manually created parameter lists as training examples | `prompts.py` builds a few-shot prompt from 3 worked examples (swap in real examples from the ISA Manual yaml / keyword_matches sheet / UDB yaml) |
| Extend the classification scheme | `schema.py` `ParameterEntry` models `kind` (boolean/integer/enum/string/**warl**/**wlrl**), possible_values, extension, chapter_source, confidence — extend further as the SIG's scheme grows |
| AI coding agents + reproducible, reusable workflows | `ParameterExtractorAgent` class, single deterministic CLI command, paragraph-aware chunking for context management |
| Export in UDB yaml format, no missing fields | `kind` and `long_name` are now **required, non-optional** Pydantic fields. If the LLM omits either, validation hard-fails and the self-correction loop (`extract_chunk`) sends the error back to the model and asks it to fix its own output — verified in testing that this actually recovers a bad response into a valid one |
| Correct WARL/WLRL classification | System prompt explicitly instructs: only classify a field as `warl`/`wlrl` when the *text itself* says the legal-value set is implementation-chosen — being a CSR bitfield alone is not sufficient. WARL/WLRL entries leave `possible_values` null rather than listing one implementation's example values |
| PR with reviewed parameter files | `agent.py` output is a ready-to-review `params.yaml`; commit that alongside the code |

## Setup

```bash
pip install -r requirements.txt
```

No OpenAI/Anthropic key? Use a free-tier provider instead — both are
wired up as OpenAI-compatible endpoints:

- **Groq** (fast, free, no card): get a key at https://console.groq.com
  ```bash
  export GROQ_API_KEY=gsk_...
  ```
- **Gemini** (free tier, no card): get a key at https://aistudio.google.com/apikey
  ```bash
  export GEMINI_API_KEY=AI...
  ```

Or if you do have paid keys:
```bash
export OPENAI_API_KEY=sk-...      # or: export ANTHROPIC_API_KEY=...
```

## Run

```bash
# free option (default provider is groq)
python agent.py --input spec_chapter_3.txt --output params.yaml --chapter-hint "3.1.6"

# explicit provider
python agent.py --input spec_chapter_3.txt --output params.yaml \
  --chapter-hint "3.1.6" --provider gemini
```

## Test without an API key

```bash
python test_offline.py
```

This mocks the LLM call so you can verify chunking + validation logic
locally before spending API credits.

