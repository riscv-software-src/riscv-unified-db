# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Standalone-first environment identity and non-canonical audit evidence."""

from __future__ import annotations

import datetime as datetime_module
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .canonical import canonical_json_bytes, sha256_bytes


class EnvironmentError(ValueError):
    """A stable failure while observing the dependency-light environment."""


@dataclass(frozen=True)
class EnvironmentObservation:
    """Stable tool identity fields allowed in the canonical decision."""

    python_implementation: str
    python_version: str
    git_implementation: str
    git_version: str


@dataclass(frozen=True)
class IncidentSnapshot:
    """Runtime state for the audit receipt; timestamps never enter the canonical view."""

    elapsed_seconds: float
    expansion_stopped: bool
    outcome: str
    started_at: float | None
    workaround: str | None


_GIT_VERSION_RE = re.compile(r"^git version ([0-9]+(?:\.[0-9]+)+(?:[A-Za-z0-9.+-]*)?)$")
_SENSITIVE_KEY_RE = re.compile(r"(?:credential|password|secret|token)", re.IGNORECASE)
_SENSITIVE_ARGUMENT_RE = re.compile(r"(?i)(--(?:credential|password|secret|token)(?:=|\s+))\S+")
_ABSOLUTE_PATH_RE = re.compile(r"(?<!\S)/(?:[^\s/]+/)*[^\s]+")
_ERROR_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class CumulativeIncident:
    """One non-pausing 90-minute incident for an unexpected Phase 1 dependency."""

    def __init__(self, ceiling_seconds: float = 90 * 60) -> None:
        if ceiling_seconds <= 0:
            raise EnvironmentError("INVALID_INCIDENT_CEILING")
        self._ceiling_seconds = ceiling_seconds
        self._error_codes: set[str] = set()
        self._events: list[dict[str, Any]] = []
        self._outcome = "not_triggered"
        self._started_at: float | None = None
        self._stopped = False
        self._workaround: str | None = None

    @property
    def exit_code(self) -> int:
        """Return the stable nonzero stop result only at the frozen ceiling."""
        return 1 if self._outcome == "ceiling_exceeded" else 0

    def _require_monotonic_timestamp(self, timestamp: float) -> None:
        if self._started_at is not None and timestamp < self._started_at:
            raise EnvironmentError("INCIDENT_TIME_REGRESSION")

    def _snapshot(self, timestamp: float) -> IncidentSnapshot:
        self._require_monotonic_timestamp(timestamp)
        elapsed = 0.0 if self._started_at is None else timestamp - self._started_at
        if self._started_at is not None and elapsed >= self._ceiling_seconds and self._outcome == "active":
            self._outcome = "ceiling_exceeded"
            self._stopped = True
            self._workaround = "red_blocker"
        return IncidentSnapshot(
            elapsed_seconds=elapsed,
            expansion_stopped=self._stopped,
            outcome=self._outcome,
            started_at=self._started_at,
            workaround=self._workaround,
        )

    def _append_event(self, kind: str, timestamp: float, **details: Any) -> IncidentSnapshot:
        self._require_monotonic_timestamp(timestamp)
        self._events.append({"kind": kind, "timestamp": timestamp, **_sanitize_audit_value(details)})
        return self._snapshot(timestamp)

    def record_failure(self, error_code: str, timestamp: float, **details: Any) -> IncidentSnapshot:
        """Start the incident at its first concrete failure and never replace that time."""
        if _ERROR_CODE_RE.fullmatch(error_code) is None:
            raise EnvironmentError("INVALID_INCIDENT_ERROR_CODE")
        if self._stopped:
            raise EnvironmentError("INCIDENT_EXPANSION_STOPPED")
        if self._outcome not in ("not_triggered", "active"):
            raise EnvironmentError("INCIDENT_RESOLVED")
        if self._started_at is None:
            self._started_at = timestamp
            self._outcome = "active"
        self._error_codes.add(error_code)
        return self._append_event("failure", timestamp, error_code=error_code, **details)

    def record_setup_action(self, error_code: str, timestamp: float, **details: Any) -> IncidentSnapshot:
        """A concrete setup action is an alternative valid incident trigger."""
        return self.record_failure(error_code, timestamp, trigger="setup_action", **details)

    def record_event(self, kind: str, timestamp: float, **details: Any) -> IncidentSnapshot:
        """Log retries, alternatives, downloads, builds, and waits without pausing time."""
        if self._started_at is None:
            raise EnvironmentError("INCIDENT_NOT_TRIGGERED")
        if self._stopped:
            raise EnvironmentError("INCIDENT_EXPANSION_STOPPED")
        if self._outcome != "active":
            raise EnvironmentError("INCIDENT_RESOLVED")
        return self._append_event(kind, timestamp, **details)

    def resolve(self, outcome: str, timestamp: float, **details: Any) -> IncidentSnapshot:
        """Resolve only before the ceiling as standalone restoration or dependency repair."""
        if outcome not in ("restored_standalone", "dependency_resolved"):
            raise EnvironmentError("INVALID_INCIDENT_RESOLUTION")
        snapshot = self.record_event("resolution", timestamp, resolution=outcome, **details)
        if snapshot.outcome == "ceiling_exceeded":
            return snapshot
        self._outcome = outcome
        self._workaround = None
        return self._snapshot(timestamp)

    def canonical_projection(self) -> dict[str, Any]:
        """Expose only stable incident outcome and sorted diagnostic codes to identity."""
        return {
            "error_codes": sorted(self._error_codes),
            "outcome": self._outcome,
            "triggered": self._started_at is not None,
        }

    def audit_events(self) -> list[dict[str, Any]]:
        """Return a copy of non-canonical attempt evidence for an audit receipt."""
        return [dict(event) for event in self._events]

    def audit_projection(self, timestamp: float) -> dict[str, Any]:
        """Keep elapsed timing, attempts, workaround, and blocker evidence out of identity."""
        snapshot = self._snapshot(timestamp)
        return {
            "ceiling_seconds": self._ceiling_seconds,
            "elapsed_seconds": snapshot.elapsed_seconds,
            "events": self.audit_events(),
            "red_blocker": snapshot.outcome == "ceiling_exceeded",
            "started_at": snapshot.started_at,
            "workaround": snapshot.workaround,
        }


