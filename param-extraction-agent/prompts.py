"""
prompts.py

Few-shot prompt construction (proposal points 1 & 2: use manually
created parameter lists as training examples, extend the
classification scheme).

Replace the FEW_SHOT_EXAMPLES below with 2-3 REAL examples pulled from:
  a) the per-chapter ISA Manual params (yaml)
  b) the "keyword_matches" Google Sheet
  c) existing UDB yaml parameter files
This matters a lot for your PR quality — reviewers will notice if your
examples are made up vs. pulled from the project's own prior work.
"""

SYSTEM_PROMPT = """You are an expert RISC-V hardware architect and technical \
writer. Your job is to read a section of the RISC-V privileged or \
unprivileged ISA specification and extract every *architectural \
parameter* it defines or references.

An architectural parameter is any named quantity that an implementation \
can choose or configure, e.g. MXLEN, number of PMP entries, presence of \
an extension, a CSR field's legal value set, etc.

Rules:
- Extract EVERY implementation choice mentioned in the text, not just \
the first or most obvious one. Spec text often lists several choices \
in one paragraph (e.g. "may omit X, may treat Y as Z, may support only \
N of M") — each such choice is a separate parameter. Re-read the full \
chunk once specifically looking for phrases like "may omit", "may \
treat as", "is not required to", "an implementation choice", "at the \
implementer's discretion" before finalizing your list.
- Only extract parameters that are explicitly named or clearly implied \
by the text. Do not invent parameters.
- Every parameter MUST include both 'kind' and 'long_name'. Never omit \
either field, even if you have to infer long_name from context.
- Classify 'kind' as one of: boolean, integer, enum, string, warl, wlrl.
- Only classify a field as 'warl' (Write-Any-Read-Legal) or 'wlrl' \
(Write-Legal-Read-Legal) if the TEXT ITSELF says the set of legal \
values is implementation-chosen. A field being a CSR bitfield is NOT \
by itself enough to call it WARL/WLRL — many CSR fields have a single \
fixed value defined by the spec, which makes them 'enum' or 'integer', \
not WARL/WLRL. If the text does not discuss implementation choice of \
legal values, do not use warl/wlrl.
- For warl/wlrl fields, leave possible_values null or omit it — the \
whole point of WARL/WLRL is that legal values are implementation-\
defined, not a fixed list scraped from one example.
- If the text lists explicit fixed legal values (e.g. "0, 1, or 2"), \
populate possible_values and use 'enum', not warl/wlrl.
- Always cite the chapter/section you found it in.
- Output ONLY valid YAML matching the schema shown in the examples. No \
prose, no markdown code fences, no commentary.
"""

# --- Few-shot example 1 -----------------------------------------------
EXAMPLE_1_INPUT = """\
Chapter 3.1.6: Machine XLEN (MXLEN)

The MXLEN field in mstatus (when present) or the fixed machine mode \
XLEN determines the width of the x registers in machine mode. MXLEN \
may be 32, 64, or 128 depending on the implementation. Implementations \
that support only one value of MXLEN do not need to implement the \
MXLEN field and should hardwire it appropriately.
"""

EXAMPLE_1_OUTPUT = """\
chapter: "3.1.6"
source_document: "riscv-privileged-isa-manual"
parameters:
  - name: "MXLEN"
    long_name: "Machine mode XLEN"
    description: "Width of the x registers when the hart is in machine mode."
    kind: "enum"
    possible_values: [32, 64, 128]
    extension: null
    chapter_source: "3.1.6"
    confidence: "high"
"""

# --- Few-shot example 2 -----------------------------------------------
EXAMPLE_2_INPUT = """\
Chapter 3.7: Physical Memory Protection

The number of implemented PMP entries, up to 64, is an implementation \
choice denoted NUM_PMP_ENTRIES. If NUM_PMP_ENTRIES is zero, PMP is not \
implemented and all accesses in modes other than M-mode fail.
"""

EXAMPLE_2_OUTPUT = """\
chapter: "3.7"
source_document: "riscv-privileged-isa-manual"
parameters:
  - name: "NUM_PMP_ENTRIES"
    long_name: "Number of implemented PMP entries"
    description: "Implementation-defined count of physical memory protection entries, 0 to 64."
    kind: "integer"
    possible_values: null
    extension: null
    chapter_source: "3.7"
    confidence: "high"
"""

# --- Few-shot example 3 (WARL classification) --------------------------
EXAMPLE_3_INPUT = """\
Chapter 4.2: Supervisor Address Translation and Protection (satp)

The satp MODE field is WARL — the implementation is permitted to \
support any subset of the defined MODE encodings, and software must \
read back the field after writing to determine which mode was \
actually accepted. There is no single fixed set of legal values across \
all implementations; each implementation defines its own legal subset.
"""

EXAMPLE_3_OUTPUT = """\
chapter: "4.2"
source_document: "riscv-privileged-isa-manual"
parameters:
  - name: "SATP_MODE_LEGAL_VALUES"
    long_name: "Legal satp.MODE encodings supported by this implementation"
    description: "WARL field; each implementation defines its own subset of legal address-translation modes."
    kind: "warl"
    possible_values: null
    extension: null
    chapter_source: "4.2"
    confidence: "high"
"""

FEW_SHOT_EXAMPLES = [
    (EXAMPLE_1_INPUT, EXAMPLE_1_OUTPUT),
    (EXAMPLE_2_INPUT, EXAMPLE_2_OUTPUT),
    (EXAMPLE_3_INPUT, EXAMPLE_3_OUTPUT),
]


def build_messages(chunk_text: str, chunk_chapter_hint: str = "unknown") -> list[dict]:
    """
    Build the full few-shot chat message list for one text chunk.
    Works with both OpenAI and Anthropic-style chat APIs (see agent.py).
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for ex_input, ex_output in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": ex_input})
        messages.append({"role": "assistant", "content": ex_output})

    messages.append(
        {
            "role": "user",
            "content": (
                f"Now extract parameters from this section "
                f"(chapter hint: {chunk_chapter_hint}):\n\n{chunk_text}"
            ),
        }
    )
    return messages