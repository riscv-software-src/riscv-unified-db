# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Closed, source-bound offline treatment response validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_measurement.diagnostics import Diagnostic, ordered_diagnostics
from specchoice_measurement.strict_json import decode_strict_json

REQUIRED_FRAME_AXES = ("authority", "choice_object", "choice_space_origin")
FRAME_ENUMS = {
    "authority": frozenset({"implementation", "ISA", "software", "platform", "unknown"}),
    "choice_object": frozenset(
        {
            "direct_value",
            "count",
            "width",
            "legal_set",
            "access_mode",
            "presence",
            "extension_gate",
            "other",
        }
    ),
    "choice_space_origin": frozenset(
        {
            "implementation_selected",
            "ISA_fixed",
            "derived",
            "not_applicable",
            "unknown",
        }
    ),
}

_RESPONSE_SCHEMA_VERSION = "delegation-frame-response-v1"
_RESPONSE_BASE_KEYS = frozenset(
    {
        "schema_version",
        "system",
        "origin",
        "model_generated",
        "target_sha256",
        "adjudication",
    }
)
_AXIS_KEYS = frozenset({"value", "evidence_span"})
_SPAN_KEYS = frozenset({"source_sha256", "start_byte", "end_byte", "text"})
_ADJUDICATION_KEYS = frozenset(
    {
        "surfaced",
        "parameter_status",
        "proposed_name",
        "evidence_spans",
        "rationale",
    }
)
_SURFACED_STATUSES = frozenset({"accept", "classify_out", "review"})
_ADVISORY_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config/treatments/frame-advisory-patterns-v1.json"
)
_ADVISORY_CONFIG_KEYS = frozenset({"schema_version", "patterns"})
_ADVISORY_PATTERN_KEYS = frozenset({"id", "when", "diagnostic"})
_ADVISORY_SCHEMA_VERSION = "frame-advisory-patterns-v1"
_ADVISORY_DIAGNOSTIC = "FRAME_COMBINATION_REQUIRES_REVIEW"