def observe_environment() -> EnvironmentObservation:
    """Observe only CPython and Git CLI identities; never probe the UDB toolchain."""
    completed = subprocess.run(
        ["git", "--version"],
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    match = _GIT_VERSION_RE.fullmatch(completed.stdout.strip())
    if completed.returncode != 0 or match is None:
        raise EnvironmentError("GIT_VERSION_OBSERVATION_FAILED")
    return EnvironmentObservation(
        python_implementation=platform.python_implementation(),
        python_version=".".join(str(component) for component in sys.version_info[:3]),
        git_implementation="git",
        git_version=match.group(1),
    )


def build_environment_decision(
    observation: EnvironmentObservation,
    incident: CumulativeIncident | None = None,
) -> dict[str, Any]:
    """Return the versioned, stable canonical projection for a normal success route."""
    if observation.python_implementation != "CPython":
        raise EnvironmentError("UNSUPPORTED_PYTHON_IMPLEMENTATION")
    if observation.git_implementation != "git":
        raise EnvironmentError("UNSUPPORTED_GIT_IMPLEMENTATION")
    incident_projection = incident.canonical_projection() if incident is not None else {
        "error_codes": [], "outcome": "not_triggered", "triggered": False
    }
    incident_outcome = incident_projection["outcome"]
    if incident_outcome == "not_triggered":
        ceiling_status = "not_started"
    elif incident_outcome == "ceiling_exceeded":
        ceiling_status = "ceiling_exceeded"
    elif incident_outcome == "active":
        ceiling_status = "active"
    else:
        ceiling_status = "resolved"
    return {
        "capabilities": {
            "construction": ["git_cli_for_construction", "python_standard_library"],
            "downstream": ["offline_bundle_access", "python_standard_library"],
        },
        "fallback_ceiling_status": ceiling_status,
        "fallback_policy": {
            "ceiling_minutes": 90,
            "retries_reset_clock": False,
            "timing_mode": "cumulative_wall_clock",
            "waits_pause_clock": False,
        },
        "fallback_triggered": incident_projection["triggered"],
        "full_udb_setup": {"attempted": False, "required": False},
        "incident": incident_projection,
        "outcome": "ceiling_exceeded" if incident_outcome == "ceiling_exceeded" else "success",
        "route": "standalone_first",
        "schema_version": "1",
        "tools": {
            "git_cli": {"implementation": observation.git_implementation, "version": observation.git_version},
            "python": {"implementation": observation.python_implementation, "version": observation.python_version},
        },
    }


def build_default_decision(observation: EnvironmentObservation | None = None) -> dict[str, Any]:
    """Build the normal route decision without treating it as a fallback."""
    return build_environment_decision(observation or observe_environment())


def _sanitize_audit_value(value: Any) -> Any:
    if isinstance(value, str):
        sanitized = _SENSITIVE_ARGUMENT_RE.sub(r"\1<redacted>", value)
        if os.path.isabs(sanitized):
            return "<absolute-path>"
        return _ABSOLUTE_PATH_RE.sub("<absolute-path>", sanitized)
    if isinstance(value, list):
        return [_sanitize_audit_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _sanitize_audit_value(item)
            for key, item in value.items()
            if _SENSITIVE_KEY_RE.search(str(key)) is None
        }
    return value


def build_audit_receipt(
    canonical_decision_sha256: str,
    observation: EnvironmentObservation,
    audit_metadata: Mapping[str, Any] | None = None,
    incident: CumulativeIncident | None = None,
    incident_timestamp: float | None = None,
) -> dict[str, Any]:
    """Return non-canonical operational evidence with a one-way decision reference."""
    metadata = _sanitize_audit_value(dict(audit_metadata or {}))
    receipt = {
        "audit": metadata,
        "canonical_environment_decision_sha256": canonical_decision_sha256,
        "observed_tools": {
            "git_cli": {"implementation": observation.git_implementation, "version": observation.git_version},
            "python": {"implementation": observation.python_implementation, "version": observation.python_version},
        },
        "schema_version": "1",
    }
    if incident is not None and incident_timestamp is not None:
        receipt["incident"] = incident.audit_projection(incident_timestamp)
    return receipt


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def write_environment_artifacts(
    decision_path: Path,
    audit_path: Path,
    observation: EnvironmentObservation | None = None,
    audit_metadata: Mapping[str, Any] | None = None,
    incident: CumulativeIncident | None = None,
    incident_timestamp: float | None = None,
) -> str:
    """Write the decision before its audit receipt and return the decision digest."""
    current_observation = observation or observe_environment()
    decision_bytes = canonical_json_bytes(build_environment_decision(current_observation, incident))
    digest = sha256_bytes(decision_bytes)
    _atomic_write(decision_path, decision_bytes)
    receipt = build_audit_receipt(
        digest,
        current_observation,
        audit_metadata,
        incident=incident,
        incident_timestamp=incident_timestamp,
    )
    _atomic_write(audit_path, canonical_json_bytes(receipt))
    return digest


def default_audit_metadata(command: str) -> dict[str, Any]:
    """Capture machine-local details solely for the non-canonical audit receipt."""
    return {
        "command": command,
        "hostname": platform.node(),
        "platform": platform.platform(),
        "timestamp": datetime_module.datetime.now(datetime_module.timezone.utc).isoformat(),
        "working_directory": str(Path.cwd()),
    }
