# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Validate configuration-independent declarations before sharing native names."""

from types import SimpleNamespace

from udb.idl.types import EnumerationType

from .types import CppGenerationError


class Catalog:
    """Union compatible metadata; never choose one conflicting overlay silently."""

    def __init__(self, contexts):
        self.first = contexts[0]
        enum_members = {}
        enum_order = {}
        parameters = {}
        self._parameter_contexts = {}
        extensions = {}
        bitfields = {}
        for context in contexts:
            for enum in context.global_ast.enums:
                dtype = enum.type(context.table)
                members = enum_members.setdefault(enum.name, {})
                order = enum_order.setdefault(enum.name, [])
                for name, value in zip(dtype.element_names, dtype.element_values, strict=True):
                    if name in members and members[name] != value:
                        raise CppGenerationError(
                            f"Configurations have incompatible shared {enum.name}::{name} ordinals; generate separate trees"
                        )
                    if name not in members:
                        members[name] = value
                        order.append(name)
            for parameter in context.parameters:
                existing = parameters.get(parameter.name)
                if existing is not None and existing.to_dict() != parameter.to_dict():
                    raise CppGenerationError(
                        f"Conflicting shared parameter {parameter.name!r} definitions"
                    )
                parameters[parameter.name] = parameter
                self._parameter_contexts.setdefault(parameter.name, context)
            for extension in context.database.extensions:
                extensions.setdefault(extension.name, extension)
            for bitfield in context.global_ast.bitfields:
                dtype = bitfield.type(context.table)
                names = tuple(field.field_name for field in bitfield.bitfield_fields)
                signature = (
                    bitfield.size.value(context.table),
                    tuple((name, dtype.range(name)) for name in names),
                )
                if bitfield.name in bitfields and bitfields[bitfield.name][0] != signature:
                    raise CppGenerationError(
                        f"Conflicting shared bitfield {bitfield.name!r} layouts"
                    )
                bitfields.setdefault(bitfield.name, (signature, bitfield, context.table))
        self.enum_types = tuple(
            EnumerationType(
                name, enum_order[name], tuple(values[item] for item in enum_order[name])
            )
            for name, values in enum_members.items()
        )
        self.bitfield_items = tuple((node, table) for _, node, table in bitfields.values())
        self.parameters = tuple(parameters.values())
        self.database = SimpleNamespace(extensions=tuple(extensions.values()))
        self.table = self

    def get(self, name):
        context = self._parameter_contexts.get(name, self.first)
        return context.table.get(name)

    def symbol(self, kind, *args):
        return self.first.symbol(kind, *args)

    def condition(self, parameter):
        return self._parameter_contexts[parameter.name].condition(parameter)