class TreatmentContractError(ValueError):
    """A stable treatment-contract failure with all ordered blocker diagnostics."""

    def __init__(self, code: str, diagnostics: tuple[Diagnostic, ...] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.diagnostics = diagnostics


@dataclass(frozen=True)
class ParsedTreatmentResponse:
    """A validated response retaining only its exact source-bound values."""

    schema_version: str
    system: str
    origin: str
    model_generated: bool
    target_sha256: str
    delegation_frame: dict[str, dict[str, object]] | None
    adjudication: dict[str, object]
    canonical_projection: bytes
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def valid(self) -> bool:
        return not any(item.severity == "blocker" for item in self.diagnostics)

    def as_dict(self) -> dict[str, object]:
        response = {
            "schema_version": self.schema_version,
            "system": self.system,
            "origin": self.origin,
            "model_generated": self.model_generated,
            "target_sha256": self.target_sha256,
            "adjudication": self.adjudication,
        }
        if self.delegation_frame is not None:
            response["delegation_frame"] = self.delegation_frame
        return response


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _exact_keys(
    value: object,
    expected: frozenset[str],
    field: str,
    code: str,
    diagnostics: list[Diagnostic],
) -> bool:
    if not isinstance(value, dict):
        diagnostics.append(
            Diagnostic(
                code, "blocker", field=field, expected="object", observed=type(value).__name__
            )
        )
        return False
    actual = set(value)
    for key in sorted(expected - actual):
        diagnostics.append(Diagnostic(code, "blocker", field=f"{field}.{key}", expected="present"))
    for key in sorted(actual - expected):
        diagnostics.append(Diagnostic(code, "blocker", field=f"{field}.{key}", observed=value[key]))
    return actual == set(expected)


def _raise_blockers(diagnostics: list[Diagnostic]) -> None:
    ordered = ordered_diagnostics(diagnostics)
    if ordered:
        raise TreatmentContractError(ordered[0].code, ordered)


def _validate_span(
    value: object,
    *,
    target_raw: bytes,
    target_sha256: str,
    field: str,
    required: bool,
    diagnostics: list[Diagnostic],
) -> dict[str, object] | None:
    code = (
        "FRAME_EVIDENCE_SPAN_REQUIRED"
        if required and value is None
        else "FRAME_EVIDENCE_SPAN_INVALID"
    )
    valid = _exact_keys(value, _SPAN_KEYS, field, code, diagnostics)
    if not isinstance(value, dict):
        return None
    source_sha256 = value.get("source_sha256")
    start_byte = value.get("start_byte")
    end_byte = value.get("end_byte")
    text = value.get("text")
    if source_sha256 != target_sha256:
        diagnostics.append(
            Diagnostic(
                "FRAME_EVIDENCE_SPAN_INVALID",
                "blocker",
                field=f"{field}.source_sha256",
                expected=target_sha256,
                observed=source_sha256,
            )
        )
        valid = False
    if not _is_int(start_byte) or not _is_int(end_byte):
        diagnostics.append(
            Diagnostic(
                "FRAME_EVIDENCE_SPAN_INVALID",
                "blocker",
                field=field,
                expected="integer byte offsets",
                observed=[start_byte, end_byte],
            )
        )
        valid = False
    if not isinstance(text, str) or not text:
        diagnostics.append(
            Diagnostic(
                "FRAME_EVIDENCE_SPAN_INVALID",
                "blocker",
                field=f"{field}.text",
                expected="non-empty string",
                observed=text,
            )
        )
        valid = False
    if not valid:
        return None
    assert isinstance(start_byte, int) and isinstance(end_byte, int) and isinstance(text, str)
    if start_byte < 0 or end_byte <= start_byte or end_byte > len(target_raw):
        diagnostics.append(
            Diagnostic(
                "FRAME_EVIDENCE_SPAN_INVALID",
                "blocker",
                field=field,
                expected=f"[0,{len(target_raw)}] non-empty",
                observed=[start_byte, end_byte],
            )
        )
        return None
    try:
        actual_text = target_raw[start_byte:end_byte].decode("utf-8")
    except UnicodeDecodeError:
        diagnostics.append(
            Diagnostic(
                "FRAME_EVIDENCE_TEXT_NOT_UTF8", "blocker", field=field, source_sha256=target_sha256
            )
        )
        return None
    if actual_text != text:
        diagnostics.append(
            Diagnostic(
                "FRAME_EVIDENCE_TEXT_MISMATCH",
                "blocker",
                field=f"{field}.text",
                expected=actual_text,
                observed=text,
                source_sha256=target_sha256,
            )
        )
        return None
    return {
        "source_sha256": target_sha256,
        "start_byte": start_byte,
        "end_byte": end_byte,
        "text": text,
    }


def validate_source_span_v1(value: object, target_raw: bytes) -> dict[str, object]:
    """Validate one non-empty, exact raw-byte span without normalizing the source."""
    diagnostics: list[Diagnostic] = []
    parsed = _validate_span(
        value,
        target_raw=target_raw,
        target_sha256=sha256_bytes(target_raw),
        field="evidence_span",
        required=True,
        diagnostics=diagnostics,
    )
    _raise_blockers(diagnostics)
    assert parsed is not None
    return parsed


def validate_delegation_frame_v1(
    value: object,
    target_raw: bytes,
) -> dict[str, dict[str, object]]:
    """Validate exactly the three frozen axes and their independent evidence spans."""
    diagnostics: list[Diagnostic] = []
    parsed = _parse_delegation_frame(value, target_raw, diagnostics)
    _raise_blockers(diagnostics)
    assert parsed is not None
    return parsed


def _load_frame_advisory_patterns_v1() -> tuple[dict[str, object], ...]:
    raw = _ADVISORY_CONFIG_PATH.read_bytes()
    try:
        config = decode_strict_json(raw)
    except (UnicodeDecodeError, ValueError) as error:
        raise RuntimeError("FRAME_ADVISORY_CONFIG_INVALID") from error
    if canonical_json_bytes(config) != raw:
        raise RuntimeError("FRAME_ADVISORY_CONFIG_INVALID")
    if not isinstance(config, dict) or set(config) != _ADVISORY_CONFIG_KEYS:
        raise RuntimeError("FRAME_ADVISORY_CONFIG_INVALID")
    if config.get("schema_version") != _ADVISORY_SCHEMA_VERSION:
        raise RuntimeError("FRAME_ADVISORY_CONFIG_INVALID")
    patterns = config.get("patterns")
    if not isinstance(patterns, list):
        raise RuntimeError("FRAME_ADVISORY_CONFIG_INVALID")

    pattern_ids: set[str] = set()
    validated: list[dict[str, object]] = []
    for pattern in patterns:
        if not isinstance(pattern, dict) or set(pattern) != _ADVISORY_PATTERN_KEYS:
            raise RuntimeError("FRAME_ADVISORY_CONFIG_INVALID")
        pattern_id = pattern.get("id")
        when = pattern.get("when")
        diagnostic = pattern.get("diagnostic")
        if not isinstance(pattern_id, str) or not pattern_id or pattern_id in pattern_ids:
            raise RuntimeError("FRAME_ADVISORY_CONFIG_INVALID")
        if diagnostic != _ADVISORY_DIAGNOSTIC or not isinstance(when, dict) or not when:
            raise RuntimeError("FRAME_ADVISORY_CONFIG_INVALID")
        if any(
            axis not in FRAME_ENUMS or value not in FRAME_ENUMS[axis]
            for axis, value in when.items()
        ):
            raise RuntimeError("FRAME_ADVISORY_CONFIG_INVALID")
        pattern_ids.add(pattern_id)
        validated.append({"id": pattern_id, "when": when, "diagnostic": diagnostic})
    if [item["id"] for item in validated] != sorted(pattern_ids):
        raise RuntimeError("FRAME_ADVISORY_CONFIG_INVALID")
    return tuple(validated)


_FRAME_ADVISORY_PATTERNS = _load_frame_advisory_patterns_v1()


def evaluate_frame_advisories_v1(
    delegation_frame: dict[str, dict[str, object]],
) -> tuple[Diagnostic, ...]:
    """Return preregistered warning-only advisory diagnostics for a parsed frame."""
    warnings: list[Diagnostic] = []
    for occurrence, pattern in enumerate(_FRAME_ADVISORY_PATTERNS):
        when = pattern["when"]
        assert isinstance(when, dict)
        if all(
            isinstance(delegation_frame.get(axis), dict)
            and delegation_frame[axis].get("value") == value
            for axis, value in when.items()
        ):
            warnings.append(
                Diagnostic(
                    _ADVISORY_DIAGNOSTIC,
                    "warning",
                    field="delegation_frame",
                    finding_id=pattern["id"],
                    occurrence=occurrence,
                )
            )
    return ordered_diagnostics(warnings)


def _parse_delegation_frame(
    value: object,
    target_raw: bytes,
    diagnostics: list[Diagnostic],
) -> dict[str, dict[str, object]] | None:
    expected_axes = frozenset(REQUIRED_FRAME_AXES)
    valid = _exact_keys(
        value, expected_axes, "delegation_frame", "DELEGATION_FRAME_AXES_INVALID", diagnostics
    )
    if not isinstance(value, dict):
        return None
    target_sha256 = sha256_bytes(target_raw)
    parsed: dict[str, dict[str, object]] = {}
    for axis in REQUIRED_FRAME_AXES:
        axis_value = value.get(axis)
        axis_valid = _exact_keys(
            axis_value,
            _AXIS_KEYS,
            f"delegation_frame.{axis}",
            "DELEGATION_FRAME_AXES_INVALID",
            diagnostics,
        )
        if not isinstance(axis_value, dict):
            valid = False
            continue
        chosen_value = axis_value.get("value")
        if chosen_value not in FRAME_ENUMS[axis]:
            diagnostics.append(
                Diagnostic(
                    "DELEGATION_FRAME_ENUM_INVALID",
                    "blocker",
                    field=f"delegation_frame.{axis}.value",
                    expected=sorted(FRAME_ENUMS[axis]),
                    observed=chosen_value,
                )
            )
            axis_valid = False
        span = _validate_span(
            axis_value.get("evidence_span"),
            target_raw=target_raw,
            target_sha256=target_sha256,
            field=f"delegation_frame.{axis}.evidence_span",
            required=True,
            diagnostics=diagnostics,
        )
        if not axis_valid or span is None:
            valid = False
            continue
        parsed[axis] = {"value": chosen_value, "evidence_span": span}
    return parsed if valid else None


def _parse_adjudication(
    value: object,
    target_raw: bytes,
    diagnostics: list[Diagnostic],
) -> dict[str, object] | None:
    valid = _exact_keys(
        value, _ADJUDICATION_KEYS, "adjudication", "ADJUDICATION_INVALID", diagnostics
    )
    if not isinstance(value, dict):
        return None
    surfaced = value.get("surfaced")
    parameter_status = value.get("parameter_status")
    proposed_name = value.get("proposed_name")
    evidence_spans = value.get("evidence_spans")
    rationale = value.get("rationale")
    if not isinstance(surfaced, bool):
        diagnostics.append(
            Diagnostic(
                "ADJUDICATION_INVALID",
                "blocker",
                field="adjudication.surfaced",
                expected="boolean",
                observed=surfaced,
            )
        )
        valid = False
    if not isinstance(evidence_spans, list):
        diagnostics.append(
            Diagnostic(
                "ADJUDICATION_INVALID",
                "blocker",
                field="adjudication.evidence_spans",
                expected="array",
                observed=evidence_spans,
            )
        )
        evidence_spans = []
        valid = False
    if surfaced is False:
        if not (
            parameter_status is None
            and proposed_name is None
            and evidence_spans == []
            and isinstance(rationale, str)
            and rationale
        ):
            diagnostics.append(
                Diagnostic(
                    "ADJUDICATION_INVALID",
                    "blocker",
                    field="adjudication",
                    expected="canonical unsurfaced state",
                    observed=value,
                )
            )
            valid = False
    elif surfaced is True:
        if parameter_status not in _SURFACED_STATUSES:
            diagnostics.append(
                Diagnostic(
                    "ADJUDICATION_INVALID",
                    "blocker",
                    field="adjudication.parameter_status",
                    expected=sorted(_SURFACED_STATUSES),
                    observed=parameter_status,
                )
            )
            valid = False
        if proposed_name is not None and (not isinstance(proposed_name, str) or not proposed_name):
            diagnostics.append(
                Diagnostic(
                    "ADJUDICATION_INVALID",
                    "blocker",
                    field="adjudication.proposed_name",
                    expected="non-empty string or null",
                    observed=proposed_name,
                )
            )
            valid = False
        if not isinstance(rationale, str) or not rationale:
            diagnostics.append(
                Diagnostic(
                    "ADJUDICATION_INVALID",
                    "blocker",
                    field="adjudication.rationale",
                    expected="non-empty string",
                    observed=rationale,
                )
            )
            valid = False
        if not evidence_spans:
            diagnostics.append(
                Diagnostic(
                    "ADJUDICATION_INVALID",
                    "blocker",
                    field="adjudication.evidence_spans",
                    expected="non-empty array",
                    observed=evidence_spans,
                )
            )
            valid = False
    else:
        valid = False
    parsed_spans: list[dict[str, object]] = []
    for index, span in enumerate(evidence_spans):
        parsed_span = _validate_span(
            span,
            target_raw=target_raw,
            target_sha256=sha256_bytes(target_raw),
            field=f"adjudication.evidence_spans[{index}]",
            required=False,
            diagnostics=diagnostics,
        )
        if parsed_span is None:
            valid = False
        else:
            parsed_spans.append(parsed_span)
    if not valid:
        return None
    return {
        "surfaced": surfaced,
        "parameter_status": parameter_status,
        "proposed_name": proposed_name,
        "evidence_spans": parsed_spans,
        "rationale": rationale,
    }


def parse_treatment_response_v1(raw: bytes, target_raw: bytes) -> ParsedTreatmentResponse:
    """Parse one closed A/B/C response and fail closed on every malformed boundary."""
    try:
        response = decode_strict_json(raw)
    except (UnicodeDecodeError, ValueError) as error:
        diagnostic = Diagnostic(
            "TREATMENT_JSON_INVALID", "blocker", field="response", observed=str(error)
        )
        raise TreatmentContractError("TREATMENT_JSON_INVALID", (diagnostic,)) from error

    diagnostics: list[Diagnostic] = []
    if not isinstance(response, dict):
        diagnostics.append(
            Diagnostic(
                "TREATMENT_RESPONSE_KEYS_INVALID",
                "blocker",
                field="response",
                expected="object",
                observed=type(response).__name__,
            )
        )
        _raise_blockers(diagnostics)
    assert isinstance(response, dict)
    system = response.get("system")
    if system not in {"A", "B", "C"}:
        diagnostics.append(
            Diagnostic(
                "TREATMENT_SYSTEM_INVALID",
                "blocker",
                field="response.system",
                expected=["A", "B", "C"],
                observed=system,
            )
        )
    expected_keys = (
        _RESPONSE_BASE_KEYS if system == "A" else _RESPONSE_BASE_KEYS | {"delegation_frame"}
    )
    _exact_keys(response, expected_keys, "response", "TREATMENT_RESPONSE_KEYS_INVALID", diagnostics)
    if system == "A" and "delegation_frame" in response:
        diagnostics.append(
            Diagnostic(
                "DELEGATION_FRAME_FORBIDDEN_FOR_A", "blocker", field="response.delegation_frame"
            )
        )
    if system in {"B", "C"} and "delegation_frame" not in response:
        diagnostics.append(
            Diagnostic(
                "DELEGATION_FRAME_REQUIRED",
                "blocker",
                field="response.delegation_frame",
                expected="present",
            )
        )
    if response.get("schema_version") != _RESPONSE_SCHEMA_VERSION:
        diagnostics.append(
            Diagnostic(
                "TREATMENT_RESPONSE_KEYS_INVALID",
                "blocker",
                field="response.schema_version",
                expected=_RESPONSE_SCHEMA_VERSION,
                observed=response.get("schema_version"),
            )
        )
    if not isinstance(response.get("origin"), str) or not response["origin"]:
        diagnostics.append(
            Diagnostic(
                "TREATMENT_RESPONSE_KEYS_INVALID",
                "blocker",
                field="response.origin",
                expected="non-empty string",
                observed=response.get("origin"),
            )
        )
    if not isinstance(response.get("model_generated"), bool):
        diagnostics.append(
            Diagnostic(
                "TREATMENT_RESPONSE_KEYS_INVALID",
                "blocker",
                field="response.model_generated",
                expected="boolean",
                observed=response.get("model_generated"),
            )
        )
    target_sha256 = sha256_bytes(target_raw)
    if response.get("target_sha256") != target_sha256:
        diagnostics.append(
            Diagnostic(
                "TREATMENT_RESPONSE_KEYS_INVALID",
                "blocker",
                field="response.target_sha256",
                expected=target_sha256,
                observed=response.get("target_sha256"),
            )
        )

    frame = None
    if system in {"B", "C"} and "delegation_frame" in response:
        frame = _parse_delegation_frame(response["delegation_frame"], target_raw, diagnostics)
    adjudication = _parse_adjudication(response.get("adjudication"), target_raw, diagnostics)
    _raise_blockers(diagnostics)

    assert isinstance(system, str)
    assert isinstance(response["origin"], str)
    assert isinstance(response["model_generated"], bool)
    assert isinstance(response["target_sha256"], str)
    assert adjudication is not None
    parsed = ParsedTreatmentResponse(
        schema_version=_RESPONSE_SCHEMA_VERSION,
        system=system,
        origin=response["origin"],
        model_generated=response["model_generated"],
        target_sha256=response["target_sha256"],
        delegation_frame=frame,
        adjudication=adjudication,
        canonical_projection=b"",
    )
    return ParsedTreatmentResponse(
        **{**parsed.__dict__, "canonical_projection": canonical_json_bytes(parsed.as_dict())}
    )
