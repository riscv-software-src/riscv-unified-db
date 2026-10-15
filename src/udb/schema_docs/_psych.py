# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Isolated Psych-compatible representation; no global ruamel customization."""

from __future__ import annotations

from io import StringIO

from ruamel.yaml import YAML
from ruamel.yaml.nodes import ScalarNode
from ruamel.yaml.representer import SafeRepresenter
from ruamel.yaml.resolver import VersionedResolver

from ._psych_emitter import PsychEmitter
from ._psych_scalars import plain_tag, ruby_float, string_style

_PREFIX = "tag:yaml.org,2002:"


class _Resolver(VersionedResolver):
    def resolve(self, kind, value, implicit):
        if kind is ScalarNode:
            if value == "<<":
                return _PREFIX + "merge"
            if implicit[0]:
                return _PREFIX + plain_tag(value)
            return _PREFIX + "str"
        return super().resolve(kind, value, implicit)


class _Representer(SafeRepresenter):
    def represent_str(self, value):
        return self.represent_scalar(_PREFIX + "str", value, style=string_style(value))

    def represent_none(self, value):
        return self.represent_scalar(_PREFIX + "null", "")

    def represent_float(self, value):
        return self.represent_scalar(_PREFIX + "float", ruby_float(value))

    def ignore_aliases(self, value):
        return True


_Representer.add_representer(str, _Representer.represent_str)
_Representer.add_representer(type(None), _Representer.represent_none)
_Representer.add_representer(float, _Representer.represent_float)


def dump(value) -> str:
    yaml = YAML(typ="rt")
    yaml.Representer = _Representer
    yaml.Resolver = _Resolver
    yaml.Emitter = PsychEmitter
    yaml.default_flow_style = False
    yaml.sort_base_mapping_type_on_output = False
    yaml.allow_unicode = True
    yaml.width = 80
    yaml.explicit_start = not value
    output = StringIO()
    yaml.dump(value, output)
    return output.getvalue()
