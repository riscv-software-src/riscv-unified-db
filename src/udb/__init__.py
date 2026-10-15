# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Python access to the RISC-V Unified Database."""

from .authoring import AuthoringPlan, GeneratedFile
from .database import (
    Csr,
    Database,
    DatabaseObject,
    Extension,
    Instruction,
    Profile,
    ResolvedDatabase,
)
from .errors import (
    AuthoringError,
    DataError,
    LayoutError,
    ObjectNotFoundError,
    ReferenceError,
    ResolutionError,
    SerializationError,
    UdbError,
    UnknownKindError,
)
from .layouts import (
    LayoutJob,
    generate_layouts,
    iter_layout_jobs,
    layout_plan,
    layout_sources,
    render_layout,
)
from .reference import DataReference, Reference, ResolvedNode, SchemaReference
from .resolver import YamlResolver, merge_patch
from .schema import SchemaError, SchemaStore
from .serialization import (
    SCHEMAS_BASE_URL,
    dumps_json,
    dumps_yaml,
    write_config,
    write_resolved_database,
    write_resolved_schemas,
)
from .source import SourceMap, SourceSpan
from .versions import (
    ExtensionVersion,
    ExtensionVersionSet,
    RequirementOperator,
    Version,
    VersionRequirement,
    parse_version_requirements,
)

__all__ = [
    "SCHEMAS_BASE_URL",
    "AuthoringError",
    "AuthoringPlan",
    "Csr",
    "DataError",
    "DataReference",
    "Database",
    "DatabaseObject",
    "Extension",
    "ExtensionVersion",
    "ExtensionVersionSet",
    "GeneratedFile",
    "Instruction",
    "LayoutError",
    "LayoutJob",
    "ObjectNotFoundError",
    "Profile",
    "Reference",
    "ReferenceError",
    "RequirementOperator",
    "ResolutionError",
    "ResolvedDatabase",
    "ResolvedNode",
    "SchemaError",
    "SchemaReference",
    "SchemaStore",
    "SerializationError",
    "SourceMap",
    "SourceSpan",
    "UdbError",
    "UnknownKindError",
    "Version",
    "VersionRequirement",
    "YamlResolver",
    "dumps_json",
    "dumps_yaml",
    "generate_layouts",
    "iter_layout_jobs",
    "layout_plan",
    "layout_sources",
    "merge_patch",
    "parse_version_requirements",
    "render_layout",
    "write_config",
    "write_resolved_database",
    "write_resolved_schemas",
]
