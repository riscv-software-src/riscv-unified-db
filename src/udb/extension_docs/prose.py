# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""One adapter to configured-prose23's public API; no template engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..architecture import ConfiguredArchitecture
from .model import ExtensionDocumentError, ProseProvider


def needs_configured_prose(value: object) -> bool:
    if isinstance(value, str):
        return "<%" in value or "{%" in value or "{{" in value
    if isinstance(value, Mapping):
        return any(needs_configured_prose(item) for item in value.values())
    if isinstance(value, Sequence):
        return any(needs_configured_prose(item) for item in value)
    return False


def configured_prose_provider(architecture: ConfiguredArchitecture) -> ProseProvider:
    try:
        from ..prose import CapturedProse, ProseInputs, render_legacy, render_native
    except ModuleNotFoundError as error:
        raise ExtensionDocumentError(
            "Configured prose provider required: integrate configured-prose23's "
            "udb.prose package or pass DocumentOptions(prose=...)"
        ) from error
    inputs = ProseInputs.from_architecture(architecture)
    native_values = {
        "extensions": inputs.extensions,
        "params": inputs.parameters,
    }

    def provider(text, *, record, field_path, architecture):
        captured = CapturedProse.from_record(architecture.database, record, *field_path)
        if captured.text != text:
            raise ExtensionDocumentError(
                f"{captured.label}: configured prose scalar changed during rendering"
            )
        if "<%" in text:
            return render_legacy(captured, inputs)
        return render_native(captured, native_values)

    return provider
