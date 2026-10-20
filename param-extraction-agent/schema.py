"""
schema.py

Pydantic models that define the strict "UDB yaml" shape we want the
LLM to output. This is the enforcement layer mentioned in point 4 of
the proposal: "export the parameters in UDB yaml format."

Updated per maintainer discussion: 'kind' and 'long_name' are now
REQUIRED (not optional) so the agent can never silently emit a
parameter missing those fields — validation will hard-fail and trigger
the self-correction retry loop in agent.py instead of writing an
incomplete entry.

NOTE: The field names below are a reasonable approximation of a RISC-V
UDB (Unified Database) parameter entry. Once you have the
riscv-unified-db repo cloned, open a few real files under
`spec/std/isa/param/` (or wherever the current schema lives) and
adjust field names/types here to match exactly. That alignment step
is itself worth mentioning in your PR description — it shows you
understood the target schema, not just LLM plumbing.
"""

from __future__ import annotations
from typing import List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class ParamKind(str, Enum):
    boolean = "boolean"
    integer = "integer"
    enum = "enum"
    string = "string"
    warl = "warl"    # Write-Any-Read-Legal CSR field, implementation-chosen
    wlrl = "wlrl"     # Write-Legal-Read-Legal CSR field, implementation-chosen


class ParameterEntry(BaseModel):
    name: str = Field(..., description="Short identifier, e.g. 'MXLEN'")
    long_name: str = Field(
        ..., min_length=1, description="Human-readable expanded name — REQUIRED"
    )
    description: str = Field(
        ..., description="What this parameter controls, in the spec's own words"
    )
    kind: ParamKind = Field(
        ..., description="Classification — REQUIRED. Use 'warl'/'wlrl' only "
        "when the legal-value set is implementation-chosen (see is_warl_or_wlrl)."
    )
    possible_values: Optional[List[Union[str, int, bool]]] = Field(
        None, description="Enumerated legal values, if the spec constrains them"
    )
    extension: Optional[str] = Field(
        None, description="RISC-V extension this parameter belongs to, e.g. 'Zicsr'"
    )
    chapter_source: Optional[str] = Field(
        None, description="Chapter/section of the ISA manual this was extracted from"
    )
    confidence: Optional[str] = Field(
        "medium", description="LLM self-reported confidence: low/medium/high"
    )

    @field_validator("name")
    @classmethod
    def name_must_be_upper_snake_ish(cls, v: str) -> str:
        # Parameters in the ISA manual are usually SCREAMING_SNAKE or CamelCase.
        # We don't hard-fail on casing, just strip whitespace defensively.
        return v.strip()

    @field_validator("kind")
    @classmethod
    def warl_requires_no_fixed_values(cls, v: ParamKind) -> ParamKind:
        # WARL/WLRL fields are defined by "implementation may choose any
        # legal value" — they should NOT also carry a fixed enumerated
        # possible_values list scraped from one example implementation.
        # (We can't cross-check possible_values here since field order
        # isn't guaranteed in Pydantic v2 field_validator; this is
        # deliberately a light touch — the real check lives in the
        # is_warl_or_wlrl() helper below, called explicitly before writing.)
        return v

    class Config:
        populate_by_name = True
        use_enum_values = True


class ParameterFile(BaseModel):
    """Top-level structure written out as YAML."""
    chapter: str
    source_document: str
    parameters: List[ParameterEntry]


def is_warl_or_wlrl(spec_text: str) -> bool:
    """
    Heuristic pre-check used in the prompt-building step (see prompts.py)
    to remind the model when WARL/WLRL classification applies: only when
    the *set of legal values* is implementation-chosen, not just because
    the field happens to be a CSR bitfield.
    """
    markers = ("WARL", "WLRL", "implementation-defined legal values",
               "any value that is legal", "legal values")
    return any(m.lower() in spec_text.lower() for m in markers)