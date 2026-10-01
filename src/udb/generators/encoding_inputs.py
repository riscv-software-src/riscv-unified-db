# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Immutable inputs shared by the retained generic encoding generators.

Selection deliberately retains the original scripts' name-only extension
filter and raw ``base``/encoding-branch policy. It is not a configured presence
query: in particular a generic encoding is not filtered by MXLEN or by a
``definedBy.xlen`` constraint. Use the architecture APIs for presence queries.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from udb.architecture import ConfiguredArchitecture
from udb.database import Database, DatabaseObject, ResolvedDatabase
from udb.errors import DataError
from udb.instruction_fields import InstructionFieldBuilder

type EncodingSource = Database | ConfiguredArchitecture
type TargetArch = Literal["RV32", "RV64", "BOTH"]
GO_EXTENSIONS = "A,D,F,I,M,Q,Zba,Zbb,Zbs,S,System,V,Zicsr,Sm,H,U,Zicntr,Zihpm"


class EncodingGeneratorError(DataError):
    """A generic encoding artifact cannot represent the supplied input."""


@dataclass(frozen=True, slots=True)
class ExceptionRecord:
    """One fully rendered wrapper row, before numeric deduplication."""

    num: int
    name: str
    var: str
    ext: str

    def __post_init__(self) -> None:
        if type(self.num) is not int or self.num < 0:
            raise EncodingGeneratorError("exception num must be a nonnegative integer")
        for field in ("name", "var", "ext"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value:
                raise EncodingGeneratorError(f"exception {field} must be nonempty text")
            if field != "var" and ("<%" in value or "%>" in value):
                raise EncodingGeneratorError(f"exception {field} must be fully rendered text")

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> ExceptionRecord:
        if not isinstance(row, Mapping) or set(row) != {"num", "name", "var", "ext"}:
            raise EncodingGeneratorError("exception rows require exactly num, name, var and ext")
        return cls(row["num"], row["name"], row["var"], row["ext"])


@dataclass(frozen=True, slots=True)
class NamedEncoding:
    name: str
    match: str

    @property
    def value(self) -> int:
        return int(self.match.replace("-", "0"), 2)

    @property
    def mask(self) -> int:
        return int("".join("0" if char == "-" else "1" for char in self.match), 2)


@dataclass(frozen=True, slots=True)
class EncodingInputs:
    instructions: tuple[NamedEncoding, ...]
    csrs: tuple[tuple[int, str], ...]


def normalize_extensions(extensions: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(extensions, str):
        extensions = (extensions,)
    if not isinstance(extensions, Sequence) or any(
        not isinstance(item, str) for item in extensions
    ):
        raise EncodingGeneratorError("extensions must be a string or a sequence of strings")
    return tuple(part.strip() for item in extensions for part in item.split(",") if part.strip())


def _requirement(requirement: Any, enabled: tuple[str, ...]) -> bool:
    if isinstance(requirement, str):
        return requirement in enabled
    return isinstance(requirement, Mapping) and requirement.get("name") in enabled


def _requirements(value: Any) -> Sequence:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, Sequence):
        raise EncodingGeneratorError("extension filter alternatives must be a sequence")
    return value


def _legacy_filter(specification: Any, enabled: tuple[str, ...]) -> bool:
    # Preserve the old generator's deliberately permissive unknown-shape policy,
    # including modern {"extension": ...} conditions. Do not invoke a solver.
    if specification is None:
        return False
    if isinstance(specification, str):
        if specification.startswith("RV"):
            suffix = (
                specification[4:]
                if specification.startswith(("RV32", "RV64"))
                else specification[2:]
            )
            return any(part in enabled for part in suffix)
        return specification in enabled
    if not isinstance(specification, Mapping):
        raise EncodingGeneratorError(f"unsupported extension filter {specification!r}")
    if "allOf" in specification:
        return all(_requirement(item, enabled) for item in _requirements(specification["allOf"]))
    if "oneOf" in specification:
        return any(_requirement(item, enabled) for item in _requirements(specification["oneOf"]))
    if "anyOf" in specification:

        def alternative(item: Any) -> bool:
            if isinstance(item, Mapping) and "allOf" in item:
                return all(_requirement(part, enabled) for part in _requirements(item["allOf"]))
            return _requirement(item, enabled)

        return any(alternative(item) for item in _requirements(specification["anyOf"]))
    if "name" in specification and "version" in specification:
        return specification["name"] in enabled
    return True


def resolved_database(source: EncodingSource) -> ResolvedDatabase:
    database = source.database if isinstance(source, ConfiguredArchitecture) else source
    if not isinstance(database, Database):
        raise TypeError("source must be a Database or ConfiguredArchitecture")
    return database if isinstance(database, ResolvedDatabase) else database.resolve()


def _error(record: DatabaseObject, field: str, message: str) -> EncodingGeneratorError:
    span = record.source_at(field)
    return EncodingGeneratorError(f"{span.label if span else record.path}#/{field}: {message}")


def build_encoding_inputs(
    source: EncodingSource,
    *,
    extensions: str | Sequence[str] = (),
    include_all: bool = True,
    arch: TargetArch = "BOTH",
) -> EncodingInputs:
    """Project native-script-compatible instructions and CSR addresses.

    This does not solve/filter the configured architecture. A configured source
    supplies its resolved database (and any caller-applied overlays), just as the
    original Rake task supplied the complete resolved YAML tree.
    """
    if arch not in ("RV32", "RV64", "BOTH"):
        raise EncodingGeneratorError(f"unsupported target architecture {arch!r}")
    if type(include_all) is not bool:
        raise EncodingGeneratorError("include_all must be a boolean")
    enabled = normalize_extensions(extensions)
    database = resolved_database(source)
    builder = InstructionFieldBuilder(database)
    instructions: dict[str, NamedEncoding] = {}
    for record in database.instructions:
        if not include_all:
            if not _legacy_filter(record.get("definedBy"), enabled):
                continue
            if record.get("excludedBy") and _legacy_filter(record["excludedBy"], enabled):
                continue
        if record.get("base") in (32, 64) and arch not in (f"RV{record['base']}", "BOTH"):
            continue
        descriptor = builder.describe(record)
        raw = record.get("encoding", record.get("format", {}))
        split = "RV32" in raw or "RV64" in raw
        if not split:
            instructions[record.name] = NamedEncoding(record.name, descriptor.encodings[0].match)
            continue
        branches = {encoding.xlen: encoding.match for encoding in descriptor.encodings}
        # Descriptor selection is structural; raw declared branches determine
        # legacy naming, independently of the machine's configured XLEN.
        for xlen in (64, 32):
            if f"RV{xlen}" not in raw or arch not in (f"RV{xlen}", "BOTH"):
                continue
            match = branches.get(xlen)
            if match is None:
                raise _error(record, "encoding", f"declared RV{xlen} branch has no descriptor")
            name = record.name
            if arch == "BOTH" and xlen == 32:
                if 64 in branches and match == branches[64]:
                    continue
                name += "_rv32"
            instructions[name] = NamedEncoding(name, match)
    csrs: dict[int, str] = {}
    # Filesystem traversal in the old loader is extension-major. Use stable path
    # order for address collisions, not the API's name-major object order.
    for record in sorted(database.csrs, key=lambda item: str(item.path)):
        if record.get("base") in (32, 64) and arch not in (f"RV{record['base']}", "BOTH"):
            continue
        if (
            not include_all
            and "definedBy" in record
            and not _legacy_filter(record["definedBy"], enabled)
        ):
            continue
        address = record.get("address")
        indirect = record.get("indirect_address")
        # The old loader skips a lone zero address; retain this observable rule.
        if not address and not indirect:
            continue
        value = address if address is not None else indirect
        try:
            value = value if type(value) is int else int(value, 0)
        except (TypeError, ValueError) as error:
            raise _error(record, "address", f"invalid CSR address {value!r}") from error
        if value < 0:
            raise _error(record, "address", "CSR address must be nonnegative")
        csrs[value] = record.name.upper()
    return EncodingInputs(tuple(instructions.values()), tuple(sorted(csrs.items())))


def exception_records(
    source: EncodingSource, records: Sequence[ExceptionRecord] | None
) -> tuple[ExceptionRecord, ...]:
    """Use explicit typed rows or the shared configured-prose all-code service."""
    if records is not None:
        if not isinstance(records, Sequence) or any(
            not isinstance(row, ExceptionRecord) for row in records
        ):
            raise EncodingGeneratorError("exception_records must be a sequence of ExceptionRecord")
        return tuple(records)
    if not isinstance(source, ConfiguredArchitecture):
        raise EncodingGeneratorError(
            "exception names need a ConfiguredArchitecture or explicit ExceptionRecord rows"
        )
    try:
        from udb.prose import ProseInputs, resolve_all_exception_records
    except ImportError as error:
        raise EncodingGeneratorError(
            "configured exception names require the shared udb.prose provider; "
            "explicit ExceptionRecord rows may be supplied"
        ) from error
    inputs = ProseInputs.from_architecture(source)
    return tuple(
        ExceptionRecord.from_mapping(row)
        for row in resolve_all_exception_records(source.database, inputs)
    )


def causes(records: Sequence[ExceptionRecord]) -> tuple[tuple[int, str], ...]:
    """Stable numeric sort, first-code deduplication and native sanitization."""
    unique: dict[int, str] = {}
    for row in sorted(records, key=lambda item: item.num):
        name = row.name.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
        identifier(name.upper(), "exception identifier")
        unique.setdefault(row.num, name)
    if len(set(unique.values())) != len(unique):
        raise EncodingGeneratorError("exception identifier collision after sanitization")
    return tuple(unique.items())


def identifier(value: str, description: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", value) is None:
        raise EncodingGeneratorError(f"invalid {description}: {value!r}")
    return value
