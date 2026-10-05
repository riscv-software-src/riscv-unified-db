# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Local document anchors and the accepted IDL pass's intermediate-link boundary."""

from __future__ import annotations

import re

from ..architecture import ConfiguredArchitecture, QueryPresence
from ..configuration import Configuration, ConfigurationKind
from .model import ExtensionDocumentError

_KINDS = {
    "inst": "insn",
    "csr": "csr",
    "csr_field": "csrfield",
    "ext": "extension",
    "ext_param": "param",
    "func": "function",
}


def identifier(kind: str, name: str) -> str:
    if kind not in _KINDS:
        raise ExtensionDocumentError(f"Unknown link kind {kind!r}")
    if kind == "csr_field":
        name = name.replace("*", "-")
    return f"udb-{_KINDS[kind]}-{name.replace('.', '_')}"


def link(kind: str, name: str, text: str | None = None) -> str:
    return f"xref:#{identifier(kind, name)}[{name if text is None else text}]"


def anchor(kind: str, name: str) -> str:
    return f"[#{identifier(kind, name)}]"


def anchors(kind: str, name: str) -> str:
    legacy = {
        "inst": "inst",
        "csr": "csr",
        "csr_field": "csr_field",
        "ext": "ext",
        "ext_param": "ext_param",
    }.get(kind)
    result = anchor(kind, name)
    if legacy:
        result += f"\n[#udb:doc:{legacy}:{name.replace('.', '_').replace('*', ':')}]"
    return result


class LinkResolver:
    def __init__(self, architecture: ConfiguredArchitecture) -> None:
        self.architecture = architecture
        self.instruction_architecture = architecture
        if architecture.kind is ConfigurationKind.FULL:
            # Native instruction SAT permits undeclared extensions, unlike its
            # closed full-config CSR/extension lists. Use the accepted partial
            # model with exactly the same mandatory versions and parameter facts.
            configuration = architecture.configuration
            self.instruction_architecture = architecture.database.configure(
                Configuration(
                    {
                        "$schema": "config_schema.json#",
                        "kind": "architecture configuration",
                        "name": configuration.name + "-instruction-links",
                        "description": "Native open-world instruction-link query projection",
                        "type": ConfigurationKind.PARTIAL.value,
                        "mandatory_extensions": [
                            {
                                "name": selection.name,
                                "version": [str(req) for req in selection.requirements],
                            }
                            for selection in configuration.extensions
                        ],
                        "params": dict(configuration.params),
                    }
                )
            )
        db = architecture.database
        self.available: dict[str, set[str]] = {
            "inst": {item.name for item in db.instructions},
            "csr": {item.name for item in db.csrs},
            "ext": {item.name for item in db.extensions},
            "ext_param": {item.name for item in db.objects("parameter")},
        }
        self.available["csr_field"] = {
            f"{csr.name}*{field}" for csr in db.csrs for field in csr.data.get("fields", {})
        }
        self.presence: dict[tuple[str, str], bool] = {}

    def resolve(self, text: str) -> str:
        def monospace(match: re.Match[str]) -> str:
            name = match[1]
            # Native precedence: CSR field, CSR, instruction, extension.
            if "." in name:
                csr, field = name.split(".", 1)
                if f"{csr}*{field}" in self.available["csr_field"] and self._possible("csr", csr):
                    return link("csr_field", f"{csr}*{field}", match[0])
                if csr in self.available["csr"] and self._possible("csr", csr):
                    return link("csr", csr, match[0])
            for kind in ("csr", "inst", "ext"):
                if name in self.available[kind] and self._possible(kind, name):
                    return link(kind, name, match[0])
            return match[0]

        text = re.sub(r"`([\w.]+)`", monospace, text)

        def intermediate(match: re.Match[str]) -> str:
            kind, name, label = (match[i].strip() for i in (1, 2, 3))
            if kind not in _KINDS:
                raise ExtensionDocumentError(f"Unknown intermediate link {match[0]!r}")
            # Function existence was already checked by the compiler. Some links
            # reference valid definitions outside this document; keep native links.
            if kind == "func" or name in self.available.get(kind, set()):
                return link(kind, name, label)
            return match[0]

        return re.sub(
            r"%%UDB_DOC_LINK%([^;%]+)\s*;\s*([^;%]+)\s*;\s*([^%]+)%%",
            intermediate,
            text,
        )

    def _possible(self, kind: str, name: str) -> bool:
        key = (kind, name)
        if key not in self.presence:
            if kind == "ext":
                state = self.architecture.extension_presence(name)
            else:
                record_kind = "instruction" if kind == "inst" else "csr"
                architecture = (
                    self.instruction_architecture if kind == "inst" else self.architecture
                )
                state = architecture.object_presence(
                    self.architecture.database.get(record_kind, name)
                )
            if state is QueryPresence.DEFERRED:
                raise ExtensionDocumentError(f"Unresolved link availability for {name}")
            self.presence[key] = state is not QueryPresence.ABSENT
        return self.presence[key]
