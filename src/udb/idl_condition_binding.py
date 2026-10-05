# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Architecture-owned symbolic condition context and captured YAML source binding."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .conditions import Condition, UnresolvedIdlCondition, parse_condition
from .errors import DataError
from .idl.source import IdlSource
from .idl.symbols import SymbolTable
from .idl_conditions import resolve_idl_conditions
from .idl_yaml_source import idl_field_source
from .source import SourceMap

if TYPE_CHECKING:
    from .configuration import Configuration
    from .database import DatabaseObject, ResolvedDatabase


@dataclass(slots=True)
class IdlConditionBinding:
    """Keep each architecture's translation-only context independent and lazy."""

    database: ResolvedDatabase
    configuration: Configuration
    _symtab: SymbolTable | None = field(default=None, init=False, repr=False)

    def resolve_record(
        self, raw: Any, record: DatabaseObject, path: Sequence[str | int]
    ) -> Condition:
        return self.resolve(
            parse_condition(raw, source=str(record.path), path=path), sources=record.sources
        )

    def resolve(
        self,
        condition: Condition,
        *,
        sources: SourceMap | None = None,
        source_text: str | None = None,
    ) -> Condition:
        if not condition.has_unresolved:
            return condition
        if self._symtab is None:
            from .idl_environment import condition_symbol_table

            self._symtab = condition_symbol_table(self.database)

        def source_for(leaf: UnresolvedIdlCondition) -> IdlSource | str | None:
            span = sources.at(*leaf.source_path) if sources is not None else None
            if span is None or span.start_line is None:
                return leaf.source
            if source_text is not None:
                document_text = source_text
            elif sources is self.configuration.sources:
                raise DataError(f"{span.source}: original configuration YAML text is unavailable")
            else:
                document_text = self.database.source_text(span.source, layer=span.layer)
            label = span.source if span.layer == "source" else f"{span.layer}:{span.source}"
            return idl_field_source(document_text, span, leaf.text, label=label)

        return resolve_idl_conditions(condition, self._symtab, source_for=source_for)
